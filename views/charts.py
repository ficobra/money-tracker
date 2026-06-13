from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath
import numpy as np
from datetime import date, timedelta

from database.db import (
    get_all_snapshots, get_all_accounts, get_all_income,
    get_snapshot_income, get_all_expenses, get_extra_income,
    get_expenses_by_category,
)
from styles.theme import (
    BG_CARD, BG_ELEM, BG_MAIN, ACCENT, TEXT_PRI, TEXT_SEC,
    BORDER, GREEN, RED, FONT,
)
from utils import fmt_eur, fmt_eur_signed

matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['text.color'] = '#eef2f7'
matplotlib.rcParams['axes.labelcolor'] = '#eef2f7'
matplotlib.rcParams['xtick.color'] = '#5a7a94'
matplotlib.rcParams['ytick.color'] = '#5a7a94'

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_FIG_W = 8.5
_FIG_H = 3.2

_TRACKER_COLORS = ["#00b4d8", "#A78BFA", "#F59E0B", "#10B981", "#EF4444", "#F97316"]


def _snap_total_incl(s: dict) -> float:
    """Return snapshot total including portfolio_eur if available."""
    return s["total"] + (dict(s).get("portfolio_eur") or 0.0)


def _snap_label(snap: dict) -> str:
    return f"{_MONTHS_SHORT[snap['month'] - 1]} '{str(snap['year'])[2:]}"


def _eu_axis_fmt(v: float) -> str:
    s = f"{abs(v):,.0f}".replace(",", ".")
    return f"-€{s}" if v < 0 else f"€{s}"


def _palette() -> dict:
    return {
        "fig_bg": BG_CARD,
        "axes_bg": "#161b22",
        "text": TEXT_PRI,
        "grid": BORDER,
        "spine": "#444c56",
        "line": ACCENT,
        "green": GREEN,
        "red": RED,
    }


def _get_filter_options(snapshots: list) -> list[str]:
    if not snapshots:
        return ["All"]
    earliest = min(snapshots, key=lambda s: (s["year"], s["month"]))
    today = date.today()
    earliest_date = date(earliest["year"], earliest["month"], 1)
    months_available = (today.year - earliest_date.year) * 12 + (today.month - earliest_date.month)
    options = ["1M", "3M", "6M"]
    if months_available >= 12:
        options.append("1Y")
    options.append("YTD")
    if months_available >= 36:
        options.append("3Y")
    if months_available >= 60:
        options.append("5Y")
    options.append("All")
    return options


