"""PyInstaller 빌드 스크립트 — ssuan_kor.exe (Windows 단일 파일).

실행:
    python tools/build_exe.py
    python tools/build_exe.py --clean    # build/, dist/ 정리 후 빌드

요구:
    pip install pyinstaller

PyInstaller는 실행 OS의 바이너리를 만든다 (Windows → .exe, Linux → ELF).
Windows 사용자에게 .exe를 주려면 Windows에서 빌드해야 한다.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="ssuan_kor PyInstaller 빌드")
    ap.add_argument(
        "--clean", action="store_true",
        help="빌드 전 build/, dist/, __pycache__ 정리",
    )
    ap.add_argument(
        "--onefile", action="store_true",
        help="단일 .exe 파일로 패키징 (느린 시동 / 매번 풀림 비용 있음)",
    )
    args = ap.parse_args()

    spec = ROOT / "ssuan_kor.spec"
    if not spec.exists():
        print(f"[!] spec 파일 없음: {spec}", file=sys.stderr)
        return 1

    if args.clean:
        for d in ("build", "dist"):
            target = ROOT / d
            if target.exists():
                print(f"[*] 정리: {target}")
                shutil.rmtree(target)

    cmd = [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"]
    if args.onefile:
        cmd.append("--onefile")
    print("[*] 빌드 시작:", " ".join(cmd))
    try:
        subprocess.check_call(cmd, cwd=ROOT)
    except subprocess.CalledProcessError as e:
        print(f"[!] 빌드 실패 (exit {e.returncode})", file=sys.stderr)
        return e.returncode
    except FileNotFoundError:
        print(
            "[!] PyInstaller 미설치 — `pip install pyinstaller` 후 재시도",
            file=sys.stderr,
        )
        return 1

    out_dir = ROOT / "dist"
    print(f"\n[+] 빌드 완료. 산출물: {out_dir}")
    if (out_dir / "ssuan_kor.exe").exists():
        size_mb = (out_dir / "ssuan_kor.exe").stat().st_size / 1_000_000
        print(f"    ssuan_kor.exe ({size_mb:.1f} MB)")
    elif (out_dir / "ssuan_kor").exists():
        print(f"    ssuan_kor/ (폴더 배포)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
