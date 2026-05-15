"""캡처 워커 테스트 — WindowTracker, CaptureLoop 로직 (모킹)."""

from __future__ import annotations

import time
from unittest.mock import patch

import numpy as np

from src.capture.window_finder import WindowInfo
from src.capture.window_tracker import WindowTracker, _same_window
from src.capture.capture_loop import CaptureLoop


def _wi(x=0, y=0, w=100, h=80, hwnd=1, mini=False, full=False, fg=True) -> WindowInfo:
    return WindowInfo(
        hwnd=hwnd, title="MahjongSoul",
        x=x, y=y, width=w, height=h,
        is_minimized=mini, is_foreground=fg, is_fullscreen=full,
    )


def test_same_window_both_none():
    assert _same_window(None, None)


def test_same_window_one_none():
    assert not _same_window(_wi(), None)
    assert not _same_window(None, _wi())


def test_same_window_position_diff():
    assert not _same_window(_wi(x=0), _wi(x=10))


def test_same_window_identical():
    assert _same_window(_wi(), _wi())


def test_window_tracker_emits_on_change():
    events: list = []
    tracker = WindowTracker(on_change=events.append)
    # 창 없음
    with patch(
        "src.capture.window_tracker.find_mahjongsoul_window", return_value=None
    ):
        tracker.poll()
    # None → None : 변경 없음
    assert events == []

    # 창 등장
    win1 = _wi()
    with patch(
        "src.capture.window_tracker.find_mahjongsoul_window", return_value=win1
    ):
        tracker.poll()
    assert events[-1] is win1

    # 같은 창 (변경 없음)
    with patch(
        "src.capture.window_tracker.find_mahjongsoul_window", return_value=_wi()
    ):
        tracker.poll()
    assert len(events) == 1  # 추가 발화 없음

    # 위치 변경
    win2 = _wi(x=50)
    with patch(
        "src.capture.window_tracker.find_mahjongsoul_window", return_value=win2
    ):
        tracker.poll()
    assert events[-1] is win2

    # 사라짐
    with patch(
        "src.capture.window_tracker.find_mahjongsoul_window", return_value=None
    ):
        tracker.poll()
    assert events[-1] is None


def test_window_tracker_callback_exception_does_not_crash():
    def boom(_w):
        raise RuntimeError("boom")

    tracker = WindowTracker(on_change=boom)
    with patch(
        "src.capture.window_tracker.find_mahjongsoul_window", return_value=_wi()
    ):
        # 콜백 예외가 추적을 멈추면 안 됨
        result = tracker.poll()
    assert result is not None


def test_capture_loop_dedups_same_frame():
    """같은 프레임이 반복돼도 콜백은 한 번만 호출되어야 함."""
    frames: list = []

    class FakeCap:
        def __init__(self):
            self.backend = "fake"
            self._frame = np.zeros((10, 10, 3), dtype=np.uint8)
            self._frame[5, 5] = 255

        def grab(self, _region):
            return self._frame.copy()

        def close(self):
            pass

    region = (0, 0, 10, 10)
    with patch(
        "src.capture.capture_loop.ScreenCapture", return_value=FakeCap()
    ):
        loop = CaptureLoop(
            region_provider=lambda: region,
            on_frame=frames.append,
            fps=20.0,
        )
        loop.start()
        time.sleep(0.4)  # 여러 tick 흘러도 같은 프레임이면 1번만
        loop.stop()

    assert len(frames) == 1


def test_capture_loop_emits_on_change():
    """프레임이 바뀌면 그 때마다 콜백."""
    frames: list = []
    counter = {"n": 0}

    class FakeCap:
        def __init__(self):
            self.backend = "fake"

        def grab(self, _region):
            counter["n"] += 1
            arr = np.zeros((10, 10, 3), dtype=np.uint8)
            arr[5, 5] = counter["n"] % 256  # 매번 다른 값
            return arr

        def close(self):
            pass

    region = (0, 0, 10, 10)
    with patch(
        "src.capture.capture_loop.ScreenCapture", return_value=FakeCap()
    ):
        loop = CaptureLoop(
            region_provider=lambda: region,
            on_frame=frames.append,
            fps=20.0,
        )
        loop.start()
        time.sleep(0.4)
        loop.stop()

    assert len(frames) >= 2  # 여러 frame 변화 캡처됨


def test_capture_loop_skips_when_region_none():
    frames: list = []

    class FakeCap:
        def __init__(self):
            self.backend = "fake"

        def grab(self, _r):
            raise AssertionError("region=None일 때 grab 호출되면 안 됨")

        def close(self):
            pass

    with patch(
        "src.capture.capture_loop.ScreenCapture", return_value=FakeCap()
    ):
        loop = CaptureLoop(
            region_provider=lambda: None,
            on_frame=frames.append,
            fps=20.0,
        )
        loop.start()
        time.sleep(0.2)
        loop.stop()

    assert frames == []
