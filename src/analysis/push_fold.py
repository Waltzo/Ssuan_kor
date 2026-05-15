"""오시히키(押し引き) 판단 — 내 패 가치 vs 상대 위협 → 밀기/접기 결론.

휴리스틱 기반. 진짜 EV 계산은 데이터 기반 학습 모델(NAGA·Mortal 등)이 필요하지만,
실전에서 쓸 만한 1차 판단을 제공한다.

판정 입력:
  - 내 샹텐 / 텐파이 시 타점 / 우케이레 폭
  - 상대 위협: 리치 수, 텐파이 의심 수
  - 손에 안전패가 있는지 (베타오리 가능성)
  - 순목 (늦으면 추격 어려움)

출력: PUSH / NEUTRAL / FOLD + 점수 + 이유 + 베타오리 시 추천 타패.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.core.game_state import GameState, Seat, Tile
from src.analysis.shanten import calculate_shanten
from src.analysis.tenpai import tenpai_for_hand
from src.analysis.value import best_value_among_waits
from src.analysis.danger import DangerReport, analyze_danger


class Stance(Enum):
    PUSH = "밀기 (押し)"
    NEUTRAL = "중립 — 상황 보고 결정"
    FOLD = "접기 (ベタオリ)"


@dataclass(frozen=True)
class PushFoldAdvice:
    """오시히키 판단 결과."""

    stance: Stance
    score: int                       # +이면 push 쪽, −이면 fold 쪽
    reasons: tuple[str, ...]         # 점수 기여 항목
    safest_discard: Tile | None      # 베타오리 시 추천 타패
    danger_report: DangerReport      # 참조용


def evaluate_push_fold(
    state: GameState,
    assume_tenpai: frozenset[Seat] = frozenset(),
) -> PushFoldAdvice:
    """오시히키 판단."""
    report = analyze_danger(state, assume_tenpai=assume_tenpai)

    # 위협 없음 → 무조건 push
    if not report.has_threat:
        return PushFoldAdvice(
            stance=Stance.PUSH,
            score=999,
            reasons=("위협 없음 — 자유롭게 밀기",),
            safest_discard=None,
            danger_report=report,
        )

    score = 0
    reasons: list[str] = []

    # 1. 내 샹텐 기여
    sh = calculate_shanten(state.my_hand, state.my_melds).value
    is_tenpai_self = sh == 0
    if sh == -1:
        score += 100
        reasons.append("내 손 화료형 (+100)")
    elif sh == 0:
        score += 40
        reasons.append("내 텐파이 (+40)")
    elif sh == 1:
        score += 10
        reasons.append("1샹텐 (+10)")
    elif sh == 2:
        score -= 10
        reasons.append("2샹텐 (−10)")
    else:
        score -= 30
        reasons.append(f"{sh}샹텐 — 화료 멀음 (−30)")

    # 2. 텐파이라면 타점 기여 (1000점당 +1, 최대 +30)
    if is_tenpai_self and len(state.my_hand) % 3 == 1:
        info = tenpai_for_hand(
            state.my_hand, state.my_melds, state, state.round,
            frozenset(d.tile.index34 for d in state.my_discards),
        )
        valid_waits = tuple(w.tile for w in info.waits if not w.is_yakuless)
        if valid_waits:
            v = best_value_among_waits(
                state.my_hand, valid_waits, state.my_melds,
                state.dora_indicators, state.round,
            )
            if v and v.valid:
                bonus = min(30, v.points // 1000)
                score += bonus
                reasons.append(f"타점 {v.points}점 (+{bonus})")

    # 3. 위협 비용
    riichi_n = sum(1 for opp in report.per_opponent if opp.trigger == "riichi")
    assumed_n = sum(
        1 for opp in report.per_opponent if opp.trigger == "tenpai_assumed"
    )
    if riichi_n:
        cost = 25 * riichi_n
        score -= cost
        reasons.append(f"리치 상대 {riichi_n}명 (−{cost})")
    if assumed_n:
        cost = 15 * assumed_n
        score -= cost
        reasons.append(f"텐파이 의심 {assumed_n}명 (−{cost})")

    # 4. 안전패 보유 여부 (대안 타패 평가)
    safe_count = 0
    if report.safest_order:
        # 카테고리상 안전한 패 수
        safest_tiles_set = {
            t for opp in report.per_opponent for td in opp.tile_danger
            if td.score <= 20
            for t in (td.tile,)
        }
        safe_count = len(safest_tiles_set)
        if safe_count >= 2:
            score += 5
            reasons.append(f"안전패 {safe_count}장 보유 (+5) — 부분 후퇴 여유")

    # 5. 순목 — 늦으면 추격 더 어려움
    if state.turn >= 12 and not is_tenpai_self:
        score -= 10
        reasons.append("종반 순목, 미텐파이 (−10)")

    # 결정
    if score >= 20:
        stance = Stance.PUSH
    elif score <= -20:
        stance = Stance.FOLD
    else:
        stance = Stance.NEUTRAL

    safest = report.safest_order[0] if report.safest_order else None
    return PushFoldAdvice(
        stance=stance,
        score=score,
        reasons=tuple(reasons),
        safest_discard=safest,
        danger_report=report,
    )
