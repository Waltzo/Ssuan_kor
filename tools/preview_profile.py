"""좌표 프로파일을 이미지 위에 시각화 — 캘리브레이션 보조.

사용:
    python tools/preview_profile.py <image> [--profile <yaml>] [--out <png>]

기본:
    프로파일 = config/profiles/default_16x9.yaml
    출력 = debug/preview_<image_stem>.png

손패 영역(빨강) + 슬롯 분할선(노랑)을 그려서 좌표가 맞는지 한눈에 확인.
좌표가 어긋나면 프로파일 YAML의 x/y/w/h 값을 조정 → 재실행.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.recognition.profile import load_profile  # noqa: E402

DEFAULT_PROFILE = ROOT / "config" / "profiles" / "default_16x9.yaml"
DEBUG_DIR = ROOT / "debug"


def main() -> int:
    ap = argparse.ArgumentParser(description="프로파일 시각화")
    ap.add_argument("image", type=Path, help="대상 이미지 경로")
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    img = cv2.imread(str(args.image))
    if img is None:
        print(f"[!] 이미지 로드 실패: {args.image}")
        return 1
    h, w = img.shape[:2]

    profile = load_profile(args.profile)
    print(f"[*] 프로파일: {profile.name}  이미지: {w}x{h}")

    overlay = img.copy()
    if profile.my_hand:
        bx, by, br, bb = profile.my_hand.bounds.to_pixels(w, h)
        cv2.rectangle(overlay, (bx, by), (br, bb), (0, 0, 255), 2)
        cv2.putText(
            overlay, f"my_hand ({profile.my_hand.tile_count} slots)",
            (bx, max(by - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            (0, 0, 255), 1, cv2.LINE_AA,
        )
        for i in range(profile.my_hand.tile_count):
            sx, sy, sr, sb = profile.my_hand.slot_region(i).to_pixels(w, h)
            cv2.rectangle(overlay, (sx, sy), (sr, sb), (0, 255, 255), 1)

    for name, region in profile.regions.items():
        rx, ry, rr, rb = region.to_pixels(w, h)
        cv2.rectangle(overlay, (rx, ry), (rr, rb), (255, 200, 0), 2)
        cv2.putText(
            overlay, name, (rx, max(ry - 6, 14)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1, cv2.LINE_AA,
        )

    DEBUG_DIR.mkdir(exist_ok=True)
    out = args.out or (DEBUG_DIR / f"preview_{args.image.stem}.png")
    cv2.imwrite(str(out), overlay)
    print(f"[+] 저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
