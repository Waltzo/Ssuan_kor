"""레퍼런스 시트(grid 배치된 패 일람표)에서 템플릿 자동 추출.

작혼 패 일람을 캡처한 이미지가 있으면, layout YAML로 셀 좌표·라벨을 정의해
한 번에 34종 + 아카 3종 템플릿을 추출한다.

사용:
    python tools/extract_grid.py <layout.yaml> <theme_name> [--root <image_root>]

Layout YAML 형식:
    image: screanshots/hand_2.png
    rows: 4
    cols: 10
    cell:
        x0: 5
        y0: 5
        w: 78
        h: 121
        pad_x: 1     # 셀 사이 가로 간격
        pad_y: 5     # 셀 사이 세로 간격
    labels:
        - [0s, 1s, 2s, ..., 9s]    # rows × cols 배열, 빈 칸은 ""
        - [0m, 1m, ...]
        - ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.recognition.theme import save_template  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Grid 레퍼런스에서 템플릿 추출")
    ap.add_argument("layout", type=Path, help="레이아웃 YAML 경로")
    ap.add_argument("theme", type=str, help="저장할 테마 이름")
    ap.add_argument(
        "--image", type=Path, default=None,
        help="(선택) layout YAML의 image 필드 대신 사용할 이미지 경로",
    )
    ap.add_argument(
        "--preview", action="store_true",
        help="추출 후 디버그 디렉토리에 프리뷰 저장",
    )
    args = ap.parse_args()

    with open(args.layout, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    img_path = args.image or (ROOT / cfg["image"])
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"[!] 이미지 로드 실패: {img_path}")
        return 1
    print(f"[*] 이미지: {img_path} ({img.shape[1]}x{img.shape[0]})")

    cell = cfg["cell"]
    x0, y0 = int(cell["x0"]), int(cell["y0"])
    w, h = int(cell["w"]), int(cell["h"])
    pad_x = int(cell.get("pad_x", 0))
    pad_y = int(cell.get("pad_y", 0))
    rows = int(cfg["rows"])
    cols = int(cfg["cols"])
    labels = cfg["labels"]

    if len(labels) != rows or any(len(r) != cols for r in labels):
        print(f"[!] labels 크기 불일치: {rows}x{cols} 기대")
        return 1

    saved = 0
    skipped = 0
    preview = img.copy() if args.preview else None
    for r in range(rows):
        for c in range(cols):
            label = str(labels[r][c]).strip()
            if not label:
                skipped += 1
                continue
            x = x0 + c * (w + pad_x)
            y = y0 + r * (h + pad_y)
            if x + w > img.shape[1] or y + h > img.shape[0]:
                print(f"[!] 셀 ({r},{c}) {label} — 이미지 범위 초과, 건너뜀")
                continue
            crop = img[y : y + h, x : x + w].copy()
            out = save_template(args.theme, label, crop)
            saved += 1
            if preview is not None:
                cv2.rectangle(
                    preview, (x, y), (x + w, y + h), (0, 255, 0), 1
                )
                cv2.putText(
                    preview, label, (x + 2, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA,
                )

    print(f"[+] 저장: {saved}개  /  건너뜀: {skipped}개")
    print(f"    → assets/templates/{args.theme}/")

    if preview is not None:
        debug_dir = ROOT / "debug"
        debug_dir.mkdir(exist_ok=True)
        out_path = debug_dir / f"extract_{args.theme}.png"
        cv2.imwrite(str(out_path), preview)
        print(f"[+] 프리뷰: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
