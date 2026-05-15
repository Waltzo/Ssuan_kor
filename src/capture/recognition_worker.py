"""WindowTracker + CaptureLoop + 인식 통합 — 실시간 GameState 업데이트.

흐름:
    Tracker (poll로 호출) → 작혼 창 region → CaptureLoop (별도 스레드)
        → 변경 프레임 → recognize_my_hand → 콜백으로 (tiles, confs) emit

사용 (PyQt 오버레이서):
    worker = RecognitionWorker(profile, theme, on_recognized=handle)
    worker.start()
    qt_timer.timeout.connect(worker.poll_window)   # main thread서 200ms 간격
    qt_timer.start(200)
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from src.capture.capture_loop import CaptureLoop
from src.capture.window_finder import WindowInfo
from src.capture.window_tracker import WindowTracker
from src.core.game_state import Tile
from src.recognition import (
    Profile, Theme, recognize_my_hand,
)


class RecognitionWorker:
    """창 추적 + 캡처 루프 + 인식 → 콜백."""

    def __init__(
        self,
        profile: Profile,
        theme: Theme,
        on_recognized: Callable[
            [tuple[Tile | None, ...], tuple[float, ...]], None
        ] | None = None,
        on_window: Callable[[WindowInfo | None], None] | None = None,
        fps: float = 2.0,
        min_confidence: float = 0.5,
    ) -> None:
        self._profile = profile
        self._theme = theme
        self._on_recognized = on_recognized
        self._on_window_external = on_window
        self._min_confidence = min_confidence
        self._win: WindowInfo | None = None
        self._tracker = WindowTracker(on_change=self._on_window_internal)
        self._loop = CaptureLoop(
            region_provider=self._region,
            on_frame=self._on_frame,
            fps=fps,
        )

    @property
    def window(self) -> WindowInfo | None:
        return self._win

    def start(self) -> None:
        self._loop.start()

    def stop(self) -> None:
        self._loop.stop()

    def poll_window(self) -> WindowInfo | None:
        """메인 스레드(PyQt timer)서 주기 호출."""
        return self._tracker.poll()

    # --- internal callbacks ----------------------------------------------

    def _region(self) -> tuple[int, int, int, int] | None:
        if self._win is None or self._win.is_minimized:
            return None
        return self._win.region

    def _on_window_internal(self, win: WindowInfo | None) -> None:
        self._win = win
        if self._on_window_external:
            self._on_window_external(win)

    def _on_frame(self, frame: np.ndarray) -> None:
        if self._on_recognized is None:
            return
        try:
            tiles, confs = recognize_my_hand(
                frame, self._profile, self._theme,
                min_confidence=self._min_confidence,
            )
        except Exception:  # noqa: BLE001
            return
        try:
            self._on_recognized(tiles, confs)
        except Exception:  # noqa: BLE001
            pass
