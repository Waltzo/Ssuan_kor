"""value (타점 추정) + yaku_suggest (역 추천) 테스트."""

from __future__ import annotations

from src.core.game_state import GameState, MeldType, Meld, RoundInfo, Tile, Wind
from src.analysis.value import estimate_value, best_value_among_waits
from src.analysis.yaku_suggest import (
    STATUS_CONFIRMED,
    STATUS_POSSIBLE,
    suggest_yaku,
)
from src.analysis.tiles import parse_hand


# --- value.estimate_value -------------------------------------------------

def test_estimate_value_tanyao_ron():
    # 234m 567m 234p 567p + 5s 단기 → 5s 론, 탕야오
    hand13 = parse_hand("234567m234567p5s")
    win = Tile("s", 5)
    v = estimate_value(hand13, win)
    assert v.valid
    assert v.han >= 1
    assert any("Tanyao" in y or "tanyao" in y.lower() for y in v.yaku)
    assert v.points > 0


def test_estimate_value_yakuless():
    # 234m 567m 234p 678p + 9s 단기 → 역 없음
    hand13 = parse_hand("234567m234678p9s")
    win = Tile("s", 9)
    v = estimate_value(hand13, win)
    assert not v.valid
    assert v.error == "no_yaku"


def test_estimate_value_riichi_adds_han():
    # 같은 손에 리치 선언 시 1판 추가
    hand13 = parse_hand("234567m234678p9s")
    win = Tile("s", 9)
    v_no = estimate_value(hand13, win, is_riichi=False)
    v_ri = estimate_value(hand13, win, is_riichi=True)
    assert not v_no.valid           # 다마텐: 役なし
    assert v_ri.valid               # 리치 1판으로 화료
    assert v_ri.han >= 1


def test_estimate_value_dora_counts():
    # 도라표시 1m → 도라 2m. 234m이 있으니 도라 1.
    hand13 = parse_hand("234567m234567p5s")
    win = Tile("s", 5)
    v = estimate_value(
        hand13, win, dora_indicators=(Tile("m", 1),)
    )
    assert v.valid
    assert v.dora >= 1


def test_best_value_picks_highest():
    hand13 = parse_hand("234567m234567p5s")
    waits = (Tile("s", 5),)
    best = best_value_among_waits(hand13, waits)
    assert best is not None and best.valid


# --- yaku_suggest.suggest_yaku --------------------------------------------

def test_suggest_tanyao_confirmed_when_no_yaochu():
    # 야오추 0장 — 탕야오 확정형
    state = GameState(my_hand=parse_hand("234567m234567p23s"))
    leads = suggest_yaku(state)
    names = {l.name: l for l in leads}
    assert "탕야오" in names
    assert names["탕야오"].status == STATUS_CONFIRMED


def test_suggest_yakuhai_for_dragon_pair():
    # 백패 또이쯔 → 역패(삼원패) 가능
    state = GameState(my_hand=parse_hand("234m456p55z123s12p"))
    leads = suggest_yaku(state)
    assert any("역패" in l.name and "삼원패" in l.name for l in leads)


def test_suggest_yakuhai_for_round_wind():
    # 동패 또이쯔 + 장풍 동 → 장풍 역패
    state = GameState(
        my_hand=parse_hand("234m456p11z123s12p"),
        round=RoundInfo(round_wind=Wind.EAST, seat_wind=Wind.SOUTH),
    )
    leads = suggest_yaku(state)
    assert any("장풍" in l.name for l in leads)


def test_suggest_honitsu_when_one_suit_plus_honors():
    # 만수+자패만 — 혼일색 경향
    state = GameState(my_hand=parse_hand("123456789m1122z"))
    leads = suggest_yaku(state)
    assert any(l.name == "혼일색" for l in leads)


def test_suggest_chinitsu_when_pure_one_suit():
    # 만수만, 자패 0 — 청일색 경향
    state = GameState(my_hand=parse_hand("11223344556677m"))
    leads = suggest_yaku(state)
    assert any(l.name == "청일색" for l in leads)


def test_suggest_chiitoitsu_when_many_pairs():
    # 또이쯔 5개 이상 (멘젠) — 치또이쯔 가능
    state = GameState(my_hand=parse_hand("11223344m55667p"))
    leads = suggest_yaku(state)
    assert any(l.name == "치또이쯔" for l in leads)


def test_suggest_toitoi_with_open_pons():
    # 부로 모두 폰 + 또이쯔 다수
    state = GameState(
        my_hand=parse_hand("11m22p33s4m"),
        my_melds=(
            Meld(MeldType.PON, parse_hand("555p")),
            Meld(MeldType.PON, parse_hand("777s")),
        ),
    )
    leads = suggest_yaku(state)
    assert any(l.name == "또이또이" for l in leads)
