"""
Main Application Window
=======================
Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │  Menu Bar                                                   │
  ├──────────────┬──────────────────────────┬───────────────────┤
  │  Settings    │   Preview / Comparison   │  Tab Panel        │
  │  Panel       │                          │  [Plugins|Batch   │
  │  (scroll)    │                          │   |Debug]         │
  ├──────────────┴──────────────────────────┴───────────────────┤
  │  Status Bar + Progress                                      │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations
import os
import logging
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QFileDialog, QTabWidget, QFrame,
    QStatusBar, QMessageBox, QProgressBar, QSizePolicy, QToolBar
)
from config.manager import ConfigManager
from presets.profiles import PRESETS, RenderProfile
from ui.settings_panel import SettingsPanel
from ui.preview_panel import PreviewPanel
from ui.plugins_panel import PluginsPanel
from ui.batch_panel import BatchPanel
from ui.debug_panel import DebugPanel
from ui.widgets import DropZone, SectionHeader, StatCard
from ui.styles import STYLESHEET, ACCENT, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_MUTED, RED, BG_DEEP, TEXT_PRIMARY, BG_BASE

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self._config = ConfigManager()
        self._profile: RenderProfile = self._config.get_active_profile()
        self._active_plugins: list = []
        self._input_path: str = ""
        self._output_path: str = ""
        self._pipeline = None
        self._is_processing = False

        self.setWindowTitle("ASCII VIDEO CONVERTER  ◈  v1.0")
        self.setMinimumSize(1200, 760)
        self.resize(
            self._config.get("window_width", 1400),
            self._config.get("window_height", 900),
        )
        if self._config.get("window_maximized"):
            self.showMaximized()

        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._connect_signals()

    # ─── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top toolbar ──────────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # ── Main splitter: settings | preview | tabs ──────────────────────────
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setHandleWidth(3)

        # LEFT: Settings
        self._settings_panel = SettingsPanel(self._profile, self._config)
        main_split.addWidget(self._settings_panel)

        # CENTER: Preview
        self._preview_panel = PreviewPanel()
        main_split.addWidget(self._preview_panel)

        # RIGHT: Tab panel
        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(300)
        right_tabs.setMaximumWidth(400)

        self._plugins_panel = PluginsPanel()
        right_tabs.addTab(self._plugins_panel, "Plugins")

        self._batch_panel = BatchPanel()
        right_tabs.addTab(self._batch_panel, "Batch")

        self._debug_panel = DebugPanel()
        right_tabs.addTab(self._debug_panel, "Debug")
        main_split.addWidget(right_tabs)

        main_split.setSizes([360, 720, 340])
        root.addWidget(main_split, 1)

        # ── Bottom: progress + output path + encode button ────────────────────
        bottom = self._build_bottom_bar()
        root.addWidget(bottom)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"""
            background: {BG_DEEP};
            border-bottom: 1px solid {BORDER};
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Logo
        logo = QLabel("◈ ASCII VIDEO CONVERTER")
        logo.setStyleSheet(f"""
            color: {ACCENT};
            font-size: 15px;
            font-weight: bold;
            letter-spacing: 2px;
            font-family: 'JetBrains Mono', monospace;
        """)
        layout.addWidget(logo)
        layout.addStretch()

        # Drop zone (compact)
        self._drop_zone = DropZone()
        self._drop_zone.setMinimumHeight(36)
        self._drop_zone.setMaximumHeight(40)
        self._drop_zone.setMinimumWidth(300)
        self._drop_zone.setToolTip("Drop a video file here, or click Browse")
        layout.addWidget(self._drop_zone, 1)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_input)
        layout.addWidget(browse_btn)

        layout.addSpacing(16)

        # Encode action button
        self._encode_btn = QPushButton("⚡  ENCODE")
        self._encode_btn.setProperty("role", "primary")
        self._encode_btn.setFixedHeight(36)
        self._encode_btn.setMinimumWidth(110)
        self._encode_btn.clicked.connect(self._start_encoding)
        self._encode_btn.setEnabled(False)
        layout.addWidget(self._encode_btn)

        self._cancel_btn = QPushButton("✕  CANCEL")
        self._cancel_btn.setProperty("role", "danger")
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.setMinimumWidth(100)
        self._cancel_btn.clicked.connect(self._cancel_encoding)
        self._cancel_btn.setEnabled(False)
        layout.addWidget(self._cancel_btn)

        return bar

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"""
            background: {BG_DEEP};
            border-top: 1px solid {BORDER};
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Output:"))

        self._output_edit = __import__("PyQt6.QtWidgets", fromlist=["QLineEdit"]).QLineEdit()
        self._output_edit.setPlaceholderText("Output path (auto-generated if blank)")
        self._output_edit.setStyleSheet(f"""
            QLineEdit {{
                background: #1a1a1e;
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                color: {TEXT_PRIMARY};
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }}
        """)
        layout.addWidget(self._output_edit, 1)

        out_browse = QPushButton("…")
        out_browse.setFixedWidth(30)
        out_browse.clicked.connect(self._browse_output)
        layout.addWidget(out_browse)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        layout.addWidget(self._progress_bar)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; min-width: 160px;")
        layout.addWidget(self._progress_lbl)

        return bar

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("File")
        open_act = QAction("Open Video…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._browse_input)
        file_menu.addAction(open_act)

        recent_menu = file_menu.addMenu("Recent Files")
        for path in self._config.get_recent_files()[:10]:
            act = QAction(os.path.basename(path), self)
            act.setData(path)
            act.triggered.connect(lambda checked, p=path: self._load_video(p))
            recent_menu.addAction(act)

        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # Encode
        encode_menu = mb.addMenu("Encode")
        start_act = QAction("Start Encoding", self)
        start_act.setShortcut("Ctrl+Return")
        start_act.triggered.connect(self._start_encoding)
        encode_menu.addAction(start_act)

        cancel_act = QAction("Cancel", self)
        cancel_act.triggered.connect(self._cancel_encoding)
        encode_menu.addAction(cancel_act)

        # Presets
        preset_menu = mb.addMenu("Presets")
        for key, preset in PRESETS.items():
            act = QAction(preset.name, self)
            act.setData(key)
            act.triggered.connect(lambda checked, k=key: self._apply_preset(k))
            preset_menu.addAction(act)

        # View
        view_menu = mb.addMenu("View")
        debug_act = QAction("Toggle Debug Panel", self)
        debug_act.setShortcut("Ctrl+D")
        debug_act.triggered.connect(self._toggle_debug)
        view_menu.addAction(debug_act)

        # Help
        help_menu = mb.addMenu("Help")
        about_act = QAction("About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_msg = QLabel("Ready — Drop a video file to begin")
        self._status_msg.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        sb.addWidget(self._status_msg, 1)

        self._gpu_indicator = QLabel("GPU: checking…")
        self._gpu_indicator.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        sb.addPermanentWidget(self._gpu_indicator)
        QTimer.singleShot(500, self._check_gpu)

    # ─── Signal Connections ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._settings_panel.profile_changed.connect(self._on_profile_changed)
        self._drop_zone.file_dropped.connect(self._load_video)
        self._plugins_panel.plugins_changed.connect(self._on_plugins_changed)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _browse_input(self) -> None:
        last_dir = self._config.get("last_input_dir", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video File", last_dir,
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv *.m4v *.ts *.mts);;All Files (*)"
        )
        if path:
            self._load_video(path)

    def _load_video(self, path: str) -> None:
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{path}")
            return

        self._input_path = path
        self._config.add_recent_file(path)
        self._config.set("last_input_dir", str(Path(path).parent))
        self._config.save()

        self._drop_zone.set_file(path)
        self._encode_btn.setEnabled(True)
        self._auto_set_output()
        self._preview_panel.set_video(path)
        self._preview_panel.update_profile(self._profile, self._active_plugins)
        self._batch_panel.update_profile(self._profile)

        from core.pipeline import VideoInfo
        try:
            info = VideoInfo.from_path(path)
            self._status_msg.setText(
                f"{os.path.basename(path)}  |  {info.width}×{info.height}  |  "
                f"{info.fps:.2f} fps  |  {info.total_frames} frames  |  "
                f"{info.duration_sec:.1f}s  |  {info.codec}"
            )
        except Exception as e:
            self._status_msg.setText(f"Loaded: {os.path.basename(path)}")

        self._debug_panel.log(f"Loaded: {path}")

    def _auto_set_output(self) -> None:
        if not self._input_path:
            return
        base = os.path.splitext(self._input_path)[0]
        fmt = self._profile.output_format
        ext_map = {"mp4": "_ascii.mp4", "gif": "_ascii.gif",
                   "image_seq": "_ascii_frames", "txt_stream": "_ascii.txt"}
        ext = ext_map.get(fmt, "_ascii.mp4")
        self._output_edit.setText(base + ext)

    def _browse_output(self) -> None:
        fmt = self._profile.output_format
        if fmt == "image_seq":
            path = QFileDialog.getExistingDirectory(self, "Output Directory")
        else:
            ext_map = {"mp4": "*.mp4", "gif": "*.gif", "txt_stream": "*.txt"}
            filt = ext_map.get(fmt, "*.mp4")
            path, _ = QFileDialog.getSaveFileName(self, "Save As", "", f"Output ({filt})")
        if path:
            self._output_edit.setText(path)

    def _start_encoding(self) -> None:
        if not self._input_path:
            QMessageBox.warning(self, "No Input", "Please select a video file first.")
            return
        if self._is_processing:
            return

        out_path = self._output_edit.text().strip()
        if not out_path:
            self._auto_set_output()
            out_path = self._output_edit.text().strip()

        if not out_path:
            QMessageBox.warning(self, "No Output Path", "Please specify an output path.")
            return

        # Ensure parent dir exists
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        self._is_processing = True
        self._encode_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._debug_panel.reset()
        self._debug_panel.log(f"Starting: {os.path.basename(self._input_path)} → {os.path.basename(out_path)}")

        from core.pipeline import FramePipeline
        n_workers = self._config.get("worker_threads", 0)
        self._pipeline = FramePipeline(self._profile, self._active_plugins, num_workers=n_workers)
        self._pipeline.start(
            self._input_path,
            out_path,
            progress_cb=self._on_progress,
            completion_cb=self._on_complete,
        )

    def _cancel_encoding(self) -> None:
        if self._pipeline:
            self._pipeline.cancel()
            self._debug_panel.log("Cancellation requested…")
        self._cancel_btn.setEnabled(False)

    @pyqtSlot(object)
    def _on_profile_changed(self, profile: RenderProfile) -> None:
        self._profile = profile
        self._preview_panel.update_profile(profile, self._active_plugins)
        self._batch_panel.update_profile(profile)
        self._auto_set_output()

    @pyqtSlot(list)
    def _on_plugins_changed(self, plugins: list) -> None:
        self._active_plugins = plugins
        self._preview_panel.update_plugins(plugins)
        self._batch_panel.update_plugins(plugins)

    def _on_progress(self, prog) -> None:
        """Called from background thread — post to UI via Qt signal."""
        # Direct call is OK since QLabel/QProgressBar are thread-safe for reads,
        # but we use a timer shot for safety
        QTimer.singleShot(0, lambda: self._update_progress_ui(prog))

    def _update_progress_ui(self, prog) -> None:
        if prog.total_frames > 0:
            pct = int(prog.frames_done / prog.total_frames * 100)
            self._progress_bar.setValue(pct)
        eta = f"ETA {int(prog.eta_seconds//60)}:{int(prog.eta_seconds%60):02d}" if prog.eta_seconds > 0 else ""
        fps_str = f" · {prog.fps_current:.1f} fps" if prog.fps_current > 0 else ""
        self._progress_lbl.setText(f"{prog.frames_done}/{prog.total_frames}{fps_str}  {eta}")
        self._debug_panel.update_progress(prog)

    def _on_complete(self, prog) -> None:
        QTimer.singleShot(0, lambda: self._handle_completion(prog))

    def _handle_completion(self, prog) -> None:
        self._is_processing = False
        self._encode_btn.setEnabled(bool(self._input_path))
        self._cancel_btn.setEnabled(False)

        if prog.cancelled:
            self._status_msg.setText("Encoding cancelled.")
            self._debug_panel.log("Encoding cancelled.")
        elif prog.error:
            self._status_msg.setText(f"Error: {prog.error}")
            self._debug_panel.log(f"Error: {prog.error}", error=True)
            QMessageBox.critical(self, "Encoding Error", prog.error)
        else:
            out = self._output_edit.text()
            self._progress_bar.setValue(100)
            self._status_msg.setText(f"Done! → {os.path.basename(out)}")
            self._debug_panel.log(f"Complete! Saved to: {out}")
            QMessageBox.information(self, "Done", f"Encoding complete!\n\nSaved to:\n{out}")

    def _apply_preset(self, key: str) -> None:
        presets = self._config.get_all_presets()
        if key in presets:
            self._profile = presets[key]
            self._settings_panel.load_profile(self._profile)
            self._preview_panel.update_profile(self._profile, self._active_plugins)
            self._debug_panel.log(f"Preset applied: {self._profile.name}")

    def _toggle_debug(self) -> None:
        # Find debug tab
        for widget_idx in range(self.centralWidget().findChild(
            __import__("PyQt6.QtWidgets", fromlist=["QTabWidget"]).QTabWidget
        ).count()):
            pass  # just focus debug tab
        self._debug_panel.log("Debug panel toggled")

    def _check_gpu(self) -> None:
        import subprocess
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=5
            )
            has_nvenc = "h264_nvenc" in result.stdout
            if has_nvenc:
                self._gpu_indicator.setText("GPU: NVENC ✓")
                self._gpu_indicator.setStyleSheet(f"color: {ACCENT}; font-size: 10px;")
            else:
                self._gpu_indicator.setText("GPU: CPU only")
                self._gpu_indicator.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        except Exception:
            self._gpu_indicator.setText("GPU: N/A")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About ASCII Video Converter",
            """<h3>ASCII Video Converter v1.0</h3>
<p>High-performance ASCII art video generator.</p>
<ul>
<li>OpenCV frame processing</li>
<li>FFmpeg encoding (CPU/GPU)</li>
<li>PyQt6 dark-mode UI</li>
<li>Plugin-based filter pipeline</li>
<li>Preset profiles</li>
<li>Batch processing</li>
</ul>
<p>Built with Python 3.11+, OpenCV, NumPy, Pillow, PyQt6.</p>"""
        )

    # ─── Window Events ─────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._is_processing:
            reply = QMessageBox.question(
                self, "Processing Active",
                "Encoding is in progress. Cancel and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self._pipeline:
                self._pipeline.cancel()

        self._config.set("window_width", self.width())
        self._config.set("window_height", self.height())
        self._config.set("window_maximized", self.isMaximized())
        self._config.save()
        event.accept()
