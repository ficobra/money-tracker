import calendar
import csv
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QFileDialog, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import numpy as np
import matplotlib
import matplotlib.colors
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from database.db import (
    get_latest_snapshots, get_all_snapshots, get_all_expenses,
    get_snapshot, get_earliest_snapshot, get_extra_income,
    get_snapshot_income, get_setting, get_portfolio_positions,
    get_portfolio_cache, get_portfolio_reminder,
)
from PyQt6.QtGui import QColor, QPalette
from styles.theme import (
    BG_CARD, BG_ELEM, ACCENT, TEXT_PRI, TEXT_SEC,
    BORDER, GREEN, RED, FONT
)
from utils import fmt_eur, fmt_eur_signed

matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['text.color'] = '#eef2f7'
matplotlib.rcParams['axes.labelcolor'] = '#eef2f7'
matplotlib.rcParams['xtick.color'] = '#5a7a94'
matplotlib.rcParams['ytick.color'] = '#5a7a94'

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]


def _mlabel(year: int, month: int) -> str:
    return f"{MONTHS[month - 1]} {year}"


def make_label(text: str, size: int = 13, bold: bool = False, color: str = TEXT_PRI) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT, size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none; outline: none;")
    return lbl


def make_card_l3() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #162440;"
        "border-top: 1px solid #2a4a6a;"
        "border-left: 1px solid #1e3a55;"
        "border-right: 1px solid #0d1a28;"
        "border-bottom: 1px solid #0d1a28;"
        "border-radius: 14px;"
    )
    f.setContentsMargins(0, 0, 0, 0)
    return f


def make_card_l2() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #111d2e;"
        "border: 1px solid #1a2e45;"
        "border-radius: 14px;"
    )
    f.setContentsMargins(0, 0, 0, 0)
    return f


def make_card_l1() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #0d1520;"
        "border: 1px solid #0f1e30;"
        "border-radius: 12px;"
    )
    f.setContentsMargins(0, 0, 0, 0)
    return f


def make_card() -> QFrame:
    return make_card_l2()


def make_divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setFixedHeight(1)
    f.setProperty("class", "divider")
    f.setStyleSheet("background: #1a2e45; border: none;")
    return f


def make_eyebrow(left_text: str, right_text: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    left = QLabel(left_text.upper())
    left.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    left.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    left.setStyleSheet("color: #6b7d94; font-size: 11px; letter-spacing: 2px; background: transparent; border: none;")
    row.addWidget(left)
    if right_text:
        right = QLabel(right_text)
        right.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        right.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        right.setStyleSheet("color: #6b7d94; font-size: 11px; font-family: 'Courier New'; background: transparent; border: none;")
        right.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(right)
    return row


def make_pill(text: str, color: str = ACCENT, bg_alpha: float = 0.12) -> QFrame:
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    alpha = bg_alpha
    base_r, base_g, base_b = 0x11, 0x1d, 0x2e
    blended_r = int(base_r + (r - base_r) * alpha)
    blended_g = int(base_g + (g - base_g) * alpha)
    blended_b = int(base_b + (b - base_b) * alpha)
    bg_hex = f"#{blended_r:02x}{blended_g:02x}{blended_b:02x}"
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.NoFrame)
    frame.setFixedHeight(22)
    frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    frame.setStyleSheet(f"QFrame {{ background: {bg_hex}; border-radius: 10px; border: none; }}")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(8, 0, 8, 0)
    layout.setSpacing(0)
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none; font-size: 11px; font-weight: 500;")
    layout.addWidget(lbl)
    return frame


def _clear_layout(layout) -> None:
    """Remove all widgets and sub-layouts from a layout."""
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        else:
            sub = item.layout()
            if sub is not None:
                _clear_layout(sub)


