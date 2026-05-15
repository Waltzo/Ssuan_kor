"""위험패 분석 테스트."""

from __future__ import annotations

from src.core.game_state import Discard, GameState, Seat, Tile
from src.analysis.danger import (
    DangerCategory,
    analyze_danger,
    safety_against_opponent,
)
from src.analysis.tiles import parse_hand


def _opp_state(opp_discard_str: str, my_hand_str: str = "1m",
               riichi_seats=(Seat.SHIMOCHA,), **kw) -> GameState:
    """하가(SHIMOCHA)가 리치한 상황 + 그 사람 버림패 셋업."""
    discards = tuple(
        Discard(tile=t, turn=i + 1)
        for i, t in enumerate(parse_hand(opp_discard_str))
    )
    return GameState(
        my_hand=parse_hand(my_hand_str),
        discards={Seat.SHIMOCHA: discards},
        riichi={s: True for s in riichi_seats},
        **kw,
    )


# --- 단일 패 안전도 -------------------------------------------------------

def test_genbutsu():
    # 하가가 5m을 버렸음 → 5m은 현물
    state = _opp_state("5m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 5))
    assert td.category == DangerCategory.GENBUTSU
    assert td.score == 0


def test_suji_middle_when_both_ends_discarded():
    # 2m, 8m 모두 버림 → 5m은 중스지
    state = _opp_state("2m8m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 5))
    assert td.category == DangerCategory.SUJI_MIDDLE


def test_suji_half_when_one_end_discarded():
    # 2m만 버림 → 5m은 편스지
    state = _opp_state("2m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 5))
    assert td.category == DangerCategory.SUJI_HALF


def test_suji_edge_tile():
    # 4m 버림 → 1m은 편스지 (23 ryanmen 끊김)
    state = _opp_state("4m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 1))
    assert td.category == DangerCategory.SUJI_HALF


def test_no_chance_wall_blocks_both_ryanmen():
    # 5m을 노릴 ryanmen은 (3m,4m) 또는 (6m,7m)
    # 4m 4장 + 6m 4장 보이게 하면 양쪽 모두 ryanmen 불가 → 노찬스
    state = GameState(
        my_hand=parse_hand("4444m6666m") + (Tile("p", 1),),
        discards={Seat.SHIMOCHA: ()},
        riichi={Seat.SHIMOCHA: True},
    )
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 5))
    assert td.category == DangerCategory.NO_CHANCE


def test_honor_safe_when_3_visible():
    # 백패(5z) 3장 내 손에 보유 → 字牌안전
    state = _opp_state("1m", my_hand_str="555z2m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("z", 5))
    assert td.category == DangerCategory.HONOR_SAFE


def test_honor_2_visible():
    state = _opp_state("1m", my_hand_str="55z2m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("z", 5))
    assert td.category == DangerCategory.HONOR_2VISI


def test_unsafe_mid_no_suji():
    # 아무 단서 없는 5m — 무스지 중장패
    state = _opp_state("1m")
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 5))
    assert td.category == DangerCategory.UNSAFE_MID
    assert td.score >= 70


def test_dora_overrides_to_high_score():
    # 도라표시 4m → 5m이 도라. 무스지 5m은 도라위험까지 가중
    state = GameState(
        my_hand=parse_hand("5m"),
        discards={Seat.SHIMOCHA: (Discard(tile=Tile("m", 1), turn=1),)},
        riichi={Seat.SHIMOCHA: True},
        dora_indicators=(Tile("m", 4),),
    )
    td = safety_against_opponent(state, Seat.SHIMOCHA, Tile("m", 5))
    assert td.category == DangerCategory.DORA_RISK
    assert td.score >= 90


# --- 종합 보고 ------------------------------------------------------------

def test_no_threat_when_no_riichi():
    state = GameState(my_hand=parse_hand("123m"))
    rep = analyze_danger(state)
    assert not rep.has_threat
    assert rep.per_opponent == ()


def test_safest_order_puts_genbutsu_first():
    # 하가 리치, 5m 버림 (5m 현물). 손에 5m + 무스지 7m
    state = GameState(
        my_hand=parse_hand("5m7m"),
        discards={Seat.SHIMOCHA: (Discard(tile=Tile("m", 5), turn=3),)},
        riichi={Seat.SHIMOCHA: True},
    )
    rep = analyze_danger(state)
    assert rep.has_threat
    # 5m이 가장 안전 — 첫 번째여야 함
    assert rep.safest_order[0] == Tile("m", 5)


def test_assume_tenpai_triggers_analysis():
    # 리치 없어도 수동으로 텐파이 의심 지정
    state = GameState(
        my_hand=parse_hand("5m"),
        discards={Seat.TOIMEN: (Discard(tile=Tile("m", 5), turn=2),)},
    )
    rep = analyze_danger(state, assume_tenpai=frozenset({Seat.TOIMEN}))
    assert rep.has_threat
    assert rep.per_opponent[0].trigger == "tenpai_assumed"
    assert rep.per_opponent[0].tile_danger[0].category == DangerCategory.GENBUTSU
