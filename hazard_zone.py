"""위험 점을 금지 구역으로 묶는다.

담당: 팀원. 알고리즘 이름은 Graham Scan이다.
이 파일은 pygame을 모른다. 화면 좌표를 받지 않고, 칸 좌표만 받는다.

pygame에서는 이렇게만 부른다.

    zone = hazard_zone.keepout(points, width, height)
"""

from __future__ import annotations

from functools import cmp_to_key
from typing import Iterable, NamedTuple, Sequence


Cell = tuple[int, int]


class Keepout(NamedTuple):
    """경로 모듈에 넘기는 금지 구역.

    status
        "none": 위험 점이 없다.
        "point": 서로 다른 점이 1개다. 다각형이 아니다.
        "segment": 서로 다른 점이 2개이거나, 모두 한 직선 위에 있다.
        "polygon": 넓이가 있는 볼록 다각형이다.
    vertices
        polygon이면 한 바퀴 도는 꼭짓점. 그 외에는 위험 점 자체.
    points
        중복을 뺀 위험 점 전부.
    """

    status: str
    vertices: tuple[Cell, ...]
    points: tuple[Cell, ...]


def keepout(
    points: Iterable[Sequence[int]],
    width: int | None = None,
    height: int | None = None,
) -> Keepout:
    """위험 점 전부를 담는 가장 작은 볼록 다각형을 구한다.

    지도 범위는 칸 인덱스 기준이며, 마지막 칸은 width - 1, height - 1이다.
    width와 height는 각각 생략할 수 있다. 지정한 범위를 벗어난 점은 ValueError다.
    점이 3개 미만이거나 모두 한 직선 위면 polygon이 아닌 상태로 돌려준다.
    """

    _validate_dimension(width, "가로")
    _validate_dimension(height, "세로")

    unique = _unique_cells(points, width, height)
    if not unique:
        return Keepout("none", (), ())
    if len(unique) == 1:
        return Keepout("point", unique, unique)

    vertices = _graham_scan(unique)
    if len(vertices) < 3:
        return Keepout("segment", vertices, unique)
    return Keepout("polygon", vertices, unique)


def contains(zone: Keepout, cell: Sequence[int]) -> bool:
    """칸이 금지 다각형의 안 또는 경계 위이면 True.

    polygon이 아니면 False다. 점 자체를 막을지는 경로 모듈이 zone.points로 본다.
    """

    if zone.status != "polygon":
        return False
    return _inside_or_boundary(zone.vertices, _cell(cell))


def crosses_boundary(zone: Keepout, start: Cell, end: Cell) -> bool:
    """이동 선분이 금지 다각형의 경계와 만나면 True."""

    if zone.status != "polygon":
        return False
    for index, first in enumerate(zone.vertices):
        second = zone.vertices[(index + 1) % len(zone.vertices)]
        if _intersects(start, end, first, second):
            return True
    return False


def _intersects(a: Cell, b: Cell, c: Cell, d: Cell) -> bool:
    # 외적이 0인 평행 선분도 범위가 겹칠 때만 교차로 본다.
    for axis in (0, 1):
        if max(a[axis], b[axis]) < min(c[axis], d[axis]):
            return False
        if max(c[axis], d[axis]) < min(a[axis], b[axis]):
            return False
    return _cross(a, b, c) * _cross(a, b, d) <= 0 and _cross(c, d, a) * _cross(c, d, b) <= 0


def _validate_dimension(value: int | None, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"지도 {label} 크기는 양의 정수여야 합니다.")


def _unique_cells(
    points: Iterable[Sequence[int]],
    width: int | None,
    height: int | None,
) -> tuple[Cell, ...]:
    seen: set[Cell] = set()
    unique: list[Cell] = []
    for raw in points:
        cell = _cell(raw)
        x, y = cell
        if width is not None and not 0 <= x < width:
            raise ValueError(f"위험 점 {cell}이 지도 가로 범위 0..{width - 1} 밖에 있습니다.")
        if height is not None and not 0 <= y < height:
            raise ValueError(f"위험 점 {cell}이 지도 세로 범위 0..{height - 1} 밖에 있습니다.")
        if cell not in seen:
            seen.add(cell)
            unique.append(cell)
    return tuple(unique)


def _cell(value: Sequence[int]) -> Cell:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise TypeError("위험 점은 (x, y) 칸 좌표여야 합니다.")
    x, y = value
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
    ):
        raise TypeError("칸 좌표는 정수여야 합니다. 픽셀 좌표는 칸으로 바꾼 뒤 넘기세요.")
    return (x, y)


def _cross(origin: Cell, a: Cell, b: Cell) -> int:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def _distance2(a: Cell, b: Cell) -> int:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _graham_scan(points: Sequence[Cell]) -> tuple[Cell, ...]:
    """Graham Scan; returns hull vertices in perimeter order."""

    start = min(points, key=lambda point: (point[1], point[0]))

    def compare(a: Cell, b: Cell) -> int:
        turn = _cross(start, a, b)
        if turn > 0:
            return -1
        if turn < 0:
            return 1
        return _distance2(start, a) - _distance2(start, b)

    ordered = sorted((point for point in points if point != start), key=cmp_to_key(compare))

    # 같은 방향의 점 중 가장 먼 점만 남긴다. 내부 점은 다각형 꼭짓점이 아니다.
    rays: list[Cell] = []
    for point in ordered:
        if rays and _cross(start, rays[-1], point) == 0:
            rays[-1] = point
        else:
            rays.append(point)

    hull: list[Cell] = [start]
    for point in rays:
        while len(hull) >= 2 and _cross(hull[-2], hull[-1], point) <= 0:
            hull.pop()
        hull.append(point)
    return tuple(hull)


def _inside_or_boundary(vertices: Sequence[Cell], cell: Cell) -> bool:
    sign = 0
    for index, start in enumerate(vertices):
        end = vertices[(index + 1) % len(vertices)]
        turn = _cross(start, end, cell)
        if turn == 0:
            if _on_segment(start, end, cell):
                return True
            return False
        current = 1 if turn > 0 else -1
        if sign == 0:
            sign = current
        elif sign != current:
            return False
    return True


def _on_segment(start: Cell, end: Cell, cell: Cell) -> bool:
    return (
        min(start[0], end[0]) <= cell[0] <= max(start[0], end[0])
        and min(start[1], end[1]) <= cell[1] <= max(start[1], end[1])
    )
