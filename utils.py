import calendar as _cal


def effective_charge_day(year: int, month: int, day_of_month: int, last_day: int) -> int:
    """Return the actual banking day a charge will be processed.

    Day-31 in shorter months maps to last_day.
    Saturday and Sunday both shift to the following Monday (clamped to last_day).
    """
    actual = min(day_of_month, last_day)
    weekday = _cal.weekday(year, month, actual)
    if weekday == 5:    # Saturday → Monday
        actual = min(actual + 2, last_day)
    elif weekday == 6:  # Sunday → Monday
        actual = min(actual + 1, last_day)
    return actual


def center_on_parent(dialog, parent_widget, width: int, height: int):
    """Center a CTkToplevel dialog on the main application window."""
    parent_widget.update_idletasks()
    root = parent_widget.winfo_toplevel()
    x = root.winfo_x() + (root.winfo_width()  - width)  // 2
    y = root.winfo_y() + (root.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")


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
