"""
Batch Processing Panel
======================
Queue multiple videos for processing with a shared profile.
"""

from __future__ import annotations
import os
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QProgressBar, QLineEdit,
    QFrame, QMessageBox
)
from ui.widgets import SectionHeader
from ui.styles import ACCENT, TEXT_SECONDARY, BORDER, TEXT_MUTED, RED, BG_SURFACE, TEXT_PRIMARY


class BatchItem(QListWidgetItem):
    def __init__(self, path: str) -> None:
        super().__init__(os.path.basename(path))
        self.path = path
        self.status = "queued"  # queued | processing | done | error
        self._update_icon()

    def set_status(self, status: str, detail: str = "") -> None:
        self.status = status
        icons = {"queued": "○", "processing": "◎", "done": "✓", "error": "✗"}
        icon = icons.get(status, "?")
        name = os.path.basename(self.path)
        self.setText(f"{icon}  {name}  {detail}")
        self._update_icon()

    def _update_icon(self) -> None:
        colors = {
            "queued": TEXT_SECONDARY,
            "processing": ACCENT,
            "done": "#44ff44",
            "error": RED,
        }
        color = colors.get(self.status, TEXT_SECONDARY)
        self.setForeground(__import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(color))


class BatchWorker(QThread):
    item_started = pyqtSignal(int)        # index
    item_progress = pyqtSignal(int, int, int)  # index, done, total
    item_done = pyqtSignal(int, bool, str)   # index, success, msg
    all_done = pyqtSignal()

    def __init__(self, jobs: list[tuple[str, str]], profile, plugins: list) -> None:
        super().__init__()
        self._jobs = jobs
        self._profile = profile
        self._plugins = plugins
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        from core.pipeline import FramePipeline, PipelineProgress
        import threading

        for idx, (inp, out) in enumerate(self._jobs):
            if self._cancelled:
                break
            self.item_started.emit(idx)

            done_event = threading.Event()
            result_holder = [None]

            def _progress(prog: PipelineProgress) -> None:
                self.item_progress.emit(idx, prog.frames_done, max(1, prog.total_frames))

            def _done(prog: PipelineProgress) -> None:
                result_holder[0] = prog
                done_event.set()

            pipeline = FramePipeline(self._profile, self._plugins)
            pipeline.start(inp, out, _progress, _done)
            done_event.wait()

            prog = result_holder[0]
            if prog and prog.completed:
                self.item_done.emit(idx, True, "")
            else:
                err = prog.error if prog else "Unknown error"
                self.item_done.emit(idx, False, err)

        self.all_done.emit()


class BatchPanel(QWidget):
    """Batch processing UI."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._profile = None
        self._plugins: list = []
        self._worker: BatchWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(SectionHeader("Batch Processing", "⚙"))

        # File list
        self._list = QListWidget()
        self._list.setMinimumHeight(180)
        layout.addWidget(self._list)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Files")
        add_btn.clicked.connect(self._add_files)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._list.clear)
        for b in [add_btn, remove_btn, clear_btn]:
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # Output dir
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output Dir:"))
        self._out_dir = QLineEdit()
        self._out_dir.setPlaceholderText("Same as source")
        out_row.addWidget(self._out_dir, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_out)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)

        # Progress
        self._overall_bar = QProgressBar()
        self._overall_bar.setFormat("Overall: %p%")
        layout.addWidget(self._overall_bar)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self._status_lbl)

        # Start/Cancel
        action_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  Start Batch")
        self._start_btn.setProperty("role", "primary")
        self._start_btn.clicked.connect(self._start_batch)
        self._cancel_btn = QPushButton("✕  Cancel")
        self._cancel_btn.setProperty("role", "danger")
        self._cancel_btn.clicked.connect(self._cancel_batch)
        self._cancel_btn.setEnabled(False)
        action_row.addWidget(self._start_btn)
        action_row.addWidget(self._cancel_btn)
        layout.addLayout(action_row)

        layout.addStretch()

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Videos", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv *.m4v);;All (*)"
        )
        for p in paths:
            if not any(self._list.item(i).path == p
                       for i in range(self._list.count())
                       if hasattr(self._list.item(i), "path")):
                self._list.addItem(BatchItem(p))

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    def _browse_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Output Directory")
        if d:
            self._out_dir.setText(d)

    def _start_batch(self) -> None:
        if not self._profile:
            QMessageBox.warning(self, "No Profile", "Configure render settings first.")
            return
        count = self._list.count()
        if count == 0:
            QMessageBox.information(self, "Empty Queue", "Add videos to the batch queue first.")
            return

        out_dir = self._out_dir.text().strip()
        jobs = []
        fmt = self._profile.output_format
        ext_map = {"mp4": ".mp4", "gif": ".gif", "image_seq": "", "txt_stream": ".txt"}
        ext = ext_map.get(fmt, ".mp4")

        for i in range(count):
            item = self._list.item(i)
            if not hasattr(item, "path"):
                continue
            inp = item.path
            base = os.path.splitext(os.path.basename(inp))[0]
            if out_dir:
                if fmt == "image_seq":
                    out = os.path.join(out_dir, f"{base}_ascii")
                else:
                    out = os.path.join(out_dir, f"{base}_ascii{ext}")
            else:
                src_dir = os.path.dirname(inp)
                if fmt == "image_seq":
                    out = os.path.join(src_dir, f"{base}_ascii")
                else:
                    out = os.path.join(src_dir, f"{base}_ascii{ext}")
            jobs.append((inp, out))

        self._overall_bar.setMaximum(count)
        self._overall_bar.setValue(0)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        self._worker = BatchWorker(jobs, self._profile, self._plugins)
        self._worker.item_started.connect(self._on_item_started)
        self._worker.item_done.connect(self._on_item_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _cancel_batch(self) -> None:
        if self._worker:
            self._worker.cancel()

    # ─── Slots ────────────────────────────────────────────────────────────────

    @pyqtSlot(int)
    def _on_item_started(self, idx: int) -> None:
        item = self._list.item(idx)
        if item and hasattr(item, "set_status"):
            item.set_status("processing")
        self._status_lbl.setText(f"Processing {idx + 1}/{self._list.count()} …")

    @pyqtSlot(int, bool, str)
    def _on_item_done(self, idx: int, success: bool, msg: str) -> None:
        item = self._list.item(idx)
        if item and hasattr(item, "set_status"):
            item.set_status("done" if success else "error", msg)
        self._overall_bar.setValue(idx + 1)

    @pyqtSlot()
    def _on_all_done(self) -> None:
        self._status_lbl.setText("Batch complete!")
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)

    # ─── Profile sync ─────────────────────────────────────────────────────────

    def update_profile(self, profile) -> None:
        self._profile = profile

    def update_plugins(self, plugins: list) -> None:
        self._plugins = plugins
