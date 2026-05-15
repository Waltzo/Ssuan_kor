"""위험패 분석 — 상대 리치/텐파이에 대한 내 손패 각 패의 안전도.

판정 카테고리 (안전 → 위험 순):
    GENBUTSU      현물 — 그 상대 버림패에 있음, 론 100% 안전
    HONOR_SAFE    字牌 3장 이상 보임 — 단기만 가능
    SUJI_MIDDLE   중스지 — 양쪽 ryanmen 모두 끊김
    NO_CHANCE     노찬스 — 양면 자체 불가능 (벽 분석)
    SUJI_HALF     편스지 — 한쪽 ryanmen만 끊김
    HONOR_2VISI   字牌 2장 보임 — 쌍퐁/단기만
    ONE_CHANCE    원찬스 — 한쪽 ryanmen 거의 불가능
    HONOR_1VISI   字牌 1장 보임 — 양면 외 모든 형태 가능
    UNSAFE_EDGE   끝 수패 무스지 (1·9·2·8 무스지)
    UNSAFE_MID    중장 수패 무스지 (3~7 무스지) — 가장 위험
    DORA_RISK     도라 — 위험도 가중

스지·노찬스는 ryanmen 대기에만 유효. 단기·간짱·변짱·쌍퐁에는 무력.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.game_state import Discard, GameState, Seat, Tile
from src.analysis.tiles import count_visible


class DangerCategory(Enum):
    GENBUTSU = "현물"
    HONOR_SAFE = "字牌안전"          # 3+ 보임
    SUJI_MIDDLE = "중스지"
    NO_CHANCE = "노찬스"
    SUJI_HALF = "편스지"
    HONOR_2VISI = "字牌2장"
    ONE_CHANCE = "원찬스"
    HONOR_1VISI = "字牌1장"
    UNSAFE_EDGE = "끝패무스지"
    UNSAFE_MID = "중장무스지"
    DORA_RISK = "도라위험"


# 카테고리 → 기본 위험도 점수 (0=안전, 100=최악)
_BASE_SCORE: dict[DangerCategory, int] = {
    DangerCategory.GENBUTSU: 0,
    DangerCategory.HONOR_SAFE: 5,
    DangerCategory.SUJI_MIDDLE: 15,
    DangerCategory.NO_CHANCE: 20,
    DangerCategory.SUJI_HALF: 30,
    DangerCategory.HONOR_2VISI: 25,
    DangerCategory.ONE_CHANCE: 40,
    DangerCategory.HONOR_1VISI: 55,
    DangerCategory.UNSAFE_EDGE: 60,
    DangerCategory.UNSAFE_MID: 75,
    DangerCategory.DORA_RISK: 90,
}


@dataclass(frozen=True)
class TileDanger:
    """한 패에 대한 한 상대 기준 위험도."""

    tile: Tile
    category: DangerCategory
    score: int                 # 0~100
    reasons: tuple[str, ...]   # 인간 친화 설명


@dataclass(frozen=True)
class OpponentDanger:
    """한 상대에 대한 위험도 보고."""

    seat: Seat
    trigger: str               # "riichi" | "tenpai_assumed" | "manual"
    tile_danger: tuple[TileDanger, ...]   # 내 손패 각 패


@dataclass(frozen=True)
class DangerReport:
    """전체 위험 분석 결과."""

    per_opponent: tuple[OpponentDanger, ...]
    safest_order: tuple[Tile, ...]   # 베타오리 시 버릴 순서 (가장 안전한 패부터)

    @property
    def has_threat(self) -> bool:
        return len(self.per_opponent) > 0


# --- 카테고리 판정 헬퍼 --------------------------------------------------

def _is_genbutsu(opp_discards: tuple[Discard, ...], idx34: int) -> bool:
    return any(d.tile.index34 == idx34 for d in opp_discards)


def _suji_status(
    opp_discards: tuple[Discard, ...], tile: Tile
) -> DangerCategory | None:
    """수패 ryanmen 스지 판정.

    중스지: 양쪽 X-3, X+3 모두 그 상대가 버림.
    편스지: 한쪽만 버림. 끝패는 한쪽 스지만 존재.
    """
    if tile.suit == "z":
        return None
    discarded = {
        d.tile.index34 for d in opp_discards if d.tile.suit == tile.suit
    }
    r = tile.rank
    base = tile.index34 - (r - 1)  # 해당 수트 1의 34-index

    has_lower = (r - 3) >= 1 and (base + (r - 3) - 1) in discarded
    has_upper = (r + 3) <= 9 and (base + (r + 3) - 1) in discarded

    # 끝패 (1, 2, 8, 9)는 한쪽 스지만 가능
    edge_only = r in (1, 2, 8, 9)

    if edge_only:
        # 1: ryanmen 23만 → suji X+3=4 필요
        # 2: ryanmen 34만 → suji X+3=5 필요
        # 8: ryanmen 67만 → suji X-3=5 필요
        # 9: ryanmen 78만 → suji X-3=6 필요
        if r in (1, 2) and has_upper:
            return DangerCategory.SUJI_HALF
        if r in (8, 9) and has_lower:
            return DangerCategory.SUJI_HALF
        return None

    # 중간 패 3~7: 양쪽 ryanmen 가능
    if has_lower and has_upper:
        return DangerCategory.SUJI_MIDDLE
    if has_lower or has_upper:
        return DangerCategory.SUJI_HALF
    return None


def _wall_status(state: GameState, tile: Tile) -> DangerCategory | None:
    """노찬스/원찬스 판정 — ryanmen 가능 여부.

    X에 ryanmen으로 들어오려면 (X-2, X-1) 또는 (X+1, X+2)가 상대 손에 있어야 함.
    각 ryanmen에 필요한 두 패 중 하나라도 4장 다 보이면 그 ryanmen 불가능.
    """
    if tile.suit == "z":
        return None
    r = tile.rank
    base = tile.index34 - (r - 1)

    def fully_visible(rank: int) -> bool:
        if not 1 <= rank <= 9:
            return True  # 존재 안 함 = 사용 불가 = "끊김"으로 취급
        return count_visible(state, base + rank - 1) >= 4

    # 두 ryanmen 후보
    lower_blocked = fully_visible(r - 2) or fully_visible(r - 1)
    upper_blocked = fully_visible(r + 1) or fully_visible(r + 2)

    # 끝패는 애초에 한쪽 ryanmen만 존재
    if r == 1:
        upper_blocked = upper_blocked  # 23 ryanmen만
        lower_blocked = True
    elif r == 2:
        lower_blocked = True           # 34 ryanmen만 (12 ryanmen은 없음)
    elif r == 8:
        upper_blocked = True           # 67 ryanmen만
    elif r == 9:
        upper_blocked = True
        lower_blocked = lower_blocked  # 78 ryanmen만

    if lower_blocked and upper_blocked:
        return DangerCategory.NO_CHANCE
    if lower_blocked or upper_blocked:
        return DangerCategory.ONE_CHANCE
    return None


def _honor_safety(state: GameState, tile: Tile) -> DangerCategory | None:
    """字牌의 보이는 매수로 안전도 판정."""
    if tile.suit != "z":
        return None
    visible = count_visible(state, tile.index34)
    # 자기 손에 있는 그 자패는 visible에 포함됨 — 매수 그대로 사용
    if visible >= 3:
        return DangerCategory.HONOR_SAFE
    if visible == 2:
        return DangerCategory.HONOR_2VISI
    return DangerCategory.HONOR_1VISI


def _is_dora(state: GameState, tile: Tile) -> bool:
    """도라 표시패 → 도라 판정. 아카는 별도(여기선 제외)."""
    return any(
        _next_tile_index(ind) == tile.index34 for ind in state.dora_indicators
    )


def _next_tile_index(indicator: Tile) -> int:
    """도라 표시패의 다음 패 34-index (도라 자체)."""
    idx = indicator.index34
    if idx <= 8:           # m: 1~9 cycle
        return idx + 1 if idx < 8 else 0
    if idx <= 17:          # p: 9~17
        return idx + 1 if idx < 17 else 9
    if idx <= 26:          # s: 18~26
        return idx + 1 if idx < 26 else 18
    if idx <= 30:          # 風: 27~30 (E,S,W,N) cyclic
        return idx + 1 if idx < 30 else 27
    return idx + 1 if idx < 33 else 31  # 三元: 31,32,33 cyclic


# --- 핵심 분석 ------------------------------------------------------------

def safety_against_opponent(
    state: GameState, seat: Seat, tile: Tile
) -> TileDanger:
    """한 패의 한 상대에 대한 위험도."""
    reasons: list[str] = []
    opp_discards = state.discards.get(seat, ())
    idx = tile.index34

    # 1. 현물
    if _is_genbutsu(opp_discards, idx):
        return TileDanger(
            tile=tile,
            category=DangerCategory.GENBUTSU,
            score=_BASE_SCORE[DangerCategory.GENBUTSU],
            reasons=("그 상대 버림패에 존재 (현물)",),
        )

    # 2. 字牌 안전도
    if tile.suit == "z":
        cat = _honor_safety(state, tile)
        if cat is None:
            cat = DangerCategory.HONOR_1VISI
        visible = count_visible(state, idx)
        reasons.append(f"보이는 매수 {visible}장")
        return TileDanger(
            tile=tile, category=cat, score=_BASE_SCORE[cat],
            reasons=tuple(reasons),
        )

    # 3. 수패 — 스지/노찬스 동시 평가, 더 안전한 쪽 선택
    suji = _suji_status(opp_discards, tile)
    wall = _wall_status(state, tile)

    if suji is not None:
        reasons.append(f"{suji.value}")
    if wall is not None:
        reasons.append(f"{wall.value} (벽)")

    # 안전한 카테고리 우선 (점수 낮은 것)
    candidates = [c for c in (suji, wall) if c is not None]
    if candidates:
        best = min(candidates, key=lambda c: _BASE_SCORE[c])
        score = _BASE_SCORE[best]
    else:
        # 무스지
        if tile.rank in (1, 9, 2, 8):
            best = DangerCategory.UNSAFE_EDGE
        else:
            best = DangerCategory.UNSAFE_MID
        score = _BASE_SCORE[best]
        reasons.append("무스지")

    # 도라 가중 — 무스지/원찬스급 위험이면 카테고리도 도라위험으로 승격
    if _is_dora(state, tile):
        reasons.append("도라")
        if score >= _BASE_SCORE[DangerCategory.ONE_CHANCE]:
            best = DangerCategory.DORA_RISK
            score = _BASE_SCORE[DangerCategory.DORA_RISK]
        else:
            score = max(score, _BASE_SCORE[best] + 10)

    return TileDanger(
        tile=tile, category=best, score=score, reasons=tuple(reasons),
    )


def analyze_danger(
    state: GameState,
    assume_tenpai: frozenset[Seat] = frozenset(),
) -> DangerReport:
    """리치한 상대 + 수동 지정한 텐파이 의심 상대에 대해 위험도 분석.

    assume_tenpai로 부로 많은 상대 등을 수동 추가 가능.
    """
    threat_seats: list[tuple[Seat, str]] = []
    for seat, riichi in state.riichi.items():
        if riichi and seat != Seat.SELF:
            threat_seats.append((seat, "riichi"))
    for seat in assume_tenpai:
        if seat != Seat.SELF and not state.riichi.get(seat, False):
            threat_seats.append((seat, "tenpai_assumed"))

    if not threat_seats:
        return DangerReport(per_opponent=(), safest_order=())

    per_opp: list[OpponentDanger] = []
    for seat, trigger in threat_seats:
        tile_dangers = tuple(
            safety_against_opponent(state, seat, t)
            for t in state.my_hand
        )
        per_opp.append(OpponentDanger(
            seat=seat, trigger=trigger, tile_danger=tile_dangers,
        ))

    # 베타오리 순서: 모든 위험 상대 기준 최대 위험도가 낮은 패부터
    # (최악의 상대에 대해서도 안전한 패 우선)
    tiles_seen: set[tuple[str, int, bool]] = set()
    aggregated: list[tuple[int, Tile]] = []
    for tile in state.my_hand:
        key = (tile.suit, tile.rank, tile.is_aka)
        if key in tiles_seen:
            continue
        tiles_seen.add(key)
        max_score = max(
            (td.score for opp in per_opp for td in opp.tile_danger
             if td.tile == tile),
            default=100,
        )
        aggregated.append((max_score, tile))
    aggregated.sort(key=lambda x: x[0])
    safest = tuple(t for _, t in aggregated)

    return DangerReport(per_opponent=tuple(per_opp), safest_order=safest)
