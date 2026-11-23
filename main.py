"""WayScanner Pygame 시뮬레이터. 실행: python main.py"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import os
import random
import sys

import pygame as pg
from pygame import gfxdraw

import hazard_zone
import pathfinder


WIDTH, HEIGHT = 1280, 800
COLUMNS, ROWS, CELL = 40, 26, 20
BOARD = pg.Rect(58, 168, COLUMNS * CELL, ROWS * CELL)
SPEEDS = (1, 2, 4)

BACKGROUND, PANEL, BORDER = "#0b131f", "#111e2e", "#25394d"
TEXT, MUTED = "#edf5fd", "#a3b6cb"
FLOOR, GRID, MAJOR_GRID = "#0c1826", "#192a3b", "#283d51"
HAZARD, BLOCK = "#ffb16c", "#49637d"
ROUTE, ROBOT, TARGET = "#62def3", "#63edbb", "#c8b7ff"
HAZARDS = {"지진": "#f9cf75", "화재": "#ff896e", "방사능": "#c6adff"}


@dataclass(frozen=True)
class Layout:
    name: str
    start: hazard_zone.Cell
    goal: hazard_zone.Cell
    hazard_center: hazard_zone.Cell
    hazard_radius: hazard_zone.Cell
    barriers: tuple[tuple[int, int, int, int], ...]


LAYOUTS = (
    Layout("엇갈린 방벽", (3, 13), (36, 13), (19, 13), (5, 6), (
        (10, -2, 2, 21), (27, 6, 2, 22), (4, 6, 4, 5), (32, 15, 5, 4),
    )),
    Layout("연속 교차로", (4, 3), (35, 22), (20, 13), (5, 3), (
        (-2, 6, 28, 2), (12, 19, 30, 2), (7, 11, 4, 4), (31, 11, 5, 4),
    )),
    Layout("코너 우회", (3, 22), (35, 3), (30, 12), (5, 5), (
        (10, 4, 2, 13), (10, 15, 10, 2), (26, 9, 2, 14), (26, 21, 9, 2),
        (16, 6, 6, 3), (4, 8, 3, 4),
    )),
    Layout("중앙 교차로", (18, 2), (22, 23), (20, 13), (6, 4), (
        (7, 6, 8, 3), (25, 5, 8, 3), (7, 18, 8, 3), (25, 18, 8, 3),
        (-2, 11, 11, 2), (31, 13, 11, 2),
    )),
)


@dataclass
class Scenario:
    name: str
    start: hazard_zone.Cell
    goal: hazard_zone.Cell
    hazards: dict[hazard_zone.Cell, str]
    zone: hazard_zone.Keepout
    danger: set[hazard_zone.Cell]
    obstacles: set[hazard_zone.Cell]

    @classmethod
    def generate(cls, rng: random.Random, layout: Layout) -> Scenario:
        flip_x, flip_y = rng.choice((False, True)), rng.choice((False, True))

        def orient(cell: hazard_zone.Cell) -> hazard_zone.Cell:
            x, y = cell
            return (COLUMNS - 1 - x if flip_x else x,
                    ROWS - 1 - y if flip_y else y)

        def shift(cell: hazard_zone.Cell) -> hazard_zone.Cell:
            return cell[0] + rng.randint(-1, 1), cell[1] + rng.randint(-1, 1)

        start, goal = orient(shift(layout.start)), orient(shift(layout.goal))
        if rng.choice((False, True)):
            start, goal = goal, start

        cx, cy = shift(layout.hazard_center)
        rx, ry = layout.hazard_radius
        # 각 사분면에서 한 점씩 뽑고, 남은 두 점은 전체 위험 범위에 흩뿌린다.
        points = [
            (cx + sx * rng.randint(rx // 2, rx), cy + sy * rng.randint(ry // 2, ry))
            for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1))
        ]
        candidates = [
            (x, y)
            for x in range(cx - rx, cx + rx + 1)
            for y in range(cy - ry, cy + ry + 1)
            if (x, y) not in points
        ]
        points.extend(rng.sample(candidates, 2))
        kinds = list(HAZARDS) * 2
        rng.shuffle(kinds)
        hazards = dict(zip(map(orient, points), kinds))
        zone = hazard_zone.keepout(hazards, COLUMNS, ROWS)
        danger = pathfinder.forbidden_cells(COLUMNS, ROWS, zone=zone)

        obstacles = set()
        offset_x, offset_y = shift((0, 0))
        for left, top, width, height in layout.barriers:
            # 이어진 방벽이 한 덩어리로 움직이도록 공통 오프셋을 준다.
            left += offset_x
            top += offset_y
            obstacles.update(
                orient((x, y))
                for x in range(max(0, left), min(COLUMNS, left + width))
                for y in range(max(0, top), min(ROWS, top + height))
            )
        obstacles.difference_update(danger, (start, goal))
        return cls(layout.name, start, goal, hazards, zone, danger, obstacles)


def center(cell: tuple[float, float]) -> pg.Vector2:
    x, y = cell
    return pg.Vector2(BOARD.x + (x + 0.5) * CELL, BOARD.y + (y + 0.5) * CELL)


class Painter:
    """레이아웃 좌표를 창의 실제 픽셀에 맞춰 그린다."""

    font_families = "malgungothic,notosanscjkkr,nanumgothic,applegothic"

    def __init__(self, surface, scale, offset=(0, 0)):
        self.surface = surface
        self.scale = scale
        self.offset = offset
        self.fonts = {}
        self.text_cache = {}

    def point(self, point):
        x, y = point
        return round(x * self.scale) + self.offset[0], round(y * self.scale) + self.offset[1]

    def box(self, rect):
        x, y, width, height = rect
        left, top = self.point((x, y))
        right, bottom = self.point((x + width, y + height))
        return pg.Rect(left, top, right - left, bottom - top)

    def length(self, value):
        return max(1, round(value * self.scale)) if value else 0

    def rect(self, color, rect, width=0, border_radius=0):
        pg.draw.rect(
            self.surface, color, self.box(rect),
            width=self.length(width), border_radius=self.length(border_radius),
        )

    def line(self, color, start, end):
        pg.draw.line(self.surface, color, self.point(start), self.point(end), self.length(1))

    def circle(self, color, center, radius, width=0):
        x, y = self.point(center)
        radius_px = self.length(radius)
        color = pg.Color(color)
        if width:
            pg.draw.circle(self.surface, color, (x, y), radius_px, self.length(width))
        else:
            gfxdraw.filled_circle(self.surface, x, y, radius_px, color)
        gfxdraw.aacircle(self.surface, x, y, radius_px, color)

    def polygon(self, color, vertices):
        self.fill_polygon(pg.Color(color), [self.point(point) for point in vertices])

    def fill_polygon(self, color, vertices):
        gfxdraw.filled_polygon(self.surface, vertices, color)
        gfxdraw.aapolygon(self.surface, vertices, color)

    def stroke(self, color, closed, vertices, width):
        points = [pg.Vector2(self.point(point)) for point in vertices]
        if closed:
            points.append(points[0])
        color = pg.Color(color)
        radius = width * self.scale / 2
        for start, end in zip(points, points[1:]):
            forward = end - start
            if not forward:
                continue
            if radius < 0.75:
                pg.draw.aaline(self.surface, color, start, end)
                continue
            normal = pg.Vector2(-forward.y, forward.x).normalize() * radius
            corners = (start + normal, end + normal, end - normal, start - normal)
            self.fill_polygon(color, [(round(point.x), round(point.y)) for point in corners])
        if radius >= 0.75:
            for x, y in points:
                gfxdraw.filled_circle(self.surface, int(x), int(y), round(radius), color)
                gfxdraw.aacircle(self.surface, int(x), int(y), round(radius), color)

    def font(self, size):
        if size not in self.fonts:
            bold = size >= 21
            path = pg.font.match_font(self.font_families, bold=bold)
            font = pg.font.Font(path, self.length(size))
            if path is None:
                font.set_bold(bold)
            self.fonts[size] = font
        return self.fonts[size]

    def text(self, value, point, size=15, color=TEXT, anchor="topleft"):
        key = value, size, color
        image = self.text_cache.get(key)
        if image is None:
            image = self.font(size).render(str(value), True, color)
            if len(self.text_cache) >= 256:
                self.text_cache.clear()
            self.text_cache[key] = image
        self.surface.blit(image, image.get_rect(**{anchor: self.point(point)}))


class Simulator:
    def __init__(self, surface: pg.Surface, rng: random.Random | None = None):
        self.surface = surface
        self.rng = rng if rng is not None else random.Random()
        self.paint = Painter(surface, surface.get_width() / WIDTH)
        self.route: pathfinder.Route | None = None
        self.speed = 1
        self.scene = 0
        self.layout_order: list[Layout] = []
        self.new_map()

    def resize(self, surface):
        self.surface = surface
        self.paint = Painter(surface, surface.get_width() / WIDTH)
        self.draw_map_layer()

    def new_map(self) -> None:
        if not self.layout_order:
            self.layout_order = list(LAYOUTS)
            self.rng.shuffle(self.layout_order)
            if self.scene and self.layout_order[-1].name == self.scenario.name:
                self.layout_order[0], self.layout_order[-1] = self.layout_order[-1], self.layout_order[0]
        self.scenario = Scenario.generate(self.rng, self.layout_order.pop())
        self.hazard_counts = Counter(self.scenario.hazards.values())
        self.scene += 1
        self.route = None
        self.reset()
        self.status = "경로 탐색 대기"
        self.draw_map_layer()

    def plan(self) -> None:
        scenario = self.scenario
        self.route = pathfinder.find(
            COLUMNS, ROWS, scenario.start, scenario.goal, scenario.obstacles, scenario.zone,
        )
        self.reset()
        self.status = "경로 확보 · 출발 대기" if self.route else "통과 가능한 경로 없음"

    def reset(self) -> None:
        self.running = False
        self.position = 0.0
        self.status = "출발 대기"

    def toggle_run(self) -> None:
        if self.route is None:
            return
        if self.finished:
            self.reset()
        self.running = not self.running
        self.status = "주행 중" if self.running else "일시 정지"

    @property
    def finished(self) -> bool:
        return self.route is not None and self.position >= self.route.distance

    def update(self, elapsed: float) -> None:
        if self.running and self.route:
            self.position = min(self.route.distance, self.position + elapsed * 4 * self.speed)
            if self.finished:
                self.running = False
                self.status = "목표 도착"

    def buttons(self):
        return (
            (pg.Rect(930, 186, 296, 41), "경로 찾기", self.plan, True, True),
            (pg.Rect(930, 235, 144, 36), self.run_label(), self.toggle_run, self.route is not None, False),
            (pg.Rect(1082, 235, 144, 36), "처음으로", self.reset, self.route is not None, False),
            (pg.Rect(930, 279, 296, 34), "새 지도", self.new_map, True, False),
        )

    def run_label(self) -> str:
        if self.running:
            return "일시 정지"
        if self.finished:
            return "다시 주행"
        return "계속 주행" if self.position else "주행 시작"

    def speed_buttons(self):
        return [(speed, pg.Rect(1048 + index * 60, 324, 58, 26))
                for index, speed in enumerate(SPEEDS)]

    def click(self, point: tuple[float, float]) -> None:
        for rect, _, action, enabled, _ in self.buttons():
            if enabled and rect.collidepoint(point):
                action()
                return
        for speed, rect in self.speed_buttons():
            if rect.collidepoint(point):
                self.speed = speed
                return

    def key(self, key: int) -> None:
        if key == pg.K_RETURN:
            self.plan()
        elif key == pg.K_SPACE:
            self.toggle_run()
        elif key == pg.K_n:
            self.new_map()

    def draw_map_layer(self) -> None:
        board = self.paint.box(BOARD)
        self.map_layer = pg.Surface(board.size)
        self.map_layer.fill(FLOOR)
        layer = Painter(self.map_layer, self.paint.scale, (-board.x, -board.y))
        for x, y in self.scenario.danger:
            layer.rect("#432c24", (BOARD.x + x * CELL, BOARD.y + y * CELL, CELL, CELL))
        for x in range(COLUMNS):
            line_x = BOARD.x + x * CELL
            layer.line(MAJOR_GRID if x % 5 == 0 else GRID, (line_x, BOARD.top), (line_x, BOARD.bottom))
        for y in range(ROWS):
            line_y = BOARD.y + y * CELL
            layer.line(MAJOR_GRID if y % 5 == 0 else GRID, (BOARD.left, line_y), (BOARD.right, line_y))
        for x, y in self.scenario.obstacles:
            tile = (BOARD.x + x * CELL + 1, BOARD.y + y * CELL + 1, CELL - 1, CELL - 1)
            layer.rect("#273d51", tile)
            layer.rect(BLOCK, tile, 1)

    def text(self, value, point, size=15, color=TEXT, anchor="topleft"):
        self.paint.text(value, point, size, color, anchor)

    def panel(self, rect):
        self.paint.rect(PANEL, rect, border_radius=12)
        self.paint.rect(BORDER, rect, width=1, border_radius=12)

    def draw_board(self) -> None:
        self.panel(pg.Rect(28, 108, 865, 660))
        self.text("주행 지도", (49, 123), 21)
        self.text(f"{COLUMNS} × {ROWS} 격자", (868, 129), 15, MUTED, "topright")
        self.surface.blit(self.map_layer, self.paint.point(BOARD.topleft))
        self.paint.rect("#526a82", BOARD, 1)
        for x in range(0, COLUMNS, 5):
            self.text(f"{x:02}", (center((x, 0)).x, 158), 13, MUTED, "center")
        for y in range(0, ROWS, 5):
            self.text(f"{y:02}", (44, center((0, y)).y), 13, MUTED, "center")

        hull = self.scenario.zone.vertices
        if self.scenario.zone.status == "polygon":
            self.paint.stroke(HAZARD, True, [center(cell) for cell in hull], 2)
        for cell, kind in self.scenario.hazards.items():
            self.draw_hazard(center(cell), kind)

        start, goal = self.scenario.start, self.scenario.goal
        location = center(start)
        direction = (center(goal) - location).normalize()
        if self.route and self.route.distance:
            centers = [center(cell) for cell in self.route.cells]
            self.paint.stroke("#244a60", False, centers, 7)
            self.paint.stroke(ROUTE, False, centers, 2)
            index = min(int(self.position), self.route.distance - 1)
            location = centers[index].lerp(centers[index + 1], self.position - index)
            direction = (centers[index + 1] - centers[index]).normalize()
            if self.position > 0:
                self.paint.stroke(ROBOT, False, centers[:index + 1] + [location], 3)

        for cell, name, color in ((start, "출발", ROBOT), (goal, "목표", TARGET)):
            point = center(cell)
            box = (point.x - 7.5, point.y - 7.5, 15, 15)
            self.paint.rect(color, box, width=2, border_radius=3)
            self.text(name, (point.x, point.y - 12), 13, color, "midbottom")

        self.draw_car(location, direction)

        x = 51
        for name, color in (("금지 구역", HAZARD), ("일반 장애물", BLOCK),
                            ("예정 경로", ROUTE), ("주행 완료 구간", ROBOT), ("목표", TARGET)):
            self.paint.rect(color, (x, 726, 10, 10), border_radius=2)
            self.text(name, (x + 17, 722), 15, MUTED)
            x += self.paint.font(15).size(name)[0] / self.paint.scale + 43

    def draw_car(self, location: pg.Vector2, direction: pg.Vector2) -> None:
        across = pg.Vector2(-direction.y, direction.x)

        def shape(color, points):
            self.paint.polygon(color, [
                location + direction * forward + across * sideways
                for forward, sideways in points
            ])

        body = (
            (-9, -4), (-7, -6), (5, -6), (9, -4), (10, -2.5),
            (10, 2.5), (9, 4), (5, 6), (-7, 6), (-9, 4),
        )
        shape(BACKGROUND, [(x * 1.17, y * 1.38) for x, y in body])
        for axle in (-6, 5):
            for side in (-1, 1):
                shape("#5a7084", (
                    (axle - 2, side * 5), (axle + 2, side * 5),
                    (axle + 2, side * 7.5), (axle - 2, side * 7.5),
                ))

        shape(TARGET if self.finished else ROBOT, body)
        shape("#1b3548", ((-5, -3), (-2, -4), (3, -4), (5, -2.5),
                          (5, 2.5), (3, 4), (-2, 4), (-5, 3)))
        shape("#437783", ((-3, -3), (0, -3), (0, 3), (-3, 3)))
        for side in (-1, 1):
            shape("#fff3c1", ((7, side * 2.5), (9, side * 2.5), (8, side * 4)))
            shape("#ff7f78", ((-8, side * 2.5), (-6, side * 3.5),
                              (-7, side * 5), (-8, side * 4)))

    def draw_hazard(self, point, kind):
        x, y = point
        self.paint.circle(FLOOR, point, 8)
        color = HAZARDS[kind]
        if kind == "지진":
            self.paint.polygon(color, [(x, y-5), (x+5, y), (x, y+5), (x-5, y)])
        elif kind == "화재":
            self.paint.polygon(color, [(x, y-5), (x+5, y+4), (x-5, y+4)])
        else:
            self.paint.circle(color, point, 5, 2)
            self.paint.circle(color, point, 1)

    def draw_sidebar(self, mouse) -> None:
        self.panel(pg.Rect(912, 108, 334, 257))
        self.text("주행 제어", (930, 121), 21)
        status_color = ROBOT if self.running or self.finished else MUTED
        self.paint.circle(status_color, (935, 161), 4)
        self.text(self.status, (948, 160), 15, status_color, "midleft")
        for rect, name, _, enabled, primary in self.buttons():
            hovered = rect.collidepoint(mouse) and enabled
            if primary:
                fill = "#99ffdb" if hovered else ROBOT
                color = BACKGROUND
            else:
                fill = "#2b445d" if hovered else "#1b2d41"
                color = TEXT if enabled else "#8194a8"
            self.paint.rect(fill, rect, border_radius=6)
            self.text(name, rect.center, 17, color, "center")
        self.text("주행 속도", (930, 337), 15, MUTED, "midleft")
        for speed, rect in self.speed_buttons():
            selected = speed == self.speed
            self.paint.rect("#22463f" if selected else "#192a3d", rect, border_radius=5)
            self.text(f"{speed}×", rect.center, 15, ROBOT if selected else MUTED, "center")

        self.panel(pg.Rect(912, 377, 334, 171))
        self.text("경로 정보", (930, 391), 21)
        route = self.route
        distance = f"{route.distance}칸" if route else "—"
        turns = f"{route.turns}회" if route else "—"
        progress = self.position / route.distance if route and route.distance else 0
        for index, (name, value) in enumerate((("이동 거리", distance), ("방향 전환", turns))):
            x = 930 + index * 151
            self.paint.rect("#0d1927", (x, 426, 145, 63), border_radius=7)
            self.text(name, (x + 10, 432), 13, MUTED)
            self.text(value, (x + 10, 448), 25)
        self.text("주행 진행률", (930, 499), 15, MUTED)
        self.text(f"{int(progress * 100)}%", (1226, 499), 15, ROUTE, "topright")
        self.paint.rect("#263a4e", (930, 524, 296, 6), border_radius=3)
        if progress:
            self.paint.rect(ROBOT, (930, 524, 296 * progress, 6), border_radius=3)
        self.panel(pg.Rect(912, 560, 334, 208))
        self.text("위험 구역", (930, 574), 21)
        self.text(f"차단 {len(self.scenario.danger)}칸", (1226, 581), 15, HAZARD, "topright")
        for index, kind in enumerate(HAZARDS):
            y = 624 + index * 33
            self.draw_hazard((940, y), kind)
            self.text(kind, (957, y), 15, MUTED, "midleft")
            self.text(f"{self.hazard_counts[kind]}곳", (1226, y), 15, TEXT, "midright")
        self.paint.line(BORDER, (930, 721), (1226, 721))
        self.text(f"외곽 꼭짓점 {len(self.scenario.zone.vertices)}개", (930, 738), 13, MUTED)

    def draw(self, mouse=(-1, -1)) -> None:
        self.surface.fill(BACKGROUND)
        self.paint.rect("#194638", (28, 25, 45, 45), border_radius=10)
        self.paint.stroke(ROBOT, False, ((39, 55), (46, 46), (53, 51), (62, 39)), 3)
        self.text("WayScanner", (86, 18), 32)
        self.text("로봇 위험 구역 회피 시뮬레이터", (87, 59), 15, MUTED)
        self.text(f"시나리오 {self.scene:02} · {self.scenario.name}", (1246, 37), 17, ROUTE, "topright")
        self.text("Enter 경로 찾기    Space 주행    N 새 지도", (1246, 65), 13, MUTED, "topright")
        self.draw_board()
        self.draw_sidebar(mouse)


def viewport(size: tuple[int, int]) -> pg.Rect:
    width, height = size
    scale = min(width / WIDTH, height / HEIGHT)
    destination = pg.Rect(0, 0, max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale)))
    destination.center = width // 2, height // 2
    return destination


def map_pointer(point: tuple[int, int], destination: pg.Rect) -> tuple[float, float]:
    x, y = point
    return ((x - destination.x) * WIDTH / destination.width,
            (y - destination.y) * HEIGHT / destination.height)


def main() -> None:
    if sys.platform == "win32":
        os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    pg.display.init()
    pg.font.init()
    try:
        desktop_width, desktop_height = pg.display.get_desktop_sizes()[0]
        initial = viewport((
            min(2 * WIDTH, round(desktop_width * 0.84)),
            min(2 * HEIGHT, round(desktop_height * 0.84)),
        ))
        window = pg.display.set_mode(initial.size, pg.RESIZABLE)
        pg.display.set_caption("WayScanner | 로봇 위험 구역 회피 시뮬레이터")
        frame = pg.Surface(initial.size)
        simulation = Simulator(frame)
        clock = pg.time.Clock()

        while True:
            elapsed = min(clock.tick(60) / 1000, 0.1)
            destination = viewport(window.get_size())
            for event in pg.event.get():
                if event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                    return
                if event.type == pg.MOUSEBUTTONUP and event.button == 1:
                    simulation.click(map_pointer(event.pos, destination))
                elif event.type == pg.KEYDOWN:
                    simulation.key(event.key)
            simulation.update(elapsed)
            if destination.size != frame.get_size():
                frame = pg.Surface(destination.size)
                simulation.resize(frame)
            simulation.draw(map_pointer(pg.mouse.get_pos(), destination))
            window.fill(BACKGROUND)
            window.blit(frame, destination)
            pg.display.flip()
    finally:
        pg.quit()


if __name__ == "__main__":
    main()
