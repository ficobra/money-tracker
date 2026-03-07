"""Portfolio tab — live position tracking via yfinance."""

import threading
from datetime import date, datetime, timedelta

import customtkinter as ctk

from database.db import (
    get_portfolio_positions,
    add_position,
    update_position,
    delete_position,
    get_portfolio_cache,
    upsert_portfolio_cache,
    get_portfolio_reminder,
    upsert_portfolio_reminder,
)
from utils import fmt_eur, open_dialog, unlock_scroll, bind_numeric_entry

# ── Theme palette ──────────────────────────────────────────────────────────────
_BG_CARD       = "#161f2e"
_BG_CARD_HOVER = "#1f2d42"
_ACCENT        = "#00b4d8"
_TEXT_PRI      = "#e6edf3"
_TEXT_SEC      = "#8b949e"
_BORDER        = "#2a3a52"
_BG_ELEM       = "#21262d"
_GREEN         = "#3fb950"
_RED           = "#f85149"
_F             = "Helvetica Neue"

_CURRENCIES = ["USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD"]

# Currency → symbol mapping for display
_CURR_SYM: dict[str, str] = {
    "EUR": "€", "USD": "$", "GBP": "£", "CHF": "Fr",
    "JPY": "¥", "CAD": "C$", "AUD": "A$",
}


# ── yfinance price fetcher (runs in background thread) ────────────────────────

def _fetch_prices(tickers: list[str]) -> dict[str, dict]:
    """Fetch current prices for each ticker. Returns {} on failure or missing dep."""
    if not tickers:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        return {}

    eur_rates: dict[str, float] = {}
    result: dict[str, dict] = {}

    for ticker in tickers:
        try:
            t_obj   = yf.Ticker(ticker)
            fi      = t_obj.fast_info
            price   = fi.last_price
            if price is None:
                continue
            currency   = (fi.currency or "USD").upper()
            prev_close = fi.previous_close or price
            day_change     = price - prev_close
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
                "price":          price,
                "price_eur":      price * eur_rate,
                "currency":       currency,
                "day_change":     day_change,
                "day_change_pct": day_change_pct,
                "eur_rate":       eur_rate,
                "name":           name,
            }
        except Exception:
            pass

    return result


# ── View ──────────────────────────────────────────────────────────────────────

