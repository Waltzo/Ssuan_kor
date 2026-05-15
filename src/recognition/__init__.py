"""Recognition Layer — 작혼 화면 → GameState 변환.

테마 독립 설계:
  - 좌표는 비율(0.0~1.0)로 표현 → 해상도 무관 (`profile.py`)
  - 패 그래픽은 사용자 스킨에 따라 다름 → 테마별 템플릿 (`theme.py`)
  - 사용자가 자기 테마를 추출하는 도구: `tools/collect_templates.py`

진입점:
  recognize_my_hand(image, profile, theme) -> (tiles, confidences)
"""

from __future__ import annotations

import numpy as np

from src.core.game_state import Tile
from src.recognition.matcher import MatchResult, match_slots
from src.recognition.profile import Profile, Region, HandRegion, load_profile, save_profile
from src.recognition.slicer import crop_region, split_hand
from src.recognition.theme import Theme, list_themes, load_theme, save_template

__all__ = [
    "Profile", "Region", "HandRegion",
    "load_profile", "save_profile",
    "crop_region", "split_hand",
    "Theme", "list_themes", "load_theme", "save_template",
    "MatchResult", "match_slots",
    "recognize_my_hand",
]


def recognize_my_hand(
    image: np.ndarray,
    profile: Profile,
    theme: Theme,
    min_confidence: float = 0.5,
) -> tuple[tuple[Tile | None, ...], tuple[float, ...]]:
    """이미지에서 내 손패 인식. (tiles, confidences) 반환.

    프로파일에 my_hand 영역이 정의돼 있어야 한다. 매칭 실패 슬롯은 None.
    """
    if profile.my_hand is None:
        raise ValueError("프로파일에 my_hand 영역이 정의되지 않음")
    slots = split_hand(image, profile.my_hand)
    results = match_slots(slots, theme, min_confidence)
    tiles = tuple(r.tile for r in results)
    confs = tuple(r.confidence for r in results)
    return tiles, confs
