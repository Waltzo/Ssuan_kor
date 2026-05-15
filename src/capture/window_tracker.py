"""작혼 윈도우 위치·상태 추적 — 변경 감지 + 콜백.

플랫폼 의존성 없음 — 스레딩이나 Qt timer를 외부에서 붙이고
WindowTracker.poll()을 주기적으로 호출하면 변경 시 콜백이 발화한다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from src.capture.window_finder import WindowInfo, find_mahjongsoul_window


class WindowTracker:
    """작혼 창 위치 추적. poll() 호출 시 변경되면 on_change 콜백 발화."""

    def __init__(
        self,
        on_change: Callable[[WindowInfo | None], None] | None = None,
    ) -> None:
        self._last: WindowInfo | None = None
        self.on_change = on_change

    @property
    def current(self) -> WindowInfo | None:
        return self._last

    def poll(self) -> WindowInfo | None:
        """창 상태 1회 갱신. 변경되면 콜백 발화. 현재 상태 반환."""
        cur = find_mahjongsoul_window()
        if not _same_window(cur, self._last):
            self._last = cur
            if self.on_change:
                try:
                    self.on_change(cur)
                except Exception:  # noqa: BLE001 — 콜백 예외가 추적을 멈추지 않게
                    pass
        return cur


def _same_window(a: WindowInfo | None, b: WindowInfo | None) -> bool:
    """창 정보가 의미적으로 동일한지 — region·상태 기준."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return (
        a.hwnd == b.hwnd
        and a.x == b.x and a.y == b.y
        and a.width == b.width and a.height == b.height
        and a.is_minimized == b.is_minimized
        and a.is_fullscreen == b.is_fullscreen
    )
