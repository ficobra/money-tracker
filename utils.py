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
