"""실시간 캡처 루프 — 별도 스레드에서 N fps로 캡처, 프레임 변화시에만 콜백.

사용:
    loop = CaptureLoop(region_provider, fps=2, on_frame=handle)
    loop.start()
    ...
    loop.stop()

region_provider: () -> (l, t, r, b) | None — 매 tick 호출되어 캡처 영역을 반환.
                  None 반환 시 그 tick 건너뜀 (창 안 보임 등).
on_frame: (np.ndarray BGR) -> None — 프레임 변경 시에만 호출.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable

import numpy as np

from src.capture.screen_capture import ScreenCapture


class CaptureLoop:
    """별도 스레드 캡처 루프 + 프레임 dedup."""

    def __init__(
        self,
        region_provider: Callable[[], tuple[int, int, int, int] | None],
        on_frame: Callable[[np.ndarray], None] | None = None,
        fps: float = 2.0,
        backend: str = "auto",
    ) -> None:
        self._region_provider = region_provider
        self._on_frame = on_frame
        self._period = 1.0 / max(0.1, fps)
        self._backend = backend
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cap: ScreenCapture | None = None
        self._last_hash: str | None = None
        self._frames_total = 0
        self._frames_changed = 0

    @property
    def stats(self) -> tuple[int, int]:
        """(총 캡처 수, 변경 검출 수)."""
        return self._frames_total, self._frames_changed

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="CaptureLoop", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        if self._cap:
            self._cap.close()
            self._cap = None

    # --- internal ---------------------------------------------------------

    def _run(self) -> None:
        try:
            self._cap = ScreenCapture(prefer=self._backend)
        except Exception:
            return
        while not self._stop.is_set():
            t0 = time.time()
            region = self._region_provider()
            if region is not None:
                self._frames_total += 1
                try:
                    frame = self._cap.grab(region)
                except Exception:
                    frame = None
                if frame is not None:
                    digest = _frame_hash(frame)
                    if digest != self._last_hash:
                        self._last_hash = digest
                        self._frames_changed += 1
                        if self._on_frame:
                            try:
                                self._on_frame(frame)
                            except Exception:  # noqa: BLE001
                                pass
            elapsed = time.time() - t0
            self._stop.wait(max(0.0, self._period - elapsed))


def _frame_hash(frame: np.ndarray) -> str:
    """저비용 perceptual hash 대용 — 8x8 다운스케일 후 MD5.

    full bytes md5 (~6ms for 1080p)는 cpu 부담. 다운스케일은 cv2 import 회피
    위해 numpy stride 슬라이싱으로 단순화 — 정확도 < 진짜 phash 지만 변경 감지엔 충분.
    """
    h, w = frame.shape[:2]
    sy = max(1, h // 8)
    sx = max(1, w // 8)
    thumb = frame[::sy, ::sx]
    return hashlib.md5(thumb.tobytes()).hexdigest()
