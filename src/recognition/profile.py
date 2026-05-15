"""해상도 독립 좌표 프로파일.

각 UI 영역을 화면 비율 (0.0~1.0) 로 정의 → 1920x1080이든 955x537이든
같은 프로파일로 작동. 작혼 클라이언트는 16:9 레이아웃 기준.

YAML 프로파일 예시 (`config/profiles/default_16x9.yaml`):
    name: default_16x9
    aspect: 1.778
    regions:
      my_hand:
        x: 0.188
        y: 0.880
        w: 0.624
        h: 0.110
        tile_count: 13
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Region:
    """비율 좌표 영역 (0.0~1.0)."""

    x: float
    y: float
    w: float
    h: float

    def to_pixels(self, img_w: int, img_h: int) -> tuple[int, int, int, int]:
        """(left, top, right, bottom) 픽셀 좌표로 변환."""
        return (
            int(self.x * img_w),
            int(self.y * img_h),
            int((self.x + self.w) * img_w),
            int((self.y + self.h) * img_h),
        )


@dataclass(frozen=True)
class HandRegion:
    """손패 띠 — 비율 영역 + 슬롯 개수."""

    bounds: Region
    tile_count: int

    def slot_width_ratio(self) -> float:
        return self.bounds.w / self.tile_count

    def slot_region(self, idx: int) -> Region:
        """idx번째 슬롯의 비율 영역 (0-indexed)."""
        sw = self.slot_width_ratio()
        return Region(
            x=self.bounds.x + sw * idx,
            y=self.bounds.y,
            w=sw,
            h=self.bounds.h,
        )


@dataclass(frozen=True)
class Profile:
    """전체 좌표 프로파일."""

    name: str
    aspect: float
    my_hand: HandRegion | None = None
    regions: dict[str, Region] = field(default_factory=dict)


def load_profile(path: str | Path) -> Profile:
    """YAML 프로파일 로드."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    name = data.get("name", Path(path).stem)
    aspect = float(data.get("aspect", 16 / 9))
    raw_regions = data.get("regions", {})

    my_hand: HandRegion | None = None
    regions: dict[str, Region] = {}
    for key, val in raw_regions.items():
        region = Region(
            x=float(val["x"]),
            y=float(val["y"]),
            w=float(val["w"]),
            h=float(val["h"]),
        )
        if key == "my_hand":
            my_hand = HandRegion(
                bounds=region, tile_count=int(val.get("tile_count", 13))
            )
        else:
            regions[key] = region

    return Profile(
        name=name, aspect=aspect, my_hand=my_hand, regions=regions
    )


def save_profile(profile: Profile, path: str | Path) -> None:
    """YAML로 프로파일 저장."""
    data = {
        "name": profile.name,
        "aspect": profile.aspect,
        "regions": {},
    }
    if profile.my_hand:
        b = profile.my_hand.bounds
        data["regions"]["my_hand"] = {
            "x": b.x, "y": b.y, "w": b.w, "h": b.h,
            "tile_count": profile.my_hand.tile_count,
        }
    for key, r in profile.regions.items():
        data["regions"][key] = {"x": r.x, "y": r.y, "w": r.w, "h": r.h}

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
