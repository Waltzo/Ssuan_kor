"""테마(스킨) 템플릿 추출 — 사용자 본인 작혼 캡처에서 패 템플릿을 모은다.

사용:
    python tools/collect_templates.py <image> <theme_name> [--profile <yaml>]

흐름:
    1. 이미지 로드 → 손패 영역을 슬롯으로 분할
    2. 각 슬롯 미리보기 PNG를 debug/labeling/<theme>/slot_NN.png 로 저장
    3. CLI 프롬프트로 각 슬롯의 패 이름 입력받음
       (예: "1m", "0p"=아카 5p, "5z"=백, "skip"=건너뛰기, "q"=종료)
    4. 라벨된 슬롯을 assets/templates/<theme>/<tile>.png 에 복사

여러 캡처(다양한 패 등장)에 대해 반복 실행 → 점차 34종 모두 수집.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.game_state import Tile  # noqa: E402
from src.recognition.profile import load_profile  # noqa: E402
from src.recognition.slicer import split_hand  # noqa: E402
from src.recognition.theme import save_template  # noqa: E402

DEFAULT_PROFILE = ROOT / "config" / "profiles" / "default_16x9.yaml"
DEBUG_DIR = ROOT / "debug" / "labeling"


def _validate(name: str) -> str | None:
    """입력 이름이 유효한 패면 표준화해 반환, 아니면 None."""
    name = name.strip()
    if not name:
        return None
    try:
        return str(Tile.parse(name))   # 표준화 (예: "5m" → "5m", "0m" → "0m")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="테마 템플릿 추출")
    ap.add_argument("image", type=Path, help="작혼 캡처 이미지 경로")
    ap.add_argument("theme", type=str, help="테마 이름 (예: 'cat', 'mytheme')")
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    args = ap.parse_args()

    img = cv2.imread(str(args.image))
    if img is None:
        print(f"[!] 이미지 로드 실패: {args.image}")
        return 1
    profile = load_profile(args.profile)
    if profile.my_hand is None:
        print("[!] 프로파일에 my_hand 영역이 정의되지 않음")
        return 1

    slots = split_hand(img, profile.my_hand)
    preview_dir = DEBUG_DIR / args.theme
    preview_dir.mkdir(parents=True, exist_ok=True)
    for i, slot in enumerate(slots):
        cv2.imwrite(str(preview_dir / f"slot_{i:02d}.png"), slot)

    print(f"[+] 슬롯 {len(slots)}개 추출 → {preview_dir}/")
    print("    각 슬롯 PNG를 이미지 뷰어로 열어 확인한 뒤 패 이름을 입력하세요.")
    print("    형식: 1m~9m / 1p~9p / 1s~9s / 1z(동) 2z(남) 3z(서) 4z(북)")
    print("          5z(백) 6z(발) 7z(중) / 0m·0p·0s = 아카 5")
    print("    skip = 건너뛰기, q = 종료\n")

    saved = 0
    for i, slot in enumerate(slots):
        slot_path = preview_dir / f"slot_{i:02d}.png"
        try:
            raw = input(f"  slot {i:02d} ({slot_path.name}) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[!] 중단됨")
            break
        if raw in ("q", "quit", "exit"):
            break
        if raw in ("skip", "s", ""):
            continue
        normalized = _validate(raw)
        if normalized is None:
            print(f"    [!] 잘못된 패 표기: {raw!r} — 건너뜀")
            continue
        out = save_template(args.theme, normalized, slot)
        print(f"    → 저장: {out.relative_to(ROOT)}")
        saved += 1

    print(f"\n[+] 라벨 저장 {saved}개. 테마 디렉토리: assets/templates/{args.theme}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
