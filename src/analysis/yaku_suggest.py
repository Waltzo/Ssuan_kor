"""역 추천 — 미완성 손패에서 노릴 만한 역의 방향 제시.

휴리스틱 기반. 완성형 타점은 value.estimate_value가, 텐파이 실제 역은
tenpai.analyze_tenpai가 담당하고, 이 모듈은 "어느 역을 노릴까"를 안내한다.
정직하게 "확정 / 가능 / 경향" 3단계로만 표기한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.game_state import GameState, MeldType, Tile, Wind

# 자풍·장풍 → 해당 풍패의 34-index (z1=동 ... z4=북 → idx 27~30)
_WIND_INDEX = {
    Wind.EAST: 27,
    Wind.SOUTH: 28,
    Wind.WEST: 29,
    Wind.NORTH: 30,
}
_DRAGON_INDICES = (31, 32, 33)  # 백·발·중

STATUS_CONFIRMED = "확정"
STATUS_POSSIBLE = "가능"
STATUS_TREND = "경향"


@dataclass(frozen=True)
class YakuLead:
    """노릴 만한 역 하나."""

    name: str
    status: str   # 확정 / 가능 / 경향
    note: str


def _all_tiles(state: GameState) -> list[Tile]:
    """손패 + 부로 패 전체."""
    tiles = list(state.my_hand)
    for m in state.my_melds:
        tiles.extend(m.tiles)
    return tiles


def _counts34(tiles: list[Tile]) -> list[int]:
    arr = [0] * 34
    for t in tiles:
        arr[t.index34] += 1
    return arr


def suggest_yaku(state: GameState) -> tuple[YakuLead, ...]:
    """현재 손패에서 노릴 만한 역들을 반환 (높은 우선순위 순)."""
    tiles = _all_tiles(state)
    if not tiles:
        return ()
    counts = _counts34(tiles)
    leads: list[YakuLead] = []

    leads += _check_tanyao(counts)
    leads += _check_yakuhai(counts, state)
    leads += _check_flush(tiles, counts, state)
    leads += _check_chiitoitsu(counts, state)
    leads += _check_toitoi(counts, state)
    leads += _check_pinfu(counts, state)

    return tuple(leads)


def _check_tanyao(counts: list[int]) -> list[YakuLead]:
    """탕야오 — 야오추패(1·9·字) 보유 수로 판단."""
    yaochu_idx = [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]
    yaochu = sum(counts[i] for i in yaochu_idx)
    if yaochu == 0:
        return [YakuLead("탕야오", STATUS_CONFIRMED, "야오추패 없음 — 그대로 진행")]
    if yaochu <= 2:
        return [
            YakuLead("탕야오", STATUS_POSSIBLE,
                     f"야오추패 {yaochu}장만 정리하면 성립")
        ]
    return []


def _check_yakuhai(counts: list[int], state: GameState) -> list[YakuLead]:
    """역패 — 삼원패·자풍·장풍의 또이쯔/커쯔."""
    leads: list[YakuLead] = []
    targets: list[tuple[int, str]] = [(i, "삼원패") for i in _DRAGON_INDICES]
    targets.append((_WIND_INDEX[state.round.seat_wind], "자풍"))
    targets.append((_WIND_INDEX[state.round.round_wind], "장풍"))

    seen: set[int] = set()
    for idx, label in targets:
        if idx in seen:
            continue
        seen.add(idx)
        c = counts[idx]
        tile = Tile.from_index34(idx)
        if c >= 3:
            leads.append(
                YakuLead(f"역패({label})", STATUS_CONFIRMED, f"{tile} 커쯔 완성")
            )
        elif c == 2:
            leads.append(
                YakuLead(f"역패({label})", STATUS_POSSIBLE,
                         f"{tile} 또이쯔 — 1장 더 모으면 성립")
            )
    return leads


def _check_flush(
    tiles: list[Tile], counts: list[int], state: GameState
) -> list[YakuLead]:
    """혼일색 / 청일색 — 수패가 한 종류에 몰렸는지."""
    suit_count = {"m": 0, "p": 0, "s": 0}
    honor_count = 0
    for t in tiles:
        if t.suit == "z":
            honor_count += 1
        else:
            suit_count[t.suit] += 1

    used_suits = [s for s, n in suit_count.items() if n > 0]
    total = len(tiles)

    if len(used_suits) == 1:
        suit = used_suits[0]
        if honor_count == 0:
            return [YakuLead("청일색", STATUS_TREND if total < 11
                             else STATUS_POSSIBLE,
                             f"{suit} 단일 색 — 자패도 없음")]
        return [YakuLead("혼일색", STATUS_TREND if total < 11
                         else STATUS_POSSIBLE,
                         f"{suit} + 자패 구성")]
    if len(used_suits) == 2:
        # 한 색이 압도적이면 혼일색 경향
        dominant = max(suit_count.values())
        if dominant >= total - honor_count - 3:
            return [YakuLead("혼일색", STATUS_TREND,
                             "한 색으로 모으는 중 — 다른 색 정리 시 성립 가능")]
    return []


def _check_chiitoitsu(counts: list[int], state: GameState) -> list[YakuLead]:
    """치또이쯔 — 멘젠 + 또이쯔가 많을 때."""
    if not state.is_menzen:
        return []
    pairs = sum(1 for c in counts if c >= 2)
    if pairs >= 5:
        return [YakuLead("치또이쯔", STATUS_POSSIBLE, f"또이쯔 {pairs}개")]
    if pairs == 4:
        return [YakuLead("치또이쯔", STATUS_TREND, f"또이쯔 {pairs}개")]
    return []


def _check_toitoi(counts: list[int], state: GameState) -> list[YakuLead]:
    """또이또이 — 커쯔/또이쯔 위주, 부로가 모두 폰일 때."""
    triplets = sum(1 for c in counts if c >= 3)
    pairs = sum(1 for c in counts if c == 2)
    melds_all_pon = all(
        m.meld_type in (MeldType.PON, MeldType.KAN, MeldType.ANKAN,
                        MeldType.SHOUMINKAN)
        for m in state.my_melds
    )
    open_pons = len(state.my_melds)
    effective_sets = triplets + open_pons
    if melds_all_pon and effective_sets >= 2 and pairs >= 1:
        status = STATUS_POSSIBLE if effective_sets + pairs >= 4 else STATUS_TREND
        return [YakuLead("또이또이", status,
                         f"커쯔/폰 {effective_sets}개 + 또이쯔 {pairs}개")]
    return []


def _check_pinfu(counts: list[int], state: GameState) -> list[YakuLead]:
    """핑후 — 멘젠 + 커쯔 없음 (순쯔 위주). 거친 경향 판단."""
    if not state.is_menzen or state.my_melds:
        return []
    triplets = sum(1 for c in counts if c >= 3)
    if triplets == 0:
        return [YakuLead("핑후", STATUS_TREND,
                         "커쯔 없는 순쯔 손 — 양면 대기로 마무리 시 성립")]
    return []
