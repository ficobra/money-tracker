"""Portfolio tab — live position tracking via yfinance (PyQt6)."""

import threading
from datetime import date, datetime
from math import cos, sin, radians

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QComboBox, QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QFont

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

from database.db import (
    get_portfolio_positions, add_position, update_position, delete_position,
    get_portfolio_cache, upsert_portfolio_cache,
    get_portfolio_reminder, upsert_portfolio_reminder,
    get_latest_snapshots,
    update_snapshot_portfolio,
)
from styles.theme import (
    ACCENT, TEXT_PRI, TEXT_SEC, TEXT_DIM,
    GREEN, RED, FONT,
)
from utils import fmt_eur, open_dialog, bind_numeric_entry

matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['text.color'] = '#eef2f7'
matplotlib.rcParams['axes.labelcolor'] = '#eef2f7'
matplotlib.rcParams['xtick.color'] = '#5a7a94'
matplotlib.rcParams['ytick.color'] = '#5a7a94'

_CURRENCIES = ["USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD"]

_CURR_SYM: dict[str, str] = {
    "EUR": "€", "USD": "$", "GBP": "£", "CHF": "Fr",
    "JPY": "¥", "CAD": "C$", "AUD": "A$",
}

_L4_ENTRY = (
    "background: #1c2d4a; border: 1px solid #1a2e45; border-radius: 8px;"
    f" color: {TEXT_PRI}; padding: 6px 10px; font-size: 13px;"
)


# ── Module-level helpers ──────────────────────────────────────────────────────

def _clear_layout(layout) -> None:
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub:
                _clear_layout(sub)



def make_label(text: str, size: int = 13, bold: bool = False, color: str = TEXT_PRI) -> QLabel:
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    lbl.setFont(QFont(FONT, size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none; outline: none;")
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    return lbl


def make_card_l3() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #162440;"
        " border-top: 1px solid #1e3a58;"
        " border-left: 1px solid #1e3a58;"
        " border-right: 1px solid #0f1e30;"
        " border-bottom: 1px solid #0f1e30;"
        " border-radius: 14px;"
    )
    return f


def make_card_l2() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #111d2e;"
        " border: 1px solid #1a2e45;"
        " border-radius: 14px;"
    )
    return f


def make_card_l1() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #0d1520;"
        " border: 1px solid #0f1e30;"
        " border-radius: 10px;"
    )
    return f


def make_card() -> QFrame:
    return make_card_l2()


def make_divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setFixedHeight(1)
    f.setProperty("class", "divider")
    f.setStyleSheet("background: #1a2e45; border: none;")
    return f


def make_eyebrow(left_text: str, right_text: str = "") -> QHBoxLayout:
    h = QHBoxLayout()
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    left = QLabel(left_text.upper())
    left.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    left.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    left.setFont(QFont(FONT, 10))
    left.setStyleSheet("color: #6b8fa8; background: transparent; border: none; letter-spacing: 2px;")
    h.addWidget(left)
    h.addStretch()
    if right_text:
        right = QLabel(right_text)
        right.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        right.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        right.setFont(QFont(FONT, 10))
        right.setStyleSheet("color: #3d5a70; background: transparent; border: none; font-family: 'Courier New';")
        h.addWidget(right)
    return h


def make_pill(text: str, color: str = "#00b4d8", bg_alpha: float = 0.12) -> QLabel:
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QSizePolicy as _QSP
    c = QColor(color)
    bg = f"rgba({c.red()},{c.green()},{c.blue()},{bg_alpha})"
    border = f"rgba({c.red()},{c.green()},{c.blue()},0.35)"
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    lbl.setFont(QFont(FONT, 11))
    lbl.setStyleSheet(
        f"color: {color}; background: {bg};"
        f" border: 1px solid {border};"
        f" border-radius: 10px; padding: 2px 10px;"
    )
    pal = lbl.palette()
    pal.setColor(pal.ColorRole.Window, QColor(0, 0, 0, 0))
    lbl.setPalette(pal)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setSizePolicy(_QSP.Policy.Maximum, _QSP.Policy.Fixed)
    return lbl


# ── Background price fetcher ──────────────────────────────────────────────────

def _fetch_prices(tickers: list[str]) -> dict[str, dict]:
    """Fetch current prices for each ticker. Returns {} on failure or missing dep."""
    if not tickers or not _YF_AVAILABLE:
        return {}
    eur_rates: dict[str, float] = {}
    result: dict[str, dict] = {}
    for ticker in tickers:
        try:
            t_obj = yf.Ticker(ticker)
            fi = t_obj.fast_info
            price = fi.last_price
            if price is None:
                continue
            currency = (fi.currency or "USD").upper()
            prev_close = fi.previous_close or price
            day_change = price - prev_close
            day_change_pct = (day_change / prev_close * 100) if prev_close else 0.0
            name = None
            try:
                info = t_obj.info
                name = info.get("longName") or info.get("shortName")
            except Exception:
                pass
            if currency == "EUR":
                eur_rate = 1.0
            else:
                rk = f"{currency}EUR"
                if rk not in eur_rates:
                    try:
                        eur_rates[rk] = (
                            yf.Ticker(f"{currency}EUR=X").fast_info.last_price or 1.0
                        )
                    except Exception:
                        eur_rates[rk] = 1.0
                eur_rate = eur_rates[rk]
            result[ticker] = {
                "price": price,
                "price_eur": price * eur_rate,
                "currency": currency,
                "day_change": day_change,
                "day_change_pct": day_change_pct,
                "eur_rate": eur_rate,
                "name": name,
            }
        except Exception:
            pass
    return result


# ── View ──────────────────────────────────────────────────────────────────────

