"""우케이레(受け入れ) 계산 + 타패 추천.

타패 추천 = 이 프로젝트의 핵심 기능. 쯔모 직후 14장 손패에서
"어느 패를 버려야 하는가"를 샹텐·우케이레 매수·종류로 순위 매긴다.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.game_state import GameState, Meld, Tile
from src.analysis.shanten import calculate_shanten
from src.analysis.tiles import tiles_to_34, wall_remaining


@dataclass(frozen=True)
class UkeireTile:
    """우케이레 패 한 종류와 남은 매수."""

    tile: Tile
    count: int  # 산·상대 손에 남아 있을 수 있는 최대 매수


@dataclass(frozen=True)
class DiscardOption:
    """특정 패를 버렸을 때의 결과."""

    discard: Tile
    shanten: int
    ukeire: tuple[UkeireTile, ...]
    ukeire_total: int   # 우케이레 총 매수 (속도 지표)
    ukeire_types: int   # 우케이레 종류 수 (대기 폭 지표)


def ukeire_for_hand(
    hand13: tuple[Tile, ...],
    melds: tuple[Meld, ...] = (),
    state: GameState | None = None,
) -> tuple[UkeireTile, ...]:
    """13장(또는 10·7장) 손패의 우케이레 패 목록.

    각 패를 1장 추가했을 때 샹텐이 줄어드는 패가 우케이레.
    state가 있으면 화면상 보이는 패를 빼고 실제 남은 매수를 센다.
    """
    base = calculate_shanten(hand13, melds).value
    hand_counts = tiles_to_34(hand13)
    out: list[UkeireTile] = []

    for idx in range(34):
        if hand_counts[idx] >= 4:
            continue  # 이미 4장 보유 — 더 못 뽑음
        tile = Tile.from_index34(idx)
        if calculate_shanten(hand13 + (tile,), melds).value < base:
            if state is not None:
                count = wall_remaining(state, idx)
            else:
                count = 4 - hand_counts[idx]
            if count > 0:
                out.append(UkeireTile(tile, count))
    return tuple(out)


def recommend_discards(state: GameState) -> tuple[DiscardOption, ...]:
    """쯔모 직후 손패에서 타패 후보를 좋은 순서로 정렬해 반환.

    정렬 기준: 샹텐 오름차순 → 우케이레 총 매수 내림차순 → 종류 내림차순.
    선두 항목이 추천 타패.
    """
    hand = state.my_hand
    if len(hand) % 3 != 2:
        raise ValueError(
            f"타패 추천은 쯔모 직후(14·11·8장) 손패에만 가능 (현재 {len(hand)}장)"
        )

    seen: set[tuple[str, int]] = set()
    options: list[DiscardOption] = []

    for i, tile in enumerate(hand):
        key = (tile.suit, tile.rank)  # 아카 무시 — 같은 숫자패는 한 번만 평가
        if key in seen:
            continue
        seen.add(key)

        rest = hand[:i] + hand[i + 1 :]
        sh = calculate_shanten(rest, state.my_melds).value
        uk = ukeire_for_hand(rest, state.my_melds, state)
        total = sum(u.count for u in uk)
        options.append(
            DiscardOption(
                discard=tile,
                shanten=sh,
                ukeire=uk,
                ukeire_total=total,
                ukeire_types=len(uk),
            )
        )

    options.sort(key=lambda o: (o.shanten, -o.ukeire_total, -o.ukeire_types))
    return tuple(options)


def best_discard(state: GameState) -> DiscardOption | None:
    """추천 타패 1개 (없으면 None)."""
    opts = recommend_discards(state)
    return opts[0] if opts else None
