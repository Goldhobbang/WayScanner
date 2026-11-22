"""일반 장애물과 금지 구역을 피해 출발지에서 목적지까지 간다.

담당: 본인. 알고리즘 이름은 A*다.
이 파일은 pygame을 모르고, 배터리 잔량도 계산하지 않는다.

pygame에서는 위험 구역을 만든 다음에만 부른다.

    zone = hazard_zone.keepout(points, width, height)
    route = pathfinder.find(width, height, start, goal, obstacles, zone)
    if route is None:
        # 경로 없음. 잔량을 임의 숫자로 채우지 않는다.
        ...
"""

from __future__ import annotations

import heapq
from typing import Iterable, Mapping, NamedTuple, Sequence

from hazard_zone import Keepout, contains


Cell = tuple[int, int]


class Route(NamedTuple):
    """찾아낸 회피 경로.

    cells는 출발지와 목적지를 포함한 칸 순서다.
    distance는 칸 이동 횟수다.
    turns는 진행 방향이 바뀐 횟수다. 첫 이동은 회전이 아니다.
    """

    cells: tuple[Cell, ...]
    distance: int
    turns: int


def find(
    width: int,
    height: int,
    start: Sequence[int],
    goal: Sequence[int],
    obstacles: Iterable[Sequence[int]] = (),
    zone: Keepout | None = None,
    *,
    elevations: Mapping[Cell, int] | None = None,
) -> Route | None:
    """최단 회피 경로를 찾는다. 없으면 None.

    이동은 상하좌우만이다.
    이동 비용은 1 + 진입하는 칸의 높이다. 지정하지 않은 칸의 높이는 0이다.
    이동 비용이 최소 1이므로 맨해튼 거리를 남은 비용의 하한으로 사용한다.
    출발지나 목적지가 막혀 있으면 None이다.
    """

    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("지도 크기는 양의 정수여야 합니다.")

    if elevations is None:
        elevations = {}
    if any(
        isinstance(level, bool) or not isinstance(level, int) or level < 0
        for level in elevations.values()
    ):
        raise ValueError("칸 높이는 0 이상의 정수여야 합니다.")

    start_cell = _cell(start, "출발지")
    goal_cell = _cell(goal, "목적지")
    blocked = forbidden_cells(width, height, obstacles, zone)
    if not _inside_map(start_cell, width, height) or not _inside_map(goal_cell, width, height):
        return None
    if start_cell in blocked or goal_cell in blocked:
        return None
    if start_cell == goal_cell:
        return Route((start_cell,), 0, 0)

    open_set: list[tuple[int, int, Cell]] = [(_manhattan(start_cell, goal_cell), 0, start_cell)]
    came_from: dict[Cell, Cell] = {}
    cost_so_far: dict[Cell, int] = {start_cell: 0}

    while open_set:
        _, cost, current = heapq.heappop(open_set)
        if cost != cost_so_far.get(current):
            continue
        if current == goal_cell:
            cells = _reconstruct(came_from, current)
            return Route(cells, len(cells) - 1, count_turns(cells))

        for neighbor in _neighbors(current):
            if not _inside_map(neighbor, width, height) or neighbor in blocked:
                continue
            next_cost = cost + 1 + elevations.get(neighbor, 0)
            if next_cost >= cost_so_far.get(neighbor, next_cost + 1):
                continue
            cost_so_far[neighbor] = next_cost
            came_from[neighbor] = current
            priority = next_cost + _manhattan(neighbor, goal_cell)
            heapq.heappush(open_set, (priority, next_cost, neighbor))

    return None


def forbidden_cells(
    width: int,
    height: int,
    obstacles: Iterable[Sequence[int]] = (),
    zone: Keepout | None = None,
) -> set[Cell]:
    """경로가 들어가면 안 되는 칸.

    일반 장애물, 위험 점 자체, 볼록 다각형의 내부와 경계를 포함한다.
    """

    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("지도 크기는 양의 정수여야 합니다.")

    if zone is None:
        zone = Keepout("none", (), ())
    blocked = {_cell(point, "장애물") for point in obstacles}
    blocked.update(zone.points)
    if zone.status == "polygon":
        for y in range(height):
            for x in range(width):
                if contains(zone, (x, y)):
                    blocked.add((x, y))
    return {cell for cell in blocked if _inside_map(cell, width, height)}


def count_turns(cells: Sequence[Cell]) -> int:
    """방향이 바뀐 횟수. 직선이면 0이다."""

    if len(cells) < 3:
        return 0
    turns = 0
    previous = _direction(cells[0], cells[1])
    for index in range(1, len(cells) - 1):
        direction = _direction(cells[index], cells[index + 1])
        if direction != previous:
            turns += 1
            previous = direction
    return turns


def _neighbors(cell: Cell) -> tuple[Cell, ...]:
    x, y = cell
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _reconstruct(came_from: dict[Cell, Cell], goal: Cell) -> tuple[Cell, ...]:
    cells = [goal]
    while cells[-1] in came_from:
        cells.append(came_from[cells[-1]])
    cells.reverse()
    return tuple(cells)


def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _direction(a: Cell, b: Cell) -> Cell:
    return (b[0] - a[0], b[1] - a[1])


def _inside_map(cell: Cell, width: int, height: int) -> bool:
    return 0 <= cell[0] < width and 0 <= cell[1] < height


def _cell(value: Sequence[int], label: str) -> Cell:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise TypeError(f"{label}은 (x, y) 칸 좌표여야 합니다.")
    x, y = value
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
    ):
        raise TypeError(f"{label} 좌표는 정수 칸이어야 합니다.")
    return (x, y)
