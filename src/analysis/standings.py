"""점수상황·착순 전략 — 올라스 등 결정적 국면의 모드 판단.

타패·리치·오시히키 판단에 가중치를 주기 위한 컨텍스트 제공.

모드:
  TOP_LOCK   1등 사수 — 작은 점수도 지키고, 위험 회피
  CHASE_TOP  1등 추격 — 큰 타점 노리는 손 우선
  AVOID_LAST 라스 회피 — 적은 손이라도 화료, 방총 회피 최우선
  NEUTRAL    표준 국면 — 기본 전략
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.game_state import GameState, Seat, Wind


class Mode(Enum):
    TOP_LOCK = "1등 사수"
    CHASE_TOP = "1등 추격"
    AVOID_LAST = "라스 회피"
    NEUTRAL = "표준"


@dataclass(frozen=True)
class StandingsContext:
    """점수상황 + 전략 모드."""

    my_rank: int                   # 1~4 (점수 동일 시 자리 순서로 결정)
    my_score: int
    gap_above: int | None          # 바로 위 사람과 점수차 (1등이면 None)
    gap_below: int | None          # 바로 아래 사람과 점수차 (4등이면 None)
    mode: Mode
    is_oorasu: bool                # 올라스(=마지막 국)인지
    note: str                      # 한 줄 설명

    @property
    def is_dealer_locked_first(self) -> bool:
        """1등이면서 親(오야) — 가장 안전 (계속 親이 굴러옴)."""
        return self.my_rank == 1


def _is_oorasu(state: GameState) -> bool:
    """남2국(=하나마지) 또는 동4국·남4국이 올라스 — 정확한 판정은 局 정보 필요.

    여기선 round_wind == 남 + my_seat_wind == 북(=마지막)인 경우를
    'south game oorasu'로 간단 처리. 정밀하게는 게임 진행도 추적 필요.
    """
    rw = state.round.round_wind
    sw = state.round.seat_wind
    if rw == Wind.SOUTH and sw == Wind.NORTH:
        return True
    if rw == Wind.EAST and sw == Wind.NORTH:
        return True  # 동4국 (동풍전이면 올라스)
    return False


def evaluate_standings(state: GameState) -> StandingsContext:
    """점수상황 분석 + 전략 모드 결정."""
    scores = state.scores
    my_score = scores.get(Seat.SELF, 25000)

    if not scores:
        return StandingsContext(
            my_rank=1,
            my_score=my_score,
            gap_above=None,
            gap_below=None,
            mode=Mode.NEUTRAL,
            is_oorasu=False,
            note="점수 정보 없음 — 표준 모드",
        )

    # 자리 순서 (동→남→서→북) — 동점 시 자리 순으로 우열
    seat_order = [Seat.SELF, Seat.SHIMOCHA, Seat.TOIMEN, Seat.KAMICHA]
    ranking = sorted(
        seat_order,
        key=lambda s: (-scores.get(s, 0), seat_order.index(s)),
    )
    my_rank = ranking.index(Seat.SELF) + 1

    # 위·아래 점수차
    gap_above: int | None = None
    gap_below: int | None = None
    if my_rank > 1:
        above_seat = ranking[my_rank - 2]
        gap_above = scores.get(above_seat, 0) - my_score
    if my_rank < 4:
        below_seat = ranking[my_rank]
        gap_below = my_score - scores.get(below_seat, 0)

    is_oorasu = _is_oorasu(state)

    # 모드 결정
    if is_oorasu:
        if my_rank == 1:
            mode = Mode.TOP_LOCK
            note = (
                f"올라스 1등 — {gap_below}점 차 사수. 큰 손 노리지 말고 "
                f"빨리 화료 또는 안전하게 유국."
            )
        elif my_rank == 4:
            mode = Mode.AVOID_LAST
            note = (
                f"올라스 4등 — 위와 {gap_above}점 차. 어떤 화료라도 좋고, "
                f"방총 절대 회피."
            )
        elif my_rank in (2, 3) and gap_above and gap_above <= 8000:
            mode = Mode.CHASE_TOP
            note = f"올라스 {my_rank}등 — {gap_above}점 차 추격, 만관 이상 필요"
        else:
            mode = Mode.NEUTRAL
            note = f"올라스 {my_rank}등 — 표준"
    else:
        # 중반 국 — 보통 표준
        if my_score < 5000:
            mode = Mode.AVOID_LAST
            note = f"{my_score}점 — 점수 적음, 방총 회피 우선"
        elif my_rank == 1 and gap_below and gap_below >= 20000:
            mode = Mode.TOP_LOCK
            note = f"1등 압도 — {gap_below}점 차, 안전 운영"
        else:
            mode = Mode.NEUTRAL
            note = f"{my_rank}등 / 표준 국면"

    return StandingsContext(
        my_rank=my_rank,
        my_score=my_score,
        gap_above=gap_above,
        gap_below=gap_below,
        mode=mode,
        is_oorasu=is_oorasu,
        note=note,
    )
