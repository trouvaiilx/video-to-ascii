"""
Plugins Panel
=============
Lets users enable/disable filter plugins and configure their parameters.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QGroupBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QComboBox, QScrollArea, QFrame
)
from plugins.base_plugin import BUILTIN_PLUGINS, BasePlugin, PluginParam
from ui.widgets import SectionHeader
from ui.styles import ACCENT, TEXT_SECONDARY, BORDER, TEXT_MUTED, BG_RAISED, BG_SURFACE


class PluginsPanel(QWidget):
    """Plugin manager with live parameter editing."""
    plugins_changed = pyqtSignal(list)  # list[BasePlugin]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._active_plugins: list[BasePlugin] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(SectionHeader("Filter Plugins", "⧗"))

        # Available plugins list
        avail_lbl = QLabel("Available Plugins:")
        avail_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(avail_lbl)

        self._avail_list = QListWidget()
        self._avail_list.setMaximumHeight(130)
        for cls in BUILTIN_PLUGINS:
            item = QListWidgetItem(cls.display_name)
            item.setData(Qt.ItemDataRole.UserRole, cls.plugin_id)
            item.setToolTip(cls.description)
            self._avail_list.addItem(item)
        layout.addWidget(self._avail_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._add_plugin)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_plugin)
        move_up_btn = QPushButton("↑")
        move_up_btn.setFixedWidth(30)
        move_up_btn.clicked.connect(lambda: self._move(-1))
        move_dn_btn = QPushButton("↓")
        move_dn_btn.setFixedWidth(30)
        move_dn_btn.clicked.connect(lambda: self._move(1))
        for b in [add_btn, remove_btn, move_up_btn, move_dn_btn]:
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        # Active pipeline
        active_lbl = QLabel("Active Pipeline (top→bottom):")
        active_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(active_lbl)

        self._active_list = QListWidget()
        self._active_list.setMaximumHeight(120)
        self._active_list.currentRowChanged.connect(self._show_params)
        layout.addWidget(self._active_list)

        # Parameter editor (scrollable)
        layout.addWidget(SectionHeader("Plugin Parameters", "⚙"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        self._param_container = QWidget()
        self._param_layout = QVBoxLayout(self._param_container)
        self._param_layout.setContentsMargins(4, 4, 4, 4)
        self._param_layout.setSpacing(4)
        scroll.setWidget(self._param_container)
        layout.addWidget(scroll)

        layout.addStretch()

    def _add_plugin(self) -> None:
        from plugins.base_plugin import get_plugin
        items = self._avail_list.selectedItems()
        if not items:
            return
        pid = items[0].data(Qt.ItemDataRole.UserRole)
        plugin = get_plugin(pid)
        if plugin:
            self._active_plugins.append(plugin)
            self._refresh_active_list()
            self.plugins_changed.emit(list(self._active_plugins))

    def _remove_plugin(self) -> None:
        idx = self._active_list.currentRow()
        if 0 <= idx < len(self._active_plugins):
            del self._active_plugins[idx]
            self._refresh_active_list()
            self.plugins_changed.emit(list(self._active_plugins))

    def _move(self, direction: int) -> None:
        idx = self._active_list.currentRow()
        new_idx = idx + direction
        if 0 <= new_idx < len(self._active_plugins):
            self._active_plugins[idx], self._active_plugins[new_idx] = (
                self._active_plugins[new_idx], self._active_plugins[idx]
            )
            self._refresh_active_list()
            self._active_list.setCurrentRow(new_idx)
            self.plugins_changed.emit(list(self._active_plugins))

    def _refresh_active_list(self) -> None:
        self._active_list.clear()
        for i, plugin in enumerate(self._active_plugins):
            self._active_list.addItem(f"{i+1}. {plugin.display_name}")

    def _show_params(self, row: int) -> None:
        """Populate parameter editor for the selected plugin."""
        # Clear existing
        while self._param_layout.count():
            item = self._param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if row < 0 or row >= len(self._active_plugins):
            self._param_layout.addWidget(QLabel("Select a plugin to configure"))
            return

        plugin = self._active_plugins[row]
        if not plugin.params:
            lbl = QLabel(f"{plugin.display_name} — no parameters")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            self._param_layout.addWidget(lbl)
            return

        for param in plugin.params:
            row_w = QHBoxLayout()
            lbl = QLabel(param.label + ":")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            lbl.setMinimumWidth(100)
            row_w.addWidget(lbl)

            current = plugin.get_param(param.name)

            if param.type == "float":
                spin = QDoubleSpinBox()
                spin.setRange(param.min_val or 0.0, param.max_val or 100.0)
                spin.setSingleStep(0.1)
                spin.setValue(float(current))
                pname = param.name
                spin.valueChanged.connect(
                    lambda v, p=pname, pl=plugin: (pl.set_param(p, v), self.plugins_changed.emit(list(self._active_plugins)))
                )
                row_w.addWidget(spin)
            elif param.type == "int":
                spin = QSpinBox()
                spin.setRange(int(param.min_val or 0), int(param.max_val or 100))
                spin.setValue(int(current))
                pname = param.name
                spin.valueChanged.connect(
                    lambda v, p=pname, pl=plugin: (pl.set_param(p, v), self.plugins_changed.emit(list(self._active_plugins)))
                )
                row_w.addWidget(spin)
            elif param.type == "bool":
                chk = QCheckBox()
                chk.setChecked(bool(current))
                pname = param.name
                chk.toggled.connect(
                    lambda v, p=pname, pl=plugin: (pl.set_param(p, v), self.plugins_changed.emit(list(self._active_plugins)))
                )
                row_w.addWidget(chk)
            elif param.type == "choice":
                combo = QComboBox()
                combo.addItems(param.choices)
                idx = param.choices.index(current) if current in param.choices else 0
                combo.setCurrentIndex(idx)
                pname = param.name
                combo.currentTextChanged.connect(
                    lambda v, p=pname, pl=plugin: (pl.set_param(p, v), self.plugins_changed.emit(list(self._active_plugins)))
                )
                row_w.addWidget(combo)

            row_w.addStretch()
            container = QWidget()
            container.setLayout(row_w)
            self._param_layout.addWidget(container)

        self._param_layout.addStretch()

    def get_active_plugins(self) -> list[BasePlugin]:
        return list(self._active_plugins)
