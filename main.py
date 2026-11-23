"""Tkinter 기반 WayScanner 격자 시뮬레이터.

실행: python main.py
"""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import ttk

import hazard_zone
import pathfinder


GRID_WIDTH = 40
GRID_HEIGHT = 26
CELL_SIZE = 24
START = (1, 1)
GOAL = (GRID_WIDTH - 2, GRID_HEIGHT - 2)
MAX_HILLS = 20
HILL_COLORS = ("#fef3c7", "#fde68a", "#fcd34d", "#fbbf24", "#f59e0b")

COLORS = {
    "background": "#f8fafc",
    "grid": "#d9e2ec",
    "obstacle": "#475569",
    "zone": "#fecaca",
    "risk_point": "#dc2626",
    "path": "#2563eb",
    "start": "#16a34a",
    "goal": "#7c3aed",
}


def hill_elevations(
    rng: random.Random, count: int, unavailable: set[pathfinder.Cell]
) -> dict[pathfinder.Cell, int]:
    candidates = [
        (x, y)
        for y in range(GRID_HEIGHT)
        for x in range(GRID_WIDTH)
        if (x, y) not in unavailable
    ]
    max_height = len(HILL_COLORS)
    elevations: dict[pathfinder.Cell, int] = {}
    for _ in range(count):
        cx, cy = rng.choice(candidates)
        peak = rng.randint(2, max_height)
        # 봉우리 사이를 띄워 낮은 언덕도 주변보다 높게 유지한다.
        candidates = [
            (x, y) for x, y in candidates if abs(x - cx) + abs(y - cy) >= max_height
        ]
        for y in range(max(0, cy - peak + 1), min(GRID_HEIGHT, cy + peak)):
            for x in range(max(0, cx - peak + 1), min(GRID_WIDTH, cx + peak)):
                cell = (x, y)
                level = peak - abs(x - cx) - abs(y - cy)
                if level > 0 and cell not in unavailable:
                    elevations[cell] = max(level, elevations.get(cell, 0))
    return elevations


class WayScannerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(f"WayScanner — {GRID_WIDTH} × {GRID_HEIGHT}")
        root.resizable(False, False)

        self.zone = hazard_zone.Keepout("none", (), ())
        self.hazards: list[tuple[int, int]] = []
        self.obstacles: set[tuple[int, int]] = set()
        self.elevations: dict[pathfinder.Cell, int] = {}
        self.route: pathfinder.Route | None = None
        self.hill_count = tk.IntVar(value=2)
        self.status = tk.StringVar(value="새 지도를 생성했습니다. 경로 찾기를 눌러 보세요.")
        self.metrics = tk.StringVar(value="경로 정보가 여기에 표시됩니다.")

        outer = ttk.Frame(root, padding=12)
        outer.grid(sticky="nsew")
        self.canvas = tk.Canvas(
            outer,
            width=GRID_WIDTH * CELL_SIZE,
            height=GRID_HEIGHT * CELL_SIZE,
            background=COLORS["background"],
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, rowspan=5, sticky="nsew")

        panel = ttk.Frame(outer, padding=(16, 0, 0, 0))
        panel.grid(row=0, column=1, sticky="new")
        ttk.Label(panel, text="WayScanner", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(
            panel,
            text="위험 구역과 장애물을 피해\n목적지까지 가는 경로를 찾습니다.",
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))
        terrain = ttk.Frame(panel)
        terrain.grid(row=2, column=0, sticky="w", pady=(0, 8))
        ttk.Label(terrain, text="언덕 개수").grid(row=0, column=0, padx=(0, 8))
        ttk.Combobox(
            terrain,
            textvariable=self.hill_count,
            values=tuple(range(MAX_HILLS + 1)),
            state="readonly",
            width=4,
        ).grid(row=0, column=1)
        ttk.Button(panel, text="새 지도", command=self.new_map).grid(
            row=3, column=0, sticky="ew", pady=3
        )
        ttk.Button(panel, text="경로 찾기", command=self.find_path).grid(
            row=4, column=0, sticky="ew", pady=3
        )
        ttk.Separator(panel).grid(row=5, column=0, sticky="ew", pady=12)
        ttk.Label(panel, textvariable=self.status, wraplength=220, justify="left").grid(
            row=6, column=0, sticky="w", pady=4
        )
        ttk.Label(panel, textvariable=self.metrics, wraplength=220, justify="left").grid(
            row=7, column=0, sticky="w", pady=8
        )
        ttk.Separator(panel).grid(row=8, column=0, sticky="ew", pady=8)
        ttk.Label(
            panel,
            text="배터리 잔량: 예측 불가\n학습된 예측 모델이 아직 없습니다.",
            foreground="#64748b",
            justify="left",
        ).grid(row=9, column=0, sticky="w", pady=4)
        ttk.Label(
            panel,
            text="범례\n■ 위험 구역  ■ 장애물\n■ 경로      ■ 출발 / 목적지\n■ 언덕 (색이 진할수록 높음)",
            justify="left",
        ).grid(row=10, column=0, sticky="w", pady=(14, 0))

        self.new_map()

    def new_map(self) -> None:
        rng = random.Random()
        candidates = [
            (x, y)
            for x in range(GRID_WIDTH // 3, GRID_WIDTH * 2 // 3)
            for y in range(GRID_HEIGHT // 4, GRID_HEIGHT * 3 // 4)
        ]
        self.hazards = rng.sample(candidates, 6)
        self.zone = hazard_zone.keepout(
            self.hazards,
            width=GRID_WIDTH,
            height=GRID_HEIGHT,
        )

        forbidden = pathfinder.forbidden_cells(
            GRID_WIDTH,
            GRID_HEIGHT,
            zone=self.zone,
        )
        obstacle_candidates = [
            (x, y)
            for y in range(1, GRID_HEIGHT - 1)
            for x in range(1, GRID_WIDTH - 1)
            if (x, y) not in forbidden and (x, y) not in (START, GOAL)
        ]
        self.obstacles = set(rng.sample(obstacle_candidates, min(34, len(obstacle_candidates))))
        hill_count = self.hill_count.get()
        self.elevations = hill_elevations(rng, hill_count, forbidden | self.obstacles | {START, GOAL})
        self.route = None
        self.status.set(f"새 지도를 만들었습니다. 언덕 {hill_count}개")
        self.metrics.set("경로 정보가 여기에 표시됩니다.")
        self.draw()

    def find_path(self) -> None:
        self.route = pathfinder.find(
            GRID_WIDTH,
            GRID_HEIGHT,
            START,
            GOAL,
            self.obstacles,
            self.zone,
            elevations=self.elevations,
        )
        if self.route is None:
            self.status.set("경로를 찾지 못했습니다. 새 지도를 만들어 다시 시도하세요.")
            self.metrics.set("경로가 없어 배터리 예측을 하지 않습니다.")
        else:
            self.status.set("안전한 경로를 찾았습니다.")
            self.metrics.set(
                f"이동 거리: {self.route.distance}칸\n"
                f"방향 전환: {self.route.turns}회\n"
                "배터리 잔량: 예측 불가 (모델 없음)"
            )
        self.draw()

    def draw(self) -> None:
        self.canvas.delete("all")
        for (x, y), level in self.elevations.items():
            self._cell(x, y, HILL_COLORS[level - 1])
        blocked_zone = pathfinder.forbidden_cells(
            GRID_WIDTH,
            GRID_HEIGHT,
            zone=self.zone,
        )
        for x, y in blocked_zone:
            self._cell(x, y, COLORS["zone"])
        for x, y in self.obstacles:
            self._cell(x, y, COLORS["obstacle"])

        if self.route is not None:
            centers = [self._center(cell) for cell in self.route.cells]
            if len(centers) > 1:
                self.canvas.create_line(
                    *[coordinate for center in centers for coordinate in center],
                    fill=COLORS["path"],
                    width=5,
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND,
                )

        for x, y in self.hazards:
            self._cell(x, y, COLORS["risk_point"], inset=6)
        self._marker(START, COLORS["start"], "S")
        self._marker(GOAL, COLORS["goal"], "G")

        for x in range(GRID_WIDTH + 1):
            px = x * CELL_SIZE
            self.canvas.create_line(px, 0, px, GRID_HEIGHT * CELL_SIZE, fill=COLORS["grid"])
        for y in range(GRID_HEIGHT + 1):
            py = y * CELL_SIZE
            self.canvas.create_line(0, py, GRID_WIDTH * CELL_SIZE, py, fill=COLORS["grid"])

    def _cell(self, x: int, y: int, color: str, inset: int = 1) -> None:
        left = x * CELL_SIZE + inset
        top = y * CELL_SIZE + inset
        right = (x + 1) * CELL_SIZE - inset
        bottom = (y + 1) * CELL_SIZE - inset
        self.canvas.create_rectangle(left, top, right, bottom, fill=color, outline="")

    def _center(self, cell: tuple[int, int]) -> tuple[int, int]:
        return (cell[0] * CELL_SIZE + CELL_SIZE // 2, cell[1] * CELL_SIZE + CELL_SIZE // 2)

    def _marker(self, cell: tuple[int, int], color: str, label: str) -> None:
        x, y = self._center(cell)
        radius = CELL_SIZE // 3
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="white", width=2)
        self.canvas.create_text(x, y, text=label, fill="white", font=("Segoe UI", 9, "bold"))


def main() -> None:
    root = tk.Tk()
    WayScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
