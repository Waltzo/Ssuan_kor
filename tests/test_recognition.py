"""인식 레이어 테스트 — 프로파일 파싱·로드·슬라이서 로직."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.recognition.profile import (
    HandRegion, Profile, Region, load_profile, save_profile,
)
from src.recognition.slicer import crop_region, split_hand


def test_region_to_pixels_round_values():
    r = Region(x=0.10, y=0.20, w=0.30, h=0.40)
    assert r.to_pixels(1000, 500) == (100, 100, 400, 300)


def test_handregion_slot_widths_equal():
    bounds = Region(x=0.0, y=0.5, w=0.6, h=0.1)
    hr = HandRegion(bounds=bounds, tile_count=6)
    widths = [hr.slot_region(i).w for i in range(6)]
    assert all(abs(w - 0.1) < 1e-9 for w in widths)
    # 슬롯들이 정확히 손패 영역을 채우는지
    last = hr.slot_region(5)
    assert abs(last.x + last.w - bounds.x - bounds.w) < 1e-9


def test_crop_region_extracts_correct_pixels():
    # 100x100 이미지, 우측 절반 빨강·좌측 절반 파랑
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :50] = (255, 0, 0)   # 좌측 BGR 파랑 (Blue)
    img[:, 50:] = (0, 0, 255)   # 우측 BGR 빨강 (Red)
    left = crop_region(img, Region(0.0, 0.0, 0.5, 1.0))
    right = crop_region(img, Region(0.5, 0.0, 0.5, 1.0))
    assert left.shape == (100, 50, 3)
    assert right.shape == (100, 50, 3)
    assert (left[0, 0] == [255, 0, 0]).all()
    assert (right[0, 0] == [0, 0, 255]).all()


def test_split_hand_produces_correct_count():
    img = np.zeros((100, 130, 3), dtype=np.uint8)
    hr = HandRegion(bounds=Region(0.0, 0.0, 1.0, 1.0), tile_count=13)
    slots = split_hand(img, hr)
    assert len(slots) == 13
    # 각 슬롯이 같은 폭
    widths = {s.shape[1] for s in slots}
    assert len(widths) == 1


def test_profile_yaml_roundtrip(tmp_path: Path):
    profile = Profile(
        name="test",
        aspect=1.778,
        my_hand=HandRegion(
            bounds=Region(0.18, 0.88, 0.74, 0.11), tile_count=14,
        ),
        regions={"dora": Region(0.02, 0.02, 0.10, 0.05)},
    )
    p = tmp_path / "test.yaml"
    save_profile(profile, p)
    loaded = load_profile(p)
    assert loaded.name == "test"
    assert loaded.my_hand is not None
    assert loaded.my_hand.tile_count == 14
    assert "dora" in loaded.regions


def test_default_profile_loads():
    """저장소의 default_16x9 프로파일이 로드되는지."""
    root = Path(__file__).resolve().parents[1]
    profile = load_profile(root / "config" / "profiles" / "default_16x9.yaml")
    assert profile.name == "default_16x9"
    assert profile.my_hand is not None
    assert profile.my_hand.tile_count >= 13
