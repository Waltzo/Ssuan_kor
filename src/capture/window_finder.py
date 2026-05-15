"""작혼(MahjongSoul) 윈도우 탐색.

win32gui로 작혼 클라이언트 창을 찾아 핸들과 클라이언트 영역의
화면 절대 좌표를 반환한다.

Windows 전용 — 다른 OS에서는 find_mahjongsoul_window()가 None을 반환한다
(개발 환경이 Linux여도 import 자체는 실패하지 않도록 처리).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

# 작혼 창 제목 후보 (Steam판 / 브라우저판 / 일본어·중국어판).
# 부분 문자열 매칭으로 사용한다.
WINDOW_TITLE_CANDIDATES: tuple[str, ...] = (
    "雀魂",          # 중국어판
    "雀魂麻將",
    "じゃんたま",     # 일본어판
    "MahjongSoul",
    "Maj-Soul",
    "Mahjong Soul",
)

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import win32con
    import win32gui


@dataclass(frozen=True)
class WindowInfo:
    """작혼 창의 위치·상태 스냅샷."""

    hwnd: int
    title: str
    # 클라이언트 영역 (화면 절대 좌표)
    x: int
    y: int
    width: int
    height: int
    is_minimized: bool
    is_foreground: bool
    # 전체화면 독점 추정 — 오버레이가 가려질 위험이 있어 경고에 사용
    is_fullscreen: bool

    @property
    def region(self) -> tuple[int, int, int, int]:
        """캡처용 영역 (left, top, right, bottom) 절대 좌표."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


def _matches_mahjongsoul(title: str) -> bool:
    return any(cand.lower() in title.lower() for cand in WINDOW_TITLE_CANDIDATES)


def _client_rect_to_screen(hwnd: int) -> tuple[int, int, int, int]:
    """클라이언트 영역을 화면 절대 좌표 (x, y, w, h)로 변환."""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    # GetClientRect는 (0, 0, w, h) — 좌상단을 화면 좌표로 변환
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (left, top))
    return screen_x, screen_y, right - left, bottom - top


def _is_fullscreen(hwnd: int, width: int, height: int) -> bool:
    """창 크기가 모니터 전체와 같으면 전체화면으로 추정."""
    monitor = win32gui.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    # win32api 없이 win32gui만으로 모니터 rect 획득
    import win32api  # 지연 import — Windows에서만 필요

    info = win32api.GetMonitorInfo(monitor)
    mon_left, mon_top, mon_right, mon_bottom = info["Monitor"]
    return width >= (mon_right - mon_left) and height >= (mon_bottom - mon_top)


def find_mahjongsoul_window() -> WindowInfo | None:
    """작혼 창을 찾아 WindowInfo를 반환. 없으면 None.

    Windows가 아니거나 창을 못 찾으면 None.
    """
    if not IS_WINDOWS:
        return None

    found: list[int] = []

    def _enum_callback(hwnd: int, _ctx: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if title and _matches_mahjongsoul(title):
            found.append(hwnd)
        return True

    win32gui.EnumWindows(_enum_callback, None)
    if not found:
        return None

    # 후보가 여럿이면 클라이언트 영역이 가장 큰 창을 채택
    best_hwnd = max(found, key=lambda h: _client_area(h))
    title = win32gui.GetWindowText(best_hwnd)
    x, y, w, h = _client_rect_to_screen(best_hwnd)

    placement = win32gui.GetWindowPlacement(best_hwnd)
    is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
    is_foreground = win32gui.GetForegroundWindow() == best_hwnd
    is_fullscreen = (not is_minimized) and _is_fullscreen(best_hwnd, w, h)

    return WindowInfo(
        hwnd=best_hwnd,
        title=title,
        x=x,
        y=y,
        width=w,
        height=h,
        is_minimized=is_minimized,
        is_foreground=is_foreground,
        is_fullscreen=is_fullscreen,
    )


def _client_area(hwnd: int) -> int:
    try:
        _, _, w, h = _client_rect_to_screen(hwnd)
        return w * h
    except Exception:
        return 0
