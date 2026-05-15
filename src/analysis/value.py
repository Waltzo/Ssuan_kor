"""타점 추정 — 화료 시 판/부/점수 계산.

mahjong 라이브러리의 HandCalculator를 감싸 도라·아카도라·우라도라를
반영한 타점을 추정한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mahjong.hand_calculating.hand import HandCalculator

from src.core.game_state import Meld, RoundInfo, Tile
from src.analysis._libbridge import (
    dora_indicators_136,
    hand_and_win_136,
    make_config,
    to_lib_melds,
)

_calc = HandCalculator()

# "Dora 2", "Aka Dora 1", "Ura Dora 3" 처럼 끝에 숫자가 붙는 도라 계열 역 이름
_DORA_NAME = re.compile(r"(dora)\b", re.IGNORECASE)
_TRAILING_NUM = re.compile(r"(\d+)\s*$")


@dataclass(frozen=True)
class HandValue:
    """화료 시 타점 추정 결과."""

    han: int
    fu: int
    points: int                 # 화료 점수 총합 (cost.total)
    yaku: tuple[str, ...]       # 성립 역 이름들 (도라 포함)
    dora: int                   # 도라+아카+우라 합산 판수
    yaku_level: str | None      # mangan / haneman / baiman / ... (없으면 None)
    is_yakuman: bool
    error: str | None           # 화료 불가 사유 (no_yaku 등), 정상이면 None

    @property
    def valid(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        """한 줄 요약."""
        if not self.valid:
            return f"화료 불가 ({self.error})"
        level = f" {self.yaku_level}" if self.yaku_level else ""
        return f"{self.han}판 {self.fu}부{level} = {self.points}점"


def _count_dora_han(yaku_names: tuple[str, ...]) -> int:
    """역 이름 리스트에서 도라 계열 판수 합산."""
    total = 0
    for name in yaku_names:
        if _DORA_NAME.search(name):
            m = _TRAILING_NUM.search(name)
            total += int(m.group(1)) if m else 1
    return total


def estimate_value(
    hand13: tuple[Tile, ...],
    win: Tile,
    melds: tuple[Meld, ...] = (),
    dora_indicators: tuple[Tile, ...] = (),
    round_info: RoundInfo | None = None,
    *,
    is_tsumo: bool = False,
    is_riichi: bool = False,
    ura_indicators: tuple[Tile, ...] = (),
) -> HandValue:
    """13장 손패가 win으로 화료했을 때의 타점 추정.

    ura_indicators는 리치 화료 시에만 의미가 있다.
    """
    round_info = round_info or RoundInfo()
    full136, win136 = hand_and_win_136(hand13, win)
    config = make_config(round_info, is_tsumo=is_tsumo, is_riichi=is_riichi)

    try:
        r = _calc.estimate_hand_value(
            full136,
            win136,
            melds=to_lib_melds(melds),
            dora_indicators=dora_indicators_136(dora_indicators),
            config=config,
            ura_dora_indicators=dora_indicators_136(ura_indicators),
        )
    except Exception as exc:  # noqa: BLE001
        return HandValue(0, 0, 0, (), 0, None, False, f"calc_error: {exc}")

    if r.error:
        return HandValue(0, 0, 0, (), 0, None, False, r.error)

    yaku_names = tuple(str(y) for y in (r.yaku or ()))
    yaku_level = r.cost.get("yaku_level") if r.cost else None
    is_yakuman = yaku_level == "yakuman" or (r.han is not None and r.han >= 13)

    return HandValue(
        han=r.han or 0,
        fu=r.fu or 0,
        points=(r.cost or {}).get("total", 0),
        yaku=yaku_names,
        dora=_count_dora_han(yaku_names),
        yaku_level=yaku_level,
        is_yakuman=is_yakuman,
        error=None,
    )


def best_value_among_waits(
    hand13: tuple[Tile, ...],
    waits: tuple[Tile, ...],
    melds: tuple[Meld, ...] = (),
    dora_indicators: tuple[Tile, ...] = (),
    round_info: RoundInfo | None = None,
    *,
    is_tsumo: bool = False,
    is_riichi: bool = False,
) -> HandValue | None:
    """여러 대기패 중 가장 높은 타점을 반환 (유효한 화료가 없으면 None)."""
    best: HandValue | None = None
    for w in waits:
        v = estimate_value(
            hand13,
            w,
            melds,
            dora_indicators,
            round_info,
            is_tsumo=is_tsumo,
            is_riichi=is_riichi,
        )
        if not v.valid:
            continue
        if best is None or v.points > best.points:
            best = v
    return best
