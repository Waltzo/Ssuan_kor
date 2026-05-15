"""이미지 영역 크롭 + 손패 슬롯 분할."""

from __future__ import annotations

import numpy as np

from src.recognition.profile import HandRegion, Region


def crop_region(image: np.ndarray, region: Region) -> np.ndarray:
    """이미지의 비율 영역을 크롭해 새 ndarray로 반환."""
    h, w = image.shape[:2]
    left, top, right, bottom = region.to_pixels(w, h)
    return image[top:bottom, left:right].copy()


def split_hand(
    image: np.ndarray, hand: HandRegion
) -> list[np.ndarray]:
    """손패 영역을 tile_count개 슬롯으로 균등 분할.

    픽셀 반올림 누적을 피하려고 픽셀 단위로 직접 분할 — 슬롯 폭은
    최대 1px 차이로 균일.
    """
    h, w = image.shape[:2]
    left, top, right, bottom = hand.bounds.to_pixels(w, h)
    total_w = right - left
    n = hand.tile_count
    base = total_w // n
    extras = total_w % n
    slots: list[np.ndarray] = []
    cur = left
    for i in range(n):
        sw = base + (1 if i < extras else 0)
        slots.append(image[top:bottom, cur : cur + sw].copy())
        cur += sw
    return slots
