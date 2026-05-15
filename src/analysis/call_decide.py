"""부로 판단 — 폰/치/깡을 콜할지 스킵할지.

상대가 패를 버린 시점, 그 패를 이용해 부로(鳴き)할 수 있을 때 호출.
판단 기준:
  - 콜 후 샹텐 진전 여부
  - 役 확보 여부 (역패 폰, 쿠이탕 가능, 또이또이 진행)
  - 멘젠 손실 (수비력·리치 권리 상실)
  - 위협·순목

작혼 룰: 쿠이탕(개방 탕야오) 유효.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.game_state import (
    GameState,
    Meld,
    MeldType,
    RoundInfo,
    Tile,
    Wind,
)
from src.analysis.shanten import calculate_shanten
from src.analysis.yaku_suggest import (
    STATUS_CONFIRMED,
    STATUS_POSSIBLE,
    suggest_yaku,
)

_WIND_INDEX = {
    Wind.EAST: 27,
    Wind.SOUTH: 28,
    Wind.WEST: 29,
    Wind.NORTH: 30,
}
_DRAGON_INDICES = (31, 32, 33)


class CallAction(Enum):
    CALL = "콜 (鳴く)"
    SKIP = "스킵 (見逃す)"


@dataclass(frozen=True)
class CallAdvice:
    """부로 판단 결과."""

    action: CallAction
    score: int                 # +이면 콜 쪽
    reasons: tuple[str, ...]
    shanten_before: int
    shanten_after: int


def _is_valued_honor(tile: Tile, round_info: RoundInfo) -> bool:
    """역패(三元 / 자풍 / 장풍)인지."""
    if tile.suit != "z":
        return False
    idx = tile.index34
    if idx in _DRAGON_INDICES:
        return True
    return idx in (
        _WIND_INDEX[round_info.seat_wind],
        _WIND_INDEX[round_info.round_wind],
    )


def _build_post_call_state(
    state: GameState,
    discarded: Tile,
    call_type: MeldType,
    using_tiles: tuple[Tile, ...],
) -> GameState:
    """콜 시뮬레이션 — 손패에서 using_tiles 제거 + 부로 추가."""
    if call_type == MeldType.ANKAN:
        # 안깡은 외부 패 사용 안 함; 여기선 다루지 않음
        meld_tiles = using_tiles
    else:
        meld_tiles = using_tiles + (discarded,)

    # 손패에서 using_tiles 제거 (같은 (suit, rank) 1장씩)
    remaining = list(state.my_hand)
    for t in using_tiles:
        for i, h in enumerate(remaining):
            if h.suit == t.suit and h.rank == t.rank:
                remaining.pop(i)
                break

    new_meld = Meld(
        meld_type=call_type, tiles=meld_tiles, called_from=None,
    )
    return GameState(
        my_hand=tuple(remaining),
        my_melds=state.my_melds + (new_meld,),
        my_discards=state.my_discards,
        discards=dict(state.discards),
        melds=dict(state.melds),
        dora_indicators=state.dora_indicators,
        round=state.round,
        scores=dict(state.scores),
        riichi=dict(state.riichi),
        turn=state.turn,
        tiles_left=state.tiles_left,
    )


def evaluate_call(
    state: GameState,
    discarded: Tile,
    call_type: MeldType,
    using_tiles: tuple[Tile, ...],
) -> CallAdvice:
    """이 콜을 할지 판단.

    using_tiles: 내 손패에서 부로에 쓸 패들 (폰=같은 패 2장, 치=수트런 2장, 깡=3장).
    """
    sh_before = calculate_shanten(state.my_hand, state.my_melds).value
    after = _build_post_call_state(state, discarded, call_type, using_tiles)
    sh_after = calculate_shanten(after.my_hand, after.my_melds).value

    score = 0
    reasons: list[str] = []

    # 샹텐 진전
    if sh_after < sh_before:
        score += 30
        reasons.append(f"샹텐 진전 ({sh_before}→{sh_after}) +30")
    elif sh_after == sh_before:
        score += 5
        reasons.append("샹텐 동일 — 형태 정리 +5")
    else:
        score -= 30
        reasons.append(f"샹텐 후퇴 ({sh_before}→{sh_after}) −30")

    # 役 확보
    yakuhai_call = (
        call_type in (MeldType.PON, MeldType.KAN, MeldType.SHOUMINKAN)
        and _is_valued_honor(discarded, state.round)
    )
    if yakuhai_call:
        score += 40
        reasons.append("역패 폰/깡 — 역 확정 +40")

    # 콜 후 역 추천 — 탕야오 확정 등
    leads_after = suggest_yaku(after)
    confirmed_yaku = [
        l for l in leads_after if l.status == STATUS_CONFIRMED
    ]
    if confirmed_yaku and not yakuhai_call:
        score += 20
        reasons.append(
            f"콜 후 {confirmed_yaku[0].name} 확정 (+20)"
        )

    # 멘젠 손실 패널티 (안깡 제외)
    if state.my_melds == () and call_type != MeldType.ANKAN:
        score -= 15
        reasons.append("멘젠 손실 — 리치·수비력 ↓ (−15)")

    # 위협 — 후반 + 위협 있으면 부로 자제
    threats = sum(1 for r in state.riichi.values() if r)
    if threats and state.turn >= 10:
        cost = 5 * threats
        score -= cost
        reasons.append(f"후반 + 리치 위협 {threats}명 (−{cost})")

    # 종반 + 미텐파이 — 콜해서 빨리 마무리할 가치
    if state.turn >= 12 and sh_after == 0:
        score += 10
        reasons.append("종반에 텐파이 진입 (+10)")

    action = CallAction.CALL if score >= 20 else CallAction.SKIP
    return CallAdvice(
        action=action,
        score=score,
        reasons=tuple(reasons),
        shanten_before=sh_before,
        shanten_after=sh_after,
    )
