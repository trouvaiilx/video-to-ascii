"""
Settings Panel — all render configuration controls.
Emits profile_changed(RenderProfile) whenever any control changes.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit,
    QPushButton, QScrollArea, QFrame, QRadioButton, QButtonGroup,
    QSizePolicy, QSlider
)
from presets.profiles import RenderProfile, PRESETS
from ui.widgets import LabeledSlider, SectionHeader
from ui.styles import ACCENT, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_PRIMARY, TEXT_MUTED


class SettingsPanel(QScrollArea):
    """
    Scrollable settings panel.
    All control changes immediately update self._profile and emit profile_changed.
    """
    profile_changed = pyqtSignal(object)  # RenderProfile

    def __init__(self, profile: RenderProfile, config_manager=None, parent=None) -> None:
        super().__init__(parent)
        self._profile = profile
        self._config = config_manager
        self._updating = False

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self.setWidget(container)

        self._build_preset_section()
        self._build_ramp_section()
        self._build_resolution_section()
        self._build_image_section()
        self._build_edge_section()
        self._build_dither_section()
        self._build_color_section()
        self._build_font_section()
        self._build_temporal_section()
        self._build_output_section()

        self._layout.addStretch()
        self.load_profile(profile)

    # ─── Section Builders ─────────────────────────────────────────────────────

    def _build_preset_section(self) -> None:
        self._layout.addWidget(SectionHeader("Presets", "◈"))

        row = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._refresh_presets()
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        row.addWidget(self._preset_combo, 1)

        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(52)
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)
        self._layout.addLayout(row)

    def _build_ramp_section(self) -> None:
        self._layout.addWidget(SectionHeader("Character Ramp", "▓"))

        self._ramp_combo = QComboBox()
        self._ramp_combo.addItems([
            " .:-=+*#%@",
            " `·.,;:!|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
            " .:#@",
            " .:;=+#@",
            "@%#*+=-:. ",
        ])
        self._ramp_combo.currentTextChanged.connect(self._on_ramp_changed)
        self._layout.addWidget(self._ramp_combo)

        self._custom_ramp_chk = QCheckBox("Use Custom Ramp")
        self._custom_ramp_chk.toggled.connect(self._on_custom_ramp_toggled)
        self._layout.addWidget(self._custom_ramp_chk)

        self._custom_ramp_edit = QLineEdit()
        self._custom_ramp_edit.setPlaceholderText("Enter custom characters (dark→light)")
        self._custom_ramp_edit.textChanged.connect(self._on_custom_ramp_changed)
        self._custom_ramp_edit.setEnabled(False)
        self._layout.addWidget(self._custom_ramp_edit)

    def _build_resolution_section(self) -> None:
        self._layout.addWidget(SectionHeader("Resolution", "⊞"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Width (cols):"))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(20, 500)
        self._width_spin.setValue(120)
        self._width_spin.valueChanged.connect(self._emit)
        row.addWidget(self._width_spin)
        self._layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Height (rows, 0=auto):"))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(0, 300)
        self._height_spin.setValue(0)
        self._height_spin.valueChanged.connect(self._emit)
        row2.addWidget(self._height_spin)
        self._layout.addLayout(row2)

        self._aspect_chk = QCheckBox("Maintain Aspect Ratio")
        self._aspect_chk.setChecked(True)
        self._aspect_chk.toggled.connect(self._emit)
        self._layout.addWidget(self._aspect_chk)

    def _build_image_section(self) -> None:
        self._layout.addWidget(SectionHeader("Image Adjustments", "◐"))

        self._brightness_slider = LabeledSlider("Brightness", 0.1, 3.0, 1.0, decimals=2)
        self._brightness_slider.value_changed.connect(self._emit)
        self._layout.addWidget(self._brightness_slider)

        self._contrast_slider = LabeledSlider("Contrast", 0.1, 3.0, 1.0, decimals=2)
        self._contrast_slider.value_changed.connect(self._emit)
        self._layout.addWidget(self._contrast_slider)

        self._gamma_slider = LabeledSlider("Gamma", 0.1, 3.0, 1.0, decimals=2)
        self._gamma_slider.value_changed.connect(self._emit)
        self._layout.addWidget(self._gamma_slider)

    def _build_edge_section(self) -> None:
        self._layout.addWidget(SectionHeader("Edge Detection", "⌥"))

        edge_row = QHBoxLayout()
        self._edge_group = QButtonGroup()
        for label, val in [("Off", "none"), ("Canny", "canny"), ("Sobel", "sobel")]:
            rb = QRadioButton(label)
            rb.setProperty("edge_val", val)
            self._edge_group.addButton(rb)
            edge_row.addWidget(rb)
            if val == "none":
                rb.setChecked(True)
        self._edge_group.buttonToggled.connect(self._emit)
        self._layout.addLayout(edge_row)

        self._canny_low = LabeledSlider("Canny Low", 0, 255, 50, decimals=0)
        self._canny_low.value_changed.connect(self._emit)
        self._layout.addWidget(self._canny_low)

        self._canny_high = LabeledSlider("Canny High", 0, 255, 150, decimals=0)
        self._canny_high.value_changed.connect(self._emit)
        self._layout.addWidget(self._canny_high)

        self._edge_weight = LabeledSlider("Edge Weight", 0.0, 1.0, 0.5, decimals=2)
        self._edge_weight.value_changed.connect(self._emit)
        self._layout.addWidget(self._edge_weight)

        row = QHBoxLayout()
        row.addWidget(QLabel("Sobel Ksize:"))
        self._sobel_ksize = QSpinBox()
        self._sobel_ksize.setRange(1, 15)
        self._sobel_ksize.setSingleStep(2)
        self._sobel_ksize.setValue(3)
        self._sobel_ksize.valueChanged.connect(self._emit)
        row.addWidget(self._sobel_ksize)
        self._layout.addLayout(row)

    def _build_dither_section(self) -> None:
        self._layout.addWidget(SectionHeader("Dithering", "⣿"))
        self._dither_chk = QCheckBox("Floyd–Steinberg Dithering")
        self._dither_chk.toggled.connect(self._emit)
        self._layout.addWidget(self._dither_chk)

    def _build_color_section(self) -> None:
        self._layout.addWidget(SectionHeader("Colorization", "◉"))
        self._color_chk = QCheckBox("Colorized ASCII")
        self._color_chk.toggled.connect(self._emit)
        self._layout.addWidget(self._color_chk)

        row = QHBoxLayout()
        row.addWidget(QLabel("Color Mode:"))
        self._color_mode = QComboBox()
        self._color_mode.addItems(["rgb_image", "ansi", "terminal_256"])
        self._color_mode.currentTextChanged.connect(self._emit)
        row.addWidget(self._color_mode)
        self._layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("BG:"))
        self._bg_color = QLineEdit("#000000")
        self._bg_color.setMaximumWidth(80)
        self._bg_color.textChanged.connect(self._emit)
        row2.addWidget(self._bg_color)
        row2.addWidget(QLabel("FG:"))
        self._fg_color = QLineEdit("#00FF00")
        self._fg_color.setMaximumWidth(80)
        self._fg_color.textChanged.connect(self._emit)
        row2.addWidget(self._fg_color)
        row2.addStretch()
        self._layout.addLayout(row2)

    def _build_font_section(self) -> None:
        self._layout.addWidget(SectionHeader("Font", "Aa"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Font:"))
        self._font_combo = QComboBox()
        self._font_combo.addItems([
            "Courier New", "Consolas", "Fira Code", "JetBrains Mono",
            "DejaVu Sans Mono", "Lucida Console", "Cascadia Code"
        ])
        self._font_combo.currentTextChanged.connect(self._emit)
        row.addWidget(self._font_combo)
        self._layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Font Size:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(6, 32)
        self._font_size.setValue(10)
        self._font_size.valueChanged.connect(self._emit)
        row2.addWidget(self._font_size)
        self._layout.addLayout(row2)

    def _build_temporal_section(self) -> None:
        self._layout.addWidget(SectionHeader("Temporal", "⏱"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Frame Skip:"))
        self._frame_skip = QSpinBox()
        self._frame_skip.setRange(0, 30)
        self._frame_skip.setValue(0)
        self._frame_skip.valueChanged.connect(self._emit)
        row.addWidget(self._frame_skip)
        self._layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Target FPS (0=src):"))
        self._target_fps = QDoubleSpinBox()
        self._target_fps.setRange(0, 120)
        self._target_fps.setValue(0)
        self._target_fps.setSingleStep(1.0)
        self._target_fps.valueChanged.connect(self._emit)
        row2.addWidget(self._target_fps)
        self._layout.addLayout(row2)

    def _build_output_section(self) -> None:
        self._layout.addWidget(SectionHeader("Output", "▤"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Format:"))
        self._output_format = QComboBox()
        self._output_format.addItems(["mp4", "gif", "image_seq", "txt_stream"])
        self._output_format.currentTextChanged.connect(self._emit)
        row.addWidget(self._output_format)
        self._layout.addLayout(row)

        self._quality_slider = LabeledSlider("Quality (CRF, lower=better)", 0, 51, 23, decimals=0)
        self._quality_slider.value_changed.connect(self._emit)
        self._layout.addWidget(self._quality_slider)

        self._gpu_chk = QCheckBox("GPU Acceleration (NVENC/CUDA if available)")
        self._gpu_chk.toggled.connect(self._emit)
        self._layout.addWidget(self._gpu_chk)

    # ─── Profile I/O ──────────────────────────────────────────────────────────

    def load_profile(self, profile: RenderProfile) -> None:
        """Populate all controls from a profile without emitting."""
        self._updating = True
        try:
            self._profile = profile

            # Ramp
            ramp_idx = self._ramp_combo.findText(profile.char_ramp)
            if ramp_idx >= 0:
                self._ramp_combo.setCurrentIndex(ramp_idx)
            self._custom_ramp_chk.setChecked(profile.use_custom_ramp)
            self._custom_ramp_edit.setText(profile.custom_ramp)
            self._custom_ramp_edit.setEnabled(profile.use_custom_ramp)

            # Resolution
            self._width_spin.setValue(profile.width)
            self._height_spin.setValue(profile.height)
            self._aspect_chk.setChecked(profile.maintain_aspect)

            # Image
            self._brightness_slider.set_value(profile.brightness)
            self._contrast_slider.set_value(profile.contrast)
            self._gamma_slider.set_value(profile.gamma)

            # Edge
            for btn in self._edge_group.buttons():
                if btn.property("edge_val") == profile.edge_detection:
                    btn.setChecked(True)
            self._canny_low.set_value(profile.canny_low)
            self._canny_high.set_value(profile.canny_high)
            self._edge_weight.set_value(profile.edge_weight)
            self._sobel_ksize.setValue(profile.sobel_ksize)

            # Dither
            self._dither_chk.setChecked(profile.dithering)

            # Color
            self._color_chk.setChecked(profile.colorized)
            idx = self._color_mode.findText(profile.color_mode)
            if idx >= 0:
                self._color_mode.setCurrentIndex(idx)
            self._bg_color.setText(profile.output_bg_color)
            self._fg_color.setText(profile.output_fg_color)

            # Font
            fidx = self._font_combo.findText(profile.font_family)
            if fidx >= 0:
                self._font_combo.setCurrentIndex(fidx)
            self._font_size.setValue(profile.font_size)

            # Temporal
            self._frame_skip.setValue(profile.frame_skip)
            self._target_fps.setValue(profile.target_fps)

            # Output
            oidx = self._output_format.findText(profile.output_format)
            if oidx >= 0:
                self._output_format.setCurrentIndex(oidx)
            self._quality_slider.set_value(profile.output_quality)
            self._gpu_chk.setChecked(profile.use_gpu)
        finally:
            self._updating = False

    def _read_profile(self) -> RenderProfile:
        """Read all controls and build a new RenderProfile."""
        edge_val = "none"
        for btn in self._edge_group.buttons():
            if btn.isChecked():
                edge_val = btn.property("edge_val")
                break

        ramp = self._ramp_combo.currentText()

        return RenderProfile(
            name=self._profile.name,
            description=self._profile.description,
            char_ramp=ramp,
            custom_ramp=self._custom_ramp_edit.text(),
            use_custom_ramp=self._custom_ramp_chk.isChecked(),
            width=self._width_spin.value(),
            height=self._height_spin.value(),
            maintain_aspect=self._aspect_chk.isChecked(),
            brightness=self._brightness_slider.get_value(),
            contrast=self._contrast_slider.get_value(),
            gamma=self._gamma_slider.get_value(),
            edge_detection=edge_val,
            canny_low=int(self._canny_low.get_value()),
            canny_high=int(self._canny_high.get_value()),
            edge_weight=self._edge_weight.get_value(),
            sobel_ksize=self._sobel_ksize.value(),
            dithering=self._dither_chk.isChecked(),
            colorized=self._color_chk.isChecked(),
            color_mode=self._color_mode.currentText(),
            font_family=self._font_combo.currentText(),
            font_size=self._font_size.value(),
            frame_skip=self._frame_skip.value(),
            target_fps=self._target_fps.value(),
            output_format=self._output_format.currentText(),
            output_quality=int(self._quality_slider.get_value()),
            output_bg_color=self._bg_color.text() or "#000000",
            output_fg_color=self._fg_color.text() or "#00FF00",
            use_gpu=self._gpu_chk.isChecked(),
        )

    def _emit(self, *_) -> None:
        if self._updating:
            return
        self._profile = self._read_profile()
        self.profile_changed.emit(self._profile)

    def _on_ramp_changed(self, text: str) -> None:
        if not self._custom_ramp_chk.isChecked():
            self._emit()

    def _on_custom_ramp_toggled(self, checked: bool) -> None:
        self._custom_ramp_edit.setEnabled(checked)
        self._emit()

    def _on_custom_ramp_changed(self, text: str) -> None:
        if self._custom_ramp_chk.isChecked():
            self._emit()

    def _on_preset_selected(self, idx: int) -> None:
        if self._updating:
            return
        key = self._preset_combo.itemData(idx)
        if key and self._config:
            presets = self._config.get_all_presets()
            if key in presets:
                self.load_profile(presets[key])
                self._profile = presets[key]
                self.profile_changed.emit(self._profile)

    def _save_preset(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name and self._config:
            import re
            key = re.sub(r"[^a-z0-9_]", "_", name.lower())
            profile = self._read_profile()
            profile.name = name
            self._config.save_custom_preset(key, profile)
            self._refresh_presets()

    def _refresh_presets(self) -> None:
        self._updating = True
        self._preset_combo.clear()
        presets = self._config.get_all_presets() if self._config else PRESETS
        for key, p in presets.items():
            self._preset_combo.addItem(p.name, key)
        self._updating = False

    def get_profile(self) -> RenderProfile:
        return self._profile