def _apply_style(fig: Figure, ax, pal: dict) -> None:
    fig.patch.set_facecolor(BG_MAIN)
    ax.set_facecolor(BG_MAIN)
    ax.tick_params(colors=TEXT_SEC, labelsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _eu_axis_fmt(v)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(True, color="#1c2333", linestyle="--", linewidth=0.5, alpha=0.6, axis="y")


class ChartsView(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"background: {BG_MAIN}; border: none;")

        self._figures: list[Figure] = []
        self._tracker_checkboxes: dict[str, QCheckBox] = {}
        self._income_checkboxes: dict[int, QCheckBox] = {}
        self._income_names: dict[int, str] = {}
        self._tracker_snap_data: list = []
        self._income_snap_data: list = []
        self._tracker_chart_widget: QWidget | None = None
        self._nw_filter = "All"
        self._change_filter = "All"
        self._tracker_filter = "All"
        self._cashflow_filter = "All"

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setStyleSheet(f"background: {BG_MAIN};")
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(16)
        self.setWidget(content)

        # Header
        title = QLabel("Analytics")
        title.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        title.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        title.setFont(QFont(FONT, 22, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRI}; background: transparent;")
        self._content_layout.addWidget(title)

        sub = QLabel("Visual overview of your net worth and portfolio across all saved snapshots.")
        sub.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        sub.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        sub.setFont(QFont(FONT, 13))
        sub.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
        self._content_layout.addWidget(sub)

        # Chart container
        self._chart_container = QWidget()
        self._chart_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._chart_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._chart_container.setStyleSheet("background: transparent; border: none;")
        self._chart_layout = QVBoxLayout(self._chart_container)
        self._chart_layout.setSpacing(16)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self._chart_container)
        self._content_layout.addStretch()

        self.viewport().installEventFilter(self)
        self.refresh()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Wheel:
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - event.angleDelta().y() // 2
            )
            return True
        return super().eventFilter(obj, event)

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _clear_chart_container(self) -> None:
        layout = self._chart_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # type: ignore[call-overload]
                widget.deleteLater()

    def make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.NoFrame)
        card.setFrameShadow(QFrame.Shadow.Plain)
        card.setLineWidth(0)
        card.setStyleSheet(
            f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}"
            f"QFrame QFrame {{ border: none; background: transparent; }}"
            f"QFrame QWidget {{ border: none; background: transparent; }}"
        )
        card.setContentsMargins(0, 0, 0, 0)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(title)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        title_lbl.setFont(QFont(FONT, 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
        title_lbl.setContentsMargins(16, 12, 0, 6)
        card_layout.addWidget(title_lbl)

        return card, card_layout

    def make_filter_row(
        self,
        parent_layout: QVBoxLayout,
        options: list[str],
        current: str,
        on_select,
    ) -> None:
        row_widget = QWidget()
        row_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_widget.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        for opt in options:
            is_active = opt == current
            btn = QPushButton(opt)
            btn.setFixedHeight(28)
            btn.setMinimumWidth(36)
            btn.setMaximumWidth(56)
            btn.setFont(QFont(FONT, 11))
            if is_active:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {ACCENT}; color: white;"
                    f" border: none; border-radius: 6px; }}"
                    f" QPushButton:hover {{ background-color: #0096b4; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {BG_ELEM}; color: {TEXT_SEC};"
                    f" border: 1px solid {BORDER}; border-radius: 6px; }}"
                    f" QPushButton:hover {{ background-color: #3d4d63; }}"
                )
            btn.clicked.connect(lambda _=False, o=opt: on_select(o))
            row.addWidget(btn)

        row.addStretch()
        parent_layout.addWidget(row_widget)

    def embed_canvas(self, fig: Figure, card_layout: QVBoxLayout) -> None:
        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        wrapper.setStyleSheet("background: transparent; border: none;")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(16, 0, 16, 16)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(320)
        canvas.setStyleSheet("background: transparent;")
        canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        canvas.installEventFilter(self)
        wl.addWidget(canvas)
        card_layout.addWidget(wrapper)

    # ── Filter helpers ────────────────────────────────────────────────────────

    def _filter_snaps(self, snaps: list, key: str) -> list:
        if key == "All":
            return snaps
        today = date.today()
        cutoffs = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "3Y": 1095, "5Y": 1825}
        if key == "YTD":
            cutoff = date(today.year, 1, 1)
        elif key in cutoffs:
            cutoff = today - timedelta(days=cutoffs[key])
        else:
            return snaps
        return [s for s in snaps if date(s["year"], s["month"], 1) >= cutoff]

    # ── Shared axis helpers ───────────────────────────────────────────────────

    def _set_xticks(self, ax, labels: list[str], x: list[int]) -> None:
        rotation = 40 if len(labels) > 5 else 0
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=rotation, ha="right" if rotation else "center")

    def _annotate_bars(self, ax, x: list[int], values: list[float], pal: dict) -> None:
        if len(values) > 16:
            return
        for xi, v in zip(x, values):
            text = fmt_eur_signed(v)
            if v >= 0:
                ax.annotate(
                    text, (xi, v),
                    textcoords="offset points", xytext=(0, 5),
                    ha="center", va="bottom", fontsize=7.5, color=pal["text"],
                )
            else:
                ax.annotate(
                    text, (xi, v),
                    textcoords="offset points", xytext=(0, -5),
                    ha="center", va="top", fontsize=7.5, color=pal["text"],
                )

    def _build_chart_header(self, parent_layout: QVBoxLayout, current_val: float, prev_val: float | None) -> None:
        row_widget = QWidget()
        row_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_widget.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 6)
        row.setSpacing(12)

        val_lbl = QLabel(fmt_eur(current_val))
        val_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        val_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        val_lbl.setFont(QFont(FONT, 16, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent;")
        row.addWidget(val_lbl)

        if prev_val is not None:
            change = current_val - prev_val
            pct = (change / prev_val * 100) if prev_val else 0.0
            color = GREEN if change >= 0 else RED
            sign = "+" if pct >= 0 else ""
            chg_lbl = QLabel(f"{fmt_eur_signed(change)}  ({sign}{pct:.1f}%)")
            chg_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            chg_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            chg_lbl.setFont(QFont(FONT, 13))
            chg_lbl.setStyleSheet(f"color: {color}; background: transparent;")
            row.addWidget(chg_lbl)

        row.addStretch()
        parent_layout.addWidget(row_widget)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._clear_chart_container()
        for fig in self._figures:
            fig.clear()
        self._figures.clear()
        self._tracker_chart_widget = None

        snapshots = get_all_snapshots()

        if len(snapshots) < 2:
            card, cl = self.make_card("Analytics")
            lbl = QLabel("Add at least two monthly snapshots to see charts.")
            lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            lbl.setFont(QFont(FONT, 13))
            lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
            lbl.setContentsMargins(16, 8, 16, 16)
            cl.addWidget(lbl)
            self._chart_layout.addWidget(card)
            return

        self._render_networth(snapshots)
        self._render_changes(snapshots)
        self._render_cashflow(snapshots)
        self._render_tracker(snapshots)
        self._render_heatmap(snapshots)
        self._render_category_breakdown()

    # ── Chart 1: Net Worth Over Time ──────────────────────────────────────────

    def _render_networth(self, snapshots: list[dict]) -> None:
        pal = _palette()
        snaps = self._filter_snaps(snapshots, self._nw_filter)

        card, cl = self.make_card("Net Worth Over Time")

        inner = QWidget()
        inner.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner.setStyleSheet("background: transparent; border: none;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 0, 16, 8)
        inner_layout.setSpacing(4)

        nw_options = _get_filter_options(snapshots)
        if self._nw_filter not in nw_options:
            self._nw_filter = "All"
        self.make_filter_row(inner_layout, nw_options, self._nw_filter, self._set_nw_filter)

        if snaps:
            y_vals = [s["total"] for s in snaps]
            x_port = [i for i, s in enumerate(snaps) if dict(s).get("portfolio_eur", 0.0) > 0]
            y_total_port = [s["total"] + dict(s).get("portfolio_eur", 0.0)
                            for s in snaps if dict(s).get("portfolio_eur", 0.0) > 0]
            has_portfolio = len(x_port) > 0
            if has_portfolio:
                current_val = y_total_port[-1]
                prev_val = y_total_port[-2] if len(y_total_port) >= 2 else (y_vals[-2] if len(snaps) >= 2 else None)
            else:
                current_val = y_vals[-1]
                prev_val = y_vals[-2] if len(snaps) >= 2 else None
            self._build_chart_header(inner_layout, current_val, prev_val)
        else:
            no_data = QLabel("No data for selected period.")
            no_data.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            no_data.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            no_data.setFont(QFont(FONT, 12))
            no_data.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            no_data.setContentsMargins(0, 8, 0, 8)
            inner_layout.addWidget(no_data)
            cl.addWidget(inner)
            self._chart_layout.addWidget(card)
            return

        cl.addWidget(inner)

        labels = [_snap_label(s) for s in snaps]
        x = list(range(len(snaps)))

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        if len(snaps) >= 2:
            x_np = np.array(x, dtype=float)
            x_s = np.linspace(0, len(snaps) - 1, 300)
            y_np = np.array(y_vals, dtype=float)
            y_s = np.interp(x_s, x_np, y_np)
            ax.plot(x_s, y_s, color=ACCENT, linewidth=2, label="Excl. portfolio", zorder=3)
            y_floor = min(y_s) - abs(max(y_s) - min(y_s)) * 0.1
            n_strips = 30
            for i in range(n_strips):
                frac_lo = i / n_strips
                frac_hi = (i + 1) / n_strips
                y_lo = y_floor + frac_lo * (y_s - y_floor)
                y_hi = y_floor + frac_hi * (y_s - y_floor)
                ax.fill_between(x_s, y_lo, y_hi, color=ACCENT, alpha=0.35 * (i / n_strips), linewidth=0, zorder=2)
            if has_portfolio:
                if len(x_port) >= 2:
                    xp_np = np.array(x_port, dtype=float)
                    xp_s = np.linspace(x_port[0], x_port[-1], 300)
                    yp_np = np.array(y_total_port, dtype=float)
                    yp_s = np.interp(xp_s, xp_np, yp_np)
                    ax.plot(xp_s, yp_s, color=GREEN, linewidth=2, label="Incl. portfolio", zorder=4)
                    yp_floor = min(yp_s) - abs(max(yp_s) - min(yp_s)) * 0.05
                    n_strips_g = 30
                    for i in range(n_strips_g):
                        frac_lo = i / n_strips_g
                        frac_hi = (i + 1) / n_strips_g
                        y_lo_g = yp_floor + frac_lo * (yp_s - yp_floor)
                        y_hi_g = yp_floor + frac_hi * (yp_s - yp_floor)
                        ax.fill_between(xp_s, y_lo_g, y_hi_g, color=GREEN, alpha=0.35 * (i / n_strips_g), linewidth=0, zorder=1)
                else:
                    ax.plot(x_port, y_total_port, color=GREEN, linewidth=2,
                            marker="o", markersize=5, label="Incl. portfolio", zorder=4)
                legend = ax.legend(
                    loc="lower center",
                    bbox_to_anchor=(0.5, 1.01),
                    ncol=2,
                    frameon=False,
                    labelcolor=TEXT_PRI,
                    fontsize=10,
                )
        else:
            ax.plot(x, y_vals, color=ACCENT, linewidth=2, marker="o", markersize=5, zorder=3)

        self._set_xticks(ax, labels, x)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)
        self.embed_canvas(fig, cl)
        self._chart_layout.addWidget(card)

    # ── Chart 2: Monthly Net Worth Change ─────────────────────────────────────

    def _render_changes(self, snapshots: list[dict]) -> None:
        pal = _palette()
        snaps = self._filter_snaps(snapshots, self._change_filter)

        card, cl = self.make_card("Monthly Net Worth Change")

        inner = QWidget()
        inner.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner.setStyleSheet("background: transparent; border: none;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 0, 16, 8)
        inner_layout.setSpacing(4)

        change_options = _get_filter_options(snapshots)
        if self._change_filter not in change_options:
            self._change_filter = "All"
        self.make_filter_row(inner_layout, change_options, self._change_filter, self._set_change_filter)

        if len(snaps) >= 2:
            current_change = _snap_total_incl(snaps[-1]) - _snap_total_incl(snaps[-2])
            prev_change = (_snap_total_incl(snaps[-2]) - _snap_total_incl(snaps[-3])) if len(snaps) >= 3 else None
            self._build_chart_header(inner_layout, current_change, prev_change)
        else:
            no_data = QLabel("No data for selected period.")
            no_data.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            no_data.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            no_data.setFont(QFont(FONT, 12))
            no_data.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            no_data.setContentsMargins(0, 8, 0, 8)
            inner_layout.addWidget(no_data)
            cl.addWidget(inner)
            self._chart_layout.addWidget(card)
            return

        cl.addWidget(inner)

        changes = [_snap_total_incl(snaps[i + 1]) - _snap_total_incl(snaps[i]) for i in range(len(snaps) - 1)]
        labels = [_snap_label(s) for s in snaps[1:]]
        x = list(range(len(changes)))
        colors = [pal["green"] if c >= 0 else pal["red"] for c in changes]

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        ax.bar(x, changes, color=colors, width=0.6, zorder=3)
        ax.axhline(y=0, color="#444c56", linewidth=1)

        self._set_xticks(ax, labels, x)
        ax.margins(y=0.30)
        self._annotate_bars(ax, x, changes, pal)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)
        self.embed_canvas(fig, cl)
        self._chart_layout.addWidget(card)

    # ── Chart 3: Cash Flow ────────────────────────────────────────────────────

    def _render_cashflow(self, snapshots: list[dict]) -> None:
        pal = _palette()
        snaps = self._filter_snaps(snapshots, self._cashflow_filter)

        card, cl = self.make_card("Cash Flow")

        inner = QWidget()
        inner.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner.setStyleSheet("background: transparent; border: none;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 0, 16, 8)
        inner_layout.setSpacing(4)

        cashflow_options = _get_filter_options(snapshots)
        if self._cashflow_filter not in cashflow_options:
            self._cashflow_filter = "All"
        self.make_filter_row(inner_layout, cashflow_options, self._cashflow_filter, self._set_cashflow_filter)

        if not snaps:
            no_data = QLabel("No data for selected period.")
            no_data.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            no_data.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            no_data.setFont(QFont(FONT, 12))
            no_data.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            no_data.setContentsMargins(0, 8, 0, 8)
            inner_layout.addWidget(no_data)
            cl.addWidget(inner)
            self._chart_layout.addWidget(card)
            return

        # Build prev-NW lookup from the full unfiltered snapshots list
        prev_nw: dict[tuple, float] = {}
        for i in range(1, len(snapshots)):
            key = (snapshots[i]["year"], snapshots[i]["month"])
            prev_nw[key] = _snap_total_incl(snapshots[i - 1])

        inc_per_month: list[float] = []
        spent_per_month: list[float | None] = []

        for s in snaps:
            snap_inc = get_snapshot_income(s["year"], s["month"])
            extras = get_extra_income(s["year"], s["month"])
            income = sum(snap_inc.values() if snap_inc else []) + sum(e["amount"] for e in extras)
            inc_per_month.append(income)
            key = (s["year"], s["month"])
            if key in prev_nw:
                spent_per_month.append(prev_nw[key] + income - _snap_total_incl(s))
            else:
                spent_per_month.append(None)

        total_inc = sum(inc_per_month)
        total_exp = sum(sp for sp in spent_per_month if sp is not None)
        sav_vals = [inc - sp for inc, sp in zip(inc_per_month, spent_per_month) if sp is not None]
        avg_sav = sum(sav_vals) / len(sav_vals) if sav_vals else 0.0
        sav_color = GREEN if avg_sav >= 0 else RED

        # Stats row
        stats_widget = QWidget()
        stats_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        stats_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        stats_widget.setStyleSheet("background: transparent; border: none;")
        stats_row = QHBoxLayout(stats_widget)
        stats_row.setContentsMargins(0, 0, 0, 10)
        stats_row.setSpacing(0)

        for stat_label, stat_val, stat_color in [
            ("TOTAL EARNED", fmt_eur(total_inc), GREEN),
            ("TOTAL SPENT", fmt_eur(total_exp), RED),
            ("AVG SAVINGS/MO", fmt_eur_signed(avg_sav), sav_color),
        ]:
            col_w = QWidget()
            col_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            col_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            col_w.setStyleSheet("background: transparent; border: none;")
            col_l = QVBoxLayout(col_w)
            col_l.setContentsMargins(0, 0, 28, 0)
            col_l.setSpacing(2)

            lbl_name = QLabel(stat_label)
            lbl_name.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl_name.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            lbl_name.setFont(QFont(FONT, 11))
            lbl_name.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            col_l.addWidget(lbl_name)

            lbl_val = QLabel(stat_val)
            lbl_val.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl_val.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            lbl_val.setFont(QFont(FONT, 14, QFont.Weight.Bold))
            lbl_val.setStyleSheet(f"color: {stat_color}; background: transparent;")
            col_l.addWidget(lbl_val)

            stats_row.addWidget(col_w)

        stats_row.addStretch()
        inner_layout.addWidget(stats_widget)
        cl.addWidget(inner)

        labels = [_snap_label(s) for s in snaps]
        x = list(range(len(snaps)))
        bar_w = 0.35
        x_inc = [xi - bar_w / 2 for xi in x]
        x_exp_all = [xi + bar_w / 2 for xi in x]
        x_exp = [xi for xi, sp in zip(x_exp_all, spent_per_month) if sp is not None]
        exp_vals = [sp for sp in spent_per_month if sp is not None]
        x_net = [xi for xi, sp in zip(x, spent_per_month) if sp is not None]
        net_sav = [inc - sp for inc, sp in zip(inc_per_month, spent_per_month) if sp is not None]

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        ax.bar(x_inc, inc_per_month, width=bar_w, color=GREEN, alpha=0.8,
               label="Money Earned", zorder=3)
        if exp_vals:
            ax.bar(x_exp, exp_vals, width=bar_w, color=RED, alpha=0.8,
                   label="Money Spent", zorder=3)
        if net_sav:
            ax.plot(x_net, net_sav, color="#7c8cf8", linewidth=2,
                    marker="o", markersize=4, zorder=4, label="Net Savings")
        ax.axhline(y=0, color="#444c56", linewidth=0.8)

        leg = ax.legend(fontsize=9, facecolor=BG_MAIN, edgecolor=BORDER)
        for txt in leg.get_texts():
            txt.set_color(TEXT_PRI)

        self._set_xticks(ax, labels, x)
        ax.margins(y=0.25)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)
        self.embed_canvas(fig, cl)
        self._chart_layout.addWidget(card)

    # ── Chart 4: Account Tracker ──────────────────────────────────────────────

    def _render_tracker(self, snapshots: list[dict]) -> None:
        filtered = self._filter_snaps(snapshots, self._tracker_filter)
        self._tracker_snap_data = filtered

        self._income_snap_data = [
            get_snapshot_income(s["year"], s["month"]) for s in filtered
        ]

        all_accounts = get_all_accounts()
        all_income = list(get_all_income())

        self._income_names = {i["id"]: i["name"] for i in all_income}

        # Preserve existing checkbox states
        existing_acc_states = {name: cb.isChecked() for name, cb in self._tracker_checkboxes.items()}
        existing_inc_states = {iid: cb.isChecked() for iid, cb in self._income_checkboxes.items()}

        # Rebuild checkbox dicts
        self._tracker_checkboxes = {}
        self._income_checkboxes = {}

        card, cl = self.make_card("Account Tracker")

        ctrl = QWidget()
        ctrl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        ctrl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        ctrl.setStyleSheet("background: transparent; border: none;")
        ctrl_layout = QVBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(16, 0, 16, 8)
        ctrl_layout.setSpacing(4)

        tracker_options = _get_filter_options(snapshots)
        if self._tracker_filter not in tracker_options:
            self._tracker_filter = "All"
        self.make_filter_row(ctrl_layout, tracker_options, self._tracker_filter, self._set_tracker_filter)

        if not all_accounts and not all_income:
            no_acc = QLabel("No accounts saved yet.")
            no_acc.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            no_acc.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            no_acc.setFont(QFont(FONT, 13))
            no_acc.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            ctrl_layout.addWidget(no_acc)
        else:
            if all_accounts:
                acc_label = QLabel("Select accounts to chart:")
                acc_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                acc_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                acc_label.setFont(QFont(FONT, 12))
                acc_label.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
                ctrl_layout.addWidget(acc_label)

                cb_row = QWidget()
                cb_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                cb_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                cb_row.setStyleSheet("background: transparent; border: none;")
                cb_layout = QHBoxLayout(cb_row)
                cb_layout.setContentsMargins(0, 0, 0, 4)
                cb_layout.setSpacing(16)
                for acc in all_accounts:
                    cb = QCheckBox(acc)
                    cb.setFont(QFont(FONT, 12))
                    cb.setStyleSheet("QCheckBox { color: " + TEXT_PRI + "; background: transparent; }")
                    was_checked = existing_acc_states.get(acc, False)
                    cb.setChecked(was_checked)
                    cb.stateChanged.connect(lambda _state: self._on_tracker_change())
                    self._tracker_checkboxes[acc] = cb
                    cb_layout.addWidget(cb)
                cb_layout.addStretch()
                ctrl_layout.addWidget(cb_row)

            if all_income:
                inc_label = QLabel("Select income sources to chart:")
                inc_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                inc_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                inc_label.setFont(QFont(FONT, 12))
                inc_label.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
                ctrl_layout.addWidget(inc_label)

                inc_row = QWidget()
                inc_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                inc_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                inc_row.setStyleSheet("background: transparent; border: none;")
                inc_layout = QHBoxLayout(inc_row)
                inc_layout.setContentsMargins(0, 0, 0, 4)
                inc_layout.setSpacing(16)
                for inc in all_income:
                    iid = inc["id"]
                    cb = QCheckBox(inc["name"])
                    cb.setFont(QFont(FONT, 12))
                    cb.setStyleSheet("QCheckBox { color: " + TEXT_PRI + "; background: transparent; }")
                    was_checked = existing_inc_states.get(iid, False)
                    cb.setChecked(was_checked)
                    cb.stateChanged.connect(lambda _state: self._on_tracker_change())
                    self._income_checkboxes[iid] = cb
                    inc_layout.addWidget(cb)
                inc_layout.addStretch()
                ctrl_layout.addWidget(inc_row)

        cl.addWidget(ctrl)

        # Tracker chart container — redrawn on checkbox change
        self._tracker_chart_widget = QWidget()
        self._tracker_chart_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._tracker_chart_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._tracker_chart_widget.setStyleSheet("background: transparent; border: none;")
        self._tracker_chart_layout = QVBoxLayout(self._tracker_chart_widget)
        self._tracker_chart_layout.setContentsMargins(16, 0, 16, 16)
        self._tracker_chart_layout.setSpacing(0)
        cl.addWidget(self._tracker_chart_widget)

        self._chart_layout.addWidget(card)
        self._redraw_tracker()

    def _on_tracker_change(self) -> None:
        self._redraw_tracker()

    def _redraw_tracker(self) -> None:
        if self._tracker_chart_widget is None:
            return

        layout = self._tracker_chart_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # type: ignore[call-overload]
                widget.deleteLater()

        selected_acc = [name for name, cb in self._tracker_checkboxes.items() if cb.isChecked()]
        selected_inc = [(iid, self._income_names[iid])
                        for iid, cb in self._income_checkboxes.items() if cb.isChecked()]

        if not selected_acc and not selected_inc:
            placeholder = QLabel("Select one or more accounts or income sources above to see their values over time.")
            placeholder.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            placeholder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            placeholder.setFont(QFont(FONT, 12))
            placeholder.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            placeholder.setContentsMargins(0, 4, 0, 8)
            layout.addWidget(placeholder)
            return

        if not self._tracker_snap_data:
            return

        pal = _palette()
        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        all_labels = [_snap_label(s) for s in self._tracker_snap_data]
        all_x = list(range(len(self._tracker_snap_data)))

        color_idx = 0
        for acc in selected_acc:
            xs: list[int] = []
            ys: list[float] = []
            for xi, s in zip(all_x, self._tracker_snap_data):
                snap_dict = dict(s) if not isinstance(s, dict) else s
                balances = snap_dict.get("balances", {})
                if acc in balances:
                    xs.append(xi)
                    ys.append(balances[acc])
            if xs:
                color = _TRACKER_COLORS[color_idx % len(_TRACKER_COLORS)]
                ax.plot(xs, ys, color=color, linewidth=2.5,
                        marker="o", markersize=5, zorder=3, label=acc)
                ax.fill_between(xs, ys, alpha=0.08, color=color)
            color_idx += 1

        for iid, name in selected_inc:
            xs = []
            ys = []
            for xi, inc_data in zip(all_x, self._income_snap_data):
                if iid in inc_data:
                    xs.append(xi)
                    ys.append(inc_data[iid])
            if xs:
                color = _TRACKER_COLORS[color_idx % len(_TRACKER_COLORS)]
                ax.plot(xs, ys, color=color, linewidth=2, linestyle="--",
                        marker="s", markersize=5, zorder=3, label=f"Income: {name}")
            color_idx += 1

        self._set_xticks(ax, all_labels, all_x)

        if (len(selected_acc) + len(selected_inc)) > 1:
            leg = ax.legend(fontsize=9, facecolor=BG_MAIN, edgecolor="#3d4d63")
            for txt in leg.get_texts():
                txt.set_color(TEXT_PRI)

        fig.tight_layout(pad=1.5)
        self._figures.append(fig)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(320)
        canvas.setStyleSheet("background: transparent;")
        canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        canvas.installEventFilter(self)
        layout.addWidget(canvas)

    # ── Chart 5: Activity Heatmap ─────────────────────────────────────────────

    def _render_heatmap(self, snapshots: list[dict]) -> None:
        if len(snapshots) < 2:
            return

        card, cl = self.make_card("Activity Heatmap")

        # Build monthly changes dict: (year, month) -> change
        changes: dict[tuple, float] = {}
        for i in range(1, len(snapshots)):
            s = snapshots[i]
            changes[(s["year"], s["month"])] = _snap_total_incl(s) - _snap_total_incl(snapshots[i - 1])

        if not changes:
            return

        years = sorted({y for y, m in changes})
        months = list(range(1, 13))

        # Find max abs value for color scaling
        max_abs = max(abs(v) for v in changes.values()) or 1.0

        n_years = len(years)
        fig_h = max(1.2, 0.55 * n_years + 0.7)
        fig = Figure(figsize=(_FIG_W, fig_h), dpi=100)
        ax = fig.add_subplot(111)
        fig.patch.set_facecolor(BG_MAIN)
        ax.set_facecolor(BG_MAIN)
        ax.set_xlim(-0.5, 11.5)
        ax.set_ylim(-0.5, n_years - 0.5)
        ax.axis("off")

        month_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
        for mi, ml in enumerate(month_labels):
            ax.text(
                mi, n_years - 0.05, ml,
                ha="center", va="bottom", fontsize=9,
                color=TEXT_SEC, transform=ax.transData,
            )

        cell_w = 0.85
        cell_h = 0.72
        recorded_count = 0
        total_cells = 0

        for yi, year in enumerate(years):
            row_y = n_years - 1 - yi
            ax.text(
                -0.7, row_y, str(year),
                ha="right", va="center", fontsize=9, color=TEXT_SEC,
            )
            for mi, month in enumerate(months):
                key = (year, month)
                total_cells += 1
                if key in changes:
                    recorded_count += 1
                    val = changes[key]
                    norm = val / max_abs  # -1 to 1
                    if norm >= 0:
                        intensity = 0.15 + 0.75 * norm
                        color = (
                            0.1 * (1 - intensity) + 0.18 * intensity,
                            0.35 * (1 - intensity) + 0.73 * intensity,
                            0.1 * (1 - intensity) + 0.20 * intensity,
                        )
                    else:
                        intensity = 0.15 + 0.75 * abs(norm)
                        color = (
                            0.35 * (1 - intensity) + 0.75 * intensity,
                            0.1 * (1 - intensity) + 0.10 * intensity,
                            0.1 * (1 - intensity) + 0.10 * intensity,
                        )
                    rect = mpatches.FancyBboxPatch(
                        (mi - cell_w / 2, row_y - cell_h / 2),
                        cell_w, cell_h,
                        boxstyle="round,pad=0.08",
                        facecolor=color,
                        edgecolor="none",
                        zorder=2,
                    )
                    ax.add_patch(rect)
                    k_str = f"{'+' if val >= 0 else ''}{val/1000:.1f}k"
                    ax.text(
                        mi, row_y, k_str,
                        ha="center", va="center", fontsize=7.5,
                        color="#eef2f7", fontweight="bold", zorder=3,
                    )
                else:
                    rect = mpatches.FancyBboxPatch(
                        (mi - cell_w / 2, row_y - cell_h / 2),
                        cell_w, cell_h,
                        boxstyle="round,pad=0.08",
                        facecolor="#0d1520",
                        edgecolor="#1a2e45",
                        linewidth=0.5,
                        zorder=2,
                    )
                    ax.add_patch(rect)
                    ax.text(
                        mi, row_y, "·",
                        ha="center", va="center", fontsize=10,
                        color="#3d5a70", zorder=3,
                    )

        footer_w = QWidget()
        footer_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        footer_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        footer_w.setStyleSheet("background: transparent; border: none;")
        footer_h = QHBoxLayout(footer_w)
        footer_h.setContentsMargins(16, 0, 16, 8)

        for label, color_hex in [("Less", "#1a3d22"), ("More", "#3fb950")]:
            dot = QLabel("■")
            dot.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            dot.setStyleSheet(f"color: {color_hex}; background: transparent; font-size: 10px;")
            footer_h.addWidget(dot)
            lbl = QLabel(label)
            lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; font-size: 11px;")
            footer_h.addWidget(lbl)

        footer_h.addStretch()
        count_lbl = QLabel(f"{recorded_count} of {total_cells} mo recorded")
        count_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        count_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; font-size: 11px;")
        footer_h.addWidget(count_lbl)

        fig.tight_layout(pad=0.5)
        fig.subplots_adjust(left=0.06, right=0.99, top=0.88, bottom=0.02)
        self._figures.append(fig)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setFixedHeight(int(fig_h * 100) + 40)
        canvas.setStyleSheet("background: transparent;")
        canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        canvas.installEventFilter(self)

        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        wrapper.setStyleSheet("background: transparent; border: none;")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(16, 0, 16, 0)
        wl.addWidget(canvas)
        cl.addWidget(wrapper)
        cl.addWidget(footer_w)
        self._chart_layout.addWidget(card)

    # ── Chart 6: Category Breakdown ───────────────────────────────────────────

    def _render_category_breakdown(self) -> None:
        by_cat = get_expenses_by_category()
        if not by_cat:
            return

        card, cl = self.make_card("Category Breakdown")

        total_fx = sum(by_cat.values())

        CATEGORY_COLORS = {
            "Housing":        "#00b4d8",
            "Investing":      "#A78BFA",
            "Subscriptions":  "#F59E0B",
            "Utilities":      "#10B981",
            "Health & Fitness": "#F97316",
            "Other":          "#6b8fa8",
        }

        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        wrapper.setStyleSheet("background: transparent; border: none;")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(16, 4, 16, 16)
        wl.setSpacing(10)

        for cat, amount in by_cat.items():
            pct = (amount / total_fx * 100) if total_fx else 0.0
            color = CATEGORY_COLORS.get(cat, "#6b8fa8")

            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent; border: none;")
            row_v = QVBoxLayout(row_w)
            row_v.setContentsMargins(0, 0, 0, 0)
            row_v.setSpacing(4)

            top_h = QHBoxLayout()
            top_h.setContentsMargins(0, 0, 0, 0)
            cat_lbl = QLabel(cat)
            cat_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            cat_lbl.setFont(QFont(FONT, 13, QFont.Weight.Bold))
            cat_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent;")
            top_h.addWidget(cat_lbl)
            top_h.addStretch()
            amt_lbl = QLabel(f"€{amount:,.2f}".replace(",", "."))
            amt_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            amt_lbl.setFont(QFont(FONT, 13))
            amt_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent;")
            top_h.addWidget(amt_lbl)
            pct_lbl = QLabel(f"  {pct:.0f}%")
            pct_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            pct_lbl.setFont(QFont(FONT, 12))
            pct_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
            pct_lbl.setFixedWidth(40)
            top_h.addWidget(pct_lbl)
            row_v.addLayout(top_h)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(6)
            bar_bg.setStyleSheet("background: #1a2e45; border-radius: 3px; border: none;")
            bar_inner = QFrame(bar_bg)
            bar_inner.setFixedHeight(6)
            bar_inner.setStyleSheet(f"background: {color}; border-radius: 3px; border: none;")
            bar_inner.setFixedWidth(max(4, int(pct / 100 * 560)))
            row_v.addWidget(bar_bg)

            wl.addWidget(row_w)

        cl.addWidget(wrapper)
        self._chart_layout.addWidget(card)

    # ── Filter setters ────────────────────────────────────────────────────────

    def _set_nw_filter(self, v: str) -> None:
        self._nw_filter = v
        self.refresh()

    def _set_change_filter(self, v: str) -> None:
        self._change_filter = v
        self.refresh()

    def _set_tracker_filter(self, v: str) -> None:
        self._tracker_filter = v
        self.refresh()

    def _set_cashflow_filter(self, v: str) -> None:
        self._cashflow_filter = v
        self.refresh()
