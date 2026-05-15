"""작혼 리치 마작 오버레이 어시스턴트 — 진입점.

Phase 0: 작혼 창 탐색 + 영역 캡처 검증.

    python main.py --phase0

작혼 창을 찾아 정보를 출력하고, 클라이언트 영역을 캡처해
debug/phase0_capture.png 로 저장한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEBUG_DIR = Path(__file__).parent / "debug"


def run_phase0() -> int:
    """작혼 창 탐색 + 캡처 PoC. 성공 0, 실패 1."""
    from src.capture import ScreenCapture, find_mahjongsoul_window

    if sys.platform != "win32":
        print("[!] Phase 0 캡처는 Windows에서만 동작 (현재: %s)" % sys.platform)
        print("    Windows에서 작혼을 창 모드로 실행한 뒤 다시 실행하세요.")
        return 1

    print("[*] 작혼 창 탐색 중...")
    win = find_mahjongsoul_window()
    if win is None:
        print("[!] 작혼 창을 찾지 못함. 작혼이 실행 중인지 확인하세요.")
        return 1

    print(f"[+] 창 발견: '{win.title}' (hwnd={win.hwnd})")
    print(f"    클라이언트 영역: x={win.x} y={win.y} {win.width}x{win.height}")
    print(f"    최소화={win.is_minimized}  포그라운드={win.is_foreground}")
    if win.is_minimized:
        print("[!] 창이 최소화됨 — 복원 후 다시 실행하세요.")
        return 1
    if win.is_fullscreen:
        print("[!] 전체화면 독점 모드로 추정됨 — 오버레이가 가려질 수 있습니다.")
        print("    작혼을 '창 모드'로 변경하길 권장합니다.")

    print(f"[*] 화면 캡처 중...")
    try:
        with ScreenCapture() as cap:
            print(f"    백엔드: {cap.backend}")
            frame = cap.grab(win.region)
            # dxcam은 첫 프레임이 None일 수 있어 한 번 재시도
            if frame is None:
                frame = cap.grab(win.region)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] 캡처 실패: {exc}")
        return 1

    if frame is None:
        print("[!] 캡처 프레임이 비어 있음 (창이 가려졌거나 백엔드 문제).")
        return 1

    DEBUG_DIR.mkdir(exist_ok=True)
    out_path = DEBUG_DIR / "phase0_capture.png"
    try:
        import cv2

        cv2.imwrite(str(out_path), frame)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] 이미지 저장 실패: {exc}")
        return 1

    print(f"[+] 캡처 성공: {frame.shape[1]}x{frame.shape[0]} → {out_path}")
    print("[+] Phase 0 완료. 저장된 스크린샷을 열어 작혼 화면이 맞는지 확인하세요.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="작혼 리치 마작 오버레이 어시스턴트"
    )
    parser.add_argument(
        "--phase0",
        action="store_true",
        help="Phase 0: 작혼 창 탐색 + 캡처 PoC 실행",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="수동 입력 모드: 패를 직접 입력해 분석 (인식 레이어 불필요)",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="오버레이 모드: 투명 always-on-top 창에 분석 결과 표시",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="(--overlay 함께) 작혼 창 자동 추적 + 실시간 인식",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="(--live 함께) 사용할 인식 테마 이름",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="(--live 함께) 좌표 프로파일 YAML 경로",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=2.0,
        help="(--live 함께) 캡처·인식 주기 (초당 프레임). 기본 2.0",
    )
    args = parser.parse_args()

    if args.phase0:
        return run_phase0()
    if args.manual:
        from src.cli import run_manual_cli

        return run_manual_cli()
    if args.overlay:
        from src.overlay import run_overlay

        live_theme = args.theme if args.live else None
        if args.live and not args.theme:
            print("[!] --live 모드에는 --theme <name> 필수", file=sys.stderr)
            return 1
        return run_overlay(
            live_theme=live_theme,
            profile_path=args.profile,
            fps=args.fps,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