class DashboardView(QScrollArea):

    _DONUT_COLORS = [
        "#00b4d8", "#3fb950", "#f0c040", "#f85149",
        "#a371f7", "#fd8c73", "#79c0ff",
    ]

    def __init__(self, navigate_callback=None):
        super().__init__()
        self._navigate = navigate_callback
        self._export_status: QLabel | None = None
        self._pred_year_filter: str = "All"
        self._fx_total: float = 0.0
        self._fx_count: int = 0

        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        # ── Content widget ────────────────────────────────────────────────────
        self._content = QWidget()
        self._content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content.setStyleSheet("background: #0d1117;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(8)
        self.setWidget(self._content)

        self._build()
        self.refresh()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        cl = self._content_layout

        # ── Reminder banner (hidden initially) ────────────────────────────────
        self._reminder_widget = QWidget()
        self._reminder_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._reminder_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._reminder_widget.setVisible(False)
        self._reminder_widget.setStyleSheet("background: transparent;")
        self._reminder_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._reminder_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._reminder_layout = QVBoxLayout(self._reminder_widget)
        self._reminder_layout.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self._reminder_widget)

        # ── Header row ────────────────────────────────────────────────────────
        header_row = QWidget()
        header_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        header_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        header_row.setStyleSheet("background: transparent;")
        header_h = QHBoxLayout(header_row)
        header_h.setContentsMargins(0, 4, 0, 0)

        title_lbl = make_label("Dashboard", 22, bold=True)
        header_h.addWidget(title_lbl, stretch=1)

        self._period_label = make_label("", 13, color=TEXT_SEC)
        self._period_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_h.addWidget(self._period_label)
        cl.addWidget(header_row)

        subtitle = make_label("Monthly financial overview", 13, color=TEXT_SEC)
        subtitle.setContentsMargins(0, 0, 0, 8)
        cl.addWidget(subtitle)

        # ── Metric cards row ──────────────────────────────────────────────────
        cards_row = QWidget()
        cards_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        cards_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        cards_row.setStyleSheet("background: transparent;")
        cards_h = QHBoxLayout(cards_row)
        cards_h.setContentsMargins(0, 0, 0, 0)
        cards_h.setSpacing(8)

        # Card 0 — NET WORTH (hero card)
        nw_card = make_card_l3()
        nw_card.setFixedHeight(240)
        nw_v = QVBoxLayout(nw_card)
        nw_v.setContentsMargins(20, 20, 20, 20)
        nw_v.setSpacing(4)
        nw_v.addLayout(make_eyebrow("NET WORTH"))
        self._nw_value = make_label("—", 28, bold=True)
        font = self._nw_value.font()
        font.setPixelSize(48)
        self._nw_value.setFont(font)
        nw_v.addWidget(self._nw_value)
        self._nw_portfolio_lbl = make_label("", 12, color="#9fb0c5")
        self._nw_portfolio_lbl.setFixedHeight(16)
        nw_v.addWidget(self._nw_portfolio_lbl)
        self._nw_pill_row = QWidget()
        self._nw_pill_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._nw_pill_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._nw_pill_row.setStyleSheet("background: transparent; border: none;")
        _nw_pill_h = QHBoxLayout(self._nw_pill_row)
        _nw_pill_h.setContentsMargins(0, 0, 0, 0)
        _nw_pill_h.setSpacing(4)
        _nw_pill_h.addStretch()
        nw_v.addWidget(self._nw_pill_row)
        self._nw_spark_container = QWidget()
        self._nw_spark_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._nw_spark_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._nw_spark_container.setStyleSheet("background: transparent;")
        self._nw_spark_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._nw_spark_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._nw_spark_container.setFixedHeight(90)
        spark_layout = QVBoxLayout(self._nw_spark_container)
        spark_layout.setContentsMargins(0, 0, 0, 0)
        nw_v.addWidget(self._nw_spark_container)
        cards_h.addWidget(nw_card, stretch=3)

        # Card 1 — MONTHLY CHANGE
        ch_card = make_card()
        ch_card.setFixedHeight(240)
        ch_v = QVBoxLayout(ch_card)
        ch_v.setContentsMargins(20, 20, 20, 20)
        ch_v.setSpacing(4)
        ch_v.addLayout(make_eyebrow("MONTHLY CHANGE"))
        ch_v.addSpacing(6)

        # Net Worth row
        nw_row = QWidget()
        nw_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        nw_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        nw_row.setStyleSheet("background: transparent; border: none;")
        nw_row_h = QHBoxLayout(nw_row)
        nw_row_h.setContentsMargins(0, 0, 0, 0)
        nw_row_h.setSpacing(8)
        nw_row_h.addWidget(make_label("NET WORTH", 10, color=TEXT_SEC))
        nw_row_h.addStretch()
        self._change_value = make_label("—", 13, bold=True)
        nw_row_h.addWidget(self._change_value)
        ch_v.addWidget(nw_row)

        # Cash row
        cash_row = QWidget()
        cash_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        cash_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        cash_row.setStyleSheet("background: transparent; border: none;")
        cash_row_h = QHBoxLayout(cash_row)
        cash_row_h.setContentsMargins(0, 4, 0, 0)
        cash_row_h.setSpacing(8)
        cash_row_h.addWidget(make_label("CASH", 10, color=TEXT_SEC))
        cash_row_h.addStretch()
        self._cash_change_label = make_label("—", 13)
        cash_row_h.addWidget(self._cash_change_label)
        ch_v.addWidget(cash_row)
        ch_v.addStretch()
        self._change_spark_container = QWidget()
        self._change_spark_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._change_spark_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._change_spark_container.setStyleSheet("background: transparent;")
        self._change_spark_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._change_spark_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._change_spark_container.setFixedHeight(44)
        spark_layout2 = QVBoxLayout(self._change_spark_container)
        spark_layout2.setContentsMargins(0, 0, 0, 0)
        ch_v.addWidget(self._change_spark_container)
        self._avg_mo_label = make_label("", 11, color=TEXT_SEC)
        ch_v.addWidget(self._avg_mo_label)
        ch_v.addStretch()
        cards_h.addWidget(ch_card, stretch=2)

        # Card 2 — ALLOCATION (donut populated on refresh)
        alloc_card = make_card()
        alloc_card.setFixedHeight(240)
        alloc_card.setStyleSheet(
            "background: #111d2e;"
            " border: 1px solid #1a2e45;"
            " border-radius: 14px;"
        )
        alloc_v = QVBoxLayout(alloc_card)
        alloc_v.setContentsMargins(20, 10, 20, 10)
        alloc_v.setSpacing(4)
        alloc_v.addLayout(make_eyebrow("ALLOCATION"))
        self._alloc_card_container = QWidget()
        self._alloc_card_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._alloc_card_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._alloc_card_container.setStyleSheet("background: transparent; border: none;")
        self._alloc_card_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._alloc_card_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._alloc_card_layout = QVBoxLayout(self._alloc_card_container)
        self._alloc_card_layout.setContentsMargins(0, 0, 0, 0)
        alloc_v.addWidget(self._alloc_card_container, stretch=1)
        cards_h.addWidget(alloc_card, stretch=2)

        cl.addWidget(cards_row)

        # ── Extra cards ───────────────────────────────────────────────────────
        self._extra_cards_widget = QWidget()
        self._extra_cards_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._extra_cards_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._extra_cards_widget.setStyleSheet("background: transparent;")
        self._extra_cards_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._extra_cards_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._extra_cards_layout = QHBoxLayout(self._extra_cards_widget)
        self._extra_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._extra_cards_layout.setSpacing(8)
        cl.addWidget(self._extra_cards_widget)

        # ── Estimation (hidden initially) ─────────────────────────────────────
        self._estimation_widget = QWidget()
        self._estimation_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._estimation_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._estimation_widget.setStyleSheet("background: transparent;")
        self._estimation_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._estimation_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._estimation_layout = QVBoxLayout(self._estimation_widget)
        self._estimation_layout.setContentsMargins(0, 0, 0, 0)
        self._estimation_widget.setVisible(False)
        cl.addWidget(self._estimation_widget)

        # ── Prediction accuracy (hidden initially) ────────────────────────────
        self._prediction_widget = QWidget()
        self._prediction_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._prediction_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._prediction_widget.setStyleSheet("background: transparent;")
        self._prediction_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._prediction_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._prediction_layout = QVBoxLayout(self._prediction_widget)
        self._prediction_layout.setContentsMargins(0, 0, 0, 0)
        self._prediction_widget.setVisible(False)
        cl.addWidget(self._prediction_widget)

        # ── Annual overview ───────────────────────────────────────────────────
        cl.addWidget(make_divider())
        self._annual_widget = QWidget()
        self._annual_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._annual_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._annual_widget.setStyleSheet("background: transparent;")
        self._annual_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._annual_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._annual_layout = QVBoxLayout(self._annual_widget)
        self._annual_layout.setContentsMargins(0, 0, 0, 0)
        self._annual_layout.setSpacing(4)
        cl.addWidget(self._annual_widget)

        # ── Account Breakdown ─────────────────────────────────────────────────
        cl.addWidget(make_divider())
        cl.addWidget(make_label("Account Breakdown", 15, bold=True))
        self._breakdown_widget = QWidget()
        self._breakdown_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._breakdown_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._breakdown_widget.setStyleSheet("background: transparent;")
        self._breakdown_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._breakdown_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._breakdown_layout = QVBoxLayout(self._breakdown_widget)
        self._breakdown_layout.setContentsMargins(0, 0, 0, 0)
        self._breakdown_layout.setSpacing(2)
        cl.addWidget(self._breakdown_widget)

        # ── Snapshot History ──────────────────────────────────────────────────
        cl.addWidget(make_divider())
        cl.addWidget(make_label("Snapshot History", 15, bold=True))
        self._history_widget = QWidget()
        self._history_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._history_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._history_widget.setStyleSheet("background: transparent;")
        self._history_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._history_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._history_layout = QVBoxLayout(self._history_widget)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self._history_widget)

        # ── CSV Export ────────────────────────────────────────────────────────
        cl.addWidget(make_divider())
        export_row = QWidget()
        export_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        export_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        export_row.setStyleSheet("background: transparent;")
        export_h = QHBoxLayout(export_row)
        export_h.setContentsMargins(0, 4, 0, 16)
        export_h.setSpacing(12)

        export_btn = QPushButton("Export to CSV")
        export_btn.setFixedWidth(130)
        export_btn.clicked.connect(self._export_csv)
        export_h.addWidget(export_btn)

        self._export_status = make_label("", 12, color=TEXT_SEC)
        export_h.addWidget(self._export_status)
        export_h.addStretch()
        cl.addWidget(export_row)

        cl.addStretch()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        snapshots = get_latest_snapshots(3)
        expenses  = list(get_all_expenses())
        self._fx_total = sum(e["amount"] for e in expenses)
        self._fx_count = len(expenses)

        self._render_reminder()
        self._render_extra_cards(snapshots)

        if not snapshots:
            self._render_empty()
            self._render_estimation(None, expenses)
            self._render_annual()
            self._render_snapshot_history()
            return

        latest = snapshots[0]
        prev   = snapshots[1] if len(snapshots) >= 2 else None

        self._nw_value.setText(fmt_eur(latest["total"]))

        all_snaps = get_all_snapshots()
        if len(all_snaps) >= 2:
            snaps_slice   = all_snaps[-6:]
            month_labels  = [MONTHS[s["month"] - 1][:3] + " '" + str(s["year"])[-2:] for s in snaps_slice]
            self._add_sparkline(
                self._nw_spark_container,
                [s["total"] for s in snaps_slice],
                "line",
                bg="#162440",
                labels=month_labels,
                figsize=(1.7, 0.9),
            )
            cash_changes = [
                all_snaps[i + 1]["total"] - all_snaps[i]["total"]
                for i in range(len(all_snaps) - 1)
            ]
            self._add_sparkline(self._change_spark_container, cash_changes[-6:], "bar", bg="#111d2e")

        if prev:
            latest_str = _mlabel(latest['year'], latest['month'])
            prev_str = _mlabel(prev['year'], prev['month'])
            self._period_label.setText(
                f'<span style="color: #e8f4f8; font-weight: bold;">{latest_str}</span>'
                f'<span style="color: #6b8fa8;">  ·  vs {prev_str}</span>'
            )
            self._period_label.setTextFormat(Qt.TextFormat.RichText)
            self._render_comparison(latest, prev, self._fx_total)
        else:
            self._period_label.setText(_mlabel(latest["year"], latest["month"]))
            self._render_one_snapshot()

        if len(all_snaps) >= 2:
            def _total_incl(s: dict) -> float:
                return s["total"] + (s.get("portfolio_eur") or 0.0)
            def _change_guarded(a: dict, b: dict) -> float:
                a_port = a.get("portfolio_eur") or 0.0
                b_port = b.get("portfolio_eur") or 0.0
                if a_port > 0 and b_port > 0:
                    return _total_incl(b) - _total_incl(a)
                return b["total"] - a["total"]
            all_changes = [_change_guarded(all_snaps[i], all_snaps[i+1]) for i in range(len(all_snaps)-1)]
            first = all_snaps[0]
            last  = all_snaps[-1]
            elapsed_months = (last["year"] - first["year"]) * 12 + (last["month"] - first["month"])
            avg_mo = sum(all_changes) / elapsed_months if elapsed_months > 0 else 0.0
            avg_mo_sign = "+" if avg_mo >= 0 else ""
            cash_avg = sum(cash_changes) / elapsed_months if elapsed_months > 0 else 0.0
            cash_avg_sign = "+" if cash_avg >= 0 else ""
            self._avg_mo_label.setText(
                f"AVG/MO  {avg_mo_sign}{fmt_eur(avg_mo)}  ·  Cash {cash_avg_sign}{fmt_eur(cash_avg)}"
            )
            self._avg_mo_label.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        self._render_estimation(latest, expenses)
        self._render_prediction_accuracy(all_snaps)
        self._render_annual()
        self._render_snapshot_history()
        self._render_breakdown(latest, prev)

    # ── Reminder banner ───────────────────────────────────────────────────────

    def _render_reminder(self):
        _clear_layout(self._reminder_layout)

        today = date.today()
        if today.day <= 20:
            self._reminder_widget.setVisible(False)
            return

        if today.month == 1:
            prev_year, prev_month = today.year - 1, 12
        else:
            prev_year, prev_month = today.year, today.month - 1

        earliest = get_earliest_snapshot()
        if earliest is None:
            self._reminder_widget.setVisible(False)
            return

        e_year, e_month = earliest
        prev_as_int  = prev_year * 12 + prev_month
        first_as_int = e_year * 12 + e_month
        if prev_as_int <= first_as_int:
            self._reminder_widget.setVisible(False)
            return

        if get_snapshot(prev_year, prev_month) is not None:
            self._reminder_widget.setVisible(False)
            return

        month_name = MONTHS[prev_month - 1]

        banner = QFrame()
        banner.setStyleSheet(
            "QFrame { background: #3d3000; border-radius: 8px; border: none; }"
        )
        banner_h = QHBoxLayout(banner)
        banner_h.setContentsMargins(16, 10, 16, 10)

        lbl = QLabel(f"Reminder: No snapshot found for {month_name} {prev_year}.")
        lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl.setFont(QFont(FONT, 13))
        lbl.setStyleSheet("color: #f0c040; background: transparent;")
        banner_h.addWidget(lbl, stretch=1)

        go_btn = QPushButton("Go to Snapshot")
        go_btn.setFixedWidth(130)
        go_btn.setProperty("class", "accent")
        go_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: white; border: none; border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: #0096b4; }}"
        )

        def _go():
            from views.snapshot_entry import SnapshotEntryView
            SnapshotEntryView._pending_period = (prev_year, prev_month)
            if self._navigate:
                self._navigate("snapshot")

        go_btn.clicked.connect(_go)
        banner_h.addWidget(go_btn)

        self._reminder_layout.addWidget(banner)
        self._reminder_widget.setVisible(True)

    # ── Extra cards ───────────────────────────────────────────────────────────

    def _render_extra_cards(self, snapshots: list):
        _clear_layout(self._extra_cards_layout)

        latest    = snapshots[0] if snapshots else None
        prev_snap = snapshots[1] if len(snapshots) >= 2 else None

        # Portfolio data
        positions     = get_portfolio_positions()
        cache         = get_portfolio_cache()
        has_portfolio = bool(positions and cache)

        port_total_eur = 0.0
        port_cost_eur  = 0.0
        if has_portfolio:
            for pos in positions:
                t = pos["ticker"]
                if t not in cache:
                    continue
                c         = cache[t]
                price_eur = c.get("price_eur") or c["price"]
                eur_rate  = (price_eur / c["price"]) if c["price"] else 1.0
                port_total_eur += pos["shares"] * price_eur
                port_cost_eur  += pos["shares"] * pos["avg_buy_price"] * eur_rate

        # NW portfolio label — use stored portfolio_eur from snapshot for consistency with pill
        stored_port = (latest.get("portfolio_eur") or 0.0) if latest else 0.0
        if latest and stored_port > 0:
            self._nw_portfolio_lbl.setText(
                f"{fmt_eur(latest['total'] + stored_port)} incl. portfolio"
            )
        elif has_portfolio and latest and port_total_eur > 0:
            # Fall back to live value if no stored value yet
            self._nw_portfolio_lbl.setText(
                f"{fmt_eur(latest['total'] + port_total_eur)} incl. portfolio"
            )
        else:
            self._nw_portfolio_lbl.setText("")

        # Income data
        last_mo_income  = 0.0
        pct_change      = 0.0
        pct_color       = TEXT_SEC
        has_pct         = False
        prev_month_label = ""
        if latest:
            si = get_snapshot_income(latest["year"], latest["month"])
            ex = get_extra_income(latest["year"], latest["month"])
            last_mo_income = sum(si.values() if si else []) + sum(e["amount"] for e in ex)
            if prev_snap:
                si2 = get_snapshot_income(prev_snap["year"], prev_snap["month"])
                ex2 = get_extra_income(prev_snap["year"], prev_snap["month"])
                prev_income      = sum(si2.values() if si2 else []) + sum(e["amount"] for e in ex2)
                prev_month_label = MONTHS[prev_snap["month"] - 1]
                if prev_income > 0:
                    pct_change = (last_mo_income - prev_income) / prev_income * 100
                pct_color = GREEN if pct_change >= 0 else RED
                has_pct   = True
        has_income_data = bool(latest)

        # Always update the top-row ALLOCATION card container
        _clear_layout(self._alloc_card_layout)
        if has_portfolio:
            self._render_donut_chart(self._alloc_card_layout, positions, cache)
        else:
            self._alloc_card_layout.addWidget(make_label("No portfolio data", 12, color=TEXT_SEC))

        if not has_portfolio and not has_income_data:
            return

        if has_portfolio:
            pnl       = port_total_eur - port_cost_eur
            pnl_pct   = (pnl / port_cost_eur * 100) if port_cost_eur else 0.0
            pnl_color = GREEN if pnl >= 0 else RED
            pnl_sign  = "+" if pnl >= 0 else ""

            # Reminder date for eyebrow right label
            _reminder    = get_portfolio_reminder()
            _rem_right   = ""
            if _reminder and _reminder["is_enabled"]:
                _rem_right = f"REBALANCE {_reminder['reminder_date']}"

            # Portfolio card
            port_card = make_card()
            port_v = QVBoxLayout(port_card)
            port_v.setContentsMargins(20, 20, 20, 20)
            port_v.setSpacing(4)
            port_v.addLayout(make_eyebrow("PORTFOLIO", _rem_right))
            port_v.addWidget(make_label(fmt_eur(port_total_eur), 22, bold=True))
            arrow = "▲" if pnl >= 0 else "▼"
            pills_row = QWidget()
            pills_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            pills_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            pills_row.setStyleSheet("background: transparent; border: none;")
            pills_h = QHBoxLayout(pills_row)
            pills_h.setContentsMargins(0, 0, 0, 0)
            pills_h.setSpacing(4)
            pills_h.addWidget(make_pill(f"{arrow} {pnl_sign}{fmt_eur(pnl)}", color=pnl_color))
            pct_lbl = make_label(f"{pnl_sign}{pnl_pct:.1f}%", 11, color=pnl_color)
            pills_h.addWidget(pct_lbl)
            pills_h.addStretch()
            port_v.addWidget(pills_row)
            port_v.addStretch()
            self._extra_cards_layout.addWidget(port_card, stretch=1)

        # Fixed Expenses card (always in extra row)
        fx_card = make_card()
        fx_v = QVBoxLayout(fx_card)
        fx_v.setContentsMargins(20, 20, 20, 20)
        fx_v.setSpacing(4)
        fx_v.addLayout(make_eyebrow("FIXED EXPENSES", f"{self._fx_count} ITEMS"))
        fx_v.addWidget(make_label(fmt_eur(self._fx_total), 22, bold=True))
        fx_v.addStretch()
        self._extra_cards_layout.addWidget(fx_card, stretch=1)

        if has_income_data:
            _inc_month_right = MONTHS[latest["month"] - 1][:3].upper() if latest else ""
            inc_card = make_card()
            inc_v = QVBoxLayout(inc_card)
            inc_v.setContentsMargins(20, 20, 20, 20)
            inc_v.setSpacing(4)
            inc_v.addLayout(make_eyebrow("LAST MONTH INCOME", _inc_month_right))
            inc_v.addWidget(make_label(fmt_eur(last_mo_income), 22, bold=True))
            if has_pct:
                pct_sign  = "+" if pct_change >= 0 else ""
                pct_arrow = "▲" if pct_change >= 0 else "▼"
                pills_row_inc = QWidget()
                pills_row_inc.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                pills_row_inc.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                pills_row_inc.setStyleSheet("background: transparent; border: none;")
                pills_h_inc = QHBoxLayout(pills_row_inc)
                pills_h_inc.setContentsMargins(0, 0, 0, 0)
                pills_h_inc.setSpacing(4)
                pills_h_inc.addWidget(make_pill(f"{pct_arrow} {pct_sign}{pct_change:.1f}%", color=pct_color))
                pills_h_inc.addStretch()
                inc_v.addWidget(pills_row_inc)
                inc_v.addWidget(make_label(f"vs {prev_month_label}", 11, color=TEXT_SEC))
            inc_v.addStretch()
            self._extra_cards_layout.addWidget(inc_card, stretch=1)

    def _render_reminder_badge(self, parent_layout: QVBoxLayout):
        reminder = get_portfolio_reminder()
        if not reminder or not reminder["is_enabled"]:
            return
        try:
            rem_date = datetime.strptime(reminder["reminder_date"], "%d.%m.%Y").date()
        except ValueError:
            return
        days_away = (rem_date - date.today()).days
        if days_away < 0:
            text  = "Rebalance overdue"
            color = "#f0c040"
        elif days_away <= 30:
            text  = f"Rebalance due in {days_away}d"
            color = "#f0c040"
        else:
            text  = f"Rebalance: {reminder['reminder_date']}"
            color = TEXT_SEC
        parent_layout.addWidget(make_label(text, 11, color=color))

    def _render_donut_chart(self, parent_layout: QVBoxLayout, positions: list, cache: dict):
        valued = []
        for pos in positions:
            t = pos["ticker"]
            if t in cache:
                c         = cache[t]
                price_eur = c.get("price_eur") or c["price"]
                val       = pos["shares"] * price_eur
                if val > 0:
                    valued.append((t, val))

        if not valued:
            text = (
                "Add more positions to see allocation"
                if len(positions) < 2
                else "Refresh portfolio to see allocation"
            )
            parent_layout.addWidget(make_label(text, 12, color=TEXT_SEC))
            return

        labels = [f"{t[:6]}" for t, _ in valued]
        values = [v for _, v in valued]
        colors = [self._DONUT_COLORS[i % len(self._DONUT_COLORS)] for i in range(len(valued))]

        try:
            _BG_DONUT = "#111d2e"
            fig = Figure(figsize=(2.8, 1.8), dpi=100)
            fig.patch.set_facecolor(_BG_DONUT)
            ax  = fig.add_subplot(111)
            ax.set_facecolor(_BG_DONUT)

            wedges, *_ = ax.pie(
                values, colors=colors, startangle=90,
                wedgeprops=dict(width=0.52, edgecolor=_BG_DONUT, linewidth=2),
            )
            ax.set_aspect("equal")

            leg = ax.legend(
                wedges, labels,
                loc="center left", bbox_to_anchor=(1.02, 0.5),
                fontsize=7, facecolor=_BG_DONUT, edgecolor=BORDER,
                framealpha=0.0,
            )
            for txt in leg.get_texts():
                txt.set_color(TEXT_PRI)

            fig.subplots_adjust(left=0.0, right=0.55, top=1.0, bottom=0.0)

            canvas = FigureCanvasQTAgg(fig)
            canvas.setStyleSheet(f"background: {_BG_DONUT}; border: none;")
            _bg_color = QColor(_BG_DONUT)
            pal = QPalette()
            pal.setColor(QPalette.ColorRole.Window, _bg_color)
            pal.setColor(QPalette.ColorRole.Base, _bg_color)
            pal.setColor(QPalette.ColorRole.AlternateBase, _bg_color)
            canvas.setPalette(pal)
            canvas.setAutoFillBackground(True)

            canvas.setFixedHeight(160)
            parent_layout.addWidget(canvas)
            total_val = sum(values)
            total_row = QWidget()
            total_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            total_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            total_row.setStyleSheet("background: transparent; border: none;")
            total_h = QHBoxLayout(total_row)
            total_h.setContentsMargins(0, 0, 0, 0)
            total_h.addWidget(make_label("Total", 11, color=TEXT_SEC))
            total_h.addStretch()
            total_h.addWidget(make_label(fmt_eur(total_val), 11, bold=True))
            parent_layout.addWidget(total_row)
        except Exception:
            parent_layout.addWidget(make_label("Chart unavailable", 12, color=TEXT_SEC))

    # ── Snapshot state renderers ──────────────────────────────────────────────

    def _render_empty(self):
        self._period_label.setText("No data yet")
        self._nw_value.setText("—")
        self._nw_value.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
        if isinstance(self._change_value, QLabel):
            self._change_value.setText("—")
            self._change_value.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none; outline: none;")
        _clear_layout(self._breakdown_layout)

    def _render_one_snapshot(self):
        if isinstance(self._change_value, QLabel):
            self._change_value.setText("—")
            self._change_value.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none; outline: none;")
        if hasattr(self, '_cash_change_label') and isinstance(self._cash_change_label, QLabel):
            self._cash_change_label.setText("—")
            self._cash_change_label.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none; outline: none;")

    def _render_comparison(self, latest: dict, prev: dict, fx_total: float):  # noqa: ARG002
        latest_port = latest.get("portfolio_eur") or 0.0
        prev_port   = prev.get("portfolio_eur")   or 0.0
        # Only include portfolio in both sides if both snapshots have portfolio data
        # Avoids artificial spike when portfolio_eur transitions from 0 to a real value
        if latest_port > 0 and prev_port > 0:
            latest_total = latest["total"] + latest_port
            prev_total   = prev["total"]   + prev_port
        else:
            latest_total = latest["total"]
            prev_total   = prev["total"]
        change = latest_total - prev_total
        color  = GREEN if change >= 0 else RED
        arrow = "▲" if change >= 0 else "▼"
        cash_change = latest["total"] - prev["total"]
        cash_color = GREEN if cash_change >= 0 else RED
        cash_arrow = "▲" if cash_change >= 0 else "▼"

        # Replace _change_value widget with a pill in its parent layout
        nw_parent = self._change_value.parentWidget()
        nw_lay = nw_parent.layout() if nw_parent is not None else None
        if nw_lay is not None:
            nw_lay.removeWidget(self._change_value)
            self._change_value.deleteLater()
            self._change_value = make_pill(f"{arrow} {fmt_eur_signed(change)}", color=color)
            nw_lay.addWidget(self._change_value)

        # Replace _cash_change_label widget with a pill in its parent layout
        if hasattr(self, '_cash_change_label'):
            cash_parent = self._cash_change_label.parentWidget()
            cash_lay = cash_parent.layout() if cash_parent is not None else None
            if cash_lay is not None:
                cash_lay.removeWidget(self._cash_change_label)
                self._cash_change_label.deleteLater()
                self._cash_change_label = make_pill(f"{cash_arrow} {fmt_eur_signed(cash_change)}", color=cash_color)
                cash_lay.addWidget(self._cash_change_label)
        pct = (change / abs(prev_total) * 100) if prev_total else 0.0
        pct_sign = "+" if pct >= 0 else ""
        arrow = "▲" if change >= 0 else "▼"
        if hasattr(self, '_nw_pill_row') and self._nw_pill_row is not None:
            _clear_layout(self._nw_pill_row.layout())
            pill = make_pill(f"{arrow} {fmt_eur_signed(change)}", color=color)
            pct_lbl = make_label(f"{pct_sign}{pct:.1f}%", 11, color=color)
            self._nw_pill_row.layout().addWidget(pill)
            self._nw_pill_row.layout().addWidget(pct_lbl)
            self._nw_pill_row.layout().addStretch()
            self._nw_pill_row.setVisible(True)

    # ── Sparklines ────────────────────────────────────────────────────────────

    def _add_sparkline(self, container: QWidget, values: list, chart_type: str = "line", bg: str = BG_CARD, labels: list | None = None, figsize: tuple = (1.7, 0.42)):
        layout = container.layout()
        if layout is None:
            return
        _clear_layout(layout)

        if len(values) < 2:
            return
        try:
            BG = bg
            fig = Figure(figsize=figsize, dpi=100)
            ax  = fig.add_subplot(111)
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(BG)
            ax.axis("off")
            fig.subplots_adjust(left=0.02, right=0.98, top=1.0, bottom=0.05)

            x = list(range(len(values)))
            if chart_type == "line":
                ax.plot(x, values, color=ACCENT, linewidth=1.5, solid_capstyle="round")
                mn = min(values)
                from matplotlib.patches import PathPatch
                from matplotlib.path import Path
                z = np.linspace(0, 1, 100).reshape(100, 1)
                xmin, xmax = x[0], x[-1]
                ymin_val, ymax_val = mn, max(values)
                ax.imshow(
                    z,
                    aspect='auto',
                    extent=(xmin, xmax, ymin_val, ymax_val),
                    origin='lower',
                    cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
                        'teal_alpha',
                        [(0, (0, 0.706, 0.847, 0)),
                         (1, (0, 0.706, 0.847, 0.35))],
                    ),
                    zorder=0,
                )
                verts = (
                    [(xmin, ymin_val)]
                    + list(zip(x, values))
                    + [(xmax, ymin_val), (xmin, ymin_val)]
                )
                codes = (
                    [Path.MOVETO]
                    + [Path.LINETO] * len(values)
                    + [Path.LINETO, Path.CLOSEPOLY]
                )
                clip_path = PathPatch(
                    Path(verts, codes),
                    transform=ax.transData,
                    facecolor='none',
                    edgecolor='none',
                )
                ax.add_patch(clip_path)
                ax.images[-1].set_clip_path(clip_path)
                ax.axis("on")
                for spine in ax.spines.values():
                    spine.set_visible(False)
                ax.yaxis.set_visible(True)
                ax.yaxis.grid(True, color="#1e3a55", linewidth=0.5, linestyle="--", dashes=(3, 5))
                ax.set_yticks([mn, max(values)])
                ax.tick_params(axis="y", colors="none", length=0)
                if labels:
                    ax.xaxis.set_visible(True)
                    ax.set_xticks(x)
                    ax.set_xticklabels(labels, fontsize=7)
                    ax.tick_params(axis="x", colors="#6b7d94", labelsize=7, length=0)
                    fig.subplots_adjust(left=0.02, right=0.98, top=1.0, bottom=0.30)
                else:
                    ax.xaxis.set_visible(False)
                    fig.subplots_adjust(left=0.02, right=0.98, top=1.0, bottom=0.05)
            else:
                bar_colors = [GREEN if v >= 0 else RED for v in values]
                ax.bar(x, values, color=bar_colors, width=0.7)
                ax.axhline(y=0, color=BORDER, linewidth=0.5)

            canvas = FigureCanvasQTAgg(fig)
            canvas.setStyleSheet(f"background: {BG}; border: none;")
            pal = QPalette()
            _bg = QColor(BG)
            pal.setColor(QPalette.ColorRole.Window, _bg)
            pal.setColor(QPalette.ColorRole.Base, _bg)
            pal.setColor(QPalette.ColorRole.AlternateBase, _bg)
            canvas.setPalette(pal)
            canvas.setAutoFillBackground(True)
            layout.addWidget(canvas)
        except Exception:
            pass

    # ── End-of-month estimate ─────────────────────────────────────────────────

    def _render_estimation(self, latest: dict | None, expenses: list):
        _clear_layout(self._estimation_layout)

        if latest is None:
            self._estimation_widget.setVisible(False)
            return

        today    = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]

        if today.day >= last_day:
            self._estimation_widget.setVisible(False)
            return
        if get_snapshot(today.year, today.month) is not None:
            self._estimation_widget.setVisible(False)
            return

        daily_buffer  = float(get_setting("daily_buffer") or "20.0")
        buffer_cost   = last_day * daily_buffer
        all_fx        = list(expenses)
        fx_total      = sum(e["amount"] for e in all_fx)

        # Use recorded income for current month if already entered, otherwise use latest snapshot's income as estimate
        si_cur = get_snapshot_income(today.year, today.month)
        ex_cur = get_extra_income(today.year, today.month)
        if si_cur:
            expected_income = sum(si_cur.values()) + sum(e["amount"] for e in ex_cur)
        else:
            # Fall back to latest snapshot's income as a reasonable estimate
            si_lat = get_snapshot_income(latest["year"], latest["month"])
            ex_lat = get_extra_income(latest["year"], latest["month"])
            expected_income = (sum(si_lat.values()) + sum(e["amount"] for e in ex_lat)) if si_lat else 0.0

        estimated_eom = latest["total"] + expected_income - buffer_cost - fx_total
        est_change    = estimated_eom - latest["total"]

        card  = make_card_l1()
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(20, 16, 20, 16)
        card_v.setSpacing(4)

        card_v.addLayout(make_eyebrow("END-OF-MONTH ESTIMATE", f"{MONTHS[today.month - 1]} {today.year}"))

        card_v.addWidget(make_label(
            f"Based on {_mlabel(latest['year'], latest['month'])} snapshot",
            12, color=TEXT_SEC,
        ))
        card_v.addWidget(make_divider())

        def est_row(label: str, value: str, color: str = TEXT_PRI):
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 1, 0, 1)
            row_h.addWidget(make_label(label, 12, color=TEXT_SEC), stretch=1)
            row_h.addWidget(make_label(value, 12, color=color))
            card_v.addWidget(row_w)

        income_label = "Expected income (current month)" if si_cur else f"Expected income (est. from {_mlabel(latest['year'], latest['month'])})"
        est_row("Latest net worth", fmt_eur(latest["total"]))
        est_row(income_label, f"+{fmt_eur(expected_income)}", GREEN)
        est_row(
            f"Daily allowance  ({last_day} days × €{daily_buffer:.0f}/day)",
            f"–{fmt_eur(buffer_cost)}", RED,
        )
        est_row(
            "Fixed expenses this month",
            f"–{fmt_eur(fx_total)}", RED,
        )
        card_v.addWidget(make_divider())

        total_row = QWidget()
        total_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        total_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        total_row.setStyleSheet("background: transparent;")
        total_h = QHBoxLayout(total_row)
        total_h.setContentsMargins(0, 0, 0, 0)
        total_h.addWidget(make_label("Estimated end-of-month net worth", 13, bold=True), stretch=1)
        total_h.addWidget(make_label(
            f"{fmt_eur(estimated_eom)}  ({fmt_eur_signed(est_change)})",
            13, bold=True, color=GREEN if est_change >= 0 else RED,
        ))
        card_v.addWidget(total_row)

        self._estimation_layout.addWidget(card)
        self._estimation_widget.setVisible(True)

    # ── Prediction accuracy ───────────────────────────────────────────────────

    def _render_prediction_accuracy(self, all_snaps: list):
        _clear_layout(self._prediction_layout)

        if len(all_snaps) < 2:
            self._prediction_widget.setVisible(False)
            return

        daily_buffer = float(get_setting("daily_buffer") or "20.0")
        fx_total     = sum(e["amount"] for e in get_all_expenses())

        all_rows = []
        for i in range(1, len(all_snaps)):
            current  = all_snaps[i]
            prev     = all_snaps[i - 1]
            last_day = calendar.monthrange(current["year"], current["month"])[1]
            estimated = prev["total"] - (last_day * daily_buffer) - fx_total
            actual    = current["total"]
            delta     = actual - estimated
            all_rows.append((current["year"], current["month"], estimated, actual, delta))

        all_rows.reverse()  # most recent first

        available_years = sorted({r[0] for r in all_rows}, reverse=True)
        year_options    = ["All"] + [str(y) for y in available_years]
        most_recent_yr  = str(available_years[0]) if available_years else "All"

        if self._pred_year_filter not in year_options:
            self._pred_year_filter = most_recent_yr

        card  = make_card_l1()
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(20, 16, 20, 16)
        card_v.setSpacing(6)

        card_v.addLayout(make_eyebrow("PREDICTION ACCURACY HISTORY"))

        # Subtitle row with year filter
        sub_row = QWidget()
        sub_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        sub_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        sub_row.setStyleSheet("background: transparent;")
        sub_h = QHBoxLayout(sub_row)
        sub_h.setContentsMargins(0, 0, 0, 0)
        sub_h.addWidget(
            make_label("Estimated vs actual end-of-month net worth per month", 12, color=TEXT_SEC),
            stretch=1,
        )

        self._pred_year_combo = QComboBox()
        self._pred_year_combo.addItems(year_options)
        idx = self._pred_year_combo.findText(self._pred_year_filter)
        if idx >= 0:
            self._pred_year_combo.setCurrentIndex(idx)
        self._pred_year_combo.setFixedWidth(100)
        self._pred_year_combo.currentTextChanged.connect(self._on_pred_year_change)
        self._pred_year_combo.setProperty("_all_snaps", all_snaps)
        sub_h.addWidget(self._pred_year_combo)
        card_v.addWidget(sub_row)

        W_MON = 160
        W_EST = 160
        W_ACT = 160
        W_DIF = 160

        # Header row
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet(
            f"QFrame {{ background: {BG_ELEM}; border-radius: 8px; border: none; }}"
        )
        hdr_h = QHBoxLayout(hdr_frame)
        hdr_h.setContentsMargins(12, 6, 12, 6)
        for text, width, align in [
            ("Month",      W_MON, Qt.AlignmentFlag.AlignLeft),
            ("Estimated",  W_EST, Qt.AlignmentFlag.AlignRight),
            ("Actual",     W_ACT, Qt.AlignmentFlag.AlignRight),
            ("Difference", W_DIF, Qt.AlignmentFlag.AlignRight),
        ]:
            lbl = make_label(text, 12, color=TEXT_SEC)
            lbl.setMinimumWidth(width)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            hdr_h.addWidget(lbl)
        card_v.addWidget(hdr_frame)

        # Filter rows
        selected = self._pred_year_filter
        if selected == "All":
            rows = all_rows
        else:
            rows = [r for r in all_rows if r[0] == int(selected)]

        if not rows:
            card_v.addWidget(make_label(f"No data for {selected}.", 12, color=TEXT_SEC))
        else:
            for idx, (_, month, estimated, actual, delta) in enumerate(rows):
                row_bg    = BG_CARD if idx % 2 == 0 else "#161b22"
                row_frame = QFrame()
                row_frame.setStyleSheet(
                    f"QFrame {{ background: {row_bg}; border-radius: 6px; border: none; }}"
                )
                row_h = QHBoxLayout(row_frame)
                row_h.setContentsMargins(12, 5, 12, 5)

                diff_color = GREEN if delta >= 0 else RED
                for text, width, align, color in [
                    (MONTHS[month - 1],     W_MON, Qt.AlignmentFlag.AlignLeft,  TEXT_PRI),
                    (fmt_eur(estimated),    W_EST, Qt.AlignmentFlag.AlignRight, TEXT_SEC),
                    (fmt_eur(actual),       W_ACT, Qt.AlignmentFlag.AlignRight, TEXT_SEC),
                    (fmt_eur_signed(delta), W_DIF, Qt.AlignmentFlag.AlignRight, diff_color),
                ]:
                    lbl = make_label(text, 12, color=color)
                    lbl.setMinimumWidth(width)
                    lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                    row_h.addWidget(lbl)

                card_v.addWidget(row_frame)

        self._prediction_layout.addWidget(card)
        self._prediction_widget.setVisible(True)

    def _on_pred_year_change(self, choice: str):
        self._pred_year_filter = choice
        combo = self.sender()
        all_snaps = combo.property("_all_snaps") if combo else []
        self._render_prediction_accuracy(all_snaps or get_all_snapshots())

    # ── Annual overview ───────────────────────────────────────────────────────

    def _render_annual(self):
        _clear_layout(self._annual_layout)

        today     = date.today()
        year      = today.year
        all_snaps = get_all_snapshots()

        self._annual_layout.addWidget(
            make_label(f"Annual Overview · {year}", 15, bold=True)
        )

        year_changes: list[dict] = []
        for i in range(1, len(all_snaps)):
            s2 = all_snaps[i]
            if s2["year"] == year:
                year_changes.append({
                    "month":  s2["month"],
                    "year":   s2["year"],
                    "change": s2["total"] - all_snaps[i - 1]["total"],
                })

        if not year_changes:
            self._annual_layout.addWidget(make_label(
                f"No monthly changes recorded for {year} yet. "
                "Save snapshots across two months to see stats.",
                13, color=TEXT_SEC,
            ))
            return

        best        = max(year_changes, key=lambda x: x["change"])
        worst       = min(year_changes, key=lambda x: x["change"])
        avg         = sum(c["change"] for c in year_changes) / len(year_changes)
        total_saved = sum(c["change"] for c in year_changes if c["change"] > 0)
        n_positive  = sum(1 for c in year_changes if c["change"] > 0)

        card  = make_card()
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(20, 20, 20, 20)
        card_v.setSpacing(4)

        W_LBL = 180
        W_MON = 200
        W_VAL = 140

        def ann_row(label: str, month_str: str, value: float, color: str):
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 3, 0, 3)

            lbl_w = make_label(label, 12, color=TEXT_SEC)
            lbl_w.setMinimumWidth(W_LBL)
            row_h.addWidget(lbl_w)

            mon_w = make_label(month_str, 12)
            mon_w.setMinimumWidth(W_MON)
            row_h.addWidget(mon_w)

            val_w = make_label(fmt_eur_signed(value), 12, bold=True, color=color)
            val_w.setMinimumWidth(W_VAL)
            val_w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_h.addWidget(val_w)
            row_h.addStretch()
            card_v.addWidget(row_w)

        ann_row("Best month",     _mlabel(best["year"],  best["month"]),  best["change"],  GREEN)
        ann_row("Worst month",    _mlabel(worst["year"], worst["month"]), worst["change"], RED)
        ann_row("Average change", f"{len(year_changes)} months recorded", avg,
                GREEN if avg >= 0 else RED)
        ann_row("Total saved",    f"{n_positive} positive month{'s' if n_positive != 1 else ''}",
                total_saved, GREEN)

        self._annual_layout.addWidget(card)

    # ── Account breakdown ─────────────────────────────────────────────────────

    def _render_breakdown(self, latest: dict, prev: dict | None):
        _clear_layout(self._breakdown_layout)

        W_NAME = 220
        W_AMT  = 140
        W_CHG  = 130

        # Header
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet(
            f"QFrame {{ background: {BG_ELEM}; border-radius: 8px; border: none; }}"
        )
        hdr_h = QHBoxLayout(hdr_frame)
        hdr_h.setContentsMargins(12, 6, 12, 6)

        cols: list[tuple[str, int, Qt.AlignmentFlag]] = [
            ("Account", W_NAME, Qt.AlignmentFlag.AlignLeft)
        ]
        if prev:
            prev_lbl    = MONTHS[prev["month"] - 1][:3] + f" {prev['year']}"
            current_lbl = MONTHS[latest["month"] - 1][:3] + f" {latest['year']}"
            cols += [
                (prev_lbl,    W_AMT, Qt.AlignmentFlag.AlignRight),
                (current_lbl, W_AMT, Qt.AlignmentFlag.AlignRight),
                ("Change",    W_CHG, Qt.AlignmentFlag.AlignRight),
            ]
        else:
            cols.append(("Balance", W_AMT, Qt.AlignmentFlag.AlignRight))

        for text, width, align in cols:
            lbl = make_label(text, 12, color=TEXT_SEC)
            lbl.setMinimumWidth(width)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            hdr_h.addWidget(lbl)
        hdr_h.addStretch()
        self._breakdown_layout.addWidget(hdr_frame)

        all_names = sorted(
            set(latest["balances"]) | (set(prev["balances"]) if prev else set())
        )

        for i, name in enumerate(all_names):
            row_bg = BG_CARD if i % 2 == 0 else "#161b22"
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"QFrame {{ background: {row_bg}; border-radius: 6px; border: none; }}"
            )
            row_h = QHBoxLayout(row_frame)
            row_h.setContentsMargins(12, 5, 12, 5)

            curr = latest["balances"].get(name, 0.0)
            name_lbl = make_label(name, 12)
            name_lbl.setMinimumWidth(W_NAME)
            row_h.addWidget(name_lbl)

            if prev:
                old   = prev["balances"].get(name, 0.0)
                diff  = curr - old
                d_clr = GREEN if diff > 0 else (RED if diff < 0 else TEXT_SEC)

                old_lbl = make_label(fmt_eur(old), 12, color=TEXT_SEC)
                old_lbl.setMinimumWidth(W_AMT)
                old_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_h.addWidget(old_lbl)

                cur_lbl = make_label(fmt_eur(curr), 12)
                cur_lbl.setMinimumWidth(W_AMT)
                cur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_h.addWidget(cur_lbl)

                diff_lbl = make_label(fmt_eur_signed(diff), 12, color=d_clr)
                diff_lbl.setMinimumWidth(W_CHG)
                diff_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_h.addWidget(diff_lbl)
            else:
                bal_lbl = make_label(fmt_eur(curr), 12)
                bal_lbl.setMinimumWidth(W_AMT)
                bal_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_h.addWidget(bal_lbl)

            row_h.addStretch()
            self._breakdown_layout.addWidget(row_frame)

    # ── Snapshot History ──────────────────────────────────────────────────────

    def _render_snapshot_history(self):
        _clear_layout(self._history_layout)

        all_snaps = get_all_snapshots()
        if not all_snaps:
            self._history_layout.addWidget(
                make_label("No snapshots yet.", 13, color=TEXT_SEC)
            )
            return

        existing = {(s["year"], s["month"]) for s in all_snaps}
        nw_by_month = {(s["year"], s["month"]): s["total"] for s in all_snaps}
        years = sorted({s["year"] for s in all_snaps})

        card = make_card()
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(16, 14, 16, 14)
        card_v.setSpacing(4)

        # Month header row
        hdr_row = QWidget()
        hdr_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_row.setStyleSheet("background: transparent;")
        hdr_h = QHBoxLayout(hdr_row)
        hdr_h.setContentsMargins(0, 0, 0, 2)
        hdr_h.setSpacing(0)

        spacer_lbl = QLabel("")
        spacer_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        spacer_lbl.setFixedWidth(48)
        spacer_lbl.setStyleSheet("background: transparent;")
        hdr_h.addWidget(spacer_lbl)

        for m in range(1, 13):
            lbl = make_label(MONTHS[m - 1][:1], 10, color=TEXT_SEC)
            lbl.setFixedWidth(52)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hdr_h.addWidget(lbl)
        card_v.addWidget(hdr_row)

        # Year rows
        for year in years:
            year_row = QWidget()
            year_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            year_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            year_row.setStyleSheet("background: transparent;")
            year_h = QHBoxLayout(year_row)
            year_h.setContentsMargins(0, 2, 0, 2)
            year_h.setSpacing(0)

            yr_lbl = make_label(str(year), 11, color=TEXT_SEC)
            yr_lbl.setFixedWidth(48)
            year_h.addWidget(yr_lbl)

            for m in range(1, 13):
                if (year, m) in existing:
                    total = nw_by_month.get((year, m), 0.0)
                    cell = QPushButton(f"€{total/1000:.0f}k")
                    cell.setFixedSize(52, 32)
                    cell.setFont(QFont(FONT, 9))
                    cell.setStyleSheet(
                        f"QPushButton {{ background: #162440; color: {ACCENT};"
                        f" border: 1px solid #1e3a55; border-radius: 6px; font-size: 9px; }}"
                        f"QPushButton:hover {{ background: #1e3a55; }}"
                    )
                    cell.clicked.connect(
                        lambda _=False, y=year, mo=m: self._on_snapshot_click(y, mo)
                    )
                    year_h.addWidget(cell)
                else:
                    dot_lbl = make_label("·", 12, color="#1e3448")
                    dot_lbl.setFixedWidth(52)
                    dot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    year_h.addWidget(dot_lbl)

            card_v.addWidget(year_row)

        self._history_layout.addWidget(card)

    def _on_snapshot_click(self, year: int, month: int):
        from views.snapshot_entry import SnapshotEntryView
        SnapshotEntryView._pending_period = (year, month)
        if self._navigate:
            self._navigate("snapshot")

    # ── CSV Export ────────────────────────────────────────────────────────────

    def _export_csv(self):
        all_snaps = get_all_snapshots()
        if not all_snaps:
            if self._export_status:
                self._export_status.setText("No data to export.")
            return

        today        = date.today()
        default_name = f"money-tracker-export-{today.strftime('%Y-%m-%d')}.csv"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", default_name, "CSV Files (*.csv)"
        )
        if not filepath:
            return

        rows = []
        for snap in all_snaps:
            for acc_name, balance in snap["balances"].items():
                rows.append({
                    "Year":    snap["year"],
                    "Month":   snap["month"],
                    "Account": acc_name,
                    "Balance": f"{balance:.2f}",
                })

        fieldnames = ["Year", "Month", "Account", "Balance"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        filename = Path(filepath).name
        if self._export_status:
            self._export_status.setText(f"Exported: {filename}")
            self._export_status.setStyleSheet(f"color: {GREEN}; background: transparent;")
            QTimer.singleShot(5000, lambda: (
                self._export_status.setText(""),
                self._export_status.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            ) if self._export_status else None)
