"""리치 판단 — 리치 / 다마텐 / 비추천 결정.

판단 입력: 멘젠 여부, 텐파이, 대기 질, 타점(다마 vs 리치), 순목,
점수, 후리텐, 상대 위협.

리치 표준 격언:
  - 役なし 텐파이는 리치 안 치면 론 불가 → 리치 권고
  - 이미 타점 충분(만관+)이면 다마 → 1000점 절약, 견제 회피
  - 양면 대기 + 이른 순목 → 리치 가치 큼
  - 종반(15순목+) + 안 좋은 대기 → 비추천
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.game_state import GameState, MeldType, Seat
from src.analysis.tenpai import tenpai_for_hand
from src.analysis.value import best_value_among_waits


class RiichiAction(Enum):
    RIICHI = "리치 (リーチ)"
    DAMA = "다마텐 (黙聴)"
    NO_BET = "리치 불가 / 비추천"


@dataclass(frozen=True)
class RiichiAdvice:
    """리치 판단 결과."""

    action: RiichiAction
    score: int                  # +면 리치 쪽
    reasons: tuple[str, ...]
    dama_points: int            # 다마텐 화료 시 추정 타점 (役なし이면 0)
    riichi_points: int          # 리치 화료 시 추정 타점


def evaluate_riichi(
    state: GameState,
    my_score: int = 25000,
) -> RiichiAdvice:
    """리치 가/부 + 권장 여부 판단."""
    # --- 전제 조건 (불가 사유 우선 처리) ---
    is_menzen = all(m.meld_type == MeldType.ANKAN for m in state.my_melds)
    if not is_menzen:
        return RiichiAdvice(
            RiichiAction.NO_BET, 0,
            ("멘젠이 아님 — 리치 불가 (안깡 외 부로 있음)",), 0, 0,
        )
    if my_score < 1000:
        return RiichiAdvice(
            RiichiAction.NO_BET, 0,
            (f"점수 {my_score} < 1000 — 리치봉 부족",), 0, 0,
        )
    if state.tiles_left < 4:
        return RiichiAdvice(
            RiichiAction.NO_BET, 0,
            (f"남은 산 {state.tiles_left}장 < 4 — 리치 선언 불가",), 0, 0,
        )
    if len(state.my_hand) % 3 != 1:
        return RiichiAdvice(
            RiichiAction.NO_BET, 0,
            ("손패가 대기 중 형태(13·10·7장)가 아님",), 0, 0,
        )

    info = tenpai_for_hand(
        state.my_hand, state.my_melds, state, state.round,
        frozenset(d.tile.index34 for d in state.my_discards),
    )
    if not info.is_tenpai:
        return RiichiAdvice(
            RiichiAction.NO_BET, 0,
            ("텐파이가 아님",), 0, 0,
        )

    # --- 타점 계산 (다마 vs 리치) ---
    valid_waits = tuple(w.tile for w in info.waits if not w.is_yakuless)
    all_waits = tuple(w.tile for w in info.waits)
    dama_pts = 0
    if valid_waits:
        v = best_value_among_waits(
            state.my_hand, valid_waits, state.my_melds,
            state.dora_indicators, state.round,
        )
        if v and v.valid:
            dama_pts = v.points
    riichi_pts = 0
    if all_waits:
        v = best_value_among_waits(
            state.my_hand, all_waits, state.my_melds,
            state.dora_indicators, state.round,
            is_riichi=True,
        )
        if v and v.valid:
            riichi_pts = v.points

    # --- 점수화 ---
    score = 0
    reasons: list[str] = []

    # 役なし → 리치 강제 권고
    if info.all_waits_yakuless:
        score += 50
        reasons.append("役なし — 리치 없으면 론 불가 (+50)")

    # 대기 질·매수
    waits_total = info.waits_total
    waits_types = len(info.waits)
    if waits_total >= 6:
        score += 15
        reasons.append(f"대기 풍부 {waits_total}매 (+15)")
    elif waits_total >= 3:
        score += 5
        reasons.append(f"대기 보통 {waits_total}매 (+5)")
    else:
        score -= 15
        reasons.append(f"대기 빈약 {waits_total}매 (−15)")
    if waits_types >= 2:
        score += 5
        reasons.append(f"대기 종류 {waits_types}종 (+5)")

    # 타점 트레이드오프
    if dama_pts >= 8000:
        score -= 15
        reasons.append(f"다마텐 이미 {dama_pts}점 — 리치 가치 ↓ (−15)")
    elif dama_pts >= 5200:
        score += 0
    elif dama_pts > 0:
        score += 10
        reasons.append(f"다마텐 {dama_pts}점 — 리치로 점프 큼 (+10)")
    # dama_pts == 0 인 경우는 役なし으로 위에서 처리

    # 순목
    turn = state.turn
    if turn <= 6:
        score += 15
        reasons.append(f"이른 순목 {turn} (+15)")
    elif turn <= 10:
        score += 5
        reasons.append(f"중반 순목 {turn} (+5)")
    elif turn <= 14:
        score -= 10
        reasons.append(f"후반 순목 {turn} (−10)")
    else:
        score -= 25
        reasons.append(f"종반 순목 {turn} — 화료 시간 부족 (−25)")

    # 후리텐 — 쯔모만 가능, 리치 효과 절반
    if info.is_furiten:
        score -= 15
        reasons.append("후리텐 — 쯔모만 가능 (−15)")

    # 상대 리치 위협 — 리치는 손패 고정, 추격 어려워짐
    threats = sum(
        1 for s, r in state.riichi.items() if r and s != Seat.SELF
    )
    if threats:
        cost = 15 * threats
        score -= cost
        reasons.append(f"상대 리치 {threats}명 (−{cost})")

    # --- 결정 ---
    if score >= 25:
        action = RiichiAction.RIICHI
    elif score >= -10:
        # 中立 — 다마 추천 (역 있을 때만)
        action = RiichiAction.DAMA if dama_pts > 0 else RiichiAction.RIICHI
    else:
        # 부정적 — 다마 가능하면 다마, 役なし이면 어쩔 수 없이 리치/포기
        action = RiichiAction.DAMA if dama_pts > 0 else RiichiAction.NO_BET

    return RiichiAdvice(
        action=action,
        score=score,
        reasons=tuple(reasons),
        dama_points=dama_pts,
        riichi_points=riichi_pts,
    )
