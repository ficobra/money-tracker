import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter

from database.db import get_all_snapshots, get_all_accounts, get_all_income, get_snapshot_income
from utils import fmt_eur, fmt_eur_signed

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_FIG_W  = 8.5   # inches — fits comfortably in a 1100px window
_FIG_H  = 3.2

# Colors for the Account Tracker (light-and-dark-friendly)
_TRACKER_COLORS = ["#5B9EF4", "#A78BFA", "#F59E0B", "#10B981", "#EF4444", "#F97316"]


def _snap_label(snap: dict) -> str:
    return f"{_MONTHS_SHORT[snap['month'] - 1]} '{str(snap['year'])[2:]}"


def _eu_axis_fmt(v: float) -> str:
    """European number format for chart axis labels: €1.234"""
    s  = f"{abs(v):,.0f}"
    eu = s.replace(",", ".")
    return f"-€{eu}" if v < 0 else f"€{eu}"


def _palette() -> dict:
    dark = ctk.get_appearance_mode().lower() == "dark"
    return {
        "fig_bg":  "#2B2B2B" if dark else "#EBEBEB",
        "axes_bg": "#1E1E1E" if dark else "#F5F5F5",
        "text":    "#DCE4EE" if dark else "#1A1A1A",
        "grid":    "#383838" if dark else "#D5D5D5",
        "spine":   "#444444" if dark else "#BBBBBB",
        "line":    "#5B9EF4" if dark else "#2563EB",
        "green":   "#2CC985" if dark else "#16A34A",
        "red":     "#E74C3C" if dark else "#DC2626",
    }


def _apply_style(fig: Figure, ax, pal: dict):
    fig.patch.set_facecolor(pal["fig_bg"])
    ax.set_facecolor(pal["axes_bg"])
    ax.tick_params(colors=pal["text"], labelsize=9)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _eu_axis_fmt(v)))
    for spine in ax.spines.values():
        spine.set_edgecolor(pal["spine"])
    ax.grid(True, color=pal["grid"], linestyle="--", linewidth=0.5, alpha=0.8, axis="y")


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
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Charts",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Visual overview of your net worth and portfolio across all saved snapshots.",
            text_color="gray",
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
        self._tracker_figure = None
        self._tracker_chart_frame = None

        snapshots = get_all_snapshots()

        if len(snapshots) < 2:
            self._show_empty(len(snapshots))
            if snapshots:
                self._render_tracker(snapshots)
            return

        self._render_networth(snapshots)
        self._render_changes(snapshots)
        self._render_tracker(snapshots)

    # ── Empty state ───────────────────────────────────────────────────────────

    def _show_empty(self, count: int):
        msg = (
            "Add your first monthly snapshot to begin."
            if count == 0
            else "Add one more monthly snapshot to start seeing charts."
        )
        card = ctk.CTkFrame(self._chart_container)
        card.pack(fill="x")
        ctk.CTkLabel(
            card, text="Not enough data yet",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(36, 6))
        ctk.CTkLabel(card, text=msg, text_color="gray").pack(pady=(0, 36))

    # ── Card helper ───────────────────────────────────────────────────────────

    def _make_card(self, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self._chart_container)
        card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))
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

    # ── Chart 1: Net worth over time ──────────────────────────────────────────

    def _render_networth(self, snapshots: list[dict]):
        pal    = _palette()
        labels = [_snap_label(s) for s in snapshots]
        totals = [s["total"] for s in snapshots]
        x      = list(range(len(labels)))

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax  = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        ax.plot(x, totals, color=pal["line"], linewidth=2.5,
                marker="o", markersize=5, zorder=3)
        ax.fill_between(x, totals, alpha=0.12, color=pal["line"])

        self._set_xticks(ax, labels, x)
        self._annotate_points(ax, x, totals, pal)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)

        card = self._make_card("Net Worth Over Time (excl. investments)")
        self._embed(fig, card)

    def _embed(self, fig: Figure, card: ctk.CTkFrame):
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(padx=16, pady=(0, 16))

    # ── Chart 2: Monthly change bars ──────────────────────────────────────────

    def _render_changes(self, snapshots: list[dict]):
        pal     = _palette()
        changes = [snapshots[i + 1]["total"] - snapshots[i]["total"]
                   for i in range(len(snapshots) - 1)]
        labels  = [_snap_label(s) for s in snapshots[1:]]
        x       = list(range(len(changes)))
        colors  = [pal["green"] if c >= 0 else pal["red"] for c in changes]

        fig = Figure(figsize=(_FIG_W, _FIG_H), dpi=100)
        ax  = fig.add_subplot(111)
        _apply_style(fig, ax, pal)

        ax.bar(x, changes, color=colors, width=0.6, zorder=3)
        ax.axhline(y=0, color=pal["spine"], linewidth=1)

        self._set_xticks(ax, labels, x)
        ax.margins(y=0.30)
        self._annotate_bars(ax, x, changes, pal)
        fig.tight_layout(pad=1.5)
        self._figures.append(fig)

        card = self._make_card("Monthly Net Worth Change")
        self._embed(fig, card)

    # ── Chart 3: Account Tracker ──────────────────────────────────────────────

    def _render_tracker(self, snapshots: list[dict]):
        self._tracker_snap_data = snapshots

        # Pre-load income data for all snapshots
        self._income_snap_data = [
            get_snapshot_income(s["year"], s["month"]) for s in snapshots
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

        if not all_accounts and not all_income:
            ctk.CTkLabel(
                ctrl, text="No accounts saved yet.", text_color="gray",
            ).pack(anchor="w", pady=(0, 8))
        else:
            if all_accounts:
                ctk.CTkLabel(
                    ctrl, text="Select accounts to chart:",
                    text_color="gray", font=ctk.CTkFont(size=12),
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
                    text_color="gray", font=ctk.CTkFont(size=12),
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
                text_color="gray", font=ctk.CTkFont(size=12),
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
            leg = ax.legend(fontsize=9, facecolor=pal["axes_bg"],
                            edgecolor=pal["spine"])
            for txt in leg.get_texts():
                txt.set_color(pal["text"])

        fig.tight_layout(pad=1.5)
        self._tracker_figure = fig
        self._figures.append(fig)

        canvas = FigureCanvasTkAgg(fig, master=self._tracker_chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack()
