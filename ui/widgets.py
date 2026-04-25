"""
Reusable UI widgets:
  - DropZone: drag-and-drop video input
  - VideoPreviewLabel: OpenCV frame → QLabel
  - LabeledSlider: slider + value display
  - StatCard: metric display card
  - SectionHeader: styled section title
"""

from __future__ import annotations
import os
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QSize, QTimer
from PyQt6.QtGui import QImage, QPixmap, QDragEnterEvent, QDropEvent, QFont, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QHBoxLayout, QSlider,
    QDoubleSpinBox, QSpinBox, QFrame, QSizePolicy
)
import numpy as np
from ui.styles import ACCENT, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_MUTED, BG_RAISED, TEXT_PRIMARY


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mts"}


class DropZone(QLabel):
    """Accepts dragged video files and emits file_dropped(path)."""
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._active = False
        self._file_path = ""
        self._update_text()
        self.setMinimumHeight(120)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)

    def set_file(self, path: str) -> None:
        self._file_path = path
        fname = os.path.basename(path)
        self.setText(f"▶  {fname}\n\n{path}")
        self._update_style(True)

    def _update_text(self) -> None:
        self.setText("◈  Drop video here\nor click Browse")

    def _update_style(self, has_file: bool) -> None:
        border_color = ACCENT if has_file else BORDER
        bg = BG_RAISED if has_file else BG_SURFACE
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                border: 2px dashed {border_color};
                border-radius: 8px;
                color: {"" + ACCENT if has_file else TEXT_SECONDARY};
                font-size: 13px;
                padding: 16px;
                line-height: 1.6;
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls()]
            if any(os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS for p in paths):
                event.acceptProposedAction()
                self._update_style_hover()
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

    def _update_style_hover(self) -> None:
        self.setStyleSheet(f"""
            QLabel {{
                background: {BG_SURFACE};
                border: 2px dashed {ACCENT};
                border-radius: 8px;
                color: {ACCENT};
                font-size: 13px;
                padding: 16px;
            }}
        """)


class VideoPreviewLabel(QLabel):
    """Displays OpenCV BGR frames as a QLabel."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: #000; border: 1px solid {BORDER}; border-radius: 4px;")
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
        """Convert BGR numpy array to QPixmap and display."""
        if bgr_frame is None:
            self._show_placeholder()
            return
        h, w, ch = bgr_frame.shape
        bytes_per_line = ch * w
        # Convert BGR→RGB
        rgb = bgr_frame[:, :, ::-1].copy()
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        # Scale to fit label while maintaining aspect
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setStyleSheet(f"background: #000; border: 1px solid {BORDER}; border-radius: 4px;")


class LabeledSlider(QWidget):
    """Horizontal slider with label and numeric spinbox."""
    value_changed = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        min_val: float,
        max_val: float,
        default: float,
        decimals: int = 2,
        step: float = 0.01,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._decimals = decimals
        self._scale = 10 ** decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        self._label = QLabel(label)
        self._label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self._value_label = QLabel(f"{default:.{decimals}f}")
        self._value_label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        header.addWidget(self._label)
        header.addStretch()
        header.addWidget(self._value_label)
        layout.addLayout(header)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(int(min_val * self._scale))
        self._slider.setMaximum(int(max_val * self._scale))
        self._slider.setValue(int(default * self._scale))
        self._slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self._slider)

    def _on_slider(self, int_val: int) -> None:
        val = int_val / self._scale
        self._value_label.setText(f"{val:.{self._decimals}f}")
        self.value_changed.emit(val)

    def get_value(self) -> float:
        return self._slider.value() / self._scale

    def set_value(self, val: float) -> None:
        self._slider.setValue(int(val * self._scale))


class StatCard(QFrame):
    """Small metric display: label + big value."""

    def __init__(self, label: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setMinimumWidth(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px; letter-spacing: 0.8px;")
        self._val = QLabel(value)
        self._val.setStyleSheet(f"color: {ACCENT}; font-size: 16px; font-weight: bold; font-family: 'JetBrains Mono', monospace;")
        self._val.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._lbl)
        layout.addWidget(self._val)

    def update_value(self, value: str) -> None:
        self._val.setText(value)


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
