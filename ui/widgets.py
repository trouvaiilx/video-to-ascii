"""
Reusable UI widgets:
  - DropZone: drag-and-drop video input
  - VideoPreviewLabel: OpenCV frame → QLabel
  - LabeledSlider: slider + live spinbox + reset button
  - StatCard: metric display card
  - SectionHeader: styled section title (non-collapsible divider)
  - CollapsibleSection: toggle-able settings group
"""

from __future__ import annotations
import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QImage, QPixmap, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QSlider,
    QDoubleSpinBox, QSpinBox, QFrame, QSizePolicy, QPushButton,
    QScrollArea
)
import numpy as np
from ui.styles import (
    ACCENT, ACCENT_DIM, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_MUTED,
    BG_RAISED, TEXT_PRIMARY, BG_HOVER, BG_BASE
)


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mts"}


# ── Drop Zone ──────────────────────────────────────────────────────────────────

class DropZone(QLabel):
    """Accepts dragged video files and emits file_dropped(path)."""
    file_dropped = pyqtSignal(str)

    def __init__(self, compact: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._compact = compact
        self.setAcceptDrops(True)
        self._file_path = ""
        self._update_text()
        if compact:
            self.setMinimumHeight(36)
            self.setMaximumHeight(40)
        else:
            self.setMinimumHeight(80)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)

    def set_file(self, path: str) -> None:
        self._file_path = path
        fname = os.path.basename(path)
        if self._compact:
            self.setText(f"▶  {fname}")
        else:
            self.setText(f"▶  {fname}\n{path}")
        self._update_style(True)

    def clear_file(self) -> None:
        self._file_path = ""
        self._update_text()
        self._update_style(False)

    def _update_text(self) -> None:
        if self._compact:
            self.setText("◈  Drop video or click Browse")
        else:
            self.setText("◈  Drop video file here\nor click Browse…")

    def _update_style(self, has_file: bool, hover: bool = False) -> None:
        if hover:
            border_color = ACCENT
            bg = BG_SURFACE
            color = ACCENT
        elif has_file:
            border_color = ACCENT
            bg = BG_RAISED
            color = ACCENT
        else:
            border_color = BORDER
            bg = BG_SURFACE
            color = TEXT_SECONDARY

        padding = "8px 12px" if self._compact else "16px"
        font_size = "12px" if self._compact else "13px"
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                border: 2px dashed {border_color};
                border-radius: 6px;
                color: {color};
                font-size: {font_size};
                padding: {padding};
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls()]
            if any(os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS for p in paths):
                event.acceptProposedAction()
                self._update_style(False, hover=True)
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._update_style(bool(self._file_path))

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        for p in paths:
            if os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS:
                self.set_file(p)
                self.file_dropped.emit(p)
                break
        self._update_style(bool(self._file_path))


# ── Video Preview Label ────────────────────────────────────────────────────────

class VideoPreviewLabel(QLabel):
    """Displays OpenCV BGR frames as a QLabel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.setText("No Preview")
        self.setStyleSheet(f"""
            QLabel {{
                background: #050508;
                border: 1px solid {BORDER};
                border-radius: 4px;
                color: {TEXT_MUTED};
                font-size: 13px;
            }}
        """)

    def display_frame(self, bgr_frame: np.ndarray) -> None:
        if bgr_frame is None:
            self._show_placeholder()
            return
        h, w, ch = bgr_frame.shape
        bytes_per_line = ch * w
        rgb = bgr_frame[:, :, ::-1].copy()
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setStyleSheet(f"background: #000; border: 1px solid {BORDER}; border-radius: 4px;")


# ── Labeled Slider ─────────────────────────────────────────────────────────────

class LabeledSlider(QWidget):
    """
    Horizontal slider with:
      - Label on the left
      - Live spinbox on the right for direct input
      - Reset button (↺) to restore default
    """
    value_changed = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default: float,
        decimals: int = 2,
        step: float | None = None,
        tooltip: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._decimals = decimals
        self._scale = 10 ** decimals
        self._default = default
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)

        # ── Header row ───────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(4)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        if tooltip:
            self._lbl.setToolTip(tooltip)
            self.setToolTip(tooltip)
        header.addWidget(self._lbl)
        header.addStretch()

        # Spinbox (doubles as value display + direct input)
        spin_step = step if step is not None else (0.1 if decimals > 0 else 1.0)
        if decimals > 0:
            self._spinbox: QDoubleSpinBox | QSpinBox = QDoubleSpinBox()
            self._spinbox.setDecimals(decimals)
            self._spinbox.setSingleStep(spin_step)
        else:
            self._spinbox = QSpinBox()
            self._spinbox.setSingleStep(int(spin_step))
        self._spinbox.setRange(min_val, max_val)
        self._spinbox.setValue(default)
        self._spinbox.setFixedWidth(72)
        self._spinbox.setToolTip("Type a value directly, or use ↑↓ keys")
        self._spinbox.setStyleSheet(f"""
            QDoubleSpinBox, QSpinBox {{
                background: {BG_RAISED};
                border: 1px solid {BORDER};
                border-radius: 3px;
                padding: 1px 2px;
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                font-family: 'JetBrains Mono', monospace;
            }}
            QDoubleSpinBox:focus, QSpinBox:focus {{
                border-color: {ACCENT};
            }}
        """)
        self._spinbox.valueChanged.connect(self._on_spinbox)
        header.addWidget(self._spinbox)

        # Reset button
        self._reset_btn = QPushButton("↺")
        self._reset_btn.setFixedSize(20, 20)
        self._reset_btn.setToolTip(f"Reset to default ({default})")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_MUTED};
                border: none;
                font-size: 13px;
                padding: 0;
            }}
            QPushButton:hover {{ color: {ACCENT}; }}
            QPushButton:pressed {{ color: #fff; }}
        """)
        self._reset_btn.clicked.connect(self._reset)
        header.addWidget(self._reset_btn)

        layout.addLayout(header)

        # ── Slider ───────────────────────────────────────────────────
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(int(min_val * self._scale))
        self._slider.setMaximum(int(max_val * self._scale))
        self._slider.setValue(int(default * self._scale))
        self._slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self._slider)

    # ── Slots ────────────────────────────────────────────────────────

    def _on_slider(self, int_val: int) -> None:
        if self._updating:
            return
        val = int_val / self._scale
        self._updating = True
        self._spinbox.setValue(int(val) if self._decimals == 0 else val)
        self._updating = False
        self.value_changed.emit(val)

    def _on_spinbox(self, val) -> None:
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(int(float(val) * self._scale))
        self._updating = False
        self.value_changed.emit(float(val))

    def _reset(self) -> None:
        self.set_value(self._default)
        self.value_changed.emit(float(self._default))

    # ── Public API ───────────────────────────────────────────────────

    def get_value(self) -> float:
        return self._slider.value() / self._scale

    def set_value(self, val: float) -> None:
        self._updating = True
        self._slider.setValue(int(float(val) * self._scale))
        self._spinbox.setValue(int(val) if self._decimals == 0 else float(val))
        self._updating = False


