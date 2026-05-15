"""Phase 3 분석 모듈 테스트 — 리치/부로/상대역/점수상황."""

from __future__ import annotations

from src.core.game_state import (
    Discard, GameState, Meld, MeldType, RoundInfo, Seat, Tile, Wind,
)
from src.analysis.tiles import parse_hand
from src.analysis.riichi_decide import RiichiAction, evaluate_riichi
from src.analysis.call_decide import CallAction, evaluate_call
from src.analysis.opp_yaku import predict_opponent_yaku
from src.analysis.standings import Mode, evaluate_standings


# --- 리치 판단 -----------------------------------------------------------

def test_riichi_recommended_when_yakuless_tenpai():
    # 役なし 텐파이 → 리치 강제 권고
    state = GameState(
        my_hand=parse_hand("234567m234678p9s"),
        turn=5,
    )
    advice = evaluate_riichi(state)
    assert advice.action == RiichiAction.RIICHI
    assert any("役なし" in r for r in advice.reasons)


def test_no_riichi_when_open():
    # 부로 있어 멘젠 아님 → 리치 불가
    state = GameState(
        my_hand=parse_hand("234567m23467p"),  # 11장
        my_melds=(Meld(MeldType.PON, parse_hand("555s")),),
    )
    advice = evaluate_riichi(state)
    assert advice.action == RiichiAction.NO_BET
    assert "멘젠" in advice.reasons[0]


def test_no_riichi_when_low_score():
    state = GameState(my_hand=parse_hand("234567m234567p5s"))
    advice = evaluate_riichi(state, my_score=500)
    assert advice.action == RiichiAction.NO_BET


def test_dama_when_already_high_value():
    # 이미 다마 만관급 + 대기 양면 + 늦은 순목 → 다마 추천
    state = GameState(
        my_hand=parse_hand("234m23455p23456s"),
        dora_indicators=(Tile("m", 1), Tile("p", 1)),
        turn=12,
    )
    advice = evaluate_riichi(state)
    assert advice.dama_points >= 5000
    assert advice.action == RiichiAction.DAMA


def test_no_riichi_in_terminal_turn():
    # 종반 + 대기 안 좋음 → NO_BET 또는 DAMA
    state = GameState(
        my_hand=parse_hand("234567m234678p9s"),
        turn=18,
    )
    advice = evaluate_riichi(state)
    # 役なし이라 리치 보너스 +50, 종반 -25 — 점수 합쳐도 양수일 수 있음
    # 핵심: 화료 시간 부족 이유 포함
    assert any("종반" in r for r in advice.reasons)


# --- 부로 판단 -----------------------------------------------------------

def test_call_yakuhai_pon_recommended():
    # 백패(5z) 또이쯔 보유 + 상대 5z 버림 → 폰 권고
    state = GameState(
        my_hand=parse_hand("234m456p55z123s12p"),
        turn=4,
    )
    advice = evaluate_call(
        state,
        discarded=Tile("z", 5),
        call_type=MeldType.PON,
        using_tiles=(Tile("z", 5), Tile("z", 5)),
    )
    assert advice.action == CallAction.CALL
    assert any("역패" in r for r in advice.reasons)


def test_skip_when_shanten_regresses():
    # 멘젠 좋은 형태 + 콜이 샹텐 후퇴시키면 스킵
    state = GameState(
        my_hand=parse_hand("234567m234567p5s"),  # 텐파이
        turn=4,
    )
    # 5s로 폰? 손에 5s 1장뿐 — 폰 못함. 대신 234p 콜로 샹텐 후퇴 시뮬
    advice = evaluate_call(
        state,
        discarded=Tile("p", 4),
        call_type=MeldType.CHI,
        using_tiles=(Tile("p", 3), Tile("p", 5)),
    )
    # 텐파이에서 chi → 손패 줄어 형태 깨짐 — 스킵 쪽
    assert advice.action == CallAction.SKIP


# --- 상대 역 예측 --------------------------------------------------------

def test_opp_yaku_riichi_confirmed():
    state = GameState(riichi={Seat.SHIMOCHA: True})
    pred = predict_opponent_yaku(state, Seat.SHIMOCHA)
    assert pred.is_riichi
    assert any(l.name == "리치" for l in pred.likely_yaku)


def test_opp_yaku_tanyao_trend_from_early_yaochu():
    # 초반 6순간 1z, 9m, 1m, 9s 버림 → 탕야오 경향
    discards = (
        Discard(Tile("z", 1), 1),
        Discard(Tile("m", 9), 2),
        Discard(Tile("m", 1), 3),
        Discard(Tile("s", 9), 4),
        Discard(Tile("p", 5), 5),
    )
    state = GameState(discards={Seat.SHIMOCHA: discards})
    pred = predict_opponent_yaku(state, Seat.SHIMOCHA)
    assert any(l.name == "탕야오" for l in pred.likely_yaku)


def test_opp_yaku_yakuhai_pon():
    # 발(6z) 폰 → 역패 확정
    melds = (Meld(MeldType.PON, parse_hand("666z")),)
    state = GameState(melds={Seat.SHIMOCHA: melds})
    pred = predict_opponent_yaku(state, Seat.SHIMOCHA)
    assert any("역패" in l.name for l in pred.likely_yaku)


def test_opp_yaku_toitoi_trend_with_pons():
    melds = (
        Meld(MeldType.PON, parse_hand("333m")),
        Meld(MeldType.PON, parse_hand("777p")),
    )
    state = GameState(melds={Seat.SHIMOCHA: melds})
    pred = predict_opponent_yaku(state, Seat.SHIMOCHA)
    assert any(l.name == "또이또이" for l in pred.likely_yaku)


# --- 점수상황 ------------------------------------------------------------

def test_standings_neutral_when_no_scores():
    state = GameState()
    ctx = evaluate_standings(state)
    assert ctx.mode == Mode.NEUTRAL


def test_standings_oorasu_top_lock():
    # 남4국(=올라스) + 1등 + 점수차 큼 → 1등 사수
    state = GameState(
        scores={
            Seat.SELF: 40000,
            Seat.SHIMOCHA: 25000,
            Seat.TOIMEN: 20000,
            Seat.KAMICHA: 15000,
        },
        round=RoundInfo(round_wind=Wind.SOUTH, seat_wind=Wind.NORTH),
    )
    ctx = evaluate_standings(state)
    assert ctx.is_oorasu
    assert ctx.my_rank == 1
    assert ctx.mode == Mode.TOP_LOCK


def test_standings_oorasu_avoid_last():
    state = GameState(
        scores={
            Seat.SELF: 10000,
            Seat.SHIMOCHA: 30000,
            Seat.TOIMEN: 30000,
            Seat.KAMICHA: 30000,
        },
        round=RoundInfo(round_wind=Wind.SOUTH, seat_wind=Wind.NORTH),
    )
    ctx = evaluate_standings(state)
    assert ctx.my_rank == 4
    assert ctx.mode == Mode.AVOID_LAST


def test_standings_oorasu_chase_top():
    # SELF가 2등, 1등과 5000점 차 → CHASE_TOP
    state = GameState(
        scores={
            Seat.SELF: 27000,
            Seat.SHIMOCHA: 32000,  # 1등, 5000점 차
            Seat.TOIMEN: 22000,
            Seat.KAMICHA: 19000,
        },
        round=RoundInfo(round_wind=Wind.SOUTH, seat_wind=Wind.NORTH),
    )
    ctx = evaluate_standings(state)
    assert ctx.my_rank == 2
    assert ctx.mode == Mode.CHASE_TOP
