"""
Dark-mode Qt stylesheet for ASCII Video Converter.
Inspired by professional video/audio DAW aesthetics:
  - Near-black backgrounds (#0d0d0f, #141416)
  - Subtle warm grey surfaces (#1e1e22, #252529)
  - Cyan/teal accent (#00e5cc)
  - Red accent for actions (#e5003c)
  - Monospace terminal feel
"""

ACCENT = "#00e5cc"
ACCENT_DIM = "#009988"
RED = "#e5003c"
BG_DEEP = "#0d0d0f"
BG_BASE = "#141416"
BG_SURFACE = "#1e1e22"
BG_RAISED = "#252529"
BG_HOVER = "#2e2e34"
BORDER = "#333338"
BORDER_FOCUS = ACCENT
TEXT_PRIMARY = "#e8e8ec"
TEXT_SECONDARY = "#888898"
TEXT_MUTED = "#555560"

STYLESHEET = f"""
/* ── Global ────────────────────────────────── */
QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Courier New', monospace;
    font-size: 12px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {BG_DEEP};
}}

QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}

/* ── Scroll Bars ────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_SURFACE};
    width: 8px;
    border: none;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_SURFACE};
    height: 8px;
    border: none;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT_DIM}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Panels / Frames ───────────────────────── */
QFrame[role="panel"] {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QFrame[role="card"] {{
    background-color: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px;
}}

/* ── Labels ────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel[role="title"] {{
    font-size: 14px;
    font-weight: bold;
    color: {ACCENT};
    letter-spacing: 1px;
}}
QLabel[role="subtitle"] {{
    font-size: 11px;
    color: {TEXT_SECONDARY};
}}
QLabel[role="value"] {{
    color: {ACCENT};
    font-weight: bold;
}}
QLabel[role="muted"] {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QLabel[role="stat"] {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
}}

/* ── Group Boxes ───────────────────────────── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 16px;
    padding-top: 12px;
    font-size: 11px;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: -1px;
    padding: 0 6px;
    background: {BG_SURFACE};
}}

/* ── Buttons ───────────────────────────────── */
QPushButton {{
    background-color: {BG_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    outline: none;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {ACCENT_DIM};
    color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {BG_SURFACE};
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    background-color: {BG_SURFACE};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QPushButton[role="primary"] {{
    background-color: {ACCENT};
    color: {BG_DEEP};
    font-weight: bold;
    border: none;
}}
QPushButton[role="primary"]:hover {{
    background-color: #00ffdf;
    color: {BG_DEEP};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {ACCENT_DIM};
    color: {TEXT_MUTED};
}}
QPushButton[role="danger"] {{
    background-color: {RED};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton[role="danger"]:hover {{ background-color: #ff1a4d; }}

/* ── Sliders ───────────────────────────────── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: #00ffdf; }}
QSlider::sub-page:horizontal {{
    background: {ACCENT_DIM};
    border-radius: 2px;
}}

/* ── Combo / Spin ──────────────────────────── */
QComboBox {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    color: {TEXT_PRIMARY};
    min-height: 24px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {BG_RAISED};
    border: 1px solid {ACCENT_DIM};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}
QSpinBox, QDoubleSpinBox {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BG_HOVER};
    border: none;
    width: 16px;
}}

/* ── Line Edits ─────────────────────────────── */
QLineEdit {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-family: 'JetBrains Mono', monospace;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:read-only {{ color: {TEXT_SECONDARY}; background: {BG_SURFACE}; }}

/* ── Check Boxes ───────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background: {BG_RAISED};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT_DIM}; }}

/* ── Radio Buttons ──────────────────────────── */
QRadioButton {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}
QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER};
    border-radius: 7px;
    background: {BG_RAISED};
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Tab Widget ─────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-top: none;
    background: {BG_SURFACE};
    border-radius: 0 0 6px 6px;
}}
QTabBar::tab {{
    background: {BG_BASE};
    color: {TEXT_SECONDARY};
    padding: 6px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QTabBar::tab:selected {{
    background: {BG_SURFACE};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background: {BG_RAISED};
    color: {TEXT_PRIMARY};
}}

/* ── List Widget ────────────────────────────── */
QListWidget {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px 10px;
    border-radius: 3px;
}}
QListWidget::item:selected {{
    background: {ACCENT_DIM};
    color: {BG_DEEP};
}}
QListWidget::item:hover:!selected {{
    background: {BG_HOVER};
}}

/* ── Progress Bar ───────────────────────────── */
QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_SURFACE};
    text-align: center;
    color: {TEXT_PRIMARY};
    font-size: 11px;
    height: 18px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_DIM}, stop:1 {ACCENT});
    border-radius: 3px;
}}

/* ── Splitter ───────────────────────────────── */
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QSplitter::handle:hover {{
    background: {ACCENT_DIM};
}}

/* ── Tool Tips ──────────────────────────────── */
QToolTip {{
    background: {BG_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {ACCENT_DIM};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ── Status Bar ─────────────────────────────── */
QStatusBar {{
    background: {BG_DEEP};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}

/* ── Menu Bar ───────────────────────────────── */
QMenuBar {{
    background: {BG_DEEP};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{ background: {BG_RAISED}; color: {ACCENT}; }}
QMenu {{
    background: {BG_RAISED};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 24px 5px 10px;
    border-radius: 3px;
}}
QMenu::item:selected {{ background: {ACCENT_DIM}; color: {BG_DEEP}; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ── Text Edit ──────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT_PRIMARY};
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 11px;
}}
QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
"""
