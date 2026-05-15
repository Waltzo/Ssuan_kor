"""텐파이 분석 — 대기패, 후리텐, 役なし 경고.

플레이어 입장에서 치명적인 두 가지를 잡아낸다:
  - 후리텐(振聴): 텐파이인데 내 버림패에 대기패가 있으면 론 불가
  - 役なし 텐파이: 텐파이인데 역이 없으면 론 불가 (형식 텐파이)
"""

from __future__ import annotations

from dataclasses import dataclass

from mahjong.hand_calculating.hand import HandCalculator

from src.core.game_state import GameState, Meld, MeldType, RoundInfo, Tile
from src.analysis.shanten import calculate_shanten
from src.analysis.tiles import tiles_to_34, wall_remaining
from src.analysis._libbridge import hand_and_win_136, make_config, to_lib_melds

_calc = HandCalculator()


@dataclass(frozen=True)
class WaitTile:
    """대기패 한 종류."""

    tile: Tile
    count: int          # 남은 매수 (보이는 패 제외)
    is_yakuless: bool   # 이 패로 론하면 役なし (리치·쯔모 없이는 화료 불가)


@dataclass(frozen=True)
class TenpaiInfo:
    """텐파이 분석 결과."""

    is_tenpai: bool
    waits: tuple[WaitTile, ...]
    waits_total: int            # 남은 대기패 총 매수
    is_furiten: bool            # 후리텐 여부 (론 불가)
    can_riichi: bool            # 멘젠 + 텐파이 → 리치 가능
    has_any_yaku: bool          # 역이 있는 대기가 하나라도 존재
    all_waits_yakuless: bool    # 모든 대기가 役なし (형식 텐파이)

    @property
    def can_ron(self) -> bool:
        """론으로 화료 가능한지 — 후리텐 아니고, 역 있는 대기 존재."""
        return self.is_tenpai and not self.is_furiten and self.has_any_yaku


def _has_yaku_on_ron(
    hand13: tuple[Tile, ...],
    win: Tile,
    melds: tuple[Meld, ...],
    round_info: RoundInfo,
) -> bool:
    """주어진 대기패로 론했을 때 역이 하나라도 성립하는지.

    리치·이빠츠·멘젠쯔모 등 선언/상황 의존 역은 제외 (순수 손패 역만).
    """
    full136, win136 = hand_and_win_136(hand13, win)
    config = make_config(round_info, is_tsumo=False, is_riichi=False)
    try:
        result = _calc.estimate_hand_value(
            full136, win136, melds=to_lib_melds(melds), config=config
        )
    except Exception:  # noqa: BLE001 — 라이브러리 내부 예외 방어
        return False
    return result.error is None and bool(result.yaku)


def tenpai_for_hand(
    hand13: tuple[Tile, ...],
    melds: tuple[Meld, ...] = (),
    state: GameState | None = None,
    round_info: RoundInfo | None = None,
    my_discard_indices: frozenset[int] = frozenset(),
) -> TenpaiInfo:
    """13장(또는 10·7장) 손패의 텐파이 분석.

    my_discard_indices: 내 버림패의 34-index 집합 (후리텐 판정용).
    """
    round_info = round_info or RoundInfo()
    shanten = calculate_shanten(hand13, melds)
    if not shanten.is_tenpai:
        return TenpaiInfo(
            is_tenpai=False,
            waits=(),
            waits_total=0,
            is_furiten=False,
            can_riichi=False,
            has_any_yaku=False,
            all_waits_yakuless=False,
        )

    hand_counts = tiles_to_34(hand13)
    waits: list[WaitTile] = []
    for idx in range(34):
        if hand_counts[idx] >= 4:
            continue
        tile = Tile.from_index34(idx)
        if calculate_shanten(hand13 + (tile,), melds).is_agari:
            count = wall_remaining(state, idx) if state is not None else (
                4 - hand_counts[idx]
            )
            yakuless = not _has_yaku_on_ron(hand13, tile, melds, round_info)
            waits.append(WaitTile(tile=tile, count=count, is_yakuless=yakuless))

    is_furiten = any(w.tile.index34 in my_discard_indices for w in waits)
    has_any_yaku = any(not w.is_yakuless for w in waits)
    is_menzen = all(m.meld_type == MeldType.ANKAN for m in melds)

    return TenpaiInfo(
        is_tenpai=True,
        waits=tuple(waits),
        waits_total=sum(w.count for w in waits),
        is_furiten=is_furiten,
        can_riichi=is_menzen,
        has_any_yaku=has_any_yaku,
        all_waits_yakuless=bool(waits) and not has_any_yaku,
    )


def analyze_tenpai(state: GameState) -> TenpaiInfo:
    """GameState 기준 텐파이 분석.

    손패가 13장(대기 중)이어야 한다. 14장(쯔모 직후)이면
    먼저 efficiency.recommend_discards로 타패를 정한 뒤 분석할 것.
    """
    if len(state.my_hand) % 3 != 1:
        raise ValueError(
            f"텐파이 분석은 대기 중 손패(13·10·7장)에만 가능 "
            f"(현재 {len(state.my_hand)}장)"
        )
    my_discard_indices = frozenset(d.tile.index34 for d in state.my_discards)
    return tenpai_for_hand(
        hand13=state.my_hand,
        melds=state.my_melds,
        state=state,
        round_info=state.round,
        my_discard_indices=my_discard_indices,
    )
