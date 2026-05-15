"""mahjong 라이브러리 브릿지 — 내부 모델 ↔ 라이브러리 타입 변환.

tenpai.py / value.py가 공유. 라이브러리 의존을 이 한 곳에 모은다.
"""

from __future__ import annotations

from mahjong.constants import EAST, NORTH, SOUTH, WEST
from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules
from mahjong.meld import Meld as LibMeld

from src.core.game_state import Meld, MeldType, RoundInfo, Tile, Wind
from src.analysis.tiles import AKA_136, tile_to_136, tiles_to_136

_AKA_SLOTS = set(AKA_136.values())

WIND_TO_CONST = {
    Wind.EAST: EAST,
    Wind.SOUTH: SOUTH,
    Wind.WEST: WEST,
    Wind.NORTH: NORTH,
}

_MELD_TYPE_MAP = {
    MeldType.CHI: LibMeld.CHI,
    MeldType.PON: LibMeld.PON,
    MeldType.KAN: LibMeld.KAN,
    MeldType.ANKAN: LibMeld.KAN,
    MeldType.SHOUMINKAN: LibMeld.SHOUMINKAN,
}


def to_lib_meld(meld: Meld) -> LibMeld:
    """내부 Meld → mahjong 라이브러리 Meld."""
    return LibMeld(
        _MELD_TYPE_MAP[meld.meld_type],
        tiles=tiles_to_136(meld.tiles),
        opened=meld.meld_type != MeldType.ANKAN,
    )


def to_lib_melds(melds: tuple[Meld, ...]) -> list[LibMeld] | None:
    return [to_lib_meld(m) for m in melds] if melds else None


def hand_and_win_136(
    hand13: tuple[Tile, ...], win: Tile
) -> tuple[list[int], int]:
    """13장 손패 + 화료패를 (14장 136-list, 화료패 136-index)로.

    화료패는 손패에 안 쓰인 사본 슬롯 하나를 차지한다.
    win이 아카가 아니면 아카 슬롯(16/52/88)은 회피한다 (lib 오인 방지).
    """
    hand136 = tiles_to_136(hand13)
    base = win.index34 * 4
    if win.is_aka:
        win136 = AKA_136[win.suit]
    else:
        win136 = next(
            (b for b in range(base, base + 4)
             if b not in hand136 and b not in _AKA_SLOTS),
            base + 1,
        )
    return sorted(hand136 + [win136]), win136


def make_config(
    round_info: RoundInfo,
    is_tsumo: bool = False,
    is_riichi: bool = False,
) -> HandConfig:
    """HandConfig 생성 — 작혼 룰(쿠이탕·아카도라 유효) 기준."""
    return HandConfig(
        is_tsumo=is_tsumo,
        is_riichi=is_riichi,
        player_wind=WIND_TO_CONST[round_info.seat_wind],
        round_wind=WIND_TO_CONST[round_info.round_wind],
        options=OptionalRules(has_open_tanyao=True, has_aka_dora=True),
    )


def dora_indicators_136(indicators: tuple[Tile, ...]) -> list[int] | None:
    return [tile_to_136(t) for t in indicators] if indicators else None
