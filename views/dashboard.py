import calendar
import csv
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from database.db import (
    get_latest_snapshots,
    get_all_snapshots,
    get_all_expenses,
    get_snapshot,
    get_earliest_snapshot,
    get_extra_income,
    get_snapshot_income,
    get_setting,
    get_portfolio_positions,
    get_portfolio_cache,
    get_portfolio_reminder,
)
from utils import fmt_eur, fmt_eur_signed, effective_charge_day

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

# ── Theme palette ──────────────────────────────────────────────────────────────
_BG_CARD  = "#161f2e"
_ACCENT   = "#00b4d8"
_TEXT_PRI = "#e6edf3"
_TEXT_SEC = "#8b949e"
_BORDER   = "#2a3a52"
_BG_ELEM  = "#21262d"

_GREEN   = "#3fb950"
_RED     = "#f85149"
_NEUTRAL = _TEXT_SEC
_F       = "Helvetica Neue"


def _mlabel(year: int, month: int) -> str:
    return f"{MONTHS[month - 1]} {year}"


class DashboardView(ctk.CTkScrollableFrame):
    def __init__(self, parent, navigate=None):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._navigate       = navigate
        self._export_status: ctk.CTkLabel | None = None
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        # ── Reminder banner (not pre-packed; shown dynamically in _render_reminder) ─
        self._reminder_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Header row: title left, period right
        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.pack(fill="x", padx=24, pady=(28, 2))
        self._header.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._header, text="Dashboard",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).grid(row=0, column=0, sticky="w")

        self._period_label = ctk.CTkLabel(
            self._header, text="", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=13),
        )
        self._period_label.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            self, text="Monthly financial overview",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
        ).pack(anchor="w", padx=24, pady=(0, 16))

        # ── Metric cards ─────────────────────────────────────────────────────────
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=24, pady=(0, 8))
        cards_frame.columnconfigure([0, 1, 2], weight=1)

        self._nw_value, self._nw_sub, self._nw_spark, _nw_inner = self._make_card(
            cards_frame, "NET WORTH", 0)
        self._nw_portfolio_lbl = ctk.CTkLabel(
            _nw_inner, text="", text_color="#8b949e",
            font=ctk.CTkFont(family=_F, size=13), anchor="w")

        self._change_value, self._change_sub, self._change_spark, _ = self._make_card(
            cards_frame, "MONTHLY CHANGE", 1)
        self._fx_value, self._fx_sub, _, _ = self._make_card(
            cards_frame, "FIXED EXPENSES", 2)

        # ── Extra cards (Portfolio + Allocation Donut + Last Month Income) ────────
        self._extra_cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._extra_cards_frame.pack(fill="x", padx=24, pady=(0, 8))

        # ── Mid-month estimation (packed dynamically — not pre-packed) ───────────
        self._estimation_container = ctk.CTkFrame(self, fg_color="transparent")

        # ── Annual overview ────────────────────────────────────────────────────
        self._annual_divider = ctk.CTkFrame(self, height=1, fg_color=_BORDER)
        self._annual_divider.pack(fill="x", padx=24, pady=(4, 4))
        self._annual_container = ctk.CTkFrame(self, fg_color="transparent")
        self._annual_container.pack(fill="x", padx=24, pady=(0, 8))

        # ── Account breakdown ─────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=_BORDER).pack(fill="x", padx=24, pady=(4, 16))
        ctk.CTkLabel(
            self, text="Account Breakdown",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(0, 8))

        self._breakdown_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._breakdown_frame.pack(anchor="w", padx=24, fill="x", pady=(0, 24))

        # ── Snapshot History ──────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=_BORDER).pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(
            self, text="Snapshot History",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(0, 8))

        self._history_container = ctk.CTkFrame(self, fg_color="transparent")
        self._history_container.pack(fill="x", padx=24, pady=(0, 24))

        # ── CSV Export ────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=_BORDER).pack(fill="x", padx=24, pady=(0, 12))
        export_row = ctk.CTkFrame(self, fg_color="transparent")
        export_row.pack(anchor="w", padx=24, pady=(0, 32))
        ctk.CTkButton(
            export_row, text="Export to CSV", width=130,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, border_width=0, corner_radius=8,
            command=self._export_csv,
        ).pack(side="left", padx=(0, 12))
        self._export_status = ctk.CTkLabel(export_row, text="", text_color=_TEXT_SEC,
                                           font=ctk.CTkFont(family=_F, size=12))
        self._export_status.pack(side="left")

        self.refresh()

    def _make_card(
        self, parent: ctk.CTkFrame, title: str, col: int
    ) -> tuple[ctk.CTkLabel, ctk.CTkLabel, ctk.CTkFrame, ctk.CTkFrame]:
        padx  = {0: (0, 4), 1: (4, 4), 2: (4, 0)}.get(col, (4, 4))
        card  = ctk.CTkFrame(
            parent, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        card.grid(row=0, column=col, sticky="nsew", padx=padx)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(inner, text=title, text_color=_TEXT_SEC,
                     font=ctk.CTkFont(family=_F, size=11), anchor="w").pack(anchor="w")
        value = ctk.CTkLabel(inner, text="—", text_color=_TEXT_PRI,
                             font=ctk.CTkFont(family=_F, size=28, weight="bold"), anchor="w")
        value.pack(anchor="w", pady=(6, 2))

        # Sparkline placeholder (populated during refresh for NW and Change cards)
        sparkline_frame = ctk.CTkFrame(inner, fg_color="transparent", height=44)
        sparkline_frame.pack(anchor="w", fill="x", pady=(2, 4))
        sparkline_frame.pack_propagate(False)

        sub = ctk.CTkLabel(inner, text="", text_color=_TEXT_SEC,
                           font=ctk.CTkFont(family=_F, size=12), anchor="w")
        sub.pack(anchor="w")
        return value, sub, sparkline_frame, inner

    def _add_sparkline(self, frame: ctk.CTkFrame, values: list[float], chart_type: str = "line"):
        for w in frame.winfo_children():
            w.destroy()
        if len(values) < 2:
            return
        try:
            fig = Figure(figsize=(1.7, 0.42), dpi=100)
            ax  = fig.add_subplot(111)
            fig.patch.set_facecolor(_BG_CARD)
            ax.set_facecolor(_BG_CARD)
            ax.axis("off")
            fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.05)

            x = list(range(len(values)))
            if chart_type == "line":
                ax.plot(x, values, color=_ACCENT, linewidth=1.5, solid_capstyle="round")
                mn = min(values)
                ax.fill_between(x, [mn] * len(values), values, alpha=0.18, color=_ACCENT)
            else:
                colors = [_GREEN if v >= 0 else _RED for v in values]
                ax.bar(x, values, color=colors, width=0.7)
                ax.axhline(y=0, color=_BORDER, linewidth=0.5)

            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="x", expand=True)
        except Exception:
            pass

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        snapshots = get_latest_snapshots(3)
        expenses  = list(get_all_expenses())
        fx_total  = sum(e["amount"] for e in expenses)

        self._render_reminder()
        self._fx_value.configure(text=fmt_eur(fx_total))
        self._render_extra_cards(snapshots)

        if not snapshots:
            self._render_empty()
            self._render_estimation(None, expenses)
            self._render_annual()
            self._render_snapshot_history()
            return

        latest = snapshots[0]
        prev   = snapshots[1] if len(snapshots) >= 2 else None

        self._nw_value.configure(text=fmt_eur(latest["total"]))
        self._nw_sub.configure(
            text=_mlabel(latest["year"], latest["month"]), text_color=_TEXT_SEC)

        all_snaps = get_all_snapshots()
        if len(all_snaps) >= 2:
            self._add_sparkline(self._nw_spark,
                                [s["total"] for s in all_snaps[-6:]], "line")
            changes = [all_snaps[i + 1]["total"] - all_snaps[i]["total"]
                       for i in range(len(all_snaps) - 1)]
            self._add_sparkline(self._change_spark, changes[-6:], "bar")

        if prev:
            self._period_label.configure(
                text=f"{_mlabel(latest['year'], latest['month'])}"
                     f"  ·  vs {_mlabel(prev['year'], prev['month'])}"
            )
            self._render_comparison(latest, prev, fx_total)
        else:
            self._period_label.configure(text=_mlabel(latest["year"], latest["month"]))
            self._render_one_snapshot()

        self._render_estimation(latest, expenses)
        self._render_annual()
        self._render_snapshot_history()
        self._render_breakdown(latest, prev)

    # ── Reminder banner ───────────────────────────────────────────────────────

    def _render_reminder(self):
        for w in self._reminder_frame.winfo_children():
            w.destroy()

        if self._reminder_frame.winfo_manager() == "pack":
            self._reminder_frame.pack_forget()

        today = date.today()
        if today.day <= 20:
            self._header.pack_configure(pady=(28, 2))
            return

        if today.month == 1:
            prev_year, prev_month = today.year - 1, 12
        else:
            prev_year, prev_month = today.year, today.month - 1

        earliest = get_earliest_snapshot()
        if earliest is None:
            self._header.pack_configure(pady=(28, 2))
            return

        e_year, e_month = earliest
        prev_as_int  = prev_year * 12 + prev_month
        first_as_int = e_year * 12 + e_month
        if prev_as_int <= first_as_int:
            self._header.pack_configure(pady=(28, 2))
            return

        if get_snapshot(prev_year, prev_month) is not None:
            self._header.pack_configure(pady=(28, 2))
            return

        month_name = MONTHS[prev_month - 1]
        banner = ctk.CTkFrame(
            self._reminder_frame,
            fg_color=("#FFF3CD", "#3D3000"),
            corner_radius=8,
        )
        banner.pack(fill="x", pady=(0, 8))
        inner = ctk.CTkFrame(banner, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            inner,
            text=f"Reminder: No snapshot found for {month_name} {prev_year}.",
            font=ctk.CTkFont(family=_F, size=13),
            text_color=("#7D6000", "#FFC107"),
        ).pack(side="left")

        def go_to_snapshot():
            from views.snapshot_entry import SnapshotEntryView
            SnapshotEntryView._pending_period = (prev_year, prev_month)
            if self._navigate:
                self._navigate("snapshot")

        ctk.CTkButton(
            inner, text="Go to Snapshot", width=130,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            command=go_to_snapshot,
        ).pack(side="right")

        self._reminder_frame.pack(fill="x", padx=24, pady=(16, 0), before=self._header)
        self._header.pack_configure(pady=(8, 2))

    # ── Extra cards (Portfolio + Allocation Donut + Last Month Income) ──────────

    _DONUT_COLORS = ["#00b4d8", "#3fb950", "#f0c040", "#f85149",
                     "#a371f7", "#79c0ff", "#56d364", "#ff9500"]

    def _render_extra_cards(self, snapshots: list):
        for w in self._extra_cards_frame.winfo_children():
            w.destroy()

        latest     = snapshots[0] if snapshots else None
        prev_snap  = snapshots[1] if len(snapshots) >= 2 else None
        prev2_snap = snapshots[2] if len(snapshots) >= 3 else None

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

        # NW portfolio label
        self._nw_portfolio_lbl.pack_forget()
        if has_portfolio and latest and port_total_eur > 0:
            self._nw_portfolio_lbl.configure(
                text=f"{fmt_eur(latest['total'] + port_total_eur)} (portfolio included)")
            self._nw_portfolio_lbl.pack(anchor="w", before=self._nw_spark)

        # Income data
        last_mo_income  = 0.0
        prev_month_name = ""
        pct_change      = 0.0
        pct_color       = _TEXT_SEC
        has_pct         = False
        if prev_snap:
            si = get_snapshot_income(prev_snap["year"], prev_snap["month"])
            ex = get_extra_income(prev_snap["year"], prev_snap["month"])
            last_mo_income  = (sum(si.values()) + sum(e["amount"] for e in ex)) if si else 0.0
            prev_month_name = MONTHS[prev_snap["month"] - 1]
            if prev2_snap:
                si2 = get_snapshot_income(prev2_snap["year"], prev2_snap["month"])
                ex2 = get_extra_income(prev2_snap["year"], prev2_snap["month"])
                prev2_income = (sum(si2.values()) + sum(e["amount"] for e in ex2)) if si2 else 0.0
                if prev2_income > 0:
                    pct_change = (last_mo_income - prev2_income) / prev2_income * 100
                pct_color = _GREEN if pct_change >= 0 else _RED
                has_pct   = True
        has_income_data = bool(prev_snap)

        if not has_portfolio and not has_income_data:
            return

        num_cols = (2 if has_portfolio else 0) + (1 if has_income_data else 0)
        for c in range(num_cols):
            self._extra_cards_frame.columnconfigure(c, weight=1)

        _padx_map = {0: (0, 4), 1: (4, 4), 2: (4, 0)}
        col = 0

        if has_portfolio:
            pnl       = port_total_eur - port_cost_eur
            pnl_pct   = (pnl / port_cost_eur * 100) if port_cost_eur else 0.0
            pnl_color = _GREEN if pnl >= 0 else _RED
            pnl_sign  = "+" if pnl >= 0 else ""

            # Portfolio card
            padx  = _padx_map[col]
            card  = ctk.CTkFrame(self._extra_cards_frame, fg_color=_BG_CARD, corner_radius=14,
                                 border_width=1, border_color=_BORDER)
            card.grid(row=0, column=col, sticky="nsew", padx=padx, pady=(0, 8))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=20, pady=20, fill="both", expand=True)
            ctk.CTkLabel(inner, text="PORTFOLIO", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=11), anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner, text=fmt_eur(port_total_eur), text_color=_TEXT_PRI,
                         font=ctk.CTkFont(family=_F, size=22, weight="bold"),
                         anchor="w").pack(anchor="w", pady=(6, 2))
            ctk.CTkLabel(
                inner,
                text=f"{pnl_sign}{fmt_eur(pnl)}  ({pnl_sign}{pnl_pct:.1f}%)",
                text_color=pnl_color,
                font=ctk.CTkFont(family=_F, size=12), anchor="w",
            ).pack(anchor="w")
            self._render_reminder_badge(inner)
            col += 1

            # Donut card
            padx  = _padx_map.get(col, (4, 4))
            card2 = ctk.CTkFrame(self._extra_cards_frame, fg_color=_BG_CARD, corner_radius=14,
                                 border_width=1, border_color=_BORDER)
            card2.grid(row=0, column=col, sticky="nsew", padx=padx, pady=(0, 8))
            inner2 = ctk.CTkFrame(card2, fg_color="transparent")
            inner2.pack(padx=20, pady=20, fill="both", expand=True)
            ctk.CTkLabel(inner2, text="ALLOCATION", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=11),
                         anchor="w").pack(anchor="w", pady=(0, 6))
            self._render_donut_chart(inner2, positions, cache)
            col += 1

        if has_income_data:
            padx  = _padx_map.get(col, (4, 0))
            card3 = ctk.CTkFrame(self._extra_cards_frame, fg_color=_BG_CARD, corner_radius=14,
                                 border_width=1, border_color=_BORDER)
            card3.grid(row=0, column=col, sticky="nsew", padx=padx, pady=(0, 8))
            inner3 = ctk.CTkFrame(card3, fg_color="transparent")
            inner3.pack(padx=20, pady=20, fill="both", expand=True)
            ctk.CTkLabel(inner3, text="LAST MONTH INCOME", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=11), anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner3, text=fmt_eur(last_mo_income), text_color=_TEXT_PRI,
                         font=ctk.CTkFont(family=_F, size=22, weight="bold"),
                         anchor="w").pack(anchor="w", pady=(6, 2))
            if has_pct:
                pct_sign = "+" if pct_change >= 0 else ""
                ctk.CTkLabel(
                    inner3,
                    text=f"{pct_sign}{pct_change:.1f}%  vs {prev_month_name}",
                    text_color=pct_color,
                    font=ctk.CTkFont(family=_F, size=12), anchor="w",
                ).pack(anchor="w")

    def _render_reminder_badge(self, parent: ctk.CTkFrame):
        """Show a subtle reminder line at the bottom of the Portfolio card."""
        from datetime import date as _date
        reminder = get_portfolio_reminder()
        if not reminder or not reminder["is_enabled"]:
            return
        try:
            from datetime import datetime as _dt
            rem_date = _dt.strptime(reminder["reminder_date"], "%d.%m.%Y").date()
        except ValueError:
            return
        days_away = (rem_date - _date.today()).days
        if days_away < 0:
            text  = f"⚠ Rebalance overdue"
            color = "#f0c040"
        elif days_away <= 30:
            text  = f"⚠ Rebalance due in {days_away}d"
            color = "#f0c040"
        else:
            text  = f"Rebalance: {reminder['reminder_date']}"
            color = _TEXT_SEC
        ctk.CTkLabel(parent, text=text, text_color=color,
                     font=ctk.CTkFont(family=_F, size=11), anchor="w").pack(anchor="w", pady=(6, 0))

    def _render_donut_chart(self, parent: ctk.CTkFrame, positions: list, cache: dict):
        """Embed a matplotlib doughnut allocation chart into the given frame."""
        # Collect positions with known prices
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
            text = ("Add more positions to see allocation"
                    if len(positions) < 2
                    else "Refresh portfolio to see allocation")
            ctk.CTkLabel(parent, text=text, text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=12),
                         wraplength=160, justify="left").pack(anchor="w")
            return

        total  = sum(v for _, v in valued)
        labels = [f"{t}  {v / total * 100:.0f}%" for t, v in valued]
        values = [v for _, v in valued]
        colors = [self._DONUT_COLORS[i % len(self._DONUT_COLORS)] for i in range(len(valued))]

        try:
            fig = Figure(figsize=(3.4, 2.0), dpi=100)
            fig.patch.set_facecolor(_BG_CARD)
            ax  = fig.add_subplot(111)
            ax.set_facecolor(_BG_CARD)

            wedges, _ = ax.pie(
                values, colors=colors, startangle=90,
                wedgeprops=dict(width=0.52, edgecolor=_BG_CARD, linewidth=2),
            )
            ax.set_aspect("equal")

            leg = ax.legend(
                wedges, labels,
                loc="center left", bbox_to_anchor=(1.02, 0.5),
                fontsize=9, facecolor=_BG_CARD, edgecolor=_BORDER,
                framealpha=0.7,
            )
            for txt in leg.get_texts():
                txt.set_color(_TEXT_PRI)

            fig.subplots_adjust(left=0.0, right=0.55, top=1.0, bottom=0.0)

            canvas = FigureCanvasTkAgg(fig, master=parent)
            canvas.draw()
            canvas.get_tk_widget().pack(anchor="w")
        except Exception:
            ctk.CTkLabel(parent, text="Chart unavailable", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=12)).pack(anchor="w")

    # ── Snapshot state renderers ──────────────────────────────────────────────

    def _render_empty(self):
        self._period_label.configure(text="No data yet", text_color=_TEXT_SEC)
        self._nw_value.configure(text="—", text_color=_NEUTRAL)
        self._nw_sub.configure(text="Add your first snapshot to begin", text_color=_TEXT_SEC)
        self._change_value.configure(text="—", text_color=_NEUTRAL)
        self._change_sub.configure(text="")
        for w in self._breakdown_frame.winfo_children():
            w.destroy()

    def _render_one_snapshot(self):
        self._change_value.configure(text="—", text_color=_NEUTRAL)
        self._change_sub.configure(text="Need 2 months of data", text_color=_TEXT_SEC)

    def _render_comparison(self, latest: dict, prev: dict, fx_total: float):
        change = latest["total"] - prev["total"]
        pct    = (change / prev["total"] * 100) if prev["total"] else 0.0
        color  = _GREEN if change >= 0 else _RED

        self._change_value.configure(text=fmt_eur_signed(change), text_color=color)
        self._change_sub.configure(text=f"{'+' if pct >= 0 else ''}{pct:.2f}%", text_color=_TEXT_SEC)

    # ── End-of-month estimate ─────────────────────────────────────────────────

    def _render_estimation(self, latest: dict | None, expenses: list):
        for w in self._estimation_container.winfo_children():
            w.destroy()

        # Hide container when nothing to show
        def _hide():
            if self._estimation_container.winfo_manager():
                self._estimation_container.pack_forget()

        if latest is None:
            _hide()
            return

        today    = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]

        if today.day >= last_day:
            _hide()
            return
        if get_snapshot(today.year, today.month) is not None:
            _hide()
            return

        # Show container — insert before the Annual Overview divider
        if not self._estimation_container.winfo_manager():
            self._estimation_container.pack(
                fill="x", padx=24, pady=(0, 4),
                before=self._annual_divider,
            )

        daily_buffer  = float(get_setting("daily_buffer") or "20.0")
        buffer_cost   = last_day * daily_buffer
        all_fx        = list(expenses)
        fx_total      = sum(e["amount"] for e in all_fx)
        estimated_eom = latest["total"] - buffer_cost - fx_total
        est_change    = estimated_eom - latest["total"]

        card  = ctk.CTkFrame(self._estimation_container, fg_color=_BG_CARD, corner_radius=14,
                             border_width=1, border_color=_BORDER)
        card.pack(fill="x", pady=(4, 8))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        hdr = ctk.CTkFrame(inner, fg_color="transparent")
        hdr.pack(fill="x")
        hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="END-OF-MONTH ESTIMATE", text_color=_TEXT_SEC,
                     font=ctk.CTkFont(family=_F, size=11)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text=f"{MONTHS[today.month - 1]} {today.year}",
                     text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13)).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            inner,
            text=f"Based on {_mlabel(latest['year'], latest['month'])} snapshot",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
        ).pack(anchor="w", pady=(4, 8))

        ctk.CTkFrame(inner, height=1, fg_color=_BORDER).pack(fill="x", pady=(0, 8))

        def est_row(label: str, value: str, color=_TEXT_PRI):
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=label, anchor="w", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=12)).pack(side="left")
            ctk.CTkLabel(r, text=value, anchor="e", text_color=color,
                         font=ctk.CTkFont(family=_F, size=12)).pack(side="right")

        est_row("Latest net worth", fmt_eur(latest["total"]))
        est_row(f"Daily allowance  ({last_day} days × €{daily_buffer:.0f}/day)",
                f"–{fmt_eur(buffer_cost)}", _RED)
        est_row(f"Fixed expenses this month  ({len(all_fx)} items)",
                f"–{fmt_eur(fx_total)}", _RED)

        ctk.CTkFrame(inner, height=1, fg_color=_BORDER).pack(fill="x", pady=(8, 8))

        total_row = ctk.CTkFrame(inner, fg_color="transparent")
        total_row.pack(fill="x")
        ctk.CTkLabel(total_row, text="Estimated end-of-month net worth",
                     font=ctk.CTkFont(family=_F, size=13, weight="bold"),
                     text_color=_TEXT_PRI).pack(side="left")
        ctk.CTkLabel(
            total_row,
            text=f"{fmt_eur(estimated_eom)}  ({fmt_eur_signed(est_change)})",
            font=ctk.CTkFont(family=_F, size=13, weight="bold"),
            text_color=_GREEN if est_change >= 0 else _RED,
        ).pack(side="right")

    # ── Snapshot History ──────────────────────────────────────────────────────

    def _render_snapshot_history(self):
        for w in self._history_container.winfo_children():
            w.destroy()

        all_snaps = get_all_snapshots()
        if not all_snaps:
            ctk.CTkLabel(
                self._history_container,
                text="No snapshots yet.",
                text_color=_TEXT_SEC,
            ).pack(anchor="w")
            return

        existing = {(s["year"], s["month"]) for s in all_snaps}
        years    = sorted({s["year"] for s in all_snaps})

        card  = ctk.CTkFrame(self._history_container, fg_color=_BG_CARD, corner_radius=14,
                             border_width=1, border_color=_BORDER)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        # Month header row
        hdr = ctk.CTkFrame(inner, fg_color="transparent")
        hdr.pack(anchor="w", fill="x", pady=(0, 4))
        ctk.CTkLabel(hdr, text="", width=52).pack(side="left")
        for m in range(1, 13):
            ctk.CTkLabel(
                hdr, text=MONTHS[m - 1][:3], width=54, anchor="center",
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=11),
            ).pack(side="left")

        # One row per year
        for year in years:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(anchor="w", fill="x", pady=1)
            ctk.CTkLabel(
                row, text=str(year), width=52, anchor="w",
                text_color=_TEXT_PRI, font=ctk.CTkFont(family=_F, size=12),
            ).pack(side="left")
            for m in range(1, 13):
                if (year, m) in existing:
                    ctk.CTkButton(
                        row, text="✓", width=54, height=28,
                        fg_color=_BG_ELEM,
                        hover_color="#3d4d63",
                        text_color=_TEXT_PRI,
                        font=ctk.CTkFont(family=_F, size=12),
                        corner_radius=6,
                        command=lambda y=year, mo=m: self._go_to_snapshot(y, mo),
                    ).pack(side="left", padx=0)
                else:
                    ctk.CTkLabel(
                        row, text="·", width=54, anchor="center",
                        text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
                    ).pack(side="left")

    def _go_to_snapshot(self, year: int, month: int):
        from views.snapshot_entry import SnapshotEntryView
        SnapshotEntryView._pending_period = (year, month)
        if self._navigate:
            self._navigate("snapshot")

    # ── Annual overview ───────────────────────────────────────────────────────

    def _render_annual(self):
        for w in self._annual_container.winfo_children():
            w.destroy()

        today     = date.today()
        year      = today.year
        all_snaps = get_all_snapshots()

        ctk.CTkLabel(
            self._annual_container,
            text=f"Annual Overview · {year}",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", pady=(0, 10))

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
            ctk.CTkLabel(
                self._annual_container,
                text=f"No monthly changes recorded for {year} yet. Save snapshots across two months to see stats.",
                text_color=_TEXT_SEC,
            ).pack(anchor="w")
            return

        best        = max(year_changes, key=lambda x: x["change"])
        worst       = min(year_changes, key=lambda x: x["change"])
        avg         = sum(c["change"] for c in year_changes) / len(year_changes)
        total_saved = sum(c["change"] for c in year_changes if c["change"] > 0)
        n_positive  = sum(1 for c in year_changes if c["change"] > 0)

        card  = ctk.CTkFrame(self._annual_container, fg_color=_BG_CARD, corner_radius=14,
                             border_width=1, border_color=_BORDER)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)

        W_LBL = 180
        W_MON = 200
        W_VAL = 140

        def ann_row(label: str, month_str: str, value: float, color: str):
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(anchor="w", fill="x", pady=3)
            ctk.CTkLabel(r, text=label, width=W_LBL, anchor="w",
                         text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12)).pack(side="left")
            ctk.CTkLabel(r, text=month_str, width=W_MON, anchor="w",
                         text_color=_TEXT_PRI).pack(side="left")
            ctk.CTkLabel(r, text=fmt_eur_signed(value), width=W_VAL, anchor="e",
                         text_color=color, font=ctk.CTkFont(family=_F, weight="bold")).pack(side="left")

        ann_row("Best month",     _mlabel(best["year"],  best["month"]),  best["change"],  _GREEN)
        ann_row("Worst month",    _mlabel(worst["year"], worst["month"]), worst["change"], _RED)
        ann_row("Average change", f"{len(year_changes)} months recorded", avg,
                _GREEN if avg >= 0 else _RED)
        ann_row("Total saved",    f"{n_positive} positive month{'s' if n_positive != 1 else ''}",
                total_saved, _GREEN)

    # ── Account breakdown ─────────────────────────────────────────────────────

    def _render_breakdown(self, latest: dict, prev: dict | None):
        for w in self._breakdown_frame.winfo_children():
            w.destroy()

        W_NAME = 220
        W_AMT  = 140
        W_CHG  = 130

        hdr  = ctk.CTkFrame(self._breakdown_frame, fg_color=_BG_ELEM, corner_radius=8)
        hdr.pack(anchor="w", fill="x", pady=(0, 4))
        hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_inner.pack(anchor="w", padx=12, pady=6)

        cols: list[tuple[str, int, str]] = [("Account", W_NAME, "w")]
        if prev:
            prev_lbl    = MONTHS[prev["month"] - 1][:3] + f" {prev['year']}"
            current_lbl = MONTHS[latest["month"] - 1][:3] + f" {latest['year']}"
            cols += [(prev_lbl, W_AMT, "e"), (current_lbl, W_AMT, "e"), ("Change", W_CHG, "e")]
        else:
            cols.append(("Balance", W_AMT, "e"))

        for text, width, anchor in cols:
            ctk.CTkLabel(hdr_inner, text=text, width=width, anchor=anchor,
                         text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12)).pack(side="left")

        all_names = sorted(set(latest["balances"]) | (set(prev["balances"]) if prev else set()))

        for i, name in enumerate(all_names):
            row_bg = _BG_CARD if i % 2 == 0 else "#161b22"
            row    = ctk.CTkFrame(self._breakdown_frame, fg_color=row_bg, corner_radius=6)
            row.pack(anchor="w", fill="x", pady=1)
            row_inner = ctk.CTkFrame(row, fg_color="transparent")
            row_inner.pack(anchor="w", padx=12, pady=5)

            curr = latest["balances"].get(name, 0.0)
            ctk.CTkLabel(row_inner, text=name, width=W_NAME, anchor="w",
                         text_color=_TEXT_PRI).pack(side="left")

            if prev:
                old    = prev["balances"].get(name, 0.0)
                diff   = curr - old
                d_clr  = _GREEN if diff > 0 else (_RED if diff < 0 else _TEXT_SEC)
                ctk.CTkLabel(row_inner, text=fmt_eur(old),  width=W_AMT, anchor="e",
                             text_color=_TEXT_SEC).pack(side="left")
                ctk.CTkLabel(row_inner, text=fmt_eur(curr), width=W_AMT, anchor="e",
                             text_color=_TEXT_PRI).pack(side="left")
                ctk.CTkLabel(row_inner, text=fmt_eur_signed(diff), width=W_CHG, anchor="e",
                             text_color=d_clr).pack(side="left")
            else:
                ctk.CTkLabel(row_inner, text=fmt_eur(curr), width=W_AMT, anchor="e",
                             text_color=_TEXT_PRI).pack(side="left")


    # ── CSV Export ────────────────────────────────────────────────────────────

    def _export_csv(self):
        all_snaps = get_all_snapshots()
        if not all_snaps:
            if self._export_status:
                self._export_status.configure(text="No data to export.", text_color=_TEXT_SEC)
            return

        today        = date.today()
        default_name = f"money-tracker-export-{today.strftime('%Y-%m-%d')}.csv"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name,
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
            self._export_status.configure(text=f"Exported: {filename}", text_color=_GREEN)
            self.after(5000, lambda: self._export_status.configure(text="") if self._export_status else None)
