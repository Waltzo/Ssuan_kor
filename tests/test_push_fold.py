"""오시히키 판단 테스트."""

from __future__ import annotations

from src.core.game_state import Discard, GameState, Seat, Tile
from src.analysis.push_fold import Stance, evaluate_push_fold
from src.analysis.tiles import parse_hand


def test_push_when_no_threat():
    state = GameState(my_hand=parse_hand("123456789m1234p"))
    advice = evaluate_push_fold(state)
    assert advice.stance == Stance.PUSH
    assert advice.danger_report.has_threat is False


def test_fold_when_far_from_tenpai_against_riichi():
    # 다샹텐 + 하가 리치 → 접기
    state = GameState(
        my_hand=parse_hand("2468m1357p2468s1z"),  # 13장, 분산된 패
        discards={Seat.SHIMOCHA: ()},
        riichi={Seat.SHIMOCHA: True},
    )
    advice = evaluate_push_fold(state)
    assert advice.stance == Stance.FOLD
    assert advice.score < 0


def test_push_when_tenpai_high_value_vs_one_riichi():
    # 멘젠 탕야오+핑후+도라2 텐파이 vs 리치 1명 → push
    state = GameState(
        my_hand=parse_hand("234m23455p23456s"),  # 13장, 56s ryanmen → 4s/7s 대기
        discards={Seat.SHIMOCHA: ()},
        riichi={Seat.SHIMOCHA: True},
        dora_indicators=(Tile("m", 1), Tile("p", 1)),  # 2m, 2p 도라
    )
    advice = evaluate_push_fold(state)
    # 텐파이 +40, 타점 7000점급 +7, 리치 −25 → score ≥ 20 → push
    assert advice.stance == Stance.PUSH
    assert advice.score >= 20


def test_fold_when_two_riichis_against_mid_shanten():
    # 2샹텐 + 리치 2명 → 접기
    state = GameState(
        my_hand=parse_hand("1357m2468p258s11z"),  # 13장, 분산
        discards={Seat.SHIMOCHA: (), Seat.TOIMEN: ()},
        riichi={Seat.SHIMOCHA: True, Seat.TOIMEN: True},
    )
    advice = evaluate_push_fold(state)
    # 다샹텐 -10이상, 리치 2명 -50 → fold
    assert advice.stance == Stance.FOLD


def test_safest_discard_is_provided_when_threat():
    # 5m을 손에 보유, 하가가 5m 현물 → 베타오리 시 5m 1순위
    state = GameState(
        my_hand=parse_hand("5m7m9m123p123p123s1z"),  # 13장
        discards={Seat.SHIMOCHA: (Discard(tile=Tile("m", 5), turn=2),)},
        riichi={Seat.SHIMOCHA: True},
    )
    advice = evaluate_push_fold(state)
    assert advice.safest_discard == Tile("m", 5)
