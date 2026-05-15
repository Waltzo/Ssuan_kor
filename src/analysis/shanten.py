"""샹텐(向聴) 계산 — mahjong 라이브러리 래핑.

일반형·치또이쯔·국사무쌍 샹텐을 각각 구하고 최소값을 반환한다.
부로 패는 34-array에 합산해 완성 면자로 처리한다 (tiles.hand_with_melds_34).
"""

from __future__ import annotations

from dataclasses import dataclass

from mahjong.shanten import Shanten

from src.core.game_state import GameState, Meld, Tile
from src.analysis.tiles import hand_with_melds_34

_shanten = Shanten()

# 샹텐 의미: -1 = 화료, 0 = 텐파이, 1+ = N샹텐
AGARI = -1
TENPAI = 0


@dataclass(frozen=True)
class ShantenResult:
    """샹텐 계산 결과."""

    value: int          # 최소 샹텐 (일반/치또이/국사 중 최솟값)
    regular: int        # 일반형 샹텐
    chiitoitsu: int     # 치또이쯔 샹텐
    kokushi: int        # 국사무쌍 샹텐

    @property
    def is_agari(self) -> bool:
        return self.value == AGARI

    @property
    def is_tenpai(self) -> bool:
        return self.value == TENPAI


def calculate_shanten(
    hand: tuple[Tile, ...], melds: tuple[Meld, ...] = ()
) -> ShantenResult:
    """손패(+부로)의 샹텐을 계산.

    부로가 있으면 치또이쯔·국사무쌍은 불가하므로 일반형만 본다.
    """
    arr = hand_with_melds_34(hand, melds)
    has_melds = len(melds) > 0

    regular = _shanten.calculate_shanten(arr, use_chiitoitsu=False, use_kokushi=False)
    if has_melds:
        chiitoi = 99
        kokushi = 99
    else:
        chiitoi = _shanten.calculate_shanten(
            arr, use_chiitoitsu=True, use_kokushi=False
        )
        kokushi = _shanten.calculate_shanten(
            arr, use_chiitoitsu=False, use_kokushi=True
        )

    return ShantenResult(
        value=min(regular, chiitoi, kokushi),
        regular=regular,
        chiitoitsu=chiitoi,
        kokushi=kokushi,
    )


def shanten_of_state(state: GameState) -> ShantenResult:
    """GameState의 내 손패 샹텐."""
    return calculate_shanten(state.my_hand, state.my_melds)