class PortfolioView(QScrollArea):

    _DONUT_COLORS = [
        "#00b4d8", "#3fb950", "#f0c040", "#f85149",
        "#a371f7", "#fd8c73", "#79c0ff",
    ]

    _SEG_ACTIVE = (
        "QPushButton { background: rgba(0,180,216,0.15); border: 1px solid rgba(0,180,216,0.5);"
        " color: #00b4d8; border-radius: 6px; padding: 4px 12px; font-size: 12px; }"
        " QPushButton:hover { background: rgba(0,180,216,0.22); }"
    )
    _SEG_INACTIVE = (
        "QPushButton { background: transparent; border: 1px solid #1a2e45;"
        " color: #9fb0c5; border-radius: 6px; padding: 4px 12px; font-size: 12px; }"
        " QPushButton:hover { background: rgba(255,255,255,0.04); }"
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        self._price_data: dict[str, dict] = {}
        self._using_cache: bool = False
        self._fetch_in_progress: bool = False
        self._last_updated: str = ""

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setStyleSheet("background: #0d1117;")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(32, 28, 32, 32)
        self._layout.setSpacing(20)
        self.setWidget(content)

        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self) -> None:
        # ── Header row ────────────────────────────────────────────────────────
        hdr_widget = QWidget()
        hdr_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_widget.setStyleSheet("background: transparent;")
        hdr_row = QHBoxLayout(hdr_widget)
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.setSpacing(12)

        # Left: title + subtitle
        left_col = QVBoxLayout()
        left_col.setSpacing(4)
        left_col.addWidget(make_label("Portfolio", 24, bold=True))
        left_col.addWidget(make_label(
            "Track your investment positions and live market prices.",
            13, color=TEXT_SEC
        ))
        hdr_row.addLayout(left_col)
        hdr_row.addStretch()

        # Right: status + refresh button
        right_row = QHBoxLayout()
        right_row.setSpacing(12)
        right_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._status_lbl = make_label("", 11, color=TEXT_DIM)
        right_row.addWidget(self._status_lbl)

        self._refresh_btn = QPushButton("⟳  Refresh")
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.setFont(QFont(FONT, 12))
        self._refresh_btn.setStyleSheet(
            "QPushButton { background: #1a2332; border: 1px solid #1e3448; border-radius: 6px;"
            " color: #6b8fa8; font-size: 12px; padding: 4px 12px; }"
            " QPushButton:hover { background: #1e2d3d; border-color: #00b4d8; color: #00d4ff; }"
        )
        self._refresh_btn.clicked.connect(self._start_fetch)
        right_row.addWidget(self._refresh_btn)

        hdr_row.addLayout(right_row)
        self._layout.addWidget(hdr_widget)

        # ── Reminder banner (hidden initially) ───────────────────────────────
        self._reminder_banner = QWidget()
        self._reminder_banner.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._reminder_banner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._reminder_banner.setStyleSheet("background: #3d3000; border-radius: 8px;")
        self._reminder_banner.setVisible(False)
        banner_h = QHBoxLayout(self._reminder_banner)
        banner_h.setContentsMargins(12, 8, 12, 8)
        banner_h.setSpacing(8)
        self._reminder_banner_lbl = make_label("", 13, color="#f0c040")
        self._reminder_banner_lbl.setWordWrap(True)
        banner_h.addWidget(self._reminder_banner_lbl, 1)
        dismiss_btn = QPushButton("×")
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #8b949e; border: none; font-size: 16px; }"
            "QPushButton:hover { color: #e6edf3; }"
        )
        dismiss_btn.clicked.connect(lambda: self._reminder_banner.setVisible(False))
        banner_h.addWidget(dismiss_btn)
        self._layout.addWidget(self._reminder_banner)

        # ── Rebalance bar ─────────────────────────────────────────────────────
        self._rebalance_bar = QFrame()
        self._rebalance_bar.setStyleSheet(
            "background: #0d1520; border: 1px solid #0f1e30; border-radius: 10px;"
        )
        self._rebalance_bar.setVisible(False)
        bar_h = QHBoxLayout(self._rebalance_bar)
        bar_h.setContentsMargins(20, 14, 20, 14)
        bar_h.setSpacing(12)

        icon_lbl = QLabel("↻")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        icon_lbl.setFont(QFont(FONT, 16))
        icon_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent; border: none;")
        bar_h.addWidget(icon_lbl)

        text_col = QWidget()
        text_col.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        text_col.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        text_col.setStyleSheet("background: transparent;")
        text_v = QVBoxLayout(text_col)
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(2)
        self._rebalance_date_lbl = make_label("Next rebalance: —", 13, bold=True)
        self._rebalance_days_lbl = make_label("", 11, color=TEXT_DIM)
        text_v.addWidget(self._rebalance_date_lbl)
        text_v.addWidget(self._rebalance_days_lbl)
        bar_h.addWidget(text_col, stretch=1)

        self._rebalance_pill = make_pill("● Set reminder", color=ACCENT)
        self._rebalance_pill.setVisible(False)
        bar_h.addWidget(self._rebalance_pill)
        self._layout.addWidget(self._rebalance_bar)

        # ── Hero stats row — 3-column ─────────────────────────────────────────
        self._hero_widget = QWidget()
        self._hero_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._hero_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._hero_widget.setStyleSheet("background: transparent;")
        hero_h = QHBoxLayout(self._hero_widget)
        hero_h.setContentsMargins(0, 0, 0, 0)
        hero_h.setSpacing(16)

        # Card 0: PORTFOLIO VALUE
        self._value_card = make_card_l3()
        value_v = QVBoxLayout(self._value_card)
        value_v.setContentsMargins(20, 18, 20, 18)
        value_v.setSpacing(8)
        value_v.addLayout(make_eyebrow("PORTFOLIO VALUE", "EUR"))
        self._port_value_lbl = make_label("—", 28, bold=True)
        font = self._port_value_lbl.font()
        font.setPixelSize(40)
        self._port_value_lbl.setFont(font)
        value_v.addWidget(self._port_value_lbl)

        self._port_delta_row = QWidget()
        self._port_delta_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._port_delta_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._port_delta_row.setStyleSheet("background: transparent;")
        delta_h = QHBoxLayout(self._port_delta_row)
        delta_h.setContentsMargins(0, 0, 0, 0)
        delta_h.setSpacing(8)
        self._port_pnl_pill = make_pill("—", GREEN)
        delta_h.addWidget(self._port_pnl_pill)
        self._port_pct_lbl = make_label("—", 12, color=GREEN)
        delta_h.addWidget(self._port_pct_lbl)
        delta_h.addStretch()
        delta_h.addWidget(make_label("P&L all-time", 11, color=TEXT_DIM))
        value_v.addWidget(self._port_delta_row)

        self._port_spark_container = QWidget()
        self._port_spark_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._port_spark_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._port_spark_container.setStyleSheet("background: transparent;")
        self._port_spark_container.setFixedHeight(70)
        spark_lay = QVBoxLayout(self._port_spark_container)
        spark_lay.setContentsMargins(0, 0, 0, 0)
        value_v.addWidget(self._port_spark_container)

        hero_h.addWidget(self._value_card, stretch=3)

        # Card 1: TODAY'S CHANGE
        self._today_card = make_card_l2()
        today_v = QVBoxLayout(self._today_card)
        today_v.setContentsMargins(20, 18, 20, 18)
        today_v.setSpacing(8)
        today_v.addLayout(make_eyebrow("TODAY'S CHANGE", "live"))
        self._today_value_lbl = make_label("—", 28, bold=True)
        today_v.addWidget(self._today_value_lbl)

        self._today_pill_row = QWidget()
        self._today_pill_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._today_pill_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._today_pill_row.setStyleSheet("background: transparent;")
        today_pr_h = QHBoxLayout(self._today_pill_row)
        today_pr_h.setContentsMargins(0, 0, 0, 0)
        today_pr_h.setSpacing(8)
        self._today_pct_pill = make_pill("—")
        today_pr_h.addWidget(self._today_pct_pill)
        self._today_holdings_lbl = make_label("", 11, color=TEXT_DIM)
        today_pr_h.addWidget(self._today_holdings_lbl)
        today_pr_h.addStretch()
        today_v.addWidget(self._today_pill_row)

        self._today_holdings_container = QWidget()
        self._today_holdings_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._today_holdings_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._today_holdings_container.setStyleSheet("background: transparent;")
        self._today_holdings_layout = QVBoxLayout(self._today_holdings_container)
        self._today_holdings_layout.setContentsMargins(0, 4, 0, 0)
        self._today_holdings_layout.setSpacing(4)
        today_v.addWidget(self._today_holdings_container)
        today_v.addStretch()

        hero_h.addWidget(self._today_card, stretch=2)

        # Card 2: REBALANCE REMINDER
        self._reminder_card = make_card_l2()
        rem_v = QVBoxLayout(self._reminder_card)
        rem_v.setContentsMargins(20, 18, 20, 18)
        rem_v.setSpacing(10)
        rem_v.addLayout(make_eyebrow("REBALANCE REMINDER", ""))

        rem_v.addWidget(make_label("Notify before next rebalance:", 13, color=TEXT_SEC))

        self._reminder_option_btns: list[QPushButton] = []
        options = ["1 day", "1 week", "1 month", "Off"]
        for opt in options:
            btn = QPushButton(opt)
            btn.setFixedHeight(28)
            btn.setFont(QFont(FONT, 12))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid #1a2e45;"
                " border-radius: 6px; color: #6b8fa8; padding: 4px 10px; }"
                " QPushButton:hover { background: rgba(255,255,255,0.04); }"
            )
            btn.clicked.connect(lambda _=False, o=opt: self._on_reminder_option(o))
            self._reminder_option_btns.append(btn)
            rem_v.addWidget(btn)

        # Hidden combo kept for _on_set_reminder compatibility
        self._reminder_combo = QComboBox()
        self._reminder_combo.addItems(["Set reminder ▾", "In 1 year", "Custom..."])
        self._reminder_combo.setVisible(False)
        self._reminder_combo.currentTextChanged.connect(self._on_set_reminder)
        rem_v.addWidget(self._reminder_combo)

        rem_v.addStretch()

        hero_h.addWidget(self._reminder_card, stretch=2)

        self._layout.addWidget(self._hero_widget)

        # ── Allocation card ───────────────────────────────────────────────────
        self._alloc_card = make_card_l1()
        alloc_outer_v = QVBoxLayout(self._alloc_card)
        alloc_outer_v.setContentsMargins(20, 18, 20, 18)
        alloc_outer_v.setSpacing(12)
        alloc_outer_v.addLayout(make_eyebrow("ALLOCATION", "CURRENT VS TARGET"))

        seg_row = QWidget()
        seg_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        seg_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        seg_row.setStyleSheet("background: transparent;")
        seg_h = QHBoxLayout(seg_row)
        seg_h.setContentsMargins(0, 0, 0, 0)
        seg_h.setSpacing(6)
        _PILL_ACTIVE = (
            "QPushButton { background: rgba(0,180,216,0.12); border: 1px solid rgba(0,180,216,0.4);"
            " border-radius: 6px; color: #00b4d8; padding: 4px 14px; font-size: 12px; }"
            " QPushButton:hover { background: rgba(0,180,216,0.18); }"
        )
        _PILL_INACTIVE = (
            "QPushButton { background: transparent; border: 1px solid #1a2e45;"
            " border-radius: 6px; color: #6b8fa8; padding: 4px 14px; font-size: 12px; }"
            " QPushButton:hover { background: rgba(255,255,255,0.04); }"
        )
        self._seg_btns: list[QPushButton] = []
        for i, mode in enumerate(["Current", "Target", "Drift"]):
            sb = QPushButton(mode)
            sb.setFixedHeight(28)
            sb.setFont(QFont(FONT, 12))
            sb.setStyleSheet(self._SEG_ACTIVE if i == 0 else self._SEG_INACTIVE)
            sb.clicked.connect(lambda _=False, m=mode: self._render_alloc_donut(m))
            seg_h.addWidget(sb)
            self._seg_btns.append(sb)
        seg_h.addStretch()
        alloc_outer_v.addWidget(seg_row)

        alloc_cols = QHBoxLayout()
        alloc_cols.setSpacing(24)

        self._alloc_chart_container = QWidget()
        self._alloc_chart_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._alloc_chart_container.setStyleSheet("background: #0d1520;")
        self._alloc_chart_container.setFixedSize(240, 240)
        chart_container_lay = QVBoxLayout(self._alloc_chart_container)
        chart_container_lay.setContentsMargins(0, 0, 0, 0)
        alloc_cols.addWidget(self._alloc_chart_container, stretch=1)

        self._alloc_legend_container = QWidget()
        self._alloc_legend_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._alloc_legend_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._alloc_legend_container.setStyleSheet("background: transparent;")
        self._alloc_legend_layout = QVBoxLayout(self._alloc_legend_container)
        self._alloc_legend_layout.setContentsMargins(0, 0, 0, 0)
        self._alloc_legend_layout.setSpacing(8)
        self._alloc_legend_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        alloc_cols.addWidget(self._alloc_legend_container, stretch=1)

        alloc_outer_v.addLayout(alloc_cols)
        self._layout.addWidget(self._alloc_card)

        # ── Holdings header row ───────────────────────────────────────────────
        pos_hdr_row = QWidget()
        pos_hdr_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        pos_hdr_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        pos_hdr_row.setStyleSheet("background: transparent;")
        pos_hdr_h = QHBoxLayout(pos_hdr_row)
        pos_hdr_h.setContentsMargins(0, 8, 0, 4)
        pos_hdr_h.setSpacing(8)
        pos_hdr_h.addLayout(make_eyebrow("HOLDINGS", ""))
        pos_hdr_h.addStretch()

        add_pos_btn = QPushButton("+ Add Position")
        add_pos_btn.setFixedHeight(32)
        add_pos_btn.setFont(QFont(FONT, 12))
        add_pos_btn.setFixedWidth(140)
        add_pos_btn.setStyleSheet(
            "QPushButton { background: #00b4d8; color: #0d1117; border: none;"
            " border-radius: 6px; font-size: 12px; font-weight: 600; padding: 4px 14px; }"
            " QPushButton:hover { background: #00d4ff; }"
        )
        add_pos_btn.clicked.connect(self._open_add_dialog)
        pos_hdr_h.addWidget(add_pos_btn)
        self._layout.addWidget(pos_hdr_row)

        # ── Positions grid ────────────────────────────────────────────────────
        self._positions_widget = QWidget()
        self._positions_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._positions_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._positions_widget.setStyleSheet("background: transparent;")
        self._positions_layout = QVBoxLayout(self._positions_widget)
        self._positions_layout.setContentsMargins(0, 0, 0, 0)
        self._positions_layout.setSpacing(12)
        self._layout.addWidget(self._positions_widget)

        # ── Hidden compatibility widgets ──────────────────────────────────────
        self._reminder_status_lbl = make_label("", 12, color=TEXT_SEC)
        self._reminder_status_lbl.setVisible(False)
        self._layout.addWidget(self._reminder_status_lbl)

        self._layout.addStretch()

    # ── Event filter (for embedded canvas wheel passthrough) ──────────────────

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Wheel:
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - event.angleDelta().y() // 4
            )
            return True
        return super().eventFilter(obj, event)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._render_reminder_banner()
        self._render_reminder_status()
        self._render_all()
        if not self._price_data and not self._fetch_in_progress:
            self._start_fetch()

    # ── Render ────────────────────────────────────────────────────────────────

    def _render_all(self) -> None:
        positions = get_portfolio_positions()
        cache = get_portfolio_cache()
        self._render_hero_stats(positions, cache)
        self._render_rebalance_bar()
        self._render_allocation_section(positions, cache)
        self._render_positions_grid(positions, cache)
        self._render_reminder_banner()
        self._render_reminder_status()
        self._update_status()

    def _render_hero_stats(self, positions: list[dict], cache: dict) -> None:
        total_eur = 0.0
        total_cost = 0.0
        total_day_change = 0.0
        n_holdings = 0

        for p in positions:
            d = self._price_data.get(p["ticker"]) or cache.get(p["ticker"])
            if d:
                price_eur = d.get("price_eur") or d.get("price", 0.0)
                eur_rate = d.get("eur_rate", 1.0) or 1.0
                cur_val = p["shares"] * price_eur
                cost_val = p["shares"] * p["avg_buy_price"] * eur_rate
                dc = (d.get("day_change") or 0.0) * eur_rate
                total_eur += cur_val
                total_cost += cost_val
                total_day_change += dc * p["shares"]
                n_holdings += 1

        pnl = total_eur - total_cost
        pnl_pct = (pnl / total_cost * 100) if total_cost else 0.0
        pnl_col = GREEN if pnl >= 0 else RED
        pnl_sign = "+" if pnl >= 0 else ""

        # Save portfolio_eur to latest snapshot after fresh fetch
        if total_eur > 0 and not self._using_cache:
            latest = get_latest_snapshots(1)
            if latest:
                s = latest[0]
                update_snapshot_portfolio(s["year"], s["month"], total_eur)

        # Card 0: Portfolio Value
        self._port_value_lbl.setText(fmt_eur(total_eur) if n_holdings else "—")
        if n_holdings:
            self._port_pnl_pill.setText(f"{pnl_sign}{fmt_eur(pnl)}")
            _r, _g, _b = int(pnl_col[1:3], 16), int(pnl_col[3:5], 16), int(pnl_col[5:7], 16)
            self._port_pnl_pill.setStyleSheet(
                f"color: {pnl_col}; background: rgba({_r},{_g},{_b},30);"
                " border-radius: 999px; padding: 2px 8px; font-size: 11px; border: none;"
            )
            self._port_pct_lbl.setText(f"{pnl_sign}{pnl_pct:.1f}%")
            self._port_pct_lbl.setStyleSheet(f"color: {pnl_col}; background: transparent; border: none;")

        # Card 1: Today's Change
        dc_col = GREEN if total_day_change >= 0 else RED
        dc_sign = "+" if total_day_change >= 0 else ""
        self._today_value_lbl.setText(f"{dc_sign}{fmt_eur(total_day_change)}" if n_holdings else "—")
        self._today_value_lbl.setStyleSheet(f"color: {dc_col}; background: transparent; border: none; outline: none;")
        font = self._today_value_lbl.font()
        font.setPixelSize(28)
        self._today_value_lbl.setFont(font)

        total_prev = total_eur - total_day_change
        dc_pct = (total_day_change / total_prev * 100) if total_prev else 0.0
        if n_holdings:
            self._today_pct_pill.setText(f"{dc_sign}{dc_pct:.2f}%")
            _r, _g, _b = int(dc_col[1:3], 16), int(dc_col[3:5], 16), int(dc_col[5:7], 16)
            self._today_pct_pill.setStyleSheet(
                f"color: {dc_col}; background: rgba({_r},{_g},{_b},30);"
                " border-radius: 999px; padding: 2px 8px; font-size: 11px; border: none;"
            )
            self._today_holdings_lbl.setText(
                f"across {n_holdings} holding{'s' if n_holdings != 1 else ''}"
            )

        # Per-holding rows
        _clear_layout(self._today_holdings_layout)
        for p in positions:
            d = self._price_data.get(p["ticker"]) or cache.get(p["ticker"])
            if not d:
                continue
            eur_rate = d.get("eur_rate", 1.0) or 1.0
            dc = (d.get("day_change") or 0.0) * eur_rate * p["shares"]
            dcp = d.get("day_change_pct") or 0.0
            dc_c = GREEN if dc >= 0 else RED
            s = "+" if dc >= 0 else ""
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(8)
            tick_l = QLabel(p["ticker"])
            tick_l.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            tick_l.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            tick_l.setFont(QFont(FONT, 12))
            tick_l.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
            tick_l.setFixedWidth(80)
            row_h.addWidget(tick_l)
            val_l = QLabel(f"{s}{fmt_eur(dc)} ({s}{dcp:.2f}%)")
            val_l.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            val_l.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            val_l.setFont(QFont("Courier New", 12))
            val_l.setStyleSheet(f"color: {dc_c}; background: transparent; border: none;")
            row_h.addWidget(val_l)
            row_h.addStretch()
            self._today_holdings_layout.addWidget(row_w)

        # Card 2: update reminder option button highlights
        reminder = get_portfolio_reminder()
        if reminder:
            for btn in self._reminder_option_btns:
                btn.setStyleSheet(
                    "QPushButton { background: transparent; border: 1px solid #1a2e45;"
                    " border-radius: 6px; color: #6b8fa8; padding: 4px 10px; }"
                    " QPushButton:hover { background: rgba(255,255,255,0.04); }"
                )

    def _render_rebalance_bar(self) -> None:
        reminder = get_portfolio_reminder()
        if not reminder or not dict(reminder).get("is_enabled"):
            self._rebalance_bar.setVisible(False)
            return
        r = dict(reminder)
        try:
            rem_date_obj = datetime.strptime(r["reminder_date"], "%d.%m.%Y").date()
            days = (rem_date_obj - date.today()).days
        except Exception:
            self._rebalance_bar.setVisible(False)
            return
        self._rebalance_date_lbl.setText(f"Next rebalance: {r['reminder_date']}")
        self._rebalance_days_lbl.setText(f"{days} days away · annual interval")
        self._rebalance_pill.setVisible(True)
        self._rebalance_bar.setVisible(True)

    def _render_allocation_section(self, positions: list[dict], cache: dict) -> None:
        _clear_layout(self._alloc_legend_layout)

        valued: list[tuple[str, float, str]] = []
        port_total = 0.0
        for p in positions:
            d = self._price_data.get(p["ticker"]) or cache.get(p["ticker"])
            if d:
                price_eur = d.get("price_eur") or d.get("price", 0.0)
                val = p["shares"] * price_eur
                if val > 0:
                    name = d.get("name") or p["ticker"]
                    valued.append((p["ticker"], val, name))
                    port_total += val

        if not valued:
            self._alloc_card.setVisible(False)
            return
        self._alloc_card.setVisible(True)

        total = sum(v for _, v, _ in valued)
        colors = [self._DONUT_COLORS[i % len(self._DONUT_COLORS)] for i in range(len(valued))]

        self._valued_alloc = valued
        self._alloc_colors = colors
        self._render_alloc_donut("Current")

        # Legend
        for i, (ticker, val, name) in enumerate(valued):
            col = colors[i]
            pct = val / total * 100

            legend_row = QWidget()
            legend_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            legend_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            legend_row.setStyleSheet("background: transparent;")
            leg_h = QHBoxLayout(legend_row)
            leg_h.setContentsMargins(0, 0, 0, 0)
            leg_h.setSpacing(10)

            swatch = QFrame()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(f"background: {col}; border-radius: 6px; border: none;")
            leg_h.addWidget(swatch)

            name_v = QVBoxLayout()
            name_v.setSpacing(1)
            tick_lbl = QLabel(ticker)
            tick_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            tick_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            tick_lbl.setFont(QFont(FONT, 12, QFont.Weight.Bold))
            tick_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
            name_str = name[:30] if len(name) > 30 else name
            full_name_lbl = QLabel(name_str)
            full_name_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            full_name_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            full_name_lbl.setFont(QFont(FONT, 10))
            full_name_lbl.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
            name_v.addWidget(tick_lbl)
            name_v.addWidget(full_name_lbl)
            leg_h.addLayout(name_v, stretch=1)

            pct_lbl = QLabel(f"{pct:.0f}%")
            pct_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            pct_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            pct_lbl.setFont(QFont(FONT, 12))
            pct_lbl.setStyleSheet(f"color: {col}; background: transparent; border: none;")
            leg_h.addWidget(pct_lbl)

            val_lbl = QLabel(fmt_eur(val))
            val_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            val_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            val_lbl.setFont(QFont("Courier New", 11))
            val_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
            leg_h.addWidget(val_lbl)

            self._alloc_legend_layout.addWidget(legend_row)

    def _render_alloc_donut(self, mode: str) -> None:
        # Update segment button active styles
        for i, btn in enumerate(self._seg_btns):
            is_active = ["Current", "Target", "Drift"][i] == mode
            btn.setStyleSheet(self._SEG_ACTIVE if is_active else self._SEG_INACTIVE)

        lay = self._alloc_chart_container.layout()
        if lay is not None:
            _clear_layout(lay)

        valued = getattr(self, "_valued_alloc", [])
        colors = getattr(self, "_alloc_colors", [])
        if not valued:
            return

        total = sum(v for _, v, _ in valued)
        _BG = "#0d1520"

        try:
            fig = Figure(figsize=(2.4, 2.4), dpi=100)
            fig.patch.set_facecolor(_BG)
            ax = fig.add_subplot(111)
            ax.set_facecolor(_BG)

            if mode == "Current":
                values_list = [v for _, v, _ in valued]
                ax.pie(
                    values_list, colors=colors, startangle=90,
                    wedgeprops=dict(width=0.52, edgecolor=_BG, linewidth=2),
                )
                ax.set_aspect("equal")

            elif mode == "Target":
                n = len(valued)
                equal = [1.0 / n] * n
                ax.pie(
                    equal, colors=colors, startangle=90,
                    wedgeprops=dict(width=0.52, edgecolor=_BG, linewidth=2),
                )
                ax.set_aspect("equal")

            elif mode == "Drift":
                ax.set_facecolor(_BG)
                ax.spines[:].set_visible(False)
                ax.tick_params(colors="#5a7a94", labelsize=8)
                ax.yaxis.set_visible(False)
                n = len(valued)
                current_pcts = [v / total * 100 for _, v, _ in valued]
                target_pcts = [100.0 / n] * n
                drifts = [c - t for c, t in zip(current_pcts, target_pcts)]
                tickers = [t for t, _, _ in valued]
                bar_colors = [GREEN if d >= 0 else RED for d in drifts]
                ax.bar(range(n), drifts, color=bar_colors, width=0.6)
                ax.set_xticks(range(n))
                ax.set_xticklabels(tickers, fontsize=8, color="#5a7a94")
                ax.axhline(y=0, color="#1e3a55", linewidth=0.8)

            fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)

            canvas = FigureCanvasQTAgg(fig)
            canvas.setStyleSheet(f"background: {_BG}; border: none;")
            from PyQt6.QtGui import QPalette as _QPal, QColor as _QCol
            _bg_c = _QCol(_BG)
            pal = _QPal()
            pal.setColor(_QPal.ColorRole.Window, _bg_c)
            pal.setColor(_QPal.ColorRole.Base, _bg_c)
            pal.setColor(_QPal.ColorRole.AlternateBase, _bg_c)
            canvas.setPalette(pal)
            canvas.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            canvas.setAutoFillBackground(True)
            canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            canvas.installEventFilter(self)
            canvas.setFixedSize(240, 240)

            lay = self._alloc_chart_container.layout()
            if lay is not None:
                lay.addWidget(canvas)

        except Exception:
            pass

    def _render_positions_grid(self, positions: list[dict], cache: dict) -> None:
        _clear_layout(self._positions_layout)

        if not positions:
            self._positions_widget.setVisible(False)
            return
        self._positions_widget.setVisible(True)

        grid_w = QWidget()
        grid_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        grid_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for i, pos in enumerate(positions):
            card = self._make_position_card(pos, cache)
            grid.addWidget(card, i // 2, i % 2)

        self._positions_layout.addWidget(grid_w)

    def _make_position_card(self, pos: dict, cache: dict) -> QFrame:
        ticker = pos["ticker"]
        d = self._price_data.get(ticker) or cache.get(ticker)

        card = make_card_l2()
        inner_v = QVBoxLayout(card)
        inner_v.setContentsMargins(20, 18, 20, 18)
        inner_v.setSpacing(10)

        # Header row: ticker + name | price + delta
        hdr_row = QWidget()
        hdr_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_row.setStyleSheet("background: transparent;")
        hdr_h = QHBoxLayout(hdr_row)
        hdr_h.setContentsMargins(0, 0, 0, 0)
        hdr_h.setSpacing(8)

        name_v = QVBoxLayout()
        name_v.setSpacing(2)
        tick_lbl = make_label(ticker, 16, bold=True)
        name_v.addWidget(tick_lbl)
        name_str = (d.get("name") if d else None) or ""
        if name_str:
            name_lbl = make_label(name_str[:32], 11, color=TEXT_DIM)
            name_v.addWidget(name_lbl)
        hdr_h.addLayout(name_v, stretch=1)

        if d:
            price_v = QVBoxLayout()
            price_v.setSpacing(2)
            price_v.setAlignment(Qt.AlignmentFlag.AlignRight)

            currency = (d.get("currency") or "USD").upper()
            price_eur = d.get("price_eur") or d.get("price", 0.0)
            sym = _CURR_SYM.get(currency, currency)
            price_raw = d.get("price", 0.0)
            price_lbl = make_label(f"{sym}{price_raw:,.2f}", 16, bold=True)
            price_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            price_v.addWidget(price_lbl)

            dc = d.get("day_change") or 0.0
            dcp = d.get("day_change_pct") or 0.0
            dc_col = GREEN if dc >= 0 else RED
            s = "+" if dc >= 0 else ""
            delta_lbl = make_label(f"{s}{dcp:.2f}%", 11, color=dc_col)
            delta_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            price_v.addWidget(delta_lbl)

            hdr_h.addLayout(price_v)
        inner_v.addWidget(hdr_row)

        # Sparkline placeholder
        spark_c = QWidget()
        spark_c.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        spark_c.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        spark_c.setFixedHeight(70)
        spark_c.setStyleSheet("background: #111d2e; border-radius: 8px;")
        inner_v.addWidget(spark_c)

        # Stats grid
        if d:
            eur_rate = d.get("eur_rate", 1.0) or 1.0
            price_eur = d.get("price_eur") or d.get("price", 0.0)
            cur_val = pos["shares"] * price_eur
            cost_val = pos["shares"] * pos["avg_buy_price"] * eur_rate
            pnl = cur_val - cost_val
            pnl_pct = (pnl / cost_val * 100) if cost_val else 0.0
            pnl_col = GREEN if pnl >= 0 else RED
            pnl_sign = "+" if pnl >= 0 else ""

            grid_w = QWidget()
            grid_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            grid_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            grid_w.setStyleSheet("background: transparent;")
            stats_grid = QGridLayout(grid_w)
            stats_grid.setContentsMargins(0, 0, 0, 0)
            stats_grid.setHorizontalSpacing(24)
            stats_grid.setVerticalSpacing(6)

            stats = [
                ("Shares", f"{pos['shares']:g}", TEXT_PRI),
                ("Avg cost", fmt_eur(pos["avg_buy_price"] * eur_rate), TEXT_PRI),
                ("Value", fmt_eur(cur_val), TEXT_PRI),
                ("P&L", f"{pnl_sign}{fmt_eur(pnl)} ({pnl_sign}{pnl_pct:.1f}%)", pnl_col),
            ]
            for i, (lbl_t, val_t, val_c) in enumerate(stats):
                row_idx = i // 2
                col_pair = (i % 2) * 2
                lbl = make_label(lbl_t, 11, color=TEXT_DIM)
                val = make_label(val_t, 13, bold=True, color=val_c)
                stats_grid.addWidget(lbl, row_idx * 2, col_pair)
                stats_grid.addWidget(val, row_idx * 2 + 1, col_pair)

            inner_v.addWidget(grid_w)
        else:
            inner_v.addWidget(make_label("Fetching price…", 13, color=TEXT_SEC))

        # Button row
        btn_row = QWidget()
        btn_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row.setStyleSheet("background: transparent;")
        btn_h = QHBoxLayout(btn_row)
        btn_h.setContentsMargins(0, 4, 0, 0)
        btn_h.setSpacing(8)

        edit_btn = QPushButton("Edit position")
        edit_btn.setFixedHeight(28)
        edit_btn.setFont(QFont(FONT, 12))
        edit_btn.setStyleSheet(
            "QPushButton { background: #1a2332; border: 1px solid #1e3448;"
            " border-radius: 6px; color: #6b8fa8; font-size: 12px; padding: 3px 10px; }"
            " QPushButton:hover { background: #1e2d3d; border-color: #00b4d8; color: #00d4ff; }"
        )
        edit_btn.clicked.connect(lambda _=False, p=pos: self._open_edit_dialog(p))
        btn_h.addWidget(edit_btn)

        hist_btn = QPushButton("View history")
        hist_btn.setFixedHeight(28)
        hist_btn.setFont(QFont(FONT, 12))
        hist_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #1a2e45;"
            " border-radius: 6px; color: #3d5a70; font-size: 12px; padding: 3px 10px; }"
            " QPushButton:hover { background: rgba(255,255,255,0.04); color: #6b8fa8; }"
        )
        btn_h.addWidget(hist_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedHeight(28)
        del_btn.setFixedWidth(60)
        del_btn.setFont(QFont(FONT, 11))
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid rgba(248,81,73,0.5);"
            " border-radius: 6px; color: #f85149; font-size: 11px; padding: 2px 6px; }"
            " QPushButton:hover { background: rgba(248,81,73,0.12); border-color: #f85149; }"
        )
        del_btn.clicked.connect(lambda _=False, pid=pos["id"]: self._open_delete_dialog(pid))
        btn_h.addStretch()
        btn_h.addWidget(del_btn)

        inner_v.addWidget(btn_row)

        return card

    # ── Reminder option buttons ───────────────────────────────────────────────

    def _on_reminder_option(self, option: str) -> None:
        if option == "Off":
            upsert_portfolio_reminder("", 0)
        else:
            if option == "1 day":
                days = 1
            elif option == "1 week":
                days = 7
            else:
                days = 30
            try:
                from datetime import timedelta
                target = date.today() + timedelta(days=days)
                upsert_portfolio_reminder(target.strftime("%d.%m.%Y"), 1)
            except Exception:
                pass
        labels = ["1 day", "1 week", "1 month", "Off"]
        for btn, lbl in zip(self._reminder_option_btns, labels):
            is_active = lbl == option
            if is_active:
                btn.setStyleSheet(
                    "QPushButton { background: rgba(0,180,216,0.15); border: 1px solid rgba(0,180,216,0.5);"
                    " border-radius: 6px; color: #00b4d8; padding: 4px 10px; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: transparent; border: 1px solid #1a2e45;"
                    " border-radius: 6px; color: #6b8fa8; padding: 4px 10px; }"
                    " QPushButton:hover { background: rgba(255,255,255,0.04); }"
                )
        self._render_rebalance_bar()
        self._render_reminder_banner()
        self._render_reminder_status()

    # ── Background price fetch ────────────────────────────────────────────────

    def _start_fetch(self) -> None:
        if self._fetch_in_progress:
            return
        self._fetch_in_progress = True
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("...")
        self._status_lbl.setText("Fetching live prices…")

        positions = get_portfolio_positions()
        tickers = [p["ticker"] for p in positions]

        def do_fetch() -> None:
            data = _fetch_prices(tickers)
            if data:
                self._price_data = data
                self._using_cache = False
                self._last_updated = datetime.now().strftime("%H:%M")
                for ticker, info in data.items():
                    upsert_portfolio_cache(
                        ticker, info["price"], info["currency"],
                        info.get("day_change"), info.get("day_change_pct"),
                        info.get("name"), price_eur=info.get("price_eur"),
                    )
            else:
                # Fallback: use DB cache
                cached = get_portfolio_cache()
                if cached:
                    self._price_data = {}
                    for ticker, v in cached.items():
                        currency = (v.get("currency") or "USD").upper()
                        price_eur = v.get("price_eur") or v.get("price", 0.0)
                        price = v.get("price", 0.0) or 1.0
                        eur_rate = (price_eur / price) if price else 1.0
                        self._price_data[ticker] = {
                            "price": v.get("price", 0.0),
                            "price_eur": price_eur,
                            "currency": currency,
                            "day_change": v.get("day_change"),
                            "day_change_pct": v.get("day_change_pct"),
                            "eur_rate": eur_rate,
                            "name": v.get("name"),
                        }
                    self._using_cache = True
            self._fetch_in_progress = False
            QTimer.singleShot(0, self._on_fetch_done)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_fetch_done(self) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("⟳  Refresh")
        self._render_all()
        if not self._using_cache:
            self._status_lbl.setText("Prices updated")
            self._status_lbl.setStyleSheet(f"color: {GREEN}; background: transparent; border: none;")
            QTimer.singleShot(3000, self._update_status)

    def _update_status(self) -> None:
        if self._fetch_in_progress:
            self._status_lbl.setText("Fetching live prices…")
            self._status_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        elif self._using_cache:
            self._status_lbl.setText("Using cached prices (live fetch failed)")
            self._status_lbl.setStyleSheet("color: #FFC107; background: transparent; border: none;")
        elif self._last_updated:
            self._status_lbl.setText(f"Last updated: {self._last_updated}")
            self._status_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        else:
            self._status_lbl.setText("")

    # ── Reminder ──────────────────────────────────────────────────────────────

    def _on_set_reminder(self, choice: str) -> None:
        if choice == "Set reminder ▾":
            return
        # Reset combo to index 0 regardless of outcome
        self._reminder_combo.blockSignals(True)
        self._reminder_combo.setCurrentIndex(0)
        self._reminder_combo.blockSignals(False)

        if choice == "In 1 year":
            today = date.today()
            try:
                next_year = today.replace(year=today.year + 1)
            except ValueError:
                next_year = today.replace(year=today.year + 1, day=28)
            upsert_portfolio_reminder(next_year.strftime("%d.%m.%Y"), 1)
            self._render_reminder_status()
            self._render_reminder_banner()
        elif choice == "Custom...":
            self._open_reminder_custom_dialog()

    def _open_reminder_custom_dialog(self) -> None:
        today = date.today()
        try:
            default_date = today.replace(year=today.year + 1)
        except ValueError:
            default_date = today.replace(year=today.year + 1, day=28)

        dlg = open_dialog(self, 340, 170)
        dlg.setWindowTitle("Set Rebalance Reminder")

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(20, 16, 20, 16)
        dlg_layout.setSpacing(8)

        dlg_layout.addWidget(make_label("Reminder date (DD.MM.YYYY)", 13, color=TEXT_SEC))

        date_entry = QLineEdit()
        date_entry.setText(default_date.strftime("%d.%m.%Y"))
        date_entry.setFont(QFont(FONT, 13))
        date_entry.setFixedWidth(200)
        dlg_layout.addWidget(date_entry)

        err_lbl = make_label("", 12, color=RED)
        dlg_layout.addWidget(err_lbl)

        btn_row_w = QWidget()
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row_w.setStyleSheet("background: transparent; border: none;")
        btn_row = QHBoxLayout(btn_row_w)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "accent")
        save_btn.setFixedSize(90, 32)
        save_btn.setFont(QFont(FONT, 13))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setFont(QFont(FONT, 13))
        cancel_btn.clicked.connect(dlg.reject)

        def _save() -> None:
            date_str = date_entry.text().strip()
            try:
                datetime.strptime(date_str, "%d.%m.%Y")
            except ValueError:
                err_lbl.setText("Invalid date. Use DD.MM.YYYY")
                return
            upsert_portfolio_reminder(date_str, 1)
            dlg.accept()

        save_btn.clicked.connect(_save)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        dlg_layout.addWidget(btn_row_w)

        dlg.exec()
        self._render_reminder_status()
        self._render_reminder_banner()

    def _render_reminder_banner(self) -> None:
        reminder = get_portfolio_reminder()
        if not reminder or not dict(reminder).get("is_enabled"):
            self._reminder_banner.setVisible(False)
            return
        try:
            rem_date = datetime.strptime(dict(reminder)["reminder_date"], "%d.%m.%Y").date()
        except (ValueError, KeyError):
            self._reminder_banner.setVisible(False)
            return

        days_away = (rem_date - date.today()).days
        if days_away > 30:
            self._reminder_banner.setVisible(False)
            return

        r = dict(reminder)
        if days_away < 0:
            msg = f"Portfolio rebalance overdue: {r['reminder_date']}"
        else:
            msg = f"Portfolio rebalance due in {days_away} day{'s' if days_away != 1 else ''}: {r['reminder_date']}"

        self._reminder_banner_lbl.setText(msg)
        self._reminder_banner.setVisible(True)

    def _render_reminder_status(self) -> None:
        reminder = get_portfolio_reminder()
        if not reminder:
            self._reminder_status_lbl.setText("No reminder set.")
            self._reminder_status_lbl.setStyleSheet(
                f"color: {TEXT_SEC}; background: transparent; border: none;"
            )
            return

        r = dict(reminder)
        if not r.get("is_enabled"):
            self._reminder_status_lbl.setText("No reminder set.")
            self._reminder_status_lbl.setStyleSheet(
                f"color: {TEXT_SEC}; background: transparent; border: none;"
            )
            return

        try:
            rem_date = datetime.strptime(r["reminder_date"], "%d.%m.%Y").date()
        except (ValueError, KeyError):
            self._reminder_status_lbl.setText("")
            return

        today = date.today()
        days_away = (rem_date - today).days
        if days_away < 0:
            text = f"Rebalance overdue: {r['reminder_date']}"
            color = "#f0c040"
        elif days_away <= 30:
            text = f"Rebalance due soon: {r['reminder_date']}  ({days_away} days)"
            color = "#f0c040"
        else:
            text = f"Next rebalance: {r['reminder_date']}  ({days_away} days away)"
            color = ACCENT

        self._reminder_status_lbl.setText(text)
        self._reminder_status_lbl.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

    # ── Position dialogs ──────────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        self._position_dialog(None)

    def _open_edit_dialog(self, pos: dict) -> None:
        self._position_dialog(pos)

    def _position_dialog(self, pos: dict | None) -> None:
        is_edit = pos is not None
        dlg = open_dialog(self, 460, 350 if not is_edit else 310)
        dlg.setWindowTitle("Edit Position" if is_edit else "Add Position")

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(20, 16, 20, 16)
        dlg_layout.setSpacing(6)

        heading = make_label("Edit Position" if is_edit else "Add Position", 15, bold=True)
        heading.setContentsMargins(0, 0, 0, 8)
        dlg_layout.addWidget(heading)

        # Field helper
        def add_field(label_text: str, placeholder: str = "") -> QLineEdit:
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row_w)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            lbl = make_label(label_text, 13, color=TEXT_SEC)
            lbl.setFixedWidth(140)
            row_layout.addWidget(lbl)
            entry = QLineEdit()
            entry.setFont(QFont(FONT, 13))
            entry.setPlaceholderText(placeholder)
            row_layout.addWidget(entry, 1)
            dlg_layout.addWidget(row_w)
            return entry

        ticker_entry = add_field("Ticker", "e.g. AAPL")
        if is_edit:
            ticker_entry.setText(pos["ticker"])
            ticker_entry.setEnabled(False)
        else:
            hint = make_label(
                "Include exchange suffix for non-US stocks.\n"
                "Examples: VWCE.DE (Xetra), VOO (NYSE), AAPL (NASDAQ)",
                11, color=TEXT_SEC,
            )
            hint.setWordWrap(True)
            hint.setContentsMargins(148, 0, 0, 4)
            dlg_layout.addWidget(hint)

        shares_entry = add_field("Shares", "e.g. 10")
        bind_numeric_entry(shares_entry, decimals=8)
        if is_edit:
            shares_entry.setText(str(pos["shares"]))

        avg_entry = add_field("Avg Buy Price", "e.g. 150.00")
        bind_numeric_entry(avg_entry)
        if is_edit:
            avg_entry.setText(str(pos["avg_buy_price"]))

        # Currency combo
        curr_row_w = QWidget()
        curr_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        curr_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        curr_row_w.setStyleSheet("background: transparent; border: none;")
        curr_row = QHBoxLayout(curr_row_w)
        curr_row.setContentsMargins(0, 0, 0, 0)
        curr_row.setSpacing(8)
        curr_lbl = make_label("Currency", 13, color=TEXT_SEC)
        curr_lbl.setFixedWidth(140)
        curr_row.addWidget(curr_lbl)
        curr_combo = QComboBox()
        curr_combo.addItems(_CURRENCIES)
        curr_combo.setFont(QFont(FONT, 13))
        if is_edit:
            idx = curr_combo.findText(pos.get("currency", "USD"))
            if idx >= 0:
                curr_combo.setCurrentIndex(idx)
        curr_row.addWidget(curr_combo, 1)
        dlg_layout.addWidget(curr_row_w)

        notes_entry = add_field("Notes (optional)", "")
        if is_edit:
            notes_entry.setText(pos.get("notes") or "")

        err_lbl = make_label("", 12, color=RED)
        dlg_layout.addWidget(err_lbl)

        btn_row_w = QWidget()
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row_w.setStyleSheet("background: transparent; border: none;")
        btn_row = QHBoxLayout(btn_row_w)
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.setSpacing(8)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "accent")
        save_btn.setFixedSize(100, 32)
        save_btn.setFont(QFont(FONT, 13))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setFont(QFont(FONT, 13))
        cancel_btn.clicked.connect(dlg.reject)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        dlg_layout.addWidget(btn_row_w)

        def _set_busy(busy: bool) -> None:
            save_btn.setEnabled(not busy)
            cancel_btn.setEnabled(not busy)
            save_btn.setText("Checking…" if busy else "Save")

        def _commit(ticker: str, shares: float, avg: float) -> None:
            if is_edit:
                update_position(
                    pos["id"], ticker, shares, avg,
                    curr_combo.currentText(), notes_entry.text().strip()
                )
            else:
                add_position(ticker, shares, avg, curr_combo.currentText(), notes_entry.text().strip())
            dlg.accept()

        def _on_validate_done(valid: bool, ticker: str, shares: float, avg: float) -> None:
            if not dlg.isVisible():
                return
            _set_busy(False)
            if valid:
                _commit(ticker, shares, avg)
            else:
                err_lbl.setText(
                    "Ticker not found. Please check the symbol and\n"
                    "exchange suffix (e.g. VWCE.DE not VWCE)"
                )

        def _on_save() -> None:
            ticker = ticker_entry.text().strip().upper()
            if not ticker:
                err_lbl.setText("Ticker is required.")
                return
            try:
                shares = float(shares_entry.text().strip())
                if shares <= 0:
                    raise ValueError
            except ValueError:
                err_lbl.setText("Shares must be a positive number.")
                return
            try:
                avg = float(avg_entry.text().strip())
                if avg < 0:
                    raise ValueError
            except ValueError:
                err_lbl.setText("Avg buy price must be >= 0.")
                return

            if is_edit:
                _commit(ticker, shares, avg)
                return

            # New position: validate ticker in background
            err_lbl.setText("")
            _set_busy(True)

            _commit(ticker, shares, avg)

        save_btn.clicked.connect(_on_save)
        dlg.exec()
        self._render_all()

    def _open_delete_dialog(self, position_id: int) -> None:
        positions = get_portfolio_positions()
        ticker = next((p["ticker"] for p in positions if p["id"] == position_id), "this position")

        dlg = open_dialog(self, 400, 140)
        dlg.setWindowTitle("Delete Position")

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(20, 20, 20, 12)
        dlg_layout.setSpacing(12)

        msg_lbl = make_label(f"Delete {ticker}? This cannot be undone.", 13)
        msg_lbl.setWordWrap(True)
        dlg_layout.addWidget(msg_lbl)

        btn_row_w = QWidget()
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row_w.setStyleSheet("background: transparent; border: none;")
        btn_row = QHBoxLayout(btn_row_w)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        del_btn = QPushButton("Delete")
        del_btn.setProperty("class", "danger")
        del_btn.setFixedSize(90, 32)
        del_btn.setFont(QFont(FONT, 13))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setFont(QFont(FONT, 13))
        cancel_btn.clicked.connect(dlg.reject)

        def _confirm() -> None:
            delete_position(position_id)
            dlg.accept()

        del_btn.clicked.connect(_confirm)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        dlg_layout.addWidget(btn_row_w)

        dlg.exec()
        self._render_all()
