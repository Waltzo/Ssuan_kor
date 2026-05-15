"""테마(스킨) 관리 — 디렉토리에서 패 템플릿 이미지 로드.

작혼은 사용자별로 패 그래픽이 다를 수 있다 (스킨 시스템).
각 테마는 별도 디렉토리에 34종 패 + 아카 3종 템플릿을 보유한다.

디렉토리 구조:
    assets/templates/<theme>/
        1m.png 2m.png ... 9m.png
        1p.png ... 9p.png
        1s.png ... 9s.png
        1z.png ... 7z.png
        0m.png 0p.png 0s.png   (아카 5)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from src.core.game_state import Tile

DEFAULT_TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "assets" / "templates"


@dataclass(frozen=True)
class Theme:
    """패 스킨 — 패 이름 → 템플릿 이미지(BGR ndarray)."""

    name: str
    templates: dict[str, np.ndarray] = field(default_factory=dict)

    def has(self, tile_name: str) -> bool:
        return tile_name in self.templates

    def coverage(self) -> tuple[int, int]:
        """(보유 템플릿 수, 총 필요 수=37)."""
        return len(self.templates), 37


def _all_tile_names() -> list[str]:
    """일반 34종 + 아카 3종 = 37개 패 이름."""
    names = []
    for suit in ("m", "p", "s"):
        for r in range(1, 10):
            names.append(f"{r}{suit}")
        names.append(f"0{suit}")  # 아카
    for r in range(1, 8):
        names.append(f"{r}z")
    return names


def list_themes(root: Path | None = None) -> list[str]:
    """`root` 아래의 모든 테마 이름 리스트."""
    root = root or DEFAULT_TEMPLATES_ROOT
    if not root.exists():
        return []
    return sorted(
        d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


def load_theme(name: str, root: Path | None = None) -> Theme:
    """테마 디렉토리에서 템플릿 로드."""
    root = root or DEFAULT_TEMPLATES_ROOT
    theme_dir = root / name
    if not theme_dir.is_dir():
        raise FileNotFoundError(f"테마 디렉토리 없음: {theme_dir}")

    templates: dict[str, np.ndarray] = {}
    for tname in _all_tile_names():
        for ext in (".png", ".jpg", ".jpeg"):
            p = theme_dir / f"{tname}{ext}"
            if p.exists():
                img = cv2.imread(str(p), cv2.IMREAD_COLOR)
                if img is not None:
                    templates[tname] = img
                    break
    return Theme(name=name, templates=templates)


def save_template(
    theme_name: str,
    tile: Tile | str,
    image: np.ndarray,
    root: Path | None = None,
) -> Path:
    """단일 패 템플릿을 `<root>/<theme>/<tile>.png`에 저장."""
    root = root or DEFAULT_TEMPLATES_ROOT
    theme_dir = root / theme_name
    theme_dir.mkdir(parents=True, exist_ok=True)
    name = str(tile) if isinstance(tile, Tile) else tile
    out = theme_dir / f"{name}.png"
    cv2.imwrite(str(out), image)
    return out
