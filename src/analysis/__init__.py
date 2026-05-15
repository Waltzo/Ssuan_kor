"""Analysis Engine — 샹텐, 타패 추천, 후리텐, 役なし, 타점 추정, 역 추천.

OS·캡처와 무관한 순수 로직. GameState만 입력으로 받는다.
"""

from src.analysis.shanten import ShantenResult, calculate_shanten, shanten_of_state
from src.analysis.efficiency import (
    DiscardOption,
    UkeireTile,
    best_discard,
    recommend_discards,
    ukeire_for_hand,
)
from src.analysis.tenpai import TenpaiInfo, WaitTile, analyze_tenpai, tenpai_for_hand
from src.analysis.value import HandValue, best_value_among_waits, estimate_value
from src.analysis.yaku_suggest import YakuLead, suggest_yaku
from src.analysis.danger import (
    DangerCategory,
    DangerReport,
    OpponentDanger,
    TileDanger,
    analyze_danger,
    safety_against_opponent,
)
from src.analysis.push_fold import PushFoldAdvice, Stance, evaluate_push_fold
from src.analysis.riichi_decide import RiichiAction, RiichiAdvice, evaluate_riichi
from src.analysis.call_decide import CallAction, CallAdvice, evaluate_call
from src.analysis.opp_yaku import (
    OpponentYakuPrediction,
    predict_all_opponents,
    predict_opponent_yaku,
)
from src.analysis.standings import Mode, StandingsContext, evaluate_standings
from src.analysis.tiles import parse_hand

__all__ = [
    "ShantenResult",
    "calculate_shanten",
    "shanten_of_state",
    "DiscardOption",
    "UkeireTile",
    "best_discard",
    "recommend_discards",
    "ukeire_for_hand",
    "TenpaiInfo",
    "WaitTile",
    "analyze_tenpai",
    "tenpai_for_hand",
    "HandValue",
    "estimate_value",
    "best_value_among_waits",
    "YakuLead",
    "suggest_yaku",
    "DangerCategory",
    "DangerReport",
    "OpponentDanger",
    "TileDanger",
    "analyze_danger",
    "safety_against_opponent",
    "PushFoldAdvice",
    "Stance",
    "evaluate_push_fold",
    "RiichiAction",
    "RiichiAdvice",
    "evaluate_riichi",
    "CallAction",
    "CallAdvice",
    "evaluate_call",
    "OpponentYakuPrediction",
    "predict_opponent_yaku",
    "predict_all_opponents",
    "Mode",
    "StandingsContext",
    "evaluate_standings",
    "parse_hand",
]
