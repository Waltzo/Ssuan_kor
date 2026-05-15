"""패 인식 — OpenCV 멀티스케일 템플릿 매칭.

핵심 개선:
  - 슬롯 안에서 템플릿을 여러 크기로 슬라이딩 → 게임 화면 패가 슬롯과 정확히
    같은 크기가 아니어도 매칭 가능 (스케일 invariance)
  - grayscale + 히스토그램 정규화 (CLAHE) → 밝기·색조 변동 흡수
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.core.game_state import Tile
from src.recognition.theme import Theme

# 템플릿을 슬롯 높이의 몇 배(±%)로 시도할지 — 게임 화면의 패는 보통 슬롯보다 약간 작거나 큼
_SCALES = (0.70, 0.80, 0.90, 1.00, 1.10)
_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))


@dataclass(frozen=True)
class MatchResult:
    """슬롯 인식 결과."""

    tile: Tile | None     # 매칭 실패 시 None
    confidence: float     # 0.0~1.0 (TM_CCOEFF_NORMED 기준)
    matched_name: str     # 템플릿 패 이름 ("1m", "0p", "5z" 등)
    scale: float          # 최적 매칭에 사용된 스케일 (디버그용)


def _preprocess(img: np.ndarray) -> np.ndarray:
    """매칭용 전처리 — grayscale + CLAHE 정규화."""
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    return _CLAHE.apply(gray)


def _match_one(slot_g: np.ndarray, tpl_g: np.ndarray) -> tuple[float, float]:
    """슬롯 안에서 템플릿을 여러 스케일로 매칭, 최고 점수와 해당 스케일을 반환.

    슬롯 높이를 기준으로 템플릿을 _SCALES 배수로 리사이즈 → 슬라이딩 매칭.
    템플릿이 슬롯보다 크면 그 스케일은 건너뜀.
    """
    sh, sw = slot_g.shape[:2]
    best_score = -1.0
    best_scale = 1.0
    for s in _SCALES:
        target_h = max(8, int(sh * s))
        ratio = target_h / tpl_g.shape[0]
        target_w = max(8, int(tpl_g.shape[1] * ratio))
        if target_h > sh or target_w > sw:
            continue
        resized = cv2.resize(tpl_g, (target_w, target_h), interpolation=cv2.INTER_AREA)
        try:
            res = cv2.matchTemplate(slot_g, resized, cv2.TM_CCOEFF_NORMED)
        except cv2.error:
            continue
        score = float(res.max())
        if score > best_score:
            best_score = score
            best_scale = s
    return best_score, best_scale


def match_tile(
    slot: np.ndarray,
    theme: Theme,
    min_confidence: float = 0.5,
) -> MatchResult:
    """단일 슬롯을 테마 템플릿들과 매칭."""
    if not theme.templates:
        return MatchResult(tile=None, confidence=0.0, matched_name="", scale=1.0)

    slot_g = _preprocess(slot)
    best_score = -1.0
    best_name = ""
    best_scale = 1.0
    for name, tpl in theme.templates.items():
        tpl_g = _preprocess(tpl)
        score, scale = _match_one(slot_g, tpl_g)
        if score > best_score:
            best_score = score
            best_name = name
            best_scale = scale

    if best_score < min_confidence or not best_name:
        return MatchResult(
            tile=None, confidence=best_score,
            matched_name=best_name, scale=best_scale,
        )

    return MatchResult(
        tile=Tile.parse(best_name),
        confidence=best_score,
        matched_name=best_name,
        scale=best_scale,
    )


def match_slots(
    slots: list[np.ndarray],
    theme: Theme,
    min_confidence: float = 0.5,
) -> list[MatchResult]:
    """여러 슬롯 일괄 매칭."""
    return [match_tile(s, theme, min_confidence) for s in slots]
