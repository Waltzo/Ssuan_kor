"""작혼 위에 띄우는 투명 오버레이 — PyQt6 frameless / translucent / always-on-top.

수동 입력 CLI(`src.cli.manual`)의 `handle_command`를 재사용해서, 입력란에 명령을
치면 분석 결과가 패널에 표시된다. `--live` 모드면 인식 워커가 작혼 창을
실시간 추적·캡처해 분석을 자동 갱신.

조작:
    드래그            창 이동
    F8               클릭 통과 모드 토글 (Windows 한정 — 게임 조작 방해 안 함)
    F2               창 투명도 ↑
    F3               창 투명도 ↓
    Esc / 닫기 버튼  종료
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.cli.manual import _StateBuilder, format_analysis, handle_command
from src.core.game_state import Tile

_IS_WINDOWS = sys.platform == "win32"


class OverlayWindow(QWidget):
    """투명 오버레이 메인 창."""

    # 워커 스레드 → UI 스레드 안전 전달
    _recognized_sig = pyqtSignal(tuple, tuple)
    _window_sig = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__(
            flags=Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._builder = _StateBuilder()
        self._drag_origin: QPoint | None = None
        self._click_through = False
        self._worker = None
        self._poll_timer: QTimer | None = None
        self._recognized_sig.connect(self._handle_recognized)
        self._window_sig.connect(self._handle_window_change)
        self._build_ui()

    # --- UI 구성 ----------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addLayout(self._build_title_bar())
        root.addWidget(self._build_input())
        root.addWidget(self._build_output(), stretch=1)
        root.addWidget(self._build_status_bar())

        self.setStyleSheet(
            """
            QWidget#bg { background-color: rgba(20,20,28,210); border-radius: 8px; }
            QLineEdit, QTextEdit {
                background-color: rgba(40,40,55,220);
                color: #f0f0f0;
                border: 1px solid #555;
                padding: 4px;
            }
            QPushButton {
                background-color: #333;
                color: white;
                border: none;
                padding: 3px 10px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #555; }
            QLabel#title { color: #ddd; font-weight: bold; }
            QLabel#status { color: #aaa; font-size: 10px; }
            """
        )
        self.setWindowOpacity(0.94)
        self.setObjectName("bg")
        self.resize(620, 560)

    def _build_title_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        title = QLabel("작혼 어시스턴트")
        title.setObjectName("title")
        bar.addWidget(title)
        bar.addStretch()

        for label, slot in (
            ("−", self.showMinimized),
            ("✕", self.close),
        ):
            btn = QPushButton(label)
            btn.setFixedSize(26, 22)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
        return bar

    def _build_input(self) -> QLineEdit:
        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "패 입력 또는 명령... (예: 234567m234567p5s, riichi s, help)"
        )
        self._input.returnPressed.connect(self._on_submit)
        self._input.setFont(_mono_font(10))
        return self._input

    def _build_output(self) -> QTextEdit:
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(_mono_font(10))
        self._output.setPlaceholderText(
            "여기에 분석 결과가 표시됩니다. 입력란에 손패를 치고 Enter."
        )
        return self._output

    def _build_status_bar(self) -> QLabel:
        self._status = QLabel(self._status_text())
        self._status.setObjectName("status")
        return self._status

    def _status_text(self) -> str:
        ct = "ON" if self._click_through else "OFF"
        op = int(self.windowOpacity() * 100)
        live = " | LIVE" if self._worker else ""
        return (
            f"클릭통과: {ct} (F8)   투명도: {op}% (F2/F3)   "
            f"드래그로 이동   Esc 종료{live}"
        )

    # --- 명령 처리 --------------------------------------------------------

    def _on_submit(self) -> None:
        line = self._input.text()
        self._input.clear()
        if not line.strip():
            return
        msg, should_quit = handle_command(self._builder, line)
        if msg:
            self._output.append(f"<pre>{_html_escape(msg)}</pre>")
        if should_quit:
            self.close()

    # --- 라이브 모드 (인식 워커) -----------------------------------------

    def enable_live(
        self,
        theme_name: str,
        profile_path: str | Path | None = None,
        fps: float = 2.0,
        min_confidence: float = 0.5,
    ) -> str | None:
        """실시간 인식 모드 시작. 실패 시 에러 메시지, 성공 시 None."""
        if self._worker is not None:
            return "이미 라이브 모드 실행 중"
        try:
            from src.capture import RecognitionWorker
            from src.recognition import load_profile, load_theme
        except ImportError as e:
            return f"의존성 누락: {e}"

        profile_path = (
            Path(profile_path) if profile_path
            else Path("config/profiles/default_16x9.yaml")
        )
        if not profile_path.exists():
            return f"프로파일 없음: {profile_path}"
        try:
            profile = load_profile(profile_path)
            theme = load_theme(theme_name)
        except Exception as e:  # noqa: BLE001
            return f"테마/프로파일 로드 실패: {e}"
        if not theme.templates:
            return f"테마 '{theme_name}'에 템플릿이 없음 — collect_templates.py로 추출하세요"

        self._worker = RecognitionWorker(
            profile=profile, theme=theme,
            on_recognized=lambda t, c: self._recognized_sig.emit(t, c),
            on_window=lambda w: self._window_sig.emit(w),
            fps=fps, min_confidence=min_confidence,
        )
        self._worker.start()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._worker.poll_window)
        self._poll_timer.start(300)
        self._output.append(
            f"<pre>[LIVE] 인식 워커 시작 — 테마={theme_name}, fps={fps}</pre>"
        )
        self._status.setText(self._status_text())
        return None

    def disable_live(self) -> None:
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._status.setText(self._status_text())

    def _handle_recognized(
        self,
        tiles: tuple,  # tuple[Tile | None, ...]
        confs: tuple,  # tuple[float, ...]
    ) -> None:
        """워커가 인식한 결과 → UI 스레드서 손패 갱신·분석 재실행."""
        valid = tuple(t for t in tiles if t is not None)
        if not valid:
            return
        self._builder.hand = valid
        avg = sum(confs) / len(confs) if confs else 0.0
        line = " ".join(f"{str(t) if t else '?'}({c:.2f})"
                        for t, c in zip(tiles, confs))
        analysis = format_analysis(
            self._builder.build(),
            frozenset(self._builder.assume_tenpai),
            self._builder.my_score,
        )
        self._output.setHtml(
            f"<pre>[LIVE 인식 평균 신뢰도 {avg:.2f}]\n  {_html_escape(line)}\n\n"
            f"{_html_escape(analysis)}</pre>"
        )

    def _handle_window_change(self, win) -> None:
        """작혼 창 변경 시 — 상태바 갱신만 (자동 이동은 옵션)."""
        if win is None:
            self._status.setText("작혼 창 미발견  |  " + self._status_text())
        else:
            self._status.setText(
                f"작혼: {win.width}x{win.height} @ ({win.x},{win.y})"
                f"  |  " + self._status_text()
            )

    # --- 키 / 마우스 ------------------------------------------------------

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.close()
        elif ev.key() == Qt.Key.Key_F8:
            self._toggle_click_through()
        elif ev.key() == Qt.Key.Key_F2:
            self.setWindowOpacity(min(1.0, self.windowOpacity() + 0.05))
            self._status.setText(self._status_text())
        elif ev.key() == Qt.Key.Key_F3:
            self.setWindowOpacity(max(0.30, self.windowOpacity() - 0.05))
            self._status.setText(self._status_text())
        else:
            super().keyPressEvent(ev)

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            ev.accept()

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if self._drag_origin is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_origin)
            ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        self._drag_origin = None

    def closeEvent(self, ev) -> None:
        self.disable_live()
        super().closeEvent(ev)

    # --- 클릭 통과 (Windows) ---------------------------------------------

    def _toggle_click_through(self) -> None:
        if not _IS_WINDOWS:
            self._output.append(
                "<pre>[i] 클릭 통과는 Windows 전용 — 현재 OS에서는 비활성</pre>"
            )
            return
        self._click_through = not self._click_through
        try:
            _set_click_through_windows(int(self.winId()), self._click_through)
        except Exception as exc:  # noqa: BLE001
            self._output.append(
                f"<pre>[!] 클릭 통과 토글 실패: {exc}</pre>"
            )
            self._click_through = False
        self._status.setText(self._status_text())


# --- Windows 전용 유틸 ----------------------------------------------------

def _set_click_through_windows(hwnd: int, enable: bool) -> None:
    """WS_EX_TRANSPARENT + WS_EX_LAYERED 토글로 클릭 통과 설정."""
    import ctypes

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.restype = ctypes.c_long

    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enable:
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


# --- 헬퍼 -----------------------------------------------------------------

def _mono_font(point: int) -> QFont:
    f = QFont()
    f.setStyleHint(QFont.StyleHint.Monospace)
    for family in ("Consolas", "Menlo", "DejaVu Sans Mono", "Courier New"):
        f.setFamily(family)
        if f.exactMatch():
            break
    f.setPointSize(point)
    return f


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# --- 진입점 ---------------------------------------------------------------

def run_overlay(
    live_theme: str | None = None,
    profile_path: str | None = None,
    fps: float = 2.0,
) -> int:
    """오버레이 실행. 메인 스레드에서 호출.

    live_theme 지정 시 시작과 동시에 라이브 인식 모드 활성화.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    win = OverlayWindow()
    win.show()
    if live_theme:
        err = win.enable_live(live_theme, profile_path=profile_path, fps=fps)
        if err:
            print(f"[!] 라이브 모드 실패: {err}", file=sys.stderr)
    return app.exec()
