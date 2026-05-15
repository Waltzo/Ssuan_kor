"""화면 캡처 — dxcam(주) / mss(대체).

작혼 창의 클라이언트 영역만 캡처해 OpenCV 호환 BGR numpy 배열로 반환한다.

백엔드 우선순위:
  1. dxcam  — Windows, GPU 기반, 빠름
  2. mss    — 크로스 플랫폼 fallback

사용:
    with ScreenCapture() as cap:
        frame = cap.grab((x, y, x + w, y + h))   # BGR ndarray 또는 None
"""

from __future__ import annotations

import sys

import numpy as np

IS_WINDOWS = sys.platform == "win32"


class CaptureError(RuntimeError):
    """캡처 백엔드 초기화·획득 실패."""


class ScreenCapture:
    """화면 캡처 래퍼. dxcam 우선, 실패 시 mss로 폴백."""

    def __init__(self, prefer: str = "auto") -> None:
        """prefer: "dxcam" | "mss" | "auto" (기본)."""
        self._backend: str = ""
        self._dxcam = None
        self._mss = None

        if prefer in ("auto", "dxcam") and IS_WINDOWS:
            self._try_init_dxcam()
        if not self._backend and prefer in ("auto", "mss", "dxcam"):
            self._try_init_mss()
        if not self._backend:
            raise CaptureError(
                "사용 가능한 캡처 백엔드 없음 (dxcam/mss 설치 확인)"
            )

    # --- 백엔드 초기화 ---------------------------------------------------

    def _try_init_dxcam(self) -> None:
        try:
            import dxcam

            # output_color="BGR" — OpenCV와 동일한 채널 순서
            self._dxcam = dxcam.create(output_color="BGR")
            if self._dxcam is not None:
                self._backend = "dxcam"
        except Exception:
            self._dxcam = None

    def _try_init_mss(self) -> None:
        try:
            import mss

            self._mss = mss.mss()
            self._backend = "mss"
        except Exception:
            self._mss = None

    # --- 캡처 ------------------------------------------------------------

    @property
    def backend(self) -> str:
        """현재 활성 백엔드 이름."""
        return self._backend

    def grab(self, region: tuple[int, int, int, int]) -> np.ndarray | None:
        """region (left, top, right, bottom) 절대 좌표를 BGR ndarray로 캡처.

        프레임이 아직 준비되지 않으면 None (dxcam은 변화 없을 때 None 반환).
        """
        if self._backend == "dxcam":
            return self._grab_dxcam(region)
        if self._backend == "mss":
            return self._grab_mss(region)
        raise CaptureError("활성 백엔드 없음")

    def _grab_dxcam(self, region: tuple[int, int, int, int]) -> np.ndarray | None:
        frame = self._dxcam.grab(region=region)
        if frame is None:
            return None
        return np.ascontiguousarray(frame)

    def _grab_mss(self, region: tuple[int, int, int, int]) -> np.ndarray | None:
        left, top, right, bottom = region
        bbox = {
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
        }
        raw = self._mss.grab(bbox)
        # mss는 BGRA → BGR로 변환
        arr = np.asarray(raw)[:, :, :3]
        return np.ascontiguousarray(arr)

    # --- 정리 ------------------------------------------------------------

    def close(self) -> None:
        if self._dxcam is not None:
            try:
                self._dxcam.release()
            except Exception:
                pass
            self._dxcam = None
        if self._mss is not None:
            try:
                self._mss.close()
            except Exception:
                pass
            self._mss = None
        self._backend = ""

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
