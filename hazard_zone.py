"""위험 점을 금지 구역으로 묶는다.

담당: 팀원. 알고리즘 이름은 Graham Scan이다.
이 파일은 pygame을 모른다. 화면 좌표를 받지 않고, 칸 좌표만 받는다.

pygame에서는 이렇게만 부른다.

    zone = hazard_zone.keepout(points, width, height)
"""

from __future__ import annotations

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
    점이 3개 미만이거나 모두 한 직선 위면 polygon이 아닌 상태로 돌려준다.
    """

    raise NotImplementedError


def contains(zone: Keepout, cell: Sequence[int]) -> bool:
    """칸이 금지 다각형의 안 또는 경계 위이면 True.

    polygon이 아니면 False다. 점 자체를 막을지는 경로 모듈이 zone.points로 본다.
    """

    raise NotImplementedError
