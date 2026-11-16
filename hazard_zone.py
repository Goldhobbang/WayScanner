"""위험 점을 금지 구역으로 묶는다.

담당: 팀원. 알고리즘 이름은 Graham Scan이다.
이 파일은 pygame을 모른다. 화면 좌표를 받지 않고, 칸 좌표만 받는다.

pygame에서는 이렇게만 부른다.

    zone = hazard_zone.keepout(points, width, height)

점을 3개 이상 주면 그 점을 모두 담는 가장 작은 볼록 다각형의 꼭짓점을 돌려준다.
점이 더 적으면 다각형을 만들지 않고, 상태만 구분한다.
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
        중복을 뺀 위험 점 전부. 다각형 안에 묻힌 점도 여기 남아 있다.
    """

    status: str
    vertices: tuple[Cell, ...]
    points: tuple[Cell, ...]


def keepout(
    points: Iterable[Sequence[int]],
    width: int | None = None,
    height: int | None = None,
) -> Keepout:
    """위험 점 목록을 Keepout으로 바꾼다.

    width, height를 주면 지도 밖의 점은 조용히 버리지 않고 오류로 알린다.
    지도 범위는 칸 인덱스 기준이며, 마지막 칸은 width - 1, height - 1이다.
    """

    unique = _unique_cells(points, width, height)
    if not unique:
        return Keepout("none", (), ())
    if len(unique) == 1:
        return Keepout("point", unique, unique)
    vertices = _graham(unique)
    if len(vertices) < 3:
        status = "point" if len(vertices) == 1 else "segment"
        return Keepout(status, vertices, unique)
    return Keepout("polygon", vertices, unique)


def contains(zone: Keepout, cell: Sequence[int]) -> bool:
    """칸이 금지 다각형의 안 또는 경계 위이면 True.

    점이 2개 이하라 다각형이 아니면 False다. 그 점 자체를 막을지는
    경로 모듈이 zone.points로 판단한다.
    """

    if zone.status != "polygon":
        return False
    return _inside_or_boundary(zone.vertices, _cell(cell))


def _unique_cells(
    points: Iterable[Sequence[int]],
    width: int | None,
    height: int | None,
) -> tuple[Cell, ...]:
    seen: set[Cell] = set()
    ordered: list[Cell] = []
    for raw in points:
        cell = _cell(raw)
        _check_bounds(cell, width, height)
        if cell not in seen:
            seen.add(cell)
            ordered.append(cell)
    return tuple(ordered)


def _cell(value: Sequence[int]) -> Cell:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise TypeError("위험 점은 (x, y) 칸 좌표여야 합니다.")
    x, y = value
    if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
        raise TypeError("칸 좌표는 정수여야 합니다. 픽셀 좌표는 main에서 칸으로 바꾼 뒤 넘기세요.")
    return (x, y)


def _check_bounds(cell: Cell, width: int | None, height: int | None) -> None:
    x, y = cell
    if width is not None and not (0 <= x < width):
        raise ValueError(f"위험 점 {cell}이 지도 가로 범위 0..{width - 1} 밖에 있습니다.")
    if height is not None and not (0 <= y < height):
        raise ValueError(f"위험 점 {cell}이 지도 세로 범위 0..{height - 1} 밖에 있습니다.")


def _cross(origin: Cell, a: Cell, b: Cell) -> int:
    """origin -> a, origin -> b의 외적. 양수면 b가 a의 왼쪽이다."""

    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def _graham(points: Sequence[Cell]) -> tuple[Cell, ...]:
    """정수 칸에서 각도를 비교하는 Graham Scan.

    atan2는 같은 직선 위의 칸도 다른 각으로 볼 수 있어 쓰지 않는다.
    기준점은 가장 아래, 같으면 가장 왼쪽 점이다.
    """

    start = min(points, key=lambda point: (point[1], point[0]))

    def compare(a: Cell, b: Cell) -> int:
        turn = _cross(start, a, b)
        if turn > 0:
            return -1
        if turn < 0:
            return 1
        return _distance2(start, a) - _distance2(start, b)

    ordered = sorted((point for point in points if point != start), key=cmp_to_key(compare))
    farthest: list[Cell] = []
    for point in ordered:
        if farthest and _cross(start, farthest[-1], point) == 0:
            farthest[-1] = point
        else:
            farthest.append(point)

    hull: list[Cell] = [start]
    for point in farthest:
        while len(hull) >= 2 and _cross(hull[-2], hull[-1], point) <= 0:
            hull.pop()
        hull.append(point)
    return tuple(hull)


def _distance2(a: Cell, b: Cell) -> int:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _inside_or_boundary(vertices: Sequence[Cell], cell: Cell) -> bool:
    sign = 0
    count = len(vertices)
    for index in range(count):
        start = vertices[index]
        end = vertices[(index + 1) % count]
        turn = _cross(start, end, cell)
        if turn == 0:
            if _on_segment(start, end, cell):
                return True
            continue
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
