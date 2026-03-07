import numpy as np
import customtkinter as ctk
from datetime import date, timedelta
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter

from database.db import (
    get_all_snapshots, get_all_accounts, get_all_income, get_snapshot_income,
    get_all_expenses, get_extra_income,
)
from utils import fmt_eur, fmt_eur_signed

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_FIG_W  = 8.5   # inches — fits comfortably in a 1100px window
_FIG_H  = 3.2

# Premium dark theme palette
_BG_CARD = "#161f2e"
_ACCENT  = "#00b4d8"
_TEXT_PRI = "#e6edf3"
_TEXT_SEC = "#8b949e"
_BORDER  = "#2a3a52"
_BG_ELEM = "#21262d"
_GREEN   = "#3fb950"
_RED     = "#f85149"
_BG_MAIN = "#0d1117"
_F       = "Helvetica Neue"

# Colors for the Account Tracker
_TRACKER_COLORS = ["#00b4d8", "#A78BFA", "#F59E0B", "#10B981", "#EF4444", "#F97316"]


def _snap_label(snap: dict) -> str:
    return f"{_MONTHS_SHORT[snap['month'] - 1]} '{str(snap['year'])[2:]}"


def _eu_axis_fmt(v: float) -> str:
    """European number format for chart axis labels: €1.234"""
    s  = f"{abs(v):,.0f}"
    eu = s.replace(",", ".")
    return f"-€{eu}" if v < 0 else f"€{eu}"


def _palette() -> dict:
    return {
        "fig_bg":  _BG_CARD,
        "axes_bg": "#161b22",
        "text":    _TEXT_PRI,
        "grid":    _BORDER,
        "spine":   "#444c56",
        "line":    _ACCENT,
        "green":   _GREEN,
        "red":     _RED,
    }


def _apply_style(fig: Figure, ax, pal: dict):
    fig.patch.set_facecolor(_BG_MAIN)
    ax.set_facecolor(_BG_MAIN)
    ax.tick_params(colors=_TEXT_SEC, labelsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _eu_axis_fmt(v)))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(True, color="#1c2333", linestyle="--", linewidth=0.5, alpha=0.6, axis="y")


