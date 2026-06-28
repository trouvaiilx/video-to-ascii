"""
Preview & Comparison Panel
==========================
  - Left pane: original video frame
  - Right pane: ASCII-rendered preview
  - Scrubber + playback + step (prev/next frame)
  - Preview requests are debounced (200 ms) to avoid flooding the worker
    when dragging sliders.
"""

from __future__ import annotations
import threading
import logging

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QSplitter, QFrame, QSizePolicy
)
from ui.widgets import VideoPreviewLabel, StatCard, SectionHeader
from ui.styles import ACCENT, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_MUTED, BG_RAISED

logger = logging.getLogger(__name__)


# ── Preview worker ─────────────────────────────────────────────────────────────

class PreviewWorker(QThread):
    """Background thread: reads a single frame and renders it.
    Only the most recently requested render is executed — intermediate
    requests that arrive while a render is in progress are dropped.
    """
    frame_ready = pyqtSignal(np.ndarray, np.ndarray)  # (original, ascii)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._video_path: str = ""
        self._frame_idx: int = 0
        self._profile = None
        self._plugins: list = []
        self._lock = threading.Lock()
        self._pending = False

    def request_render(self, video_path: str, frame_idx: int, profile, plugins: list) -> None:
        with self._lock:
            self._video_path = video_path
            self._frame_idx = frame_idx
            self._profile = profile
            self._plugins = list(plugins)
            self._pending = True
        if not self.isRunning():
            self.start()

    def run(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    break
                path = self._video_path
                idx = self._frame_idx
                profile = self._profile
                plugins = list(self._plugins)
                self._pending = False

            try:
                cap = cv2.VideoCapture(path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, float(idx))
                ret, frame = cap.read()
                cap.release()
                if not ret or frame is None:
                    continue

                original = frame.copy()
                for plugin in plugins:
                    try:
                        frame = plugin.process(frame)
                    except Exception:
                        pass

                from core.ascii_renderer import AsciiRenderer
                renderer = AsciiRenderer(profile)
                ascii_img = renderer.render_frame_to_image(frame, font_size=profile.font_size)
                self.frame_ready.emit(original, ascii_img)

            except Exception as e:
                logger.warning("Preview render error: %s", e)
                self.error.emit(str(e))


# ── Preview panel ──────────────────────────────────────────────────────────────

class PreviewPanel(QWidget):
    """Side-by-side comparison panel with scrubber, playback, and step buttons."""

    _DEBOUNCE_MS = 200   # wait this long after the last change before rendering

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._video_path: str = ""
        self._total_frames: int = 1
        self._fps: float = 25.0
        self._profile = None
        self._plugins: list = []
        self._current_frame = 0
        self._is_playing = False

        # Worker
        self._worker = PreviewWorker()
        self._worker.frame_ready.connect(self._on_frame_ready)

        # Playback timer
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._playback_tick)

        # Debounce timer — fires once after _DEBOUNCE_MS of no new requests
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._do_render)

        self._build_ui()

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(SectionHeader("Live Preview", "◈"))

        # Column labels
        label_row = QHBoxLayout()
        orig_lbl = QLabel("ORIGINAL")
        orig_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; letter-spacing: 1px;")
        ascii_lbl = QLabel("ASCII OUTPUT")
        ascii_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 9px; letter-spacing: 1px; font-weight: bold;"
        )
        ascii_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        label_row.addWidget(orig_lbl)
        label_row.addStretch()
        label_row.addWidget(ascii_lbl)
        layout.addLayout(label_row)

        # Split view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._original_view = VideoPreviewLabel()
        self._ascii_view = VideoPreviewLabel()
        self._ascii_view.setStyleSheet(
            f"background: #050508; border: 1px solid {ACCENT}; border-radius: 4px;"
        )
        splitter.addWidget(self._original_view)
        splitter.addWidget(self._ascii_view)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        # Scrubber + playback controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(26, 26)
        self._prev_btn.setToolTip("Step back one frame")
        self._prev_btn.clicked.connect(self._step_back)
        ctrl_row.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(32, 26)
        self._play_btn.setToolTip("Play / pause preview")
        self._play_btn.clicked.connect(self._toggle_playback)
        ctrl_row.addWidget(self._play_btn)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(26, 26)
        self._next_btn.setToolTip("Step forward one frame")
        self._next_btn.clicked.connect(self._step_forward)
        ctrl_row.addWidget(self._next_btn)

        # Use a slightly larger Unicode char for fwd
        self._next_btn.setText("▶")

        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setMinimum(0)
        self._scrubber.setMaximum(0)
        self._scrubber.setToolTip("Drag to seek to a frame")
        self._scrubber.sliderMoved.connect(self._on_scrub)
        ctrl_row.addWidget(self._scrubber, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; min-width: 90px;"
            f" font-family: 'JetBrains Mono', monospace;"
        )
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ctrl_row.addWidget(self._time_label)
        layout.addLayout(ctrl_row)

        # Stats row
        stats_row = QHBoxLayout()
        self._stat_res = StatCard("Source Res", "—")
        self._stat_fps = StatCard("Source FPS", "—")
        self._stat_frame = StatCard("Frame #", "—")
        self._stat_size = StatCard("Output Size", "—")
        for card in [self._stat_res, self._stat_fps, self._stat_frame, self._stat_size]:
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

    # ─── Public API ───────────────────────────────────────────────────────────

    def set_video(self, path: str) -> None:
        self._video_path = path
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return
        self._total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self._fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        self._scrubber.setMaximum(self._total_frames - 1)
        self._scrubber.setValue(0)
        self._current_frame = 0
        self._stat_res.update_value(f"{w}×{h}")
        self._stat_fps.update_value(f"{self._fps:.1f}")
        self._update_time_label()
        self._schedule_render()

    def update_profile(self, profile, plugins: list | None = None) -> None:
        self._profile = profile
        if plugins is not None:
            self._plugins = plugins
        if self._video_path:
            self._schedule_render()

    def update_plugins(self, plugins: list) -> None:
        self._plugins = plugins
        if self._video_path and self._profile:
            self._schedule_render()

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _schedule_render(self) -> None:
        """Restart the debounce timer. Actual render fires after _DEBOUNCE_MS."""
        self._debounce_timer.start(self._DEBOUNCE_MS)

    def _do_render(self) -> None:
        if not self._video_path or not self._profile:
            return
        self._worker.request_render(
            self._video_path, self._current_frame, self._profile, self._plugins
        )

    @pyqtSlot(np.ndarray, np.ndarray)
    def _on_frame_ready(self, original: np.ndarray, ascii_img: np.ndarray) -> None:
        self._original_view.display_frame(original)
        self._ascii_view.display_frame(ascii_img)
        h, w = ascii_img.shape[:2]
        self._stat_size.update_value(f"{w}×{h}")
        self._stat_frame.update_value(str(self._current_frame))

    def _on_scrub(self, value: int) -> None:
        self._current_frame = value
        self._update_time_label()
        self._schedule_render()

    def _step_back(self) -> None:
        if self._current_frame > 0:
            self._current_frame -= 1
            self._scrubber.setValue(self._current_frame)
            self._update_time_label()
            self._schedule_render()

    def _step_forward(self) -> None:
        if self._current_frame < self._total_frames - 1:
            self._current_frame += 1
            self._scrubber.setValue(self._current_frame)
            self._update_time_label()
            self._schedule_render()

    def _toggle_playback(self) -> None:
        if self._is_playing:
            self._playback_timer.stop()
            self._is_playing = False
            self._play_btn.setText("▶")
        else:
            interval = max(33, int(1000 / self._fps))
            self._playback_timer.start(interval)
            self._is_playing = True
            self._play_btn.setText("⏸")

    def _playback_tick(self) -> None:
        if self._current_frame >= self._total_frames - 1:
            self._current_frame = 0
        else:
            self._current_frame += 1
        self._scrubber.setValue(self._current_frame)
        self._update_time_label()
        # Don't debounce during playback — render every tick
        self._do_render()

    def _update_time_label(self) -> None:
        cur = self._current_frame / self._fps
        total = self._total_frames / self._fps
        self._time_label.setText(
            f"{int(cur // 60)}:{int(cur % 60):02d} / {int(total // 60)}:{int(total % 60):02d}"
        )
