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

from typing import Iterable, NamedTuple, Sequence

from hazard_zone import Keepout


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
) -> Route | None:
    """최단 회피 경로를 찾는다. 없으면 None.

    이동은 상하좌우만이다.
    평가값은 f(n) = g(n) + h(n)이고, h(n)은 실제 남은 비용보다 크면 안 된다.
    출발지나 목적지가 막혀 있으면 None이다.
    """

    raise NotImplementedError


def forbidden_cells(
    width: int,
    height: int,
    obstacles: Iterable[Sequence[int]] = (),
    zone: Keepout | None = None,
) -> set[Cell]:
    """경로가 들어가면 안 되는 칸.

    일반 장애물, 위험 점 자체, 볼록 다각형의 내부와 경계를 포함한다.
    """

    raise NotImplementedError


def count_turns(cells: Sequence[Cell]) -> int:
    """방향이 바뀐 횟수. 직선이면 0이다."""

    raise NotImplementedError