# ── Section Header (non-collapsible divider) ───────────────────────────────────

class SectionHeader(QWidget):
    """Styled section divider with optional icon prefix."""

    def __init__(self, text: str, icon: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(6)

        if icon:
            ic = QLabel(icon)
            ic.setStyleSheet(f"color: {ACCENT}; font-size: 14px;")
            layout.addWidget(ic)

        lbl = QLabel(text.upper())
        lbl.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1.2px;
        """)
        layout.addWidget(lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
        layout.addWidget(line, 1)


# ── Collapsible Section ────────────────────────────────────────────────────────

class CollapsibleSection(QWidget):
    """
    A settings group that can be toggled open/closed.
    Usage:
        sec = CollapsibleSection("Resolution", icon="⊞")
        sec.add_widget(some_widget)
        sec.add_layout(some_layout)
    """

    def __init__(
        self,
        title: str,
        icon: str = "",
        collapsed: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._collapsed = collapsed
        self._title = title
        self._icon = icon

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 0)
        outer.setSpacing(0)

        # Toggle header button
        self._btn = QPushButton()
        self._btn.setCheckable(True)
        self._btn.setChecked(not collapsed)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._on_toggle)
        self._refresh_btn()
        outer.addWidget(self._btn)

        # Content area
        self._content = QWidget()
        self._content.setObjectName("collapsible_content")
        self._content.setStyleSheet(f"""
            QWidget#collapsible_content {{
                background: transparent;
                border-left: 2px solid {BORDER};
                margin-left: 6px;
            }}
        """)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 6, 0, 8)
        self._content_layout.setSpacing(6)
        self._content.setVisible(not collapsed)
        outer.addWidget(self._content)

    def _refresh_btn(self) -> None:
        arrow = "▼" if not self._collapsed else "▶"
        icon_part = f"  {self._icon}" if self._icon else ""
        self._btn.setText(f"  {arrow}{icon_part}  {self._title.upper()}")
        checked_color = ACCENT if not self._collapsed else TEXT_SECONDARY
        self._btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: {BG_RAISED};
                color: {checked_color};
                border: none;
                border-top: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                padding: 7px 8px;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
                font-family: 'JetBrains Mono', monospace;
            }}
            QPushButton:hover {{
                color: {ACCENT};
                background: {BG_HOVER};
                border-color: {ACCENT_DIM};
            }}
        """)

    def _on_toggle(self, checked: bool) -> None:
        self._collapsed = not checked
        self._content.setVisible(checked)
        self._refresh_btn()

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._content_layout.addLayout(layout)

    @property
    def content_layout(self):
        return self._content_layout

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._btn.setChecked(not collapsed)
        self._content.setVisible(not collapsed)
        self._refresh_btn()


# ── Stat Card ──────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    """Small metric display: label + big value."""

    def __init__(self, label: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setMinimumWidth(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 9px; letter-spacing: 0.8px;"
        )
        self._val = QLabel(value)
        self._val.setStyleSheet(
            f"color: {ACCENT}; font-size: 15px; font-weight: bold;"
            f" font-family: 'JetBrains Mono', monospace;"
        )
        self._val.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._lbl)
        layout.addWidget(self._val)

    def update_value(self, value: str) -> None:
        self._val.setText(value)
