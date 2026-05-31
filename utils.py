import calendar as _cal


def effective_charge_day(year: int, month: int, day_of_month: int, last_day: int) -> int:
    """Return the actual banking day a charge will be processed.

    Day-31 in shorter months maps to last_day.
    Saturday and Sunday both shift to the following Monday (clamped to last_day).
    """
    actual = min(day_of_month, last_day)
    weekday = _cal.weekday(year, month, actual)
    if weekday == 5:    # Saturday -> Monday
        actual = min(actual + 2, last_day)
    elif weekday == 6:  # Sunday -> Monday
        actual = min(actual + 1, last_day)
    return actual


def fmt_eur(value: float) -> str:
    """Format value as European currency: €1.234,56 or -€1.234,56"""
    s  = f"{abs(value):,.2f}"
    eu = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-€{eu}" if value < 0 else f"€{eu}"


def fmt_eur_signed(value: float) -> str:
    """Format with explicit sign: +€1.234,56 or -€1.234,56"""
    s  = f"{abs(value):,.2f}"
    eu = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"+€{eu}" if value >= 0 else f"-€{eu}"


def bind_numeric_entry(widget, decimals: int = 2) -> None:
    """Install a QDoubleValidator on a QLineEdit. Allows digits + one decimal, no negatives.
    Also handles comma-to-dot conversion on textChanged.
    """
    from PyQt6.QtGui import QDoubleValidator
    from PyQt6.QtCore import QLocale
    validator = QDoubleValidator(0.0, 999999999.0, decimals, widget)
    validator.setNotation(QDoubleValidator.Notation.StandardNotation)
    validator.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
    widget.setValidator(validator)

    def _fix_comma(text: str) -> None:
        if "," in text:
            widget.blockSignals(True)
            cursor = widget.cursorPosition()
            widget.setText(text.replace(",", "."))
            widget.setCursorPosition(cursor)
            widget.blockSignals(False)

    widget.textChanged.connect(_fix_comma)


def open_dialog(parent, width: int, height: int):
    """Create a centered modal QDialog."""
    from PyQt6.QtWidgets import QDialog
    from PyQt6.QtCore import Qt
    dialog = QDialog(parent.window() if parent else None)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setFixedSize(width, height)
    dialog.setStyleSheet("QDialog { background-color: #161f2e; border-radius: 12px; }")
    center_on_parent(dialog, parent)
    return dialog


def center_on_parent(dialog, parent) -> None:
    """Center dialog on parent widget."""
    if parent:
        root = parent.window()
        geom = root.geometry()
        x = geom.x() + (geom.width() - dialog.width()) // 2
        y = geom.y() + (geom.height() - dialog.height()) // 2
        dialog.move(x, y)


# ── Scroll lock (no-ops in PyQt6 — Qt handles modal blocking natively) ─────────

def lock_scroll() -> None:
    pass


def unlock_scroll() -> None:
    pass


def is_scroll_locked() -> bool:
    return False
