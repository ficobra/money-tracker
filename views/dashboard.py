import calendar
import csv
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from database.db import (
    get_latest_snapshots,
    get_all_snapshots,
    get_all_expenses,
    get_all_income,
    get_snapshot,
    get_setting,
    set_setting,
)
from utils import fmt_eur, fmt_eur_signed

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

_GREEN   = "#2CC985"
_RED     = "#E74C3C"
_NEUTRAL = ("gray65", "gray50")


def _mlabel(year: int, month: int) -> str:
    return f"{MONTHS[month - 1]} {year}"


class DashboardView(ctk.CTkScrollableFrame):
    def __init__(self, parent, navigate=None):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._navigate        = navigate
        self._editing_buffer  = False
        self._export_status:  ctk.CTkLabel | None = None
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        # ── Reminder banner (shown when prev month has no snapshot) ───────────
        self._reminder_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._reminder_frame.pack(fill="x", padx=24, pady=(16, 0))

        # Header row: title left, period right
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(8, 2))
        header.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Dashboard",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self._period_label = ctk.CTkLabel(
            header, text="", text_color="gray",
            font=ctk.CTkFont(size=13),
        )
        self._period_label.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            self, text="Monthly financial overview", text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        # ── Main metric cards (4) ─────────────────────────────────────────────
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=24, pady=(0, 4))
        cards_frame.columnconfigure([0, 1, 2, 3], weight=1)

        self._nw_value,     self._nw_sub     = self._make_card(cards_frame, "NET WORTH",          0)
        self._change_value, self._change_sub = self._make_card(cards_frame, "MONTHLY CHANGE",     1)
        self._fx_value,     self._fx_sub     = self._make_card(cards_frame, "FIXED EXPENSES",     2)
        self._disp_value,   self._disp_sub   = self._make_card(cards_frame, "DISPOSABLE INCOME",  3)

        # ── Extra cards row (conditional: Investment Portfolio + Income) ───────
        self._extra_cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._extra_cards_frame.pack(fill="x", padx=24, pady=(0, 4))

        # ── Mid-month estimation (shown conditionally) ────────────────────────
        self._estimation_container = ctk.CTkFrame(self, fg_color="transparent")
        self._estimation_container.pack(fill="x", padx=24, pady=(0, 0))

        # ── Annual overview ────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(0, 2)
        )
        self._annual_container = ctk.CTkFrame(self, fg_color="transparent")
        self._annual_container.pack(fill="x", padx=24, pady=(0, 8))

        # ── Investment breakdown (simplified) ─────────────────────────────────
        self._investment_container = ctk.CTkFrame(self, fg_color="transparent")
        self._investment_container.pack(fill="x", padx=24, pady=(0, 0))

        # ── Account breakdown ─────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(0, 16)
        )
        ctk.CTkLabel(
            self, text="Account Breakdown",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(0, 8))

        self._breakdown_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._breakdown_frame.pack(anchor="w", padx=24, fill="x", pady=(0, 24))

        # ── CSV Export ────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(0, 12)
        )
        export_row = ctk.CTkFrame(self, fg_color="transparent")
        export_row.pack(anchor="w", padx=24, pady=(0, 32))
        ctk.CTkButton(
            export_row, text="Export to CSV", width=130,
            fg_color="transparent", border_width=1,
            command=self._export_csv,
        ).pack(side="left", padx=(0, 12))
        self._export_status = ctk.CTkLabel(export_row, text="", text_color="gray",
                                           font=ctk.CTkFont(size=12))
        self._export_status.pack(side="left")

        self.refresh()

    def _make_card(
        self, parent: ctk.CTkFrame, title: str, col: int
    ) -> tuple[ctk.CTkLabel, ctk.CTkLabel]:
        padx  = {0: (0, 4), 1: (4, 4), 2: (4, 4), 3: (4, 0)}.get(col, (4, 4))
        card  = ctk.CTkFrame(parent)
        card.grid(row=0, column=col, sticky="nsew", padx=padx)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=16, pady=16, fill="both", expand=True)
        ctk.CTkLabel(inner, text=title, text_color="gray",
                     font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w")
        value = ctk.CTkLabel(inner, text="—",
                             font=ctk.CTkFont(size=22, weight="bold"), anchor="w")
        value.pack(anchor="w", pady=(6, 2))
        sub = ctk.CTkLabel(inner, text="", text_color="gray",
                           font=ctk.CTkFont(size=12), anchor="w")
        sub.pack(anchor="w")
        return value, sub

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        snapshots = get_latest_snapshots(2)
        expenses  = list(get_all_expenses())
        income    = list(get_all_income())
        fx_total  = sum(e["amount"] for e in expenses)
        inc_total = sum(i["amount"] for i in income)

        self._render_reminder()
        self._render_extra_cards(snapshots, inc_total, fx_total)

        self._fx_value.configure(text=fmt_eur(fx_total), text_color=("gray90", "gray95"))
        self._fx_sub.configure(text="per month")

        if not snapshots:
            self._render_empty()
            self._render_estimation(None, expenses)
            self._render_annual()
            self._render_investment_summary(None)
            return

        latest = snapshots[0]
        prev   = snapshots[1] if len(snapshots) >= 2 else None

        if prev:
            self._period_label.configure(
                text=f"{_mlabel(latest['year'], latest['month'])}"
                     f"  ·  vs {_mlabel(prev['year'], prev['month'])}"
            )
        else:
            self._period_label.configure(text=_mlabel(latest["year"], latest["month"]))

        self._nw_value.configure(text=fmt_eur(latest["total"]), text_color=("gray90", "gray95"))
        self._nw_sub.configure(
            text=f"{_mlabel(latest['year'], latest['month'])}  (excl. investments)",
            text_color="gray",
        )

        if prev:
            self._render_comparison(latest, prev, fx_total)
        else:
            self._render_one_snapshot()

        self._render_estimation(latest, expenses)
        self._render_annual()
        self._render_investment_summary(latest)
        self._render_breakdown(latest, prev)

    # ── Reminder banner ───────────────────────────────────────────────────────

    def _render_reminder(self):
        for w in self._reminder_frame.winfo_children():
            w.destroy()

        today = date.today()
        if today.day <= 20:
            return

        if today.month == 1:
            prev_year, prev_month = today.year - 1, 12
        else:
            prev_year, prev_month = today.year, today.month - 1

        if get_snapshot(prev_year, prev_month) is not None:
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
            font=ctk.CTkFont(size=13),
            text_color=("#7D6000", "#FFC107"),
        ).pack(side="left")

        def go_to_snapshot():
            from views.snapshot_entry import SnapshotEntryView
            SnapshotEntryView._pending_period = (prev_year, prev_month)
            if self._navigate:
                self._navigate("snapshot")

        ctk.CTkButton(
            inner, text="Go to Snapshot", width=130,
            command=go_to_snapshot,
        ).pack(side="right")

    # ── Extra cards (Investment Portfolio + Expected Income) ──────────────────

    def _render_extra_cards(self, snapshots: list, inc_total: float, fx_total: float):
        for w in self._extra_cards_frame.winfo_children():
            w.destroy()

        latest = snapshots[0] if snapshots else None
        has_investments = latest and latest.get("investment_total", 0) > 0
        has_income      = inc_total > 0

        if not has_investments and not has_income:
            return

        col = 0
        self._extra_cards_frame.columnconfigure(0, weight=1)
        self._extra_cards_frame.columnconfigure(1, weight=1)

        if has_investments:
            inv_total = latest["investment_total"]
            padx = (0, 4) if has_income else (0, 0)
            card  = ctk.CTkFrame(self._extra_cards_frame)
            card.grid(row=0, column=col, sticky="nsew", padx=padx)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(inner, text="INVESTMENT PORTFOLIO", text_color="gray",
                         font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner, text=fmt_eur(inv_total),
                         font=ctk.CTkFont(size=20, weight="bold"), anchor="w",
                         text_color=("gray90", "gray95")).pack(anchor="w", pady=(6, 2))
            ctk.CTkLabel(inner, text="current value", text_color="gray",
                         font=ctk.CTkFont(size=12), anchor="w").pack(anchor="w")
            col += 1

        if has_income:
            budget = inc_total - fx_total
            padx   = (4, 0) if has_investments else (0, 0)
            card   = ctk.CTkFrame(self._extra_cards_frame)
            card.grid(row=0, column=col, sticky="nsew", padx=padx)
            inner  = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(inner, text="EXPECTED MONTHLY INCOME", text_color="gray",
                         font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w")
            ctk.CTkLabel(inner, text=fmt_eur(inc_total),
                         font=ctk.CTkFont(size=20, weight="bold"), anchor="w",
                         text_color=("gray90", "gray95")).pack(anchor="w", pady=(6, 2))
            budget_color = _GREEN if budget >= 0 else _RED
            ctk.CTkLabel(
                inner,
                text=f"Spending budget: {fmt_eur_signed(budget)}",
                text_color=budget_color,
                font=ctk.CTkFont(size=12), anchor="w",
            ).pack(anchor="w")

    # ── Snapshot state renderers ──────────────────────────────────────────────

    def _render_empty(self):
        self._period_label.configure(text="No data yet")
        self._nw_value.configure(text="—", text_color=_NEUTRAL)
        self._nw_sub.configure(text="Add your first snapshot to begin", text_color="gray")
        self._change_value.configure(text="—", text_color=_NEUTRAL)
        self._change_sub.configure(text="")
        self._disp_value.configure(text="—", text_color=_NEUTRAL)
        self._disp_sub.configure(text="")
        for w in self._breakdown_frame.winfo_children():
            w.destroy()

    def _render_one_snapshot(self):
        self._change_value.configure(text="—", text_color=_NEUTRAL)
        self._change_sub.configure(text="Need 2 months of data")
        self._disp_value.configure(text="—", text_color=_NEUTRAL)
        self._disp_sub.configure(text="")

    def _render_comparison(self, latest: dict, prev: dict, fx_total: float):
        change = latest["total"] - prev["total"]
        pct    = (change / prev["total"] * 100) if prev["total"] else 0.0
        color  = _GREEN if change >= 0 else _RED

        self._change_value.configure(text=fmt_eur_signed(change), text_color=color)
        self._change_sub.configure(text=f"{'+' if pct >= 0 else ''}{pct:.2f}%")

        disposable = change - fx_total
        d_color    = _GREEN if disposable >= 0 else _RED

        self._disp_value.configure(text=fmt_eur_signed(disposable), text_color=d_color)
        self._disp_sub.configure(text="change − fixed expenses")

    # ── Mid-month estimation ──────────────────────────────────────────────────

    def _render_estimation(self, latest: dict | None, expenses: list):
        for w in self._estimation_container.winfo_children():
            w.destroy()

        if latest is None:
            return

        today    = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]

        if today.day >= last_day:
            return
        if get_snapshot(today.year, today.month) is not None:
            return

        daily_buffer   = float(get_setting("daily_buffer") or "20.0")
        remaining_days = last_day - today.day

        remaining_fx: list = []
        for e in expenses:
            d = e["day_of_month"]
            if last_day < 31 and d == 31:
                remaining_fx.append(e)
            elif d > today.day:
                remaining_fx.append(e)

        remaining_fx_total = sum(e["amount"] for e in remaining_fx)
        buffer_cost        = remaining_days * daily_buffer
        total_costs        = buffer_cost + remaining_fx_total
        estimated_eom      = latest["total"] - total_costs
        est_change         = estimated_eom - latest["total"]

        card  = ctk.CTkFrame(self._estimation_container)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        hdr = ctk.CTkFrame(inner, fg_color="transparent")
        hdr.pack(fill="x")
        hdr.columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="MID-MONTH ESTIMATION", text_color="gray",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text=f"{MONTHS[today.month - 1]} {today.year}",
                     text_color="gray", font=ctk.CTkFont(size=13)).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            inner,
            text=f"Based on {_mlabel(latest['year'], latest['month'])} snapshot",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(4, 6))

        buf_row = ctk.CTkFrame(inner, fg_color="transparent")
        buf_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(buf_row, text="Daily buffer:", anchor="w",
                     text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left")
        if self._editing_buffer:
            buf_var = ctk.StringVar(value=f"{daily_buffer:.1f}")
            ctk.CTkEntry(buf_row, textvariable=buf_var, width=80).pack(side="left", padx=(8, 4))
            ctk.CTkLabel(buf_row, text="EUR/day",
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
            ctk.CTkButton(buf_row, text="Save", width=56,
                          command=lambda v=buf_var: self._save_buffer_db(v),
                          ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(buf_row, text="Cancel", width=64,
                          fg_color="transparent", border_width=1,
                          command=self._cancel_buffer_edit,
                          ).pack(side="left")
        else:
            ctk.CTkLabel(buf_row, text=f"€{daily_buffer:.0f}/day",
                         font=ctk.CTkFont(size=12), anchor="w",
                         ).pack(side="left", padx=(8, 8))
            ctk.CTkButton(buf_row, text="Edit", width=48,
                          fg_color="transparent", border_width=1,
                          font=ctk.CTkFont(size=11),
                          command=self._start_buffer_edit,
                          ).pack(side="left")

        ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(0, 8)
        )

        def est_row(label: str, value: str, color=("gray90", "gray95"), small: bool = False):
            r  = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=1)
            fs = ctk.CTkFont(size=11) if small else ctk.CTkFont(size=12)
            ctk.CTkLabel(r, text=label, anchor="w", text_color="gray", font=fs).pack(side="left")
            ctk.CTkLabel(r, text=value, anchor="e", text_color=color, font=fs).pack(side="right")

        est_row(f"Latest net worth  ({_mlabel(latest['year'], latest['month'])})",
                fmt_eur(latest["total"]))
        est_row(f"Buffer cost  ({remaining_days} days × €{daily_buffer:.0f}/day)",
                f"–{fmt_eur(buffer_cost)}", _RED)

        expenses_hdr = ctk.CTkFrame(inner, fg_color="transparent")
        expenses_hdr.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(expenses_hdr,
                     text=f"Remaining fixed expenses  ({len(remaining_fx)} items)",
                     anchor="w", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(expenses_hdr, text=f"–{fmt_eur(remaining_fx_total)}",
                     anchor="e", text_color=_RED,
                     font=ctk.CTkFont(size=12)).pack(side="right")

        for e in remaining_fx:
            day_label = (
                "end of month" if (e["day_of_month"] == 31 and last_day < 31)
                else f"day {e['day_of_month']}"
            )
            est_row(f"  · {e['name']}  ({day_label})",
                    f"–{fmt_eur(e['amount'])}", _RED, small=True)

        ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(8, 8)
        )

        total_row = ctk.CTkFrame(inner, fg_color="transparent")
        total_row.pack(fill="x")
        ctk.CTkLabel(total_row, text="Estimated end-of-month net worth",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkLabel(
            total_row,
            text=f"{fmt_eur(estimated_eom)}  ({fmt_eur_signed(est_change)})",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_GREEN if est_change >= 0 else _RED,
        ).pack(side="right")

    def _start_buffer_edit(self):
        self._editing_buffer = True
        self.refresh()

    def _save_buffer_db(self, buf_var: ctk.StringVar):
        try:
            value = float(buf_var.get().strip())
            if value <= 0:
                raise ValueError
        except ValueError:
            return
        set_setting("daily_buffer", str(value))
        self._editing_buffer = False
        self.refresh()

    def _cancel_buffer_edit(self):
        self._editing_buffer = False
        self.refresh()

    # ── Investment summary ────────────────────────────────────────────────────

    def _render_investment_summary(self, latest: dict | None):
        for w in self._investment_container.winfo_children():
            w.destroy()

        if not latest:
            return

        inv_balances = latest.get("investment_balances", {})
        if not inv_balances:
            return

        inv_total = latest.get("investment_total", 0.0)

        ctk.CTkFrame(self._investment_container, height=1,
                     fg_color=("gray80", "gray30")).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            self._investment_container,
            text="Investment Portfolio",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        card  = ctk.CTkFrame(self._investment_container)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        W_LBL = 220
        W_VAL = 200

        def inv_row(label: str, value: str, color=("gray90", "gray95")):
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(anchor="w", fill="x", pady=3)
            ctk.CTkLabel(r, text=label, width=W_LBL, anchor="w",
                         text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(r, text=value, width=W_VAL, anchor="w",
                         text_color=color, font=ctk.CTkFont(weight="bold")).pack(side="left")

        inv_row("Total portfolio value", fmt_eur(inv_total))

        if len(inv_balances) > 1:
            ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
                fill="x", pady=(6, 6)
            )
            for acc_name, balance in sorted(inv_balances.items()):
                r = ctk.CTkFrame(inner, fg_color="transparent")
                r.pack(anchor="w", fill="x", pady=1)
                ctk.CTkLabel(r, text=acc_name, width=W_LBL, anchor="w",
                             font=ctk.CTkFont(size=12)).pack(side="left")
                ctk.CTkLabel(r, text=fmt_eur(balance), width=W_VAL, anchor="w",
                             font=ctk.CTkFont(size=12)).pack(side="left")

        ctk.CTkFrame(self._investment_container, height=8,
                     fg_color="transparent").pack()

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
            font=ctk.CTkFont(size=15, weight="bold"),
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
                text_color="gray",
            ).pack(anchor="w")
            return

        best        = max(year_changes, key=lambda x: x["change"])
        worst       = min(year_changes, key=lambda x: x["change"])
        avg         = sum(c["change"] for c in year_changes) / len(year_changes)
        total_saved = sum(c["change"] for c in year_changes if c["change"] > 0)
        n_positive  = sum(1 for c in year_changes if c["change"] > 0)

        card  = ctk.CTkFrame(self._annual_container)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=16)

        W_LBL = 180
        W_MON = 200
        W_VAL = 140

        def ann_row(label: str, month_str: str, value: float, color: str):
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(anchor="w", fill="x", pady=3)
            ctk.CTkLabel(r, text=label, width=W_LBL, anchor="w",
                         text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(r, text=month_str, width=W_MON, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=fmt_eur_signed(value), width=W_VAL, anchor="e",
                         text_color=color, font=ctk.CTkFont(weight="bold")).pack(side="left")

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

        hdr  = ctk.CTkFrame(self._breakdown_frame, fg_color="transparent")
        hdr.pack(anchor="w", fill="x", pady=(0, 4))

        cols: list[tuple[str, int, str]] = [("Account", W_NAME, "w")]
        if prev:
            prev_lbl    = MONTHS[prev["month"] - 1][:3] + f" {prev['year']}"
            current_lbl = MONTHS[latest["month"] - 1][:3] + f" {latest['year']}"
            cols += [(prev_lbl, W_AMT, "e"), (current_lbl, W_AMT, "e"), ("Change", W_CHG, "e")]
        else:
            cols.append(("Balance", W_AMT, "e"))

        for text, width, anchor in cols:
            ctk.CTkLabel(hdr, text=text, width=width, anchor=anchor,
                         text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left")

        all_names = sorted(set(latest["balances"]) | (set(prev["balances"]) if prev else set()))
        inv_names = set(latest.get("investment_balances", {}).keys())
        if prev:
            inv_names |= set(prev.get("investment_balances", {}).keys())

        for name in all_names:
            row  = ctk.CTkFrame(self._breakdown_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", pady=2)
            curr = latest["balances"].get(name, 0.0)

            name_label = name + (" ★" if name in inv_names else "")
            ctk.CTkLabel(row, text=name_label, width=W_NAME, anchor="w").pack(side="left")

            if prev:
                old    = prev["balances"].get(name, 0.0)
                diff   = curr - old
                d_clr  = _GREEN if diff > 0 else (_RED if diff < 0 else "gray")
                ctk.CTkLabel(row, text=fmt_eur(old),  width=W_AMT, anchor="e",
                             text_color="gray").pack(side="left")
                ctk.CTkLabel(row, text=fmt_eur(curr), width=W_AMT, anchor="e").pack(side="left")
                ctk.CTkLabel(row, text=fmt_eur_signed(diff), width=W_CHG, anchor="e",
                             text_color=d_clr).pack(side="left")
            else:
                ctk.CTkLabel(row, text=fmt_eur(curr), width=W_AMT, anchor="e").pack(side="left")

        if inv_names:
            ctk.CTkLabel(
                self._breakdown_frame,
                text="★ Investment account (excluded from Net Worth)",
                text_color="gray", font=ctk.CTkFont(size=11),
            ).pack(anchor="w", pady=(6, 0))

    # ── CSV Export ────────────────────────────────────────────────────────────

    def _export_csv(self):
        all_snaps = get_all_snapshots()
        if not all_snaps:
            if self._export_status:
                self._export_status.configure(text="No data to export.", text_color="gray")
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
            inv_names = set(snap.get("investment_balances", {}).keys())
            for acc_name, balance in snap["balances"].items():
                rows.append({
                    "Year":          snap["year"],
                    "Month":         snap["month"],
                    "Account":       acc_name,
                    "Balance":       f"{balance:.2f}",
                    "Is_Investment": 1 if acc_name in inv_names else 0,
                })

        fieldnames = ["Year", "Month", "Account", "Balance", "Is_Investment"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        filename = Path(filepath).name
        if self._export_status:
            self._export_status.configure(text=f"Exported: {filename}", text_color=_GREEN)
            self.after(5000, lambda: self._export_status.configure(text="") if self._export_status else None)
