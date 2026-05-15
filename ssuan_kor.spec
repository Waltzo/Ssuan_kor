# PyInstaller spec — Windows .exe 빌드
#
# 실행: python tools/build_exe.py  (또는 pyinstaller ssuan_kor.spec --noconfirm)
# Windows에서만 .exe 산출. Linux서 빌드하면 ELF가 나오므로 Windows 사용자에겐 무용.
#
# 산출물: dist/ssuan_kor.exe (단일 파일) 또는 dist/ssuan_kor/ (폴더 — 더 빠름)

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve()  # noqa: F821 — PyInstaller 주입

# 데이터 파일 (런타임 필요): 좌표 프로파일, 패 템플릿, 도감 layout, 문서
datas = [
    (str(ROOT / "config" / "profiles"), "config/profiles"),
    (str(ROOT / "config" / "layouts"), "config/layouts"),
    (str(ROOT / "assets" / "templates"), "assets/templates"),
    (str(ROOT / "PLAN.md"), "."),
    (str(ROOT / "README.md"), "."),
]

# PyInstaller가 자동 못 잡는 모듈 (런타임 import)
hidden = [
    "mahjong.constants",
    "mahjong.shanten",
    "mahjong.tile",
    "mahjong.meld",
    "mahjong.hand_calculating.hand",
    "mahjong.hand_calculating.hand_config",
    "mahjong.hand_calculating.scores",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "cv2",
    "numpy",
    "yaml",
]

# 제외 — 빌드 사이즈 줄이기 위해
excludes = [
    "tkinter", "matplotlib", "PIL.ImageQt", "PySide6", "PyQt5",
    "scipy", "pandas", "jupyter", "IPython",
]

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ssuan_kor",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,   # CLI 모드(--manual) 위해 콘솔 유지. GUI만이면 False.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
