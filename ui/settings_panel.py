"""
Settings Panel — all render configuration controls.
Emits profile_changed(RenderProfile) whenever any control changes.

Improvements:
  - Collapsible sections (click header to toggle)
  - Live spinbox next to every slider for direct value entry
  - Reset button (↺) on every slider
  - Tooltips on every control
  - No max-width cap — panel is freely resizable
  - Beginner-friendly labels and inline help text
"""

from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QLineEdit,
    QPushButton, QScrollArea, QFrame, QRadioButton, QButtonGroup,
    QSizePolicy, QSlider, QToolButton
)
from presets.profiles import RenderProfile, PRESETS
from ui.widgets import LabeledSlider, SectionHeader, CollapsibleSection
from ui.styles import ACCENT, TEXT_SECONDARY, BG_SURFACE, BORDER, TEXT_PRIMARY, TEXT_MUTED, BG_RAISED


# ── Helper for uniform form rows ──────────────────────────────────────────────

def _form_row(label_text: str, widget: QWidget, tooltip: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    lbl = QLabel(label_text)
    lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
    lbl.setMinimumWidth(130)
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    if tooltip:
        lbl.setToolTip(tooltip)
        widget.setToolTip(tooltip)
    row.addWidget(lbl)
    row.addWidget(widget, 1)
    return row


# ── Settings Panel ─────────────────────────────────────────────────────────────

class SettingsPanel(QScrollArea):
    """
    Scrollable, collapsible settings panel.
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
        # No max-width — let the splitter control it
        self.setMinimumWidth(280)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(2)
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

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_preset_section(self) -> None:
        sec = CollapsibleSection("Presets", "◈", collapsed=False)

        row = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("Load a saved preset configuration")
        self._refresh_presets()
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        row.addWidget(self._preset_combo, 1)

        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(52)
        save_btn.setToolTip("Save current settings as a new preset")
        save_btn.clicked.connect(self._save_preset)
        row.addWidget(save_btn)

        sec.add_layout(row)
        self._layout.addWidget(sec)

    def _build_ramp_section(self) -> None:
        sec = CollapsibleSection("Character Ramp", "▓", collapsed=False)

        hint = QLabel("Characters used to represent brightness levels (dark → light).")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._ramp_combo = QComboBox()
        self._ramp_combo.setToolTip("Choose a preset character ramp (dark to light)")
        self._ramp_combo.addItems([
            " .:-=+*#%@",
            " `·.,;:!|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
            " .:#@",
            " .:;=+#@",
            "@%#*+=-:. ",
        ])
        self._ramp_combo.currentTextChanged.connect(self._on_ramp_changed)
        sec.add_widget(self._ramp_combo)

        self._custom_ramp_chk = QCheckBox("Use Custom Ramp")
        self._custom_ramp_chk.setToolTip("Override the preset ramp with your own characters")
        self._custom_ramp_chk.toggled.connect(self._on_custom_ramp_toggled)
        sec.add_widget(self._custom_ramp_chk)

        self._custom_ramp_edit = QLineEdit()
        self._custom_ramp_edit.setPlaceholderText("e.g.  .:+#@  (dark → light)")
        self._custom_ramp_edit.setToolTip("Enter characters from darkest (left) to brightest (right)")
        self._custom_ramp_edit.textChanged.connect(self._on_custom_ramp_changed)
        self._custom_ramp_edit.setEnabled(False)
        sec.add_widget(self._custom_ramp_edit)

        self._layout.addWidget(sec)

    def _build_resolution_section(self) -> None:
        sec = CollapsibleSection("Resolution", "⊞", collapsed=False)

        hint = QLabel("Width sets the number of character columns. Height=0 auto-fits the aspect ratio.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(20, 500)
        self._width_spin.setValue(120)
        self._width_spin.setToolTip("Number of ASCII columns in the output (larger = more detail)")
        self._width_spin.valueChanged.connect(self._emit)
        sec.add_layout(_form_row("Width (columns):", self._width_spin,
                                 "Number of ASCII columns (20–500). More columns = higher resolution."))

        self._height_spin = QSpinBox()
        self._height_spin.setRange(0, 300)
        self._height_spin.setValue(0)
        self._height_spin.setToolTip("Number of ASCII rows. Set to 0 to auto-calculate from aspect ratio.")
        self._height_spin.valueChanged.connect(self._emit)
        sec.add_layout(_form_row("Height (rows, 0=auto):", self._height_spin,
                                 "0 = auto-calculate from aspect ratio (recommended)"))

        self._aspect_chk = QCheckBox("Maintain Aspect Ratio")
        self._aspect_chk.setChecked(True)
        self._aspect_chk.setToolTip("Prevent stretching by preserving the original video proportions")
        self._aspect_chk.toggled.connect(self._emit)
        sec.add_widget(self._aspect_chk)

        self._layout.addWidget(sec)

    def _build_image_section(self) -> None:
        sec = CollapsibleSection("Image Adjustments", "◐", collapsed=False)

        hint = QLabel("Tweak brightness/contrast before ASCII conversion. Default is 1.0 for all.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._brightness_slider = LabeledSlider(
            "Brightness", 0.1, 3.0, 1.0, decimals=2,
            tooltip="Multiply frame brightness before mapping to characters (1.0 = no change)"
        )
        self._brightness_slider.value_changed.connect(self._emit)
        sec.add_widget(self._brightness_slider)

        self._contrast_slider = LabeledSlider(
            "Contrast", 0.1, 3.0, 1.0, decimals=2,
            tooltip="Scale frame contrast (1.0 = no change; higher = more harsh contrast)"
        )
        self._contrast_slider.value_changed.connect(self._emit)
        sec.add_widget(self._contrast_slider)

        self._gamma_slider = LabeledSlider(
            "Gamma", 0.1, 3.0, 1.0, decimals=2,
            tooltip="Gamma correction exponent (1.0 = linear; <1.0 = brighter shadows; >1.0 = darker)"
        )
        self._gamma_slider.value_changed.connect(self._emit)
        sec.add_widget(self._gamma_slider)

        self._layout.addWidget(sec)

    def _build_edge_section(self) -> None:
        sec = CollapsibleSection("Edge Detection", "⌥", collapsed=True)

        hint = QLabel("Overlay detected edges on the ASCII output to emphasise outlines.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        edge_row = QHBoxLayout()
        edge_row.setSpacing(12)
        self._edge_group = QButtonGroup()
        for label, val in [("Off", "none"), ("Canny", "canny"), ("Sobel", "sobel")]:
            rb = QRadioButton(label)
            rb.setProperty("edge_val", val)
            tips = {
                "none": "No edge detection",
                "canny": "Canny — sharp, clean edges (good default)",
                "sobel": "Sobel — softer gradient edges",
            }
            rb.setToolTip(tips[val])
            self._edge_group.addButton(rb)
            edge_row.addWidget(rb)
            if val == "none":
                rb.setChecked(True)
        self._edge_group.buttonToggled.connect(self._emit)
        sec.add_layout(edge_row)

        self._canny_low = LabeledSlider(
            "Canny Low Threshold", 0, 255, 50, decimals=0,
            tooltip="Lower hysteresis threshold for Canny edge detector (0–255)"
        )
        self._canny_low.value_changed.connect(self._emit)
        sec.add_widget(self._canny_low)

        self._canny_high = LabeledSlider(
            "Canny High Threshold", 0, 255, 150, decimals=0,
            tooltip="Upper hysteresis threshold for Canny edge detector (0–255)"
        )
        self._canny_high.value_changed.connect(self._emit)
        sec.add_widget(self._canny_high)

        self._edge_weight = LabeledSlider(
            "Edge Blend Weight", 0.0, 1.0, 0.5, decimals=2,
            tooltip="How strongly edge lines are mixed into the final output (0=none, 1=full)"
        )
        self._edge_weight.value_changed.connect(self._emit)
        sec.add_widget(self._edge_weight)

        self._sobel_ksize = QSpinBox()
        self._sobel_ksize.setRange(1, 15)
        self._sobel_ksize.setSingleStep(2)
        self._sobel_ksize.setValue(3)
        self._sobel_ksize.setToolTip("Sobel kernel size — must be odd (1, 3, 5, …). Larger = blurrier edges.")
        self._sobel_ksize.valueChanged.connect(self._emit)
        sec.add_layout(_form_row("Sobel Kernel Size:", self._sobel_ksize,
                                 "Kernel size for Sobel operator — odd numbers only (3 is default)"))

        self._layout.addWidget(sec)

    def _build_dither_section(self) -> None:
        sec = CollapsibleSection("Dithering", "⣿", collapsed=True)

        hint = QLabel("Floyd–Steinberg dithering spreads quantisation error to neighbouring pixels, "
                      "creating smoother gradients in the ASCII output.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._dither_chk = QCheckBox("Floyd–Steinberg Dithering")
        self._dither_chk.setToolTip("Enable error-diffusion dithering for smoother gradients")
        self._dither_chk.toggled.connect(self._emit)
        sec.add_widget(self._dither_chk)

        self._layout.addWidget(sec)

    def _build_color_section(self) -> None:
        sec = CollapsibleSection("Colorization", "◉", collapsed=True)

        hint = QLabel("Colorized mode renders each character in the original video's color "
                      "rather than a single foreground color.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._color_chk = QCheckBox("Enable Colorized ASCII")
        self._color_chk.setToolTip("Render each ASCII character using the source pixel's color")
        self._color_chk.toggled.connect(self._emit)
        sec.add_widget(self._color_chk)

        self._color_mode = QComboBox()
        self._color_mode.addItems(["rgb_image", "ansi", "terminal_256"])
        self._color_mode.setToolTip(
            "rgb_image: full color PNG/MP4 output\n"
            "ansi: ANSI escape codes in text output\n"
            "terminal_256: 256-color terminal palette"
        )
        self._color_mode.currentTextChanged.connect(self._emit)
        sec.add_layout(_form_row("Color Mode:", self._color_mode))

        self._bg_color = QLineEdit("#000000")
        self._bg_color.setMaximumWidth(100)
        self._bg_color.setToolTip("Background fill color as hex (e.g. #000000 for black)")
        self._bg_color.textChanged.connect(self._emit)

        self._fg_color = QLineEdit("#00FF00")
        self._fg_color.setMaximumWidth(100)
        self._fg_color.setToolTip("Foreground (character) color as hex — used when colorization is OFF")
        self._fg_color.textChanged.connect(self._emit)

        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        bg_lbl = QLabel("Background:")
        bg_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        fg_lbl = QLabel("Foreground:")
        fg_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        color_row.addWidget(bg_lbl)
        color_row.addWidget(self._bg_color)
        color_row.addSpacing(8)
        color_row.addWidget(fg_lbl)
        color_row.addWidget(self._fg_color)
        color_row.addStretch()
        sec.add_layout(color_row)

        self._layout.addWidget(sec)

    def _build_font_section(self) -> None:
        sec = CollapsibleSection("Font", "Aa", collapsed=True)

        hint = QLabel("The font affects character width/height ratio and readability of the ASCII output.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._font_combo = QComboBox()
        self._font_combo.addItems([
            "Courier New", "Consolas", "Fira Code", "JetBrains Mono",
            "DejaVu Sans Mono", "Lucida Console", "Cascadia Code"
        ])
        self._font_combo.setToolTip("Monospace font used to render ASCII characters into the output image")
        self._font_combo.currentTextChanged.connect(self._emit)
        sec.add_layout(_form_row("Font Family:", self._font_combo))

        self._font_size = QSpinBox()
        self._font_size.setRange(6, 32)
        self._font_size.setValue(10)
        self._font_size.setToolTip("Font point size — smaller = more characters fit, larger = more legible")
        self._font_size.valueChanged.connect(self._emit)
        sec.add_layout(_form_row("Font Size (pt):", self._font_size,
                                 "Point size for rendered characters (6–32). Smaller = more detail."))

        self._layout.addWidget(sec)

    def _build_temporal_section(self) -> None:
        sec = CollapsibleSection("Temporal / FPS", "⏱", collapsed=True)

        hint = QLabel("Control the output frame rate. Skipping frames speeds up encoding but reduces smoothness.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self._frame_skip = QSpinBox()
        self._frame_skip.setRange(0, 30)
        self._frame_skip.setValue(0)
        self._frame_skip.setToolTip(
            "Process every Nth frame (0 = all frames; 1 = every 2nd; 2 = every 3rd). "
            "Higher values encode faster but output is less smooth."
        )
        self._frame_skip.valueChanged.connect(self._emit)
        sec.add_layout(_form_row("Frame Skip (0=none):", self._frame_skip,
                                 "Skip N frames between renders. 0 = process every frame."))

        self._target_fps = QDoubleSpinBox()
        self._target_fps.setRange(0, 120)
        self._target_fps.setValue(0)
        self._target_fps.setSingleStep(1.0)
        self._target_fps.setToolTip("Target output FPS. 0 = match source video FPS.")
        self._target_fps.valueChanged.connect(self._emit)
        sec.add_layout(_form_row("Target FPS (0=source):", self._target_fps,
                                 "Set a custom output framerate, or 0 to use the source FPS."))

        self._layout.addWidget(sec)

    def _build_output_section(self) -> None:
        sec = CollapsibleSection("Output", "▤", collapsed=False)

        self._output_format = QComboBox()
        self._output_format.addItems(["mp4", "gif", "image_seq", "txt_stream"])
        self._output_format.setToolTip(
            "mp4: H.264 video file\n"
            "gif: Animated GIF (large file, no audio)\n"
            "image_seq: One PNG per frame\n"
            "txt_stream: Plain-text ASCII file"
        )
        self._output_format.currentTextChanged.connect(self._emit)
        sec.add_layout(_form_row("Format:", self._output_format))

        self._quality_slider = LabeledSlider(
            "Quality (CRF)", 0, 51, 23, decimals=0,
            tooltip="H.264 Constant Rate Factor: lower = better quality, larger file. 18 is near-lossless; 28 is decent."
        )
        self._quality_slider.value_changed.connect(self._emit)
        sec.add_widget(self._quality_slider)

        self._gpu_chk = QCheckBox("GPU Acceleration  (NVENC/CUDA)")
        self._gpu_chk.setToolTip(
            "Use NVIDIA hardware encoding if available — significantly faster for large videos. "
            "Falls back to CPU if no compatible GPU is found."
        )
        self._gpu_chk.toggled.connect(self._emit)
        sec.add_widget(self._gpu_chk)

        self._layout.addWidget(sec)

    # ── Profile I/O ───────────────────────────────────────────────────────────

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
        edge_val = "none"
        for btn in self._edge_group.buttons():
            if btn.isChecked():
                edge_val = btn.property("edge_val")
                break

        return RenderProfile(
            name=self._profile.name,
            description=self._profile.description,
            char_ramp=self._ramp_combo.currentText(),
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
