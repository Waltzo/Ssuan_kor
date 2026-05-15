"""분석 엔진 단위 테스트 — OS·캡처 무관, Linux에서 전부 검증 가능.

    python -m pytest tests/ -v
"""

from __future__ import annotations

from src.core.game_state import Discard, GameState, RoundInfo, Seat, Tile, Wind
from src.analysis.shanten import calculate_shanten
from src.analysis.efficiency import best_discard, recommend_discards, ukeire_for_hand
from src.analysis.tenpai import analyze_tenpai, tenpai_for_hand
from src.analysis.tiles import count_visible, parse_hand, wall_remaining


# --- Tile -----------------------------------------------------------------

def test_tile_parse_basic():
    assert Tile.parse("5m") == Tile("m", 5)
    assert Tile.parse("1z") == Tile("z", 1)
    assert Tile.parse("9s") == Tile("s", 9)


def test_tile_parse_aka():
    aka = Tile.parse("0p")
    assert aka.rank == 5 and aka.suit == "p" and aka.is_aka


def test_tile_index34_roundtrip():
    for idx in range(34):
        assert Tile.from_index34(idx).index34 == idx


def test_tile_classification():
    assert Tile.parse("1m").is_terminal
    assert Tile.parse("5z").is_honor
    assert Tile.parse("1m").is_terminal_or_honor
    assert not Tile.parse("5m").is_terminal_or_honor


def test_parse_hand_count():
    hand = parse_hand("123m456p789s11z")
    assert len(hand) == 11
    assert hand[0] == Tile("m", 1)


# --- Shanten --------------------------------------------------------------

def test_shanten_complete_hand():
    # 123m 456m 789m 123p 99p — 완성형
    hand = parse_hand("123456789m12399p")
    assert calculate_shanten(hand).is_agari


def test_shanten_tenpai():
    # 123m 456m 789m 123p 9p — 9p 외 1장 대기? 실제론 9p 단기
    hand = parse_hand("123456789m1239p")
    assert calculate_shanten(hand).is_tenpai


def test_shanten_chiitoitsu_tenpai():
    # 6쌍 + 1장 — 치또이쯔 텐파이
    hand = parse_hand("1122334455667m")
    res = calculate_shanten(hand)
    assert res.is_tenpai
    assert res.chiitoitsu == 0


def test_shanten_kokushi_tenpai():
    # 13면 국사무쌍 텐파이
    hand = parse_hand("19m19p19s1234567z")
    res = calculate_shanten(hand)
    assert res.is_tenpai
    assert res.kokushi == 0


# --- Efficiency / 타패 추천 ------------------------------------------------

def _state_hand(hand_str: str, **kw) -> GameState:
    return GameState(my_hand=parse_hand(hand_str), **kw)


def test_recommend_discards_picks_tenpai():
    # 123456789m 12p 99p 5s (14장) — 5s 버리면 3p 대기 텐파이
    state = _state_hand("123456789m1299p5s")
    top = best_discard(state)
    assert top is not None
    assert top.discard == Tile("s", 5)
    assert top.shanten == 0
    # 3p가 우케이레에 포함
    assert Tile("p", 3) in {u.tile for u in top.ukeire}


def test_recommend_discards_requires_drawn_tile():
    # 13장(대기 중) 손패엔 타패 추천 불가
    state = _state_hand("123456789m1239p")
    try:
        recommend_discards(state)
    except ValueError:
        pass
    else:
        raise AssertionError("13장 손패에 ValueError 미발생")


def test_ukeire_counts_remaining():
    # 손에 3p 2장 보유 → 우케이레 매수에서 차감 (4 - 2 = 2)
    hand = parse_hand("123456789m1233p")  # 13장, 3p 2장 보유, 3p 단기 대기
    uk = {u.tile: u.count for u in ukeire_for_hand(hand)}
    assert Tile("p", 3) in uk
    assert uk[Tile("p", 3)] == 2


# --- Tenpai: 후리텐 / 役なし -----------------------------------------------

def test_tenpai_furiten_detected():
    # 5s 단기 대기인데 5s를 이미 버림 → 후리텐
    hand = parse_hand("234567m234567p5s")  # 5s 단기 대기 (탕야오)
    state = GameState(
        my_hand=hand,
        my_discards=(Discard(tile=Tile("s", 5), turn=3),),
    )
    info = analyze_tenpai(state)
    assert info.is_tenpai
    assert info.is_furiten
    assert not info.can_ron  # 후리텐이면 론 불가


def test_tenpai_not_furiten_when_clean():
    hand = parse_hand("234567m234567p5s")
    state = GameState(my_hand=hand)  # 버림패 없음
    info = analyze_tenpai(state)
    assert info.is_tenpai
    assert not info.is_furiten


def test_tenpai_yakuless_warning():
    # 234m 567m 234p 678p + 9s 단기 — 역 없음 (탕야오X, 핑후X)
    hand = parse_hand("234567m234678p9s")
    info = tenpai_for_hand(hand)
    assert info.is_tenpai
    assert info.all_waits_yakuless
    assert not info.has_any_yaku


def test_tenpai_has_yaku_tanyao():
    # 234m 567m 234p 567p + 5s 단기 — 전부 2~8 → 탕야오
    hand = parse_hand("234567m234567p5s")
    info = tenpai_for_hand(hand)
    assert info.is_tenpai
    assert info.has_any_yaku
    assert not info.all_waits_yakuless


def test_tenpai_can_riichi_when_menzen():
    hand = parse_hand("234567m234567p5s")
    info = tenpai_for_hand(hand)
    assert info.can_riichi  # 멘젠 텐파이


# --- 보이는 패 계수 --------------------------------------------------------

def test_count_visible_and_remaining():
    hand = parse_hand("11m")  # 1m 2장 보유
    state = GameState(
        my_hand=hand,
        dora_indicators=(Tile("m", 1),),  # 도라표시패에 1m 1장
    )
    idx = Tile("m", 1).index34
    assert count_visible(state, idx) == 3
    assert wall_remaining(state, idx) == 1