class PortfolioView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._price_data: dict[str, dict] = {}
        self._using_cache: bool = False
        self._fetch_in_progress: bool = False
        self._last_updated: str = ""
        self._refresh_btn:    ctk.CTkButton | None = None
        self._status_lbl:     ctk.CTkLabel | None = None
        self._summary_frame:  ctk.CTkFrame | None = None
        self._positions_frame: ctk.CTkFrame | None = None
        self._reminder_banner: ctk.CTkFrame | None = None
        self._reminder_section: ctk.CTkFrame | None = None
        self._reminder_var:  ctk.StringVar | None = None
        self._reminder_menu: ctk.CTkOptionMenu | None = None
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        # Header: title + Refresh button
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(24, 2))
        hdr.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="Portfolio",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).grid(row=0, column=0, sticky="w")

        self._refresh_btn = ctk.CTkButton(
            hdr, text="↻", width=36,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            font=ctk.CTkFont(family=_F, size=18),
            command=self._refresh_prices,
        )
        self._refresh_btn.grid(row=0, column=1, sticky="e")

        self._status_lbl = ctk.CTkLabel(
            self, text="",
            text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=12),
        )
        self._status_lbl.pack(anchor="w", padx=24, pady=(0, 4))

        # Reminder banner — not pre-packed; shown dynamically in refresh()
        self._reminder_banner = ctk.CTkFrame(self, fg_color="transparent")

        self._summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._summary_frame.pack(fill="x", padx=24, pady=(0, 12))

        self._positions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._positions_frame.pack(fill="x", padx=24)

        # Action row: Add Position (left) + Set reminder dropdown (right)
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x", padx=24, pady=(16, 4))
        action_row.columnconfigure(0, weight=1)

        ctk.CTkButton(
            action_row, text="+ Add Position", width=140,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            font=ctk.CTkFont(family=_F, size=13),
            command=self._add_dialog,
        ).grid(row=0, column=0, sticky="w")

        self._reminder_var = ctk.StringVar(value="Set reminder ▾")
        self._reminder_menu = ctk.CTkOptionMenu(
            action_row,
            values=["In 1 year", "Custom..."],
            variable=self._reminder_var,
            command=self._on_set_reminder,
            fg_color=_BG_ELEM, button_color=_BG_ELEM,
            button_hover_color="#3d4d63",
            text_color=_TEXT_PRI,
            dropdown_fg_color="#1c2333",
            dropdown_text_color=_TEXT_PRI,
            dropdown_hover_color=_BORDER,
            font=ctk.CTkFont(family=_F, size=13),
            width=160,
        )
        self._reminder_menu.grid(row=0, column=1, sticky="e")

        # Reminder status line (populated by _render_reminder_status)
        self._reminder_section = ctk.CTkFrame(self, fg_color="transparent")
        self._reminder_section.pack(fill="x", padx=24, pady=(0, 32))

    # ── Rebalance reminder ────────────────────────────────────────────────────

    def _on_set_reminder(self, choice: str):
        if self._reminder_var:
            self._reminder_var.set("Set reminder ▾")
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
            self._reminder_custom_dialog()

    def _reminder_custom_dialog(self):
        today = date.today()
        try:
            default_date = today.replace(year=today.year + 1)
        except ValueError:
            default_date = today.replace(year=today.year + 1, day=28)

        dlg = open_dialog(self, 340, 170)
        dlg.title("Set Rebalance Reminder")

        inner = ctk.CTkFrame(dlg, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(
            inner, text="Reminder date (DD.MM.YYYY)",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
        ).pack(anchor="w", pady=(0, 6))

        date_var = ctk.StringVar(value=default_date.strftime("%d.%m.%Y"))
        ctk.CTkEntry(
            inner, textvariable=date_var, width=200,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
            font=ctk.CTkFont(family=_F, size=13),
        ).pack(anchor="w", pady=(0, 6))

        err_lbl = ctk.CTkLabel(inner, text="", text_color=_RED,
                               font=ctk.CTkFont(family=_F, size=12))
        err_lbl.pack(anchor="w", pady=(0, 6))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w")

        def _save():
            date_str = date_var.get().strip()
            try:
                datetime.strptime(date_str, "%d.%m.%Y")
            except ValueError:
                err_lbl.configure(text="Invalid date. Use DD.MM.YYYY")
                return
            upsert_portfolio_reminder(date_str, 1)
            dlg.destroy()

        ctk.CTkButton(
            btn_row, text="Save", width=90,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            font=ctk.CTkFont(family=_F, size=13),
            command=_save,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            font=ctk.CTkFont(family=_F, size=13),
            command=dlg.destroy,
        ).pack(side="left")

        dlg.wait_window()
        unlock_scroll()
        self._render_reminder_status()
        self._render_reminder_banner()

    def _render_reminder_status(self):
        if self._reminder_section is None:
            return
        for w in self._reminder_section.winfo_children():
            w.destroy()

        reminder = get_portfolio_reminder()
        if not reminder or not reminder["is_enabled"]:
            return
        try:
            rem_date = datetime.strptime(reminder["reminder_date"], "%d.%m.%Y").date()
        except ValueError:
            return

        today     = date.today()
        days_away = (rem_date - today).days
        if days_away < 0:
            text  = f"⚠ Rebalance overdue: {reminder['reminder_date']}"
            color = "#f0c040"
        elif days_away <= 30:
            text  = f"⚠ Rebalance due soon: {reminder['reminder_date']}  ({days_away} days)"
            color = "#f0c040"
        else:
            text  = f"Next rebalance: {reminder['reminder_date']}  ({days_away} days away)"
            color = _ACCENT

        row = ctk.CTkFrame(self._reminder_section, fg_color="transparent")
        row.pack(anchor="w", fill="x", pady=(4, 0))

        ctk.CTkLabel(
            row, text=text,
            text_color=color, font=ctk.CTkFont(family=_F, size=13),
            anchor="w",
        ).pack(side="left")

        def _clear_reminder():
            dlg = open_dialog(self, 380, 150)
            dlg.title("Remove Reminder")

            ctk.CTkLabel(
                dlg, text="Remove this rebalance reminder?",
                text_color=_TEXT_PRI, font=ctk.CTkFont(family=_F, size=14),
            ).pack(pady=(24, 6))
            ctk.CTkLabel(
                dlg, text="The saved date will be cleared.",
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            ).pack(pady=(0, 16))

            confirmed = [False]

            btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
            btn_row.pack()

            def _confirm():
                confirmed[0] = True
                dlg.destroy()

            ctk.CTkButton(
                btn_row, text="Remove", width=100,
                fg_color=_RED, hover_color="#c0392b", text_color="white",
                corner_radius=8, font=ctk.CTkFont(family=_F, size=13),
                command=_confirm,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                btn_row, text="Cancel", width=100,
                fg_color=_BG_ELEM, hover_color="#3d4d63", text_color=_TEXT_PRI,
                corner_radius=8, font=ctk.CTkFont(family=_F, size=13),
                command=dlg.destroy,
            ).pack(side="left")

            dlg.wait_window()
            unlock_scroll()

            if confirmed[0]:
                upsert_portfolio_reminder(reminder["reminder_date"], 0)
                self._render_reminder_status()
                self._render_reminder_banner()

        ctk.CTkButton(
            row, text="×", width=24, height=24,
            fg_color="transparent", hover_color="#3d1a1a",
            text_color=_TEXT_SEC, corner_radius=6,
            font=ctk.CTkFont(family=_F, size=14),
            command=_clear_reminder,
        ).pack(side="left", padx=(8, 0))

    def _render_reminder_banner(self):
        if self._reminder_banner is None:
            return
        for w in self._reminder_banner.winfo_children():
            w.destroy()
        if self._reminder_banner.winfo_manager():
            self._reminder_banner.pack_forget()

        reminder = get_portfolio_reminder()
        if not reminder or not reminder["is_enabled"]:
            return
        try:
            rem_date = datetime.strptime(reminder["reminder_date"], "%d.%m.%Y").date()
        except ValueError:
            return

        days_away = (rem_date - date.today()).days
        if days_away > 30:
            return

        banner_inner = ctk.CTkFrame(
            self._reminder_banner,
            fg_color=("#FFF3CD", "#3D2F00"),
            corner_radius=8,
        )
        banner_inner.pack(fill="x")
        row = ctk.CTkFrame(banner_inner, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=10)

        msg = (
            f"⚠ Portfolio rebalance overdue: {reminder['reminder_date']}"
            if days_away < 0
            else f"⚠ Portfolio rebalance due in {days_away} day{'s' if days_away != 1 else ''}: {reminder['reminder_date']}"
        )
        ctk.CTkLabel(
            row, text=msg,
            font=ctk.CTkFont(family=_F, size=13),
            text_color=("#7D5000", "#f0c040"),
        ).pack(side="left")

        self._reminder_banner.pack(fill="x", padx=24, pady=(0, 8),
                                   before=self._summary_frame)

    # ── Refresh (called by main show_view) ────────────────────────────────────

    def refresh(self):
        self._render_reminder_banner()
        self._render_reminder_status()
        self._render_all()
        if not self._price_data and not self._fetch_in_progress:
            self._refresh_prices()

    # ── Background price fetch ────────────────────────────────────────────────

    def _refresh_prices(self):
        if self._fetch_in_progress:
            return
        self._fetch_in_progress = True
        if self._refresh_btn:
            self._refresh_btn.configure(state="disabled", text="·")
        self._set_status("Fetching live prices…", _TEXT_SEC)

        positions = get_portfolio_positions()
        tickers   = [p["ticker"] for p in positions]

        def do_fetch():
            data = _fetch_prices(tickers)
            if data:
                self._price_data  = data
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
                        currency  = (v["currency"] or "USD").upper()
                        price_eur = v.get("price_eur") or v["price"]
                        eur_rate  = (price_eur / v["price"]) if v["price"] else 1.0
                        self._price_data[ticker] = {
                            "price":          v["price"],
                            "price_eur":      price_eur,
                            "currency":       currency,
                            "day_change":     v["day_change"],
                            "day_change_pct": v["day_change_pct"],
                            "eur_rate":       eur_rate,
                            "name":           v["name"],
                        }
                    self._using_cache = True
            self._fetch_in_progress = False
            self.after(0, self._on_fetch_done)

        threading.Thread(target=do_fetch, daemon=True).start()

    def _on_fetch_done(self):
        if self._refresh_btn:
            self._refresh_btn.configure(state="normal", text="↻")
        self._render_all()
        if not self._using_cache:
            self._set_status("Prices updated", _GREEN)
            self.after(3000, self._update_status)

    # ── Render ────────────────────────────────────────────────────────────────

    def _render_all(self):
        self._render_summary()
        self._render_positions()
        self._update_status()

    def _update_status(self):
        if self._status_lbl is None:
            return
        if self._fetch_in_progress:
            self._set_status("Fetching live prices…", _TEXT_SEC)
        elif self._using_cache:
            self._set_status("Using cached prices (live fetch failed)", "#FFC107")
        elif self._last_updated:
            self._set_status(f"Last updated: {self._last_updated}", _TEXT_SEC)
        else:
            self._set_status("", _TEXT_SEC)

    def _set_status(self, text: str, color: str):
        if self._status_lbl:
            self._status_lbl.configure(text=text, text_color=color)

    def _render_summary(self):
        if self._summary_frame is None:
            return
        for w in self._summary_frame.winfo_children():
            w.destroy()

        positions = get_portfolio_positions()
        if not positions:
            return

        total_value_eur = 0.0
        total_cost_eur  = 0.0
        any_price       = False

        for p in positions:
            ticker = p["ticker"]
            if ticker in self._price_data:
                d = self._price_data[ticker]
                total_value_eur += p["shares"] * d["price_eur"]
                total_cost_eur  += p["shares"] * p["avg_buy_price"] * d.get("eur_rate", 1.0)
                any_price = True

        pnl   = total_value_eur - total_cost_eur
        pct   = (pnl / total_cost_eur * 100) if total_cost_eur else 0.0
        color = _GREEN if pnl >= 0 else _RED
        sign  = "+" if pnl >= 0 else ""

        card  = ctk.CTkFrame(self._summary_frame, fg_color=_BG_CARD, corner_radius=14,
                             border_width=1, border_color=_BORDER)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner, text="PORTFOLIO", text_color=_TEXT_SEC,
                     font=ctk.CTkFont(family=_F, size=11)).pack(anchor="w")
        if any_price:
            ctk.CTkLabel(inner, text=fmt_eur(total_value_eur), text_color=_TEXT_PRI,
                         font=ctk.CTkFont(family=_F, size=28, weight="bold")).pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(
                inner,
                text=f"Total P&L: {fmt_eur(pnl)}  ({sign}{pct:.1f}%)",
                text_color=color, font=ctk.CTkFont(family=_F, size=13),
            ).pack(anchor="w")
        else:
            ctk.CTkLabel(inner, text="—", text_color=_TEXT_PRI,
                         font=ctk.CTkFont(family=_F, size=28, weight="bold")).pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(inner, text="Fetching prices…", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=13)).pack(anchor="w")

    def _render_positions(self):
        if self._positions_frame is None:
            return
        for w in self._positions_frame.winfo_children():
            w.destroy()

        positions = get_portfolio_positions()
        if not positions:
            ctk.CTkLabel(
                self._positions_frame,
                text="No positions added yet. Click + Add Position to get started.",
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
            ).pack(anchor="w", pady=8)
            return

        grid = ctk.CTkFrame(self._positions_frame, fg_color="transparent")
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        for i, pos in enumerate(positions):
            row  = i // 2
            col  = i % 2
            padx = (0, 6) if col == 0 else (6, 0)
            self._make_position_card(grid, pos, row, col, padx)

    def _make_position_card(self, parent, pos: dict, row: int, col: int, padx):
        ticker = pos["ticker"]
        d      = self._price_data.get(ticker)

        card  = ctk.CTkFrame(parent, fg_color=_BG_CARD, corner_radius=14,
                             border_width=1, border_color=_BORDER)
        card.grid(row=row, column=col, sticky="nsew", padx=padx, pady=(0, 12))
        card.bind("<Enter>", lambda e, c=card: c.configure(fg_color=_BG_CARD_HOVER))
        card.bind("<Leave>", lambda e, c=card: c.configure(fg_color=_BG_CARD))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        # Header: ticker + action buttons
        hdr = ctk.CTkFrame(inner, fg_color="transparent")
        hdr.pack(fill="x")
        hdr.columnconfigure(0, weight=1)

        tick_col = ctk.CTkFrame(hdr, fg_color="transparent")
        tick_col.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            tick_col, text=ticker,
            font=ctk.CTkFont(family=_F, size=16, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w")

        name_str = (d["name"] if d and d.get("name") else "") or ""
        if name_str:
            ctk.CTkLabel(inner, text=name_str, text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=11)).pack(anchor="w", pady=(2, 8))
        else:
            ctk.CTkFrame(inner, height=6, fg_color="transparent").pack()

        btn_col = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_col.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            btn_col, text="Edit", width=50, height=26,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_SEC, corner_radius=6,
            font=ctk.CTkFont(family=_F, size=11),
            command=lambda p=pos: self._edit_dialog(p),
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_col, text="×", width=28, height=26,
            fg_color="transparent", hover_color="#3d1a1a",
            text_color=_RED, corner_radius=6,
            font=ctk.CTkFont(family=_F, size=13, weight="bold"),
            command=lambda pid=pos["id"]: self._delete_confirm(pid),
        ).pack(side="left")

        if d:
            sym      = _CURR_SYM.get(d["currency"], d["currency"])
            price_str = f"{sym}{d['price']:,.2f} {d['currency']}"
            if d["currency"] != "EUR":
                price_str += f"   {fmt_eur(d['price_eur'])}"
            ctk.CTkLabel(inner, text=price_str, text_color=_TEXT_PRI,
                         font=ctk.CTkFont(family=_F, size=14, weight="bold")).pack(anchor="w")

            dc    = d.get("day_change") or 0.0
            dp    = d.get("day_change_pct") or 0.0
            dc_eur = dc * d.get("eur_rate", 1.0)
            sign  = "+" if dc >= 0 else ""
            dc_color = _GREEN if dc >= 0 else _RED
            ctk.CTkLabel(
                inner,
                text=f"{sign}{dc_eur:.2f} EUR  ({sign}{dp:.2f}%) today",
                text_color=dc_color, font=ctk.CTkFont(family=_F, size=12),
            ).pack(anchor="w", pady=(2, 8))

            cur_val  = pos["shares"] * d["price_eur"]
            cost_val = pos["shares"] * pos["avg_buy_price"] * d.get("eur_rate", 1.0)
            pnl      = cur_val - cost_val
            pnl_pct  = (pnl / cost_val * 100) if cost_val else 0.0
            pnl_col  = _GREEN if pnl >= 0 else _RED
            sign_p   = "+" if pnl >= 0 else ""

            def _row(label: str, value: str, color: str = _TEXT_PRI):
                r = ctk.CTkFrame(inner, fg_color="transparent")
                r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=label, text_color=_TEXT_SEC,
                             font=ctk.CTkFont(family=_F, size=12)).pack(side="left")
                ctk.CTkLabel(r, text=value, text_color=color,
                             font=ctk.CTkFont(family=_F, size=12)).pack(side="right")

            _row("Shares",        f"{pos['shares']:g}")
            _row("Current value", fmt_eur(cur_val))
            _row("P&L",           f"{fmt_eur(pnl)}  ({sign_p}{pnl_pct:.1f}%)", pnl_col)
        else:
            ctk.CTkLabel(inner, text="Fetching price…", text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=13)).pack(anchor="w", pady=4)
            avg_sym = _CURR_SYM.get(pos["currency"], pos["currency"])
            ctk.CTkLabel(
                inner,
                text=f"{pos['shares']:g} shares · avg {avg_sym}{pos['avg_buy_price']:,.2f}",
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            ).pack(anchor="w")

    # ── Position dialogs ──────────────────────────────────────────────────────

    def _add_dialog(self):
        self._position_dialog(None)

    def _edit_dialog(self, pos: dict):
        self._position_dialog(pos)

    def _position_dialog(self, pos: dict | None):
        is_edit = pos is not None
        dlg = open_dialog(self, 460, 350 if not is_edit else 310)
        dlg.title("Edit Position" if is_edit else "Add Position")

        inner = ctk.CTkFrame(dlg, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(
            inner,
            text="Edit Position" if is_edit else "Add Position",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", pady=(0, 10))

        def field_row(label: str, var: ctk.StringVar, placeholder: str = ""):
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=3)
            r.columnconfigure(1, weight=1)
            ctk.CTkLabel(r, text=label, width=140, anchor="w",
                         text_color=_TEXT_SEC,
                         font=ctk.CTkFont(family=_F, size=13)).grid(row=0, column=0, sticky="w")
            e = ctk.CTkEntry(r, textvariable=var, placeholder_text=placeholder,
                             fg_color=_BG_ELEM, border_color=_BORDER,
                             text_color=_TEXT_PRI, font=ctk.CTkFont(family=_F, size=13))
            e.grid(row=0, column=1, sticky="ew")
            return e

        ticker_var = ctk.StringVar(value=pos["ticker"] if is_edit else "")
        shares_var = ctk.StringVar(value=str(pos["shares"]) if is_edit else "")
        avg_var    = ctk.StringVar(value=str(pos["avg_buy_price"]) if is_edit else "")
        notes_var  = ctk.StringVar(value=(pos.get("notes") or "") if is_edit else "")

        te = field_row("Ticker", ticker_var, "e.g. AAPL")
        if is_edit:
            te.configure(state="disabled")
        else:
            ctk.CTkLabel(
                inner,
                text="Include exchange suffix for non-US stocks.\n"
                     "Examples: VWCE.DE (Xetra), VOO (NYSE), AAPL (NASDAQ)",
                text_color=_TEXT_SEC,
                font=ctk.CTkFont(family=_F, size=11),
                justify="left",
                wraplength=280,
            ).pack(anchor="w", padx=(140, 0), pady=(0, 4))

        bind_numeric_entry(field_row("Shares", shares_var, "e.g. 10"))
        bind_numeric_entry(field_row("Avg Buy Price", avg_var, "e.g. 150.00"))

        # Currency dropdown
        cr = ctk.CTkFrame(inner, fg_color="transparent")
        cr.pack(fill="x", pady=3)
        cr.columnconfigure(1, weight=1)
        ctk.CTkLabel(cr, text="Currency", width=140, anchor="w",
                     text_color=_TEXT_SEC,
                     font=ctk.CTkFont(family=_F, size=13)).grid(row=0, column=0, sticky="w")
        curr_var = ctk.StringVar(value=(pos.get("currency") or "USD") if is_edit else "USD")
        ctk.CTkOptionMenu(
            cr, values=_CURRENCIES, variable=curr_var,
            fg_color=_BG_ELEM, button_color=_BG_ELEM, button_hover_color="#3d4d63",
            text_color=_TEXT_PRI, font=ctk.CTkFont(family=_F, size=13),
        ).grid(row=0, column=1, sticky="w")

        field_row("Notes (optional)", notes_var, "")

        err_lbl = ctk.CTkLabel(inner, text="", text_color=_RED,
                               font=ctk.CTkFont(family=_F, size=12))
        err_lbl.pack(anchor="w", pady=(4, 0))

        btn_row  = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(6, 0))
        save_btn   = [None]
        cancel_btn = [None]

        def _commit(ticker, shares, avg):
            if is_edit:
                update_position(pos["id"], ticker, shares, avg,
                                curr_var.get(), notes_var.get().strip())
            else:
                add_position(ticker, shares, avg, curr_var.get(), notes_var.get().strip())
            dlg.destroy()

        def _set_busy(busy: bool):
            state = "disabled" if busy else "normal"
            if save_btn[0]:
                save_btn[0].configure(
                    state=state, text="Checking…" if busy else "Save"
                )
            if cancel_btn[0]:
                cancel_btn[0].configure(state=state)

        def on_validate_done(valid: bool, ticker: str, shares: float, avg: float):
            if not dlg.winfo_exists():
                return
            _set_busy(False)
            if valid:
                _commit(ticker, shares, avg)
            else:
                err_lbl.configure(
                    text="Ticker not found. Please check the symbol and\n"
                         "exchange suffix (e.g. VWCE.DE not VWCE)"
                )

        def on_save():
            ticker = ticker_var.get().strip().upper()
            if not ticker:
                err_lbl.configure(text="Ticker is required.")
                return
            try:
                shares = float(shares_var.get().strip())
                if shares <= 0:
                    raise ValueError
            except ValueError:
                err_lbl.configure(text="Shares must be a positive number.")
                return
            try:
                avg = float(avg_var.get().strip())
                if avg < 0:
                    raise ValueError
            except ValueError:
                err_lbl.configure(text="Avg buy price must be ≥ 0.")
                return
            if is_edit:
                _commit(ticker, shares, avg)
                return
            # New position: validate ticker exists in yfinance
            err_lbl.configure(text="")
            _set_busy(True)

            def do_validate():
                valid = False
                try:
                    import yfinance as yf
                    valid = yf.Ticker(ticker).fast_info.last_price is not None
                except Exception:
                    pass
                dlg.after(0, lambda: on_validate_done(valid, ticker, shares, avg))

            threading.Thread(target=do_validate, daemon=True).start()

        sb = ctk.CTkButton(btn_row, text="Save", width=100,
                           fg_color=_ACCENT, hover_color="#0096b4",
                           text_color="white", corner_radius=8,
                           command=on_save)
        sb.pack(side="left", padx=(0, 8))
        save_btn[0] = sb

        cb = ctk.CTkButton(btn_row, text="Cancel", width=80,
                           fg_color=_BG_ELEM, hover_color="#3d4d63",
                           text_color=_TEXT_PRI, corner_radius=8,
                           command=dlg.destroy)
        cb.pack(side="left")
        cancel_btn[0] = cb

        dlg.wait_window()
        unlock_scroll()
        self._render_all()

    def _delete_confirm(self, position_id: int):
        dlg = open_dialog(self, 400, 140)
        dlg.title("Delete Position")
        ctk.CTkLabel(
            dlg,
            text="Are you sure you want to delete this position?",
            wraplength=360, justify="left",
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_PRI,
        ).pack(padx=20, pady=(20, 12))
        btn_row   = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack()
        confirmed = [False]
        ctk.CTkButton(
            btn_row, text="Delete", width=90,
            fg_color=_RED, hover_color="#c0392b",
            text_color="white", corner_radius=8,
            command=lambda: [confirmed.__setitem__(0, True), dlg.destroy()],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=dlg.destroy,
        ).pack(side="left")
        dlg.wait_window()
        unlock_scroll()
        if confirmed[0]:
            delete_position(position_id)
            self._render_all()
