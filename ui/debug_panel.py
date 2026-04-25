"""
Debug / Benchmark Panel
=======================
Displays real-time processing metrics, system stats, and bottleneck analysis.
"""

from __future__ import annotations
import time
import logging
from collections import deque
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QGridLayout, QProgressBar
)
from ui.widgets import StatCard, SectionHeader
from ui.styles import ACCENT, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_MUTED, RED, TEXT_PRIMARY

logger = logging.getLogger(__name__)


class DebugPanel(QWidget):
    """Live stats display updated via update_stats()."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fps_history: deque[float] = deque(maxlen=60)
        self._start_time = time.time()
        self._log_lines: list[str] = []
        self._build_ui()
        self._sys_timer = QTimer(self)
        self._sys_timer.timeout.connect(self._update_sys)
        self._sys_timer.start(1000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(SectionHeader("Debug / Benchmark", "⚡"))

        # ── Processing stats ──────────────────────────
        grid = QGridLayout()
        grid.setSpacing(6)

        self._stat_fps = StatCard("Proc FPS", "—")
        self._stat_eta = StatCard("ETA", "—")
        self._stat_cpu = StatCard("CPU", "—")
        self._stat_mem = StatCard("RAM", "—")
        self._stat_gpu = StatCard("GPU", "N/A")
        self._stat_frames = StatCard("Frames", "0/0")

        grid.addWidget(self._stat_fps, 0, 0)
        grid.addWidget(self._stat_eta, 0, 1)
        grid.addWidget(self._stat_cpu, 0, 2)
        grid.addWidget(self._stat_mem, 1, 0)
        grid.addWidget(self._stat_gpu, 1, 1)
        grid.addWidget(self._stat_frames, 1, 2)
        layout.addLayout(grid)

        # ── Progress bar ──────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p% — %v frames")
        layout.addWidget(self._progress)

        # ── Stage indicator ───────────────────────────
        stage_row = QHBoxLayout()
        stage_row.addWidget(QLabel("Stage:"))
        self._stage_lbl = QLabel("Idle")
        self._stage_lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold;")
        stage_row.addWidget(self._stage_lbl)
        stage_row.addStretch()
        layout.addLayout(stage_row)

        # ── Bottleneck analyzer ───────────────────────
        layout.addWidget(SectionHeader("Bottleneck Analysis", "⊗"))
        self._bottleneck_lbl = QLabel("No active job")
        self._bottleneck_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self._bottleneck_lbl.setWordWrap(True)
        layout.addWidget(self._bottleneck_lbl)

        # ── Log output ────────────────────────────────
        layout.addWidget(SectionHeader("Log Output", "▤"))
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(160)
        self._log_view.setStyleSheet(f"""
            QTextEdit {{
                background: #050508;
                color: #88ff88;
                font-family: 'JetBrains Mono', 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._log_view)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._log_view.clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

    # ─── Public API ───────────────────────────────────────────────────────────

    def update_progress(self, prog) -> None:
        """Update from a PipelineProgress object."""
        self._stage_lbl.setText(prog.stage.replace("_", " ").title())

        if prog.total_frames > 0:
            pct = int(prog.frames_done / prog.total_frames * 100)
            self._progress.setMaximum(prog.total_frames)
            self._progress.setValue(prog.frames_done)
            self._progress.setFormat(f"{pct}% — {prog.frames_done}/{prog.total_frames} frames")
        
        if prog.fps_current > 0:
            self._stat_fps.update_value(f"{prog.fps_current:.1f}")
            self._fps_history.append(prog.fps_current)
        
        if prog.eta_seconds > 0:
            m, s = divmod(int(prog.eta_seconds), 60)
            self._stat_eta.update_value(f"{m}:{s:02d}")
        
        if prog.cpu_pct > 0:
            self._stat_cpu.update_value(f"{prog.cpu_pct:.0f}%")
        
        if prog.mem_mb > 0:
            self._stat_mem.update_value(f"{prog.mem_mb:.0f}MB")
        
        self._stat_frames.update_value(f"{prog.frames_done}/{prog.total_frames}")

        # Bottleneck analysis
        self._analyze_bottleneck(prog)

        if prog.error:
            self.log(f"[ERROR] {prog.error}", error=True)
        if prog.completed:
            self.log("[DONE] Encoding complete!")
            self._progress.setValue(self._progress.maximum())

    def reset(self) -> None:
        self._progress.setValue(0)
        self._stage_lbl.setText("Idle")
        self._stat_fps.update_value("—")
        self._stat_eta.update_value("—")
        self._stat_frames.update_value("0/0")
        self._bottleneck_lbl.setText("No active job")
        self._fps_history.clear()

    def log(self, msg: str, error: bool = False) -> None:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        color = "#ff4444" if error else "#88ff88"
        self._log_view.append(f'<span style="color:{color}">[{ts}] {msg}</span>')

    # ─── Private ──────────────────────────────────────────────────────────────

    def _update_sys(self) -> None:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            self._stat_cpu.update_value(f"{cpu:.0f}%")
            self._stat_mem.update_value(f"{mem.used/(1024**2):.0f}MB")
        except ImportError:
            pass

    def _analyze_bottleneck(self, prog) -> None:
        tips = []
        if prog.fps_current > 0 and prog.fps_current < 5:
            tips.append("⚠ Very low FPS — consider increasing frame skip or reducing width")
        if prog.cpu_pct > 90:
            tips.append("⚠ CPU at limit — reduce worker threads or enable GPU")
        if prog.mem_mb > 2000:
            tips.append("⚠ High RAM usage — large frames or long videos may cause issues")
        if not tips:
            if prog.fps_current > 0:
                tips.append(f"✓ Processing at {prog.fps_current:.1f} fps — no bottlenecks detected")
            else:
                tips.append("No active job")
        self._bottleneck_lbl.setText("\n".join(tips))
