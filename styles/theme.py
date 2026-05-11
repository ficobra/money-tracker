"""
Money Tracker — PyQt6 design system.
All color constants and the global QSS stylesheet live here.
"""

BG_MAIN       = "#0d1117"
BG_SIDEBAR    = "#060c15"
BG_CARD       = "#111922"
BG_CARD_ALT   = "#0f1923"
BG_ELEM       = "#1a2332"
ACCENT        = "#00b4d8"
ACCENT_DIM    = "#0088a8"
ACCENT_GLOW   = "#00d4ff"
TEXT_PRI      = "#e8f4f8"
TEXT_SEC      = "#6b8fa8"
TEXT_DIM      = "#3d5a70"
BORDER        = "#1e3448"
BORDER_ACCENT = "#00b4d8"
GREEN         = "#3fb950"
RED           = "#f85149"
FONT          = "Helvetica Neue"

# Legacy aliases kept for view files that import these names
BG_CARD_HOVER = "#1a2840"


def register_fonts() -> None:
    """Register DM Sans with matplotlib if available on the system."""
    import os
    import matplotlib
    import matplotlib.font_manager as fm
    font_paths = [
        "/Library/Fonts/DM Sans Regular.ttf",
        "/Library/Fonts/DMSans-Regular.ttf",
        os.path.expanduser("~/Library/Fonts/DMSans-Regular.ttf"),
        os.path.expanduser("~/Library/Fonts/DM Sans Regular.ttf"),
    ]
    for path in font_paths:
        if os.path.exists(path):
            fm.fontManager.addfont(path)
            matplotlib.rcParams['font.family'] = 'DM Sans'
            break


def get_stylesheet() -> str:
    """Return the complete QSS stylesheet for Money Tracker."""
    return """
/* ── Global reset ── */
* { outline: none; }
QWidget:focus { outline: none; }

QMainWindow { background: #0d1117; }
QWidget { color: #e8f4f8; background: transparent; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollArea QWidget { background: transparent; }
QScrollArea QLabel { background: transparent; border: none; }

QFrame > QWidget { background: transparent; }
QFrame > QLabel { background: transparent; border: none; }

/* ── Scrollbar — thin terminal style ── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #1a3050;
    border-radius: 3px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover { background: #00b4d8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 6px; background: transparent; }
QScrollBar::handle:horizontal {
    background: #1a3050;
    border-radius: 3px;
    min-width: 40px;
}
QScrollBar::handle:horizontal:hover { background: #00b4d8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Buttons ── */
QPushButton {
    background: #1a2332;
    color: #e8f4f8;
    border: 1px solid #1e3448;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background: #1e2d3d;
    border: 1px solid #00b4d8;
    color: #00d4ff;
}
QPushButton:pressed {
    background: #162030;
    border: 1px solid #0088a8;
}

QPushButton[class="accent"] {
    background: #00b4d8;
    color: #0d1117;
    border: none;
    font-weight: 600;
}
QPushButton[class="accent"]:hover {
    background: #00d4ff;
    color: #0d1117;
}
QPushButton[class="accent"]:pressed { background: #0088a8; }

QPushButton[class="danger"] {
    background: transparent;
    color: #f85149;
    border: 1px solid #2a1a1a;
}
QPushButton[class="danger"]:hover {
    background: #2a1a1a;
    border: 1px solid #f85149;
    color: #ff6b65;
}

QPushButton:focus { outline: none; }

/* ── Inputs ── */
QLineEdit {
    background: #111922;
    border: 1px solid #1e3448;
    border-radius: 6px;
    color: #e8f4f8;
    padding: 5px 10px;
    font-size: 13px;
    selection-background-color: #00b4d8;
}
QLineEdit:focus {
    border: 1px solid #00b4d8;
    background: #131f2e;
}

QComboBox {
    background: #111922;
    border: 1px solid #1e3448;
    border-radius: 6px;
    color: #e8f4f8;
    padding: 5px 10px;
    font-size: 13px;
}
QComboBox:focus { border: 1px solid #00b4d8; }
QComboBox:hover { border: 1px solid #00b4d8; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #111922;
    color: #e8f4f8;
    border: 1px solid #1e3448;
    selection-background-color: #1e3448;
    selection-color: #00b4d8;
    outline: none;
}

/* ── Checkboxes ── */
QCheckBox { color: #e8f4f8; spacing: 6px; font-size: 12px; }
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #1e3448;
    border-radius: 3px;
    background: #111922;
}
QCheckBox::indicator:checked {
    background: #00b4d8;
    border-color: #00b4d8;
}
QCheckBox::indicator:hover { border-color: #00b4d8; }

/* ── Labels ── */
QLabel { color: #e8f4f8; background: transparent; border: none; outline: none; }

/* ── Frames ── */
QFrame[class="divider"] {
    background: #1a2e45;
    border: none;
    max-height: 1px;
}

/* ── TextEdit (notes) ── */
QTextEdit {
    background: #111922;
    border: 1px solid #1e3448;
    border-radius: 8px;
    color: #e8f4f8;
    padding: 8px;
    font-size: 13px;
    selection-background-color: #00b4d8;
}
QTextEdit:focus { border: 1px solid #00b4d8; }

QToolTip {
    background: #111922;
    color: #e8f4f8;
    border: 1px solid #1e3448;
    padding: 4px 8px;
    border-radius: 4px;
}
"""
