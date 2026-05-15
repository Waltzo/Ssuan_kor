"""상대 역 예측 — 버림패·부로 패턴으로 노리는 역의 경향 추정.

본질적으로 "확정"이 아닌 "경향" 추정. 보조지표로만 사용 권장.
사용 신호:
  - 초반 야오추 정리 → 탕야오
  - 한두 수트 다량 정리 → 혼/청일색 (남는 수트 노림)
  - 役패 폰/깡 → 役패 확정
  - 폰 다수 + 같은 수트 슌쯔성 정리 → 또이또이 경향
  - 리치 선언 → 확정
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.game_state import Discard, GameState, Meld, MeldType, Seat, Tile
from src.analysis.yaku_suggest import (
    STATUS_CONFIRMED,
    STATUS_POSSIBLE,
    STATUS_TREND,
    YakuLead,
)


@dataclass(frozen=True)
class OpponentYakuPrediction:
    """한 상대의 역 경향 예측."""

    seat: Seat
    is_riichi: bool
    likely_yaku: tuple[YakuLead, ...]
    discard_summary: str           # "초반 야오추 4/6, m수트 편중" 같은 한 줄 요약


def _early_yaochu_trend(discards: tuple[Discard, ...]) -> tuple[int, int]:
    """초반 6순까지 (야오추 매수, 전체 매수) 반환."""
    early = [d for d in discards if d.turn <= 6]
    yaochu = sum(1 for d in early if d.tile.is_terminal_or_honor)
    return yaochu, len(early)


def _suit_distribution(
    discards: tuple[Discard, ...]
) -> dict[str, int]:
    counts = {"m": 0, "p": 0, "s": 0, "z": 0}
    for d in discards:
        counts[d.tile.suit] += 1
    return counts


def _meld_signals(melds: tuple[Meld, ...]) -> dict[str, int]:
    """부로 통계 — 폰 수, 자패 폰 여부 등."""
    pon_or_kan = 0
    honor_pon: list[Tile] = []
    chi_count = 0
    for m in melds:
        if m.meld_type == MeldType.CHI:
            chi_count += 1
        elif m.meld_type in (MeldType.PON, MeldType.KAN, MeldType.SHOUMINKAN):
            pon_or_kan += 1
            if m.tiles and m.tiles[0].suit == "z":
                honor_pon.append(m.tiles[0])
    return {
        "pon_or_kan": pon_or_kan,
        "chi": chi_count,
        "honor_pons": honor_pon,
    }


def predict_opponent_yaku(
    state: GameState, seat: Seat
) -> OpponentYakuPrediction:
    """한 상대의 역 경향 예측."""
    discards = state.discards.get(seat, ())
    melds = state.melds.get(seat, ())
    is_riichi = state.riichi.get(seat, False)

    leads: list[YakuLead] = []
    summary_parts: list[str] = []

    if is_riichi:
        leads.append(YakuLead("리치", STATUS_CONFIRMED, "리치 선언패 존재"))

    # 1. 役패 폰 — 확정
    sig = _meld_signals(melds)
    for tile in sig["honor_pons"]:
        idx = tile.index34
        if idx >= 31:
            leads.append(
                YakuLead(f"역패({tile})", STATUS_CONFIRMED, "삼원패 폰/깡")
            )
        elif idx in (
            27 + state.round.seat_wind.value - 1
            if seat == Seat.SELF else None,
        ):
            # 그 자리의 자풍 알기 어려움 — 보수적으로 패스
            pass

    # 2. 탕야오 경향
    yaochu_n, early_n = _early_yaochu_trend(discards)
    if early_n >= 4 and yaochu_n >= 3:
        status = STATUS_POSSIBLE if yaochu_n >= 4 else STATUS_TREND
        leads.append(
            YakuLead(
                "탕야오",
                status,
                f"초반 야오추 {yaochu_n}/{early_n}장 정리",
            )
        )
        summary_parts.append(f"야오추 정리 {yaochu_n}/{early_n}")

    # 3. 혼/청일색 경향
    suit_dist = _suit_distribution(discards)
    total = len(discards)
    if total >= 8:
        sorted_suits = sorted(
            suit_dist.items(), key=lambda x: -x[1]
        )
        # 가장 많이 버린 수트 두 개가 전체의 70% 이상이면, 남은 수트(또는 자패) 노릴 가능성
        top_two = sorted_suits[0][1] + sorted_suits[1][1]
        if top_two >= total * 0.7:
            discarded_suits = {sorted_suits[0][0], sorted_suits[1][0]}
            kept = [s for s in ("m", "p", "s") if s not in discarded_suits]
            if kept:
                status = STATUS_TREND if total < 12 else STATUS_POSSIBLE
                leads.append(
                    YakuLead(
                        f"혼/청일색({kept[0]})",
                        status,
                        f"{kept[0]} 외 정리 — {dict(sorted_suits)}",
                    )
                )
                summary_parts.append(f"{kept[0]} 수트 보존")

    # 4. 또이또이 경향
    if sig["pon_or_kan"] >= 2 and sig["chi"] == 0:
        leads.append(
            YakuLead(
                "또이또이",
                STATUS_TREND,
                f"폰/깡 {sig['pon_or_kan']}개, 치 없음",
            )
        )
        summary_parts.append(f"폰 {sig['pon_or_kan']}개")

    # 5. 빠른 페이스 — 텐파이 의심 (요약 표시)
    if not is_riichi and len(discards) >= 8:
        # 단순 휴리스틱: 부로 ≥ 2 이거나 야오추 정리 빠를 때
        if sig["pon_or_kan"] + sig["chi"] >= 2:
            summary_parts.append("부로 多 — 텐파이 의심")

    summary = " / ".join(summary_parts) if summary_parts else "특이 패턴 없음"

    return OpponentYakuPrediction(
        seat=seat,
        is_riichi=is_riichi,
        likely_yaku=tuple(leads),
        discard_summary=summary,
    )


def predict_all_opponents(state: GameState) -> tuple[OpponentYakuPrediction, ...]:
    """SHIMOCHA / TOIMEN / KAMICHA 모두에 대해 예측."""
    return tuple(
        predict_opponent_yaku(state, seat)
        for seat in (Seat.SHIMOCHA, Seat.TOIMEN, Seat.KAMICHA)
    )