class ChartsView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._figures: list[Figure] = []
        self._tracker_vars: dict[str, ctk.BooleanVar] = {}
        self._tracker_figure: Figure | None = None
        self._tracker_chart_frame: ctk.CTkFrame | None = None
        self._tracker_snap_data: list[dict] = []
        self._income_tracker_vars: dict[int, ctk.BooleanVar] = {}
        self._income_names: dict[int, str] = {}
        self._income_snap_data: list[dict[int, float]] = []
        self._nw_filter:      str = "All"
        self._change_filter:  str = "All"
        self._tracker_filter: str = "All"
        self._cashflow_filter: str = "All"
        self._patch_canvas_scroll()
        self._build()

    def _patch_canvas_scroll(self):
        """Replace CTkScrollableFrame's _parent_canvas scroll binding with a
        boundary-aware version that blocks upward scrolling at the top.
        Returns 'break' to prevent the global bind_all handler from also firing."""
        canvas = self._parent_canvas

        def _safe_scroll(event):
            scroll_up = getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4
            if scroll_up and canvas.yview()[0] <= 0:
                return "break"
            if getattr(event, "delta", 0):
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            if canvas.yview()[0] < 0:
                canvas.yview_moveto(0)
            return "break"

        canvas.bind("<MouseWheel>", _safe_scroll)
        canvas.bind("<Button-4>",   _safe_scroll)
        canvas.bind("<Button-5>",   _safe_scroll)

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Analytics",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Visual overview of your net worth and portfolio across all saved snapshots.",
            font=ctk.CTkFont(family=_F, size=13),
            text_color=_TEXT_SEC,
        ).pack(anchor="w", padx=24, pady=(0, 20))

        self._chart_container = ctk.CTkFrame(self, fg_color="transparent")
        self._chart_container.pack(fill="x", padx=24, pady=(0, 32))

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        for w in self._chart_container.winfo_children():
            w.destroy()
        for fig in self._figures:
            fig.clear()
        self._figures.clear()
        self._tracker_figure    = None
        self._tracker_chart_frame = None

        snapshots = get_all_snapshots()

        if len(snapshots) < 2:
            self._show_empty(len(snapshots))
            if snapshots:
                self._render_tracker(snapshots)
            return

        self._render_networth(snapshots)
        self._render_changes(snapshots)
        self._render_cashflow(snapshots)
        self._render_tracker(snapshots)

    # ── Empty state ───────────────────────────────────────────────────────────

    def _show_empty(self, count: int):
        msg = (
            "Add your first monthly snapshot to begin."
            if count == 0
            else "Add one more monthly snapshot to start seeing charts."
        )
        card = ctk.CTkFrame(
            self._chart_container,
            fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        card.pack(fill="x")
        ctk.CTkLabel(
            card, text="Not enough data yet",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(pady=(36, 6))
        ctk.CTkLabel(card, text=msg, text_color=_TEXT_SEC,
                     font=ctk.CTkFont(family=_F, size=13)).pack(pady=(0, 36))

    # ── Card helper ───────────────────────────────────────────────────────────

    def _make_card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self._chart_container,
            fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(family=_F, size=14, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=16, pady=(12, 6))
        return card

    # ── Shared axis helpers ───────────────────────────────────────────────────

    def _set_xticks(self, ax, labels: list[str], x: list[int]):
        rotation = 40 if len(labels) > 5 else 0
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=rotation,
                           ha="right" if rotation else "center")

    def _annotate_points(self, ax, x: list[int], values: list[float], pal: dict):
        if len(values) > 16:
            return
        for xi, v in zip(x, values):
            offset = 8 if v >= 0 else -16
            ax.annotate(
                fmt_eur(v), (xi, v),
                textcoords="offset points", xytext=(0, offset),
                ha="center", fontsize=7.5, color=pal["text"],
            )

    def _annotate_bars(self, ax, x: list[int], values: list[float], pal: dict):
        """Bar annotations: labels above positive bars, below negative bars."""
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

    # ── Filter helpers ────────────────────────────────────────────────────────

    def _filter_snaps(self, snaps: list, key: str) -> list:
        if key == "All":
            return snaps
        today = date.today()
        cutoffs = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}
        if key == "YTD":
            cutoff = date(today.year, 1, 1)
        else:
            cutoff = today - timedelta(days=cutoffs[key])
        return [s for s in snaps if date(s["year"], s["month"], 1) >= cutoff]

    def _build_chart_header(self, parent: ctk.CTkFrame, current_val: float, prev_val: float | None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(row, text=fmt_eur(current_val),
                     font=ctk.CTkFont(family=_F, size=16, weight="bold"),
                     text_color=_TEXT_PRI).pack(side="left", padx=(0, 12))
        if prev_val is not None:
            change = current_val - prev_val
            pct    = (change / prev_val * 100) if prev_val else 0
            color  = _GREEN if change >= 0 else _RED
            sign   = "+" if pct >= 0 else ""
            ctk.CTkLabel(row,
                         text=f"{fmt_eur_signed(change)}  ({sign}{pct:.1f}%)",
                         font=ctk.CTkFont(family=_F, size=13),
                         text_color=color).pack(side="left")

    def _build_filter_row(self, parent: ctk.CTkFrame, options: list[str],
                          current: str, on_select):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w", pady=(0, 8))
        for opt in options:
            is_active = (opt == current)
            ctk.CTkButton(row, text=opt, width=44,
                          fg_color=_ACCENT if is_active else _BG_ELEM,
                          hover_color="#0096b4" if is_active else "#3d4d63",
                          text_color="white" if is_active else _TEXT_SEC,
                          corner_radius=6,
                          font=ctk.CTkFont(family=_F, size=11),
                          command=lambda o=opt: on_select(o),
                          ).pack(side="left", padx=(0, 4))

    # ── Chart 1: Net worth over time ──────────────────────────────────────────

    def _render_networth(self, snapshots: list[dict]):
        pal   = _palette()
        snaps = self._filter_snaps(snapshots, self._nw_filter)

        card  = self._make_card("Net Worth Over Time (excl. investments)")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(0, 8))

        self._build_filter_row(inner, ["1M", "3M", "6M", "1Y", "YTD", "All"],
                               self._nw_filter,
                               lambda o: self._set_nw_filter(o))

        if snaps:
            current_val = snaps[-1]["total"]
            prev_val    = snaps[-2]["total"] if len(snaps) >= 2 else None
            self._build_chart_header(inner, current_val, prev_val)

        if not snaps:
            ctk.CTkLabel(inner, text="No data for selected period.",
                         text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=12)).pack(anchor="w", pady=8)
            return

        labels = [_snap_label(s) for s in snaps]
        y_vals = [s["total"] for s in snaps]
        x      = list(range(len(snaps)))

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax  = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        if len(snaps) >= 2:
            x_np = np.array(x, dtype=float)
            y_np = np.array(y_vals, dtype=float)
            x_s  = np.linspace(0, len(snaps) - 1, 300)
            y_s  = np.interp(x_s, x_np, y_np)
            ax.plot(x_s, y_s, color=_ACCENT, linewidth=2, zorder=3)
            y_min = min(y_s) - abs(max(y_s) - min(y_s)) * 0.1
            ax.fill_between(x_s, y_s, y_min, alpha=0.15, color=_ACCENT, zorder=2)
        else:
            ax.plot(x, y_vals, color=_ACCENT, linewidth=2,
                    marker="o", markersize=5, zorder=3)

        self._set_xticks(ax, labels, x)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)
        self._embed(fig, card)

    def _embed(self, fig: Figure, card: ctk.CTkFrame):
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(padx=16, pady=(0, 16))

    # ── Chart 2: Monthly change bars ──────────────────────────────────────────

    def _render_changes(self, snapshots: list[dict]):
        pal   = _palette()
        snaps = self._filter_snaps(snapshots, self._change_filter)

        card  = self._make_card("Monthly Net Worth Change")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(0, 8))

        self._build_filter_row(inner, ["1M", "3M", "6M", "1Y", "YTD", "All"],
                               self._change_filter,
                               lambda o: self._set_change_filter(o))

        if len(snaps) >= 2:
            current_change = snaps[-1]["total"] - snaps[-2]["total"]
            prev_change    = (snaps[-2]["total"] - snaps[-3]["total"]) if len(snaps) >= 3 else None
            self._build_chart_header(inner, current_change, prev_change)

        if len(snaps) < 2:
            ctk.CTkLabel(inner, text="No data for selected period.",
                         text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=12)).pack(anchor="w", pady=8)
            return

        changes = [snaps[i + 1]["total"] - snaps[i]["total"]
                   for i in range(len(snaps) - 1)]
        labels  = [_snap_label(s) for s in snaps[1:]]
        x       = list(range(len(changes)))
        colors  = [pal["green"] if c >= 0 else pal["red"] for c in changes]

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax  = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        ax.bar(x, changes, color=colors, width=0.6, zorder=3)
        ax.axhline(y=0, color="#444c56", linewidth=1)

        self._set_xticks(ax, labels, x)
        ax.margins(y=0.30)
        self._annotate_bars(ax, x, changes, pal)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)
        self._embed(fig, card)

    # ── Chart 3: Account Tracker ──────────────────────────────────────────────

    def _render_tracker(self, snapshots: list[dict]):
        filtered = self._filter_snaps(snapshots, self._tracker_filter)
        self._tracker_snap_data = filtered

        # Pre-load income data for filtered snapshots
        self._income_snap_data = [
            get_snapshot_income(s["year"], s["month"]) for s in filtered
        ]

        all_accounts = get_all_accounts()
        all_income   = list(get_all_income())

        for acc in all_accounts:
            if acc not in self._tracker_vars:
                self._tracker_vars[acc] = ctk.BooleanVar(value=False)

        self._income_names = {i["id"]: i["name"] for i in all_income}
        for i in all_income:
            if i["id"] not in self._income_tracker_vars:
                self._income_tracker_vars[i["id"]] = ctk.BooleanVar(value=False)

        card = self._make_card("Account Tracker")

        ctrl = ctk.CTkFrame(card, fg_color="transparent")
        ctrl.pack(fill="x", padx=16, pady=(0, 8))

        self._build_filter_row(ctrl, ["1M", "3M", "6M", "1Y", "YTD", "All"],
                               self._tracker_filter,
                               lambda o: self._set_tracker_filter(o))

        if not all_accounts and not all_income:
            ctk.CTkLabel(
                ctrl, text="No accounts saved yet.", text_color=_TEXT_SEC,
                font=ctk.CTkFont(family=_F, size=13),
            ).pack(anchor="w", pady=(0, 8))
        else:
            if all_accounts:
                ctk.CTkLabel(
                    ctrl, text="Select accounts to chart:",
                    text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
                ).pack(anchor="w", pady=(0, 6))

                cb_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
                cb_frame.pack(anchor="w", pady=(0, 4))
                for acc in all_accounts:
                    ctk.CTkCheckBox(
                        cb_frame, text=acc,
                        variable=self._tracker_vars[acc],
                        command=self._on_tracker_change,
                    ).pack(side="left", padx=(0, 16))

            if all_income:
                ctk.CTkLabel(
                    ctrl, text="Select income sources to chart:",
                    text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
                ).pack(anchor="w", pady=(6 if all_accounts else 0, 6))

                inc_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
                inc_frame.pack(anchor="w", pady=(0, 4))
                for inc in all_income:
                    ctk.CTkCheckBox(
                        inc_frame, text=inc["name"],
                        variable=self._income_tracker_vars[inc["id"]],
                        command=self._on_tracker_change,
                    ).pack(side="left", padx=(0, 16))

        self._tracker_chart_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._tracker_chart_frame.pack(fill="x", padx=16, pady=(0, 16))
        self._draw_tracker_chart()

    def _on_tracker_change(self):
        self._draw_tracker_chart()

    def _draw_tracker_chart(self):
        if self._tracker_chart_frame is None:
            return

        for w in self._tracker_chart_frame.winfo_children():
            w.destroy()

        if self._tracker_figure is not None:
            if self._tracker_figure in self._figures:
                self._figures.remove(self._tracker_figure)
            self._tracker_figure.clear()
            self._tracker_figure = None

        selected_acc = [acc for acc, var in self._tracker_vars.items() if var.get()]
        selected_inc = [(iid, self._income_names[iid])
                        for iid, var in self._income_tracker_vars.items() if var.get()]

        if not selected_acc and not selected_inc:
            ctk.CTkLabel(
                self._tracker_chart_frame,
                text="Select one or more accounts or income sources above to see their values over time.",
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            ).pack(anchor="w", pady=(4, 8))
            return

        if not self._tracker_snap_data:
            return

        pal = _palette()
        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax  = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        all_labels = [_snap_label(s) for s in self._tracker_snap_data]
        all_x      = list(range(len(self._tracker_snap_data)))

        color_idx = 0
        for acc in selected_acc:
            xs, ys = [], []
            for xi, s in zip(all_x, self._tracker_snap_data):
                if acc in s["balances"]:
                    xs.append(xi)
                    ys.append(s["balances"][acc])
            if xs:
                color = _TRACKER_COLORS[color_idx % len(_TRACKER_COLORS)]
                ax.plot(xs, ys, color=color, linewidth=2.5,
                        marker="o", markersize=5, zorder=3, label=acc)
                ax.fill_between(xs, ys, alpha=0.08, color=color)
            color_idx += 1

        for iid, name in selected_inc:
            xs, ys = [], []
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
            leg = ax.legend(fontsize=9, facecolor=_BG_MAIN,
                            edgecolor="#3d4d63")
            for txt in leg.get_texts():
                txt.set_color(_TEXT_PRI)

        fig.tight_layout(pad=1.5)
        self._tracker_figure = fig
        self._figures.append(fig)

        canvas = FigureCanvasTkAgg(fig, master=self._tracker_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack()

    # ── Chart 4: Cash Flow ────────────────────────────────────────────────────

    def _render_cashflow(self, snapshots: list[dict]):
        pal   = _palette()
        snaps = self._filter_snaps(snapshots, self._cashflow_filter)

        card  = self._make_card("Cash Flow")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(0, 8))

        self._build_filter_row(inner, ["1M", "3M", "6M", "1Y", "YTD", "All"],
                               self._cashflow_filter,
                               lambda o: self._set_cashflow_filter(o))

        fx_total = sum(e["amount"] for e in get_all_expenses())

        # Build a prev-NW lookup from the full (unfiltered) snapshots list
        prev_nw: dict[tuple, float] = {}
        for i in range(1, len(snapshots)):
            key = (snapshots[i]["year"], snapshots[i]["month"])
            prev_nw[key] = snapshots[i - 1]["total"]

        inc_per_month:   list[float]        = []
        spent_per_month: list[float | None] = []  # None = first snapshot (no previous)

        for s in snaps:
            snap_inc = get_snapshot_income(s["year"], s["month"])
            extras   = get_extra_income(s["year"], s["month"])
            income   = (sum(snap_inc.values()) + sum(e["amount"] for e in extras)) if snap_inc else 0.0
            inc_per_month.append(income)

            key = (s["year"], s["month"])
            if key in prev_nw:
                spent_per_month.append(prev_nw[key] + income - s["total"])
            else:
                spent_per_month.append(None)

        if not snaps:
            ctk.CTkLabel(inner, text="No data for selected period.",
                         text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=12)).pack(anchor="w", pady=8)
            return

        # Stats — only include months with confirmed spending data
        total_inc = sum(inc_per_month)
        total_exp = sum(sp for sp in spent_per_month if sp is not None)
        sav_vals  = [inc - sp for inc, sp in zip(inc_per_month, spent_per_month) if sp is not None]
        avg_sav   = sum(sav_vals) / len(sav_vals) if sav_vals else 0.0
        sav_color = _GREEN if avg_sav >= 0 else _RED

        stats = ctk.CTkFrame(inner, fg_color="transparent")
        stats.pack(anchor="w", pady=(0, 10))
        for lbl, val, col in [
            ("TOTAL EARNED",   fmt_eur(total_inc), _GREEN),
            ("TOTAL SPENT",    fmt_eur(total_exp), _RED),
            ("AVG SAVINGS/MO", fmt_eur_signed(avg_sav), sav_color),
        ]:
            col_f = ctk.CTkFrame(stats, fg_color="transparent")
            col_f.pack(side="left", padx=(0, 28))
            ctk.CTkLabel(col_f, text=lbl, text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=11)).pack(anchor="w")
            ctk.CTkLabel(col_f, text=val, text_color=col,
                         font=ctk.CTkFont(family=_F, size=14, weight="bold")).pack(anchor="w")

        labels       = [_snap_label(s) for s in snaps]
        x            = list(range(len(snaps)))
        bar_w        = 0.35
        x_inc        = [xi - bar_w / 2 for xi in x]
        x_exp_all    = [xi + bar_w / 2 for xi in x]
        x_exp        = [xi for xi, sp in zip(x_exp_all, spent_per_month) if sp is not None]
        exp_vals     = [sp for sp in spent_per_month if sp is not None]
        x_net        = [xi for xi, sp in zip(x, spent_per_month) if sp is not None]
        net_sav      = [inc - sp for inc, sp in zip(inc_per_month, spent_per_month) if sp is not None]

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax  = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        ax.bar(x_inc, inc_per_month, width=bar_w, color=_GREEN, alpha=0.8,
               label="Money Earned", zorder=3)
        if exp_vals:
            ax.bar(x_exp, exp_vals, width=bar_w, color=_RED, alpha=0.8,
                   label="Money Spent", zorder=3)
        if net_sav:
            ax.plot(x_net, net_sav, color="#7c8cf8", linewidth=2,
                    marker="o", markersize=4, zorder=4, label="Net Savings")
        ax.axhline(y=0, color="#444c56", linewidth=0.8)

        leg = ax.legend(fontsize=9, facecolor=_BG_MAIN, edgecolor=_BORDER)
        for txt in leg.get_texts():
            txt.set_color(_TEXT_PRI)

        self._set_xticks(ax, labels, x)
        ax.margins(y=0.25)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)
        self._embed(fig, card)

    # ── Filter setters ────────────────────────────────────────────────────────

    def _set_nw_filter(self, key: str):
        self._nw_filter = key
        self.refresh()

    def _set_change_filter(self, key: str):
        self._change_filter = key
        self.refresh()

    def _set_tracker_filter(self, key: str):
        self._tracker_filter = key
        self.refresh()

    def _set_cashflow_filter(self, key: str):
        self._cashflow_filter = key
        self.refresh()

