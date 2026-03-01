import calendar
import customtkinter as ctk
from datetime import date

from database.db import (
    get_snapshot,
    save_snapshot,
    delete_snapshot,
    get_all_expenses,
    get_all_accounts,
    get_all_accounts_with_flags,
    set_account_investment,
    get_all_income,
    get_snapshot_income,
    set_snapshot_income,
    get_setting,
    set_setting,
)
from utils import fmt_eur, fmt_eur_signed, center_on_parent, effective_charge_day

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

_DEFAULT_ACCOUNTS = ["Main Bank Account", "Revolut", "Cash", "Flatex"]
_GREEN = "#2CC985"
_RED   = "#E74C3C"


class SnapshotEntryView(ctk.CTkScrollableFrame):
    # Class variable: set by Dashboard "Go to Snapshot" button to pre-select a period
    _pending_period: tuple[int, int] | None = None

    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._rows: list[dict] = []
        self._editing_buffer                          = False
        self._editing_accounts                        = False
        self._edit_accounts_btn: ctk.CTkButton | None = None
        self._delete_snap_btn:   ctk.CTkButton | None = None
        self._include_estimation_var = ctk.BooleanVar(value=False)
        self._est_eom_label: ctk.CTkLabel | None = None
        self._est_total_cost: float = 0.0
        # income_id -> StringVar for actual amount entered this month
        self._income_amount_vars: dict[int, ctk.StringVar] = {}
        self._build()

    # ── Refresh (called by main.py when navigating to this view) ──────────────

    def refresh(self):
        pending = SnapshotEntryView._pending_period
        if pending:
            SnapshotEntryView._pending_period = None
            self._year_var.set(str(pending[0]))
            self._month_var.set(MONTHS[pending[1] - 1])
            self._load_existing()
        # else: preserve current state

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        today = date.today()

        ctk.CTkLabel(
            self, text="Monthly Snapshot",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Enter end-of-month balances. Accounts are fully dynamic — add or remove as needed.",
            text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # Period selector card
        period_card = ctk.CTkFrame(self)
        period_card.pack(fill="x", padx=24, pady=(0, 24))
        period_row = ctk.CTkFrame(period_card, fg_color="transparent")
        period_row.pack(anchor="w", padx=16, pady=14)

        ctk.CTkLabel(period_row, text="Period:", width=56, anchor="w").pack(side="left")

        self._month_var = ctk.StringVar(value=MONTHS[today.month - 1])
        ctk.CTkOptionMenu(
            period_row, values=MONTHS, variable=self._month_var,
            width=150, command=self._on_period_change,
        ).pack(side="left", padx=(0, 8))

        self._year_var = ctk.StringVar(value=str(today.year))
        year_entry = ctk.CTkEntry(period_row, textvariable=self._year_var, width=80)
        year_entry.pack(side="left")
        year_entry.bind("<Return>",   self._on_period_change)
        year_entry.bind("<FocusOut>", self._on_period_change)

        # Column headers
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkLabel(
            header_row, text="Account",
            width=300, anchor="w", text_color="gray",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            header_row, text="Balance (EUR)",
            width=150, anchor="w", text_color="gray",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        # Account rows container
        self._rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rows_frame.pack(anchor="w", padx=24, fill="x")

        # Add Account + Edit Accounts buttons
        add_btn_row = ctk.CTkFrame(self, fg_color="transparent")
        add_btn_row.pack(anchor="w", padx=24, pady=(10, 0))
        ctk.CTkButton(
            add_btn_row, text="+ Add Account",
            fg_color="transparent", border_width=1, width=140,
            command=self._add_account_and_edit,
        ).pack(side="left", padx=(0, 8))
        self._edit_accounts_btn = ctk.CTkButton(
            add_btn_row, text="Edit Accounts", width=130,
            fg_color="transparent", border_width=1,
            command=self._toggle_account_editing,
        )
        self._edit_accounts_btn.pack(side="left")

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(20, 12)
        )

        # Net worth totals
        total_row = ctk.CTkFrame(self, fg_color="transparent")
        total_row.pack(anchor="w", padx=24, pady=(0, 2))
        ctk.CTkLabel(
            total_row, text="Net Worth (excl. investments):",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        self._total_label = ctk.CTkLabel(
            total_row, text="€0,00",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._total_label.pack(side="left")

        # Investment total (shown when any investment account has a balance)
        inv_total_row = ctk.CTkFrame(self, fg_color="transparent")
        inv_total_row.pack(anchor="w", padx=24, pady=(0, 2))
        ctk.CTkLabel(
            inv_total_row, text="Investment Portfolio:",
            font=ctk.CTkFont(size=13), text_color="gray",
        ).pack(side="left", padx=(0, 10))
        self._inv_total_label = ctk.CTkLabel(
            inv_total_row, text="",
            font=ctk.CTkFont(size=13), text_color="gray",
        )
        self._inv_total_label.pack(side="left")

        # Adjusted net worth (shown when estimation checkbox is ticked)
        adj_row = ctk.CTkFrame(self, fg_color="transparent")
        adj_row.pack(anchor="w", padx=24, pady=(0, 16))
        ctk.CTkLabel(
            adj_row, text="Adjusted (est. remaining spend deducted):",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))
        self._adjusted_label = ctk.CTkLabel(
            adj_row, text="",
            font=ctk.CTkFont(size=12), text_color="gray",
        )
        self._adjusted_label.pack(side="left")

        # Income this month (Seasonal + Variable income sources)
        self._income_container = ctk.CTkFrame(self, fg_color="transparent")
        self._income_container.pack(fill="x", padx=24, pady=(0, 8))

        # Save + status
        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkButton(save_row, text="Save Snapshot", width=140, command=self._save).pack(
            side="left", padx=(0, 16)
        )
        self._status_label = ctk.CTkLabel(save_row, text="")
        self._status_label.pack(side="left")

        # Delete snapshot button (shown only when a snapshot exists for the period)
        del_row = ctk.CTkFrame(self, fg_color="transparent")
        del_row.pack(anchor="w", padx=24, pady=(0, 0))
        self._delete_snap_btn = ctk.CTkButton(
            del_row, text="Delete Snapshot", width=140,
            fg_color="transparent", border_width=1,
            text_color=_RED,
            hover_color=("gray85", "gray20"),
            command=self._delete_snapshot,
        )
        # Initially hidden; shown from _load_existing when snapshot exists

        # Mid-month estimation (rebuilt when period or buffer changes)
        self._estimation_container = ctk.CTkFrame(self, fg_color="transparent")
        self._estimation_container.pack(fill="x", padx=24, pady=(8, 32))

        self._load_existing()

    # ── Account rows ──────────────────────────────────────────────────────────

    def _add_row(
        self,
        name: str = "",
        balance: str = "",
        is_investment: bool = False,
    ) -> dict:
        row_frame = ctk.CTkFrame(self._rows_frame, fg_color="transparent")
        row_frame.pack(anchor="w", pady=3, fill="x")

        name_var          = ctk.StringVar(value=name)
        balance_var       = ctk.StringVar(value=balance)
        is_investment_var = ctk.BooleanVar(value=is_investment)

        balance_var.trace_add("write", lambda *_: self._update_total())

        name_container = ctk.CTkFrame(row_frame, fg_color="transparent", corner_radius=0)
        name_container.pack(side="left", padx=(0, 8))

        ctk.CTkEntry(
            row_frame, textvariable=balance_var,
            placeholder_text="0.00", width=150,
        ).pack(side="left", padx=(0, 8))

        # Edit-mode controls container — packed/unpacked dynamically by _refresh_edit_controls
        edit_controls = ctk.CTkFrame(row_frame, fg_color="transparent", corner_radius=0)

        row = {
            "frame":             row_frame,
            "name_container":    name_container,
            "name_var":          name_var,
            "balance_var":       balance_var,
            "is_investment_var": is_investment_var,
            "edit_controls":     edit_controls,
        }

        self._rows.append(row)
        self._refresh_name_widget(row)
        self._refresh_edit_controls(row)
        return row

    def _refresh_name_widget(self, row: dict):
        for w in row["name_container"].winfo_children():
            w.destroy()
        if self._editing_accounts:
            ctk.CTkEntry(
                row["name_container"], textvariable=row["name_var"],
                placeholder_text="Account name", width=300,
            ).pack(side="left")
        else:
            display_name = row["name_var"].get() or "Unnamed"
            ctk.CTkLabel(
                row["name_container"], text=display_name,
                anchor="w", width=300,
            ).pack(side="left")

    def _refresh_edit_controls(self, row: dict):
        for w in row["edit_controls"].winfo_children():
            w.destroy()
        if self._editing_accounts:
            ctk.CTkCheckBox(
                row["edit_controls"],
                text="INV",
                variable=row["is_investment_var"],
                command=lambda r=row: self._update_total(),
                width=60,
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                row["edit_controls"], text="×", width=36, height=36,
                fg_color="transparent", border_width=1,
                text_color=("gray40", "gray60"),
                hover_color=("gray85", "gray25"),
                command=lambda r=row: self._remove_row(r),
            ).pack(side="left")
            if row["edit_controls"].winfo_manager() != "pack":
                row["edit_controls"].pack(side="left")
        else:
            if row["edit_controls"].winfo_manager() == "pack":
                row["edit_controls"].pack_forget()

    def _toggle_account_editing(self):
        self._editing_accounts = not self._editing_accounts
        if self._edit_accounts_btn:
            self._edit_accounts_btn.configure(
                text="Done" if self._editing_accounts else "Edit Accounts"
            )
        for row in self._rows:
            self._refresh_name_widget(row)
            self._refresh_edit_controls(row)

    def _add_account_and_edit(self):
        if not self._editing_accounts:
            self._editing_accounts = True
            if self._edit_accounts_btn:
                self._edit_accounts_btn.configure(text="Done")
            for row in self._rows:
                self._refresh_name_widget(row)
                self._refresh_edit_controls(row)
        self._add_row()

    def _remove_row(self, row: dict):
        name = row["name_var"].get().strip() or "this account"
        if not self._confirm_dialog(
            f'Remove "{name}" from this snapshot?',
            confirm_text="Remove",
        ):
            return
        row["frame"].destroy()
        self._rows.remove(row)
        self._update_total()

    def _clear_rows(self):
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()

    # ── Period handling ───────────────────────────────────────────────────────

    def _on_period_change(self, *_):
        self._load_existing()

    def _get_period(self) -> tuple[int, int] | None:
        try:
            year  = int(self._year_var.get())
            month = MONTHS.index(self._month_var.get()) + 1
            return year, month
        except (ValueError, IndexError):
            return None

    def _load_existing(self, *_):
        period = self._get_period()
        if period is None:
            return
        year, month = period

        # Reset edit mode BEFORE creating rows so checkboxes/× stay hidden
        self._editing_accounts = False
        if self._edit_accounts_btn:
            self._edit_accounts_btn.configure(text="Edit Accounts")

        existing  = get_snapshot(year, month)
        acc_flags = {a["name"]: a["is_investment"] for a in get_all_accounts_with_flags()}

        self._clear_rows()

        if existing:
            for name, balance in existing.items():
                is_inv = acc_flags.get(name, False)
                self._add_row(name, f"{balance:.2f}", is_inv)
            self._set_status(
                f"Showing saved data for {MONTHS[month - 1]} {year}. Edit fields and re-save to update.",
                color="gray",
            )
            self._delete_snap_btn.pack(side="left")
        else:
            today = date.today()
            if year > today.year or (year == today.year and month >= today.month):
                known = get_all_accounts()
                accounts_to_use = known if known else _DEFAULT_ACCOUNTS
            else:
                accounts_to_use = _DEFAULT_ACCOUNTS
            for name in accounts_to_use:
                is_inv = acc_flags.get(name, False)
                self._add_row(name, is_investment=is_inv)
            self._set_status("")
            self._delete_snap_btn.pack_forget()

        self._update_total()
        self._editing_buffer = False
        self._render_income_section()
        self._render_estimation()

    # ── Income this month ─────────────────────────────────────────────────────

    def _render_income_section(self):
        for w in self._income_container.winfo_children():
            w.destroy()
        self._income_amount_vars.clear()

        period = self._get_period()
        if period is None:
            return
        year, month = period

        all_income = list(get_all_income())
        # Show income sources active in this month
        # active_months NULL or empty = active every month
        relevant: list[dict] = []
        for item in all_income:
            item = dict(item)
            active_str = item.get("active_months") or ""
            if not active_str.strip():
                relevant.append(item)
            else:
                active = {int(x) for x in active_str.split(",") if x.strip().isdigit()}
                if month in active:
                    relevant.append(item)

        if not relevant:
            return

        # Load previously saved amounts for this period
        saved = get_snapshot_income(year, month)

        card  = ctk.CTkFrame(self._income_container)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            inner, text="INCOME THIS MONTH",
            text_color="gray", font=ctk.CTkFont(size=11),
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Enter the actual amount received for each income source below.",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(2, 10))

        for item in relevant:
            iid       = item["id"]
            saved_val = saved.get(iid)
            default   = f"{saved_val:.2f}" if saved_val is not None else f"{item['amount']:.2f}"

            var = ctk.StringVar(value=default)
            self._income_amount_vars[iid] = var

            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=item["name"], width=300, anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(row, text="EUR", anchor="w").pack(side="left", padx=(0, 4))
            ctk.CTkEntry(row, textvariable=var, width=110).pack(side="left")

    # ── Totals ────────────────────────────────────────────────────────────────

    def _update_total(self):
        net_worth  = 0.0
        inv_total  = 0.0
        for row in self._rows:
            try:
                val = float(row["balance_var"].get())
            except ValueError:
                val = 0.0
            if row["is_investment_var"].get():
                inv_total += val
            else:
                net_worth += val
        self._total_label.configure(text=fmt_eur(net_worth))
        if inv_total > 0:
            self._inv_total_label.configure(text=fmt_eur(inv_total))
        else:
            self._inv_total_label.configure(text="")
        self._update_estimation_values(net_worth)

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self):
        period = self._get_period()
        if period is None:
            self._set_status("Invalid year.", color="#E74C3C")
            return
        year, month = period

        today = date.today()
        if year > today.year or (year == today.year and month > today.month):
            if not self._confirm_dialog(
                f"You are entering data for a future month ({MONTHS[month - 1]} {year}). "
                "This month has not started yet. Do you want to continue?",
                confirm_text="Continue",
            ):
                return

        balances:         dict[str, float] = {}
        investment_flags: dict[str, bool]  = {}

        for row in self._rows:
            name = row["name_var"].get().strip()
            if not name:
                self._set_status("Account name cannot be empty.", color="#E74C3C")
                return
            try:
                balance = float(row["balance_var"].get().strip() or "0")
            except ValueError:
                self._set_status(f'Invalid balance for "{name}".', color="#E74C3C")
                return
            balances[name] = balance
            investment_flags[name] = row["is_investment_var"].get()

        if not balances:
            self._set_status("Add at least one account before saving.", color="#E74C3C")
            return

        total_snapshots = save_snapshot(year, month, balances)
        for name, is_inv in investment_flags.items():
            set_account_investment(name, is_inv)

        # Save actual income amounts for seasonal/variable sources
        for income_id, var in self._income_amount_vars.items():
            try:
                amount = float(var.get().strip() or "0")
                set_snapshot_income(year, month, income_id, amount)
            except ValueError:
                pass

        month_name = MONTHS[month - 1]

        if total_snapshots == 1:
            self._set_status(
                f"Snapshot saved for {month_name} {year}."
                "  Add next month's data to see your first net worth change.",
                color="#2CC985",
            )
        else:
            net_worth = sum(v for name, v in balances.items() if not investment_flags.get(name))
            self._set_status(
                f"Snapshot saved for {month_name} {year}.  Net Worth: {fmt_eur(net_worth)}",
                color="#2CC985",
            )

        self._delete_snap_btn.pack(side="left")
        self._update_total()
        self._render_estimation()
        self._maybe_show_deduction_dialog(year, month, balances, investment_flags)

    # ── Delete Snapshot ───────────────────────────────────────────────────────

    def _delete_snapshot(self):
        period = self._get_period()
        if period is None:
            return
        year, month = period
        month_name = MONTHS[month - 1]
        if not self._confirm_dialog(
            f"Delete snapshot for {month_name} {year}? This cannot be undone.",
            confirm_text="Delete",
        ):
            return
        delete_snapshot(year, month)
        self._load_existing()
        self._set_status(f"Snapshot for {month_name} {year} deleted.", color="gray")

    # ── Mid-month estimation ──────────────────────────────────────────────────

    def _render_estimation(self):
        for w in self._estimation_container.winfo_children():
            w.destroy()
        self._est_eom_label  = None
        self._est_total_cost = 0.0
        self._adjusted_label.configure(text="")

        period = self._get_period()
        if period is None:
            return
        year, month = period

        today = date.today()
        if year != today.year or month != today.month:
            return

        last_day = calendar.monthrange(year, month)[1]
        if today.day >= last_day:
            return

        if get_snapshot(year, month) is not None:
            return

        daily_buffer   = float(get_setting("daily_buffer") or "20.0")
        remaining_days = last_day - today.day
        expenses       = list(get_all_expenses())

        all_fx               = list(expenses)
        fx_total             = sum(e["amount"] for e in all_fx)
        buffer_cost          = remaining_days * daily_buffer
        self._est_total_cost = buffer_cost + fx_total

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
            text=f"{remaining_days} days remaining in {MONTHS[today.month - 1]}",
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
                          command=lambda v=buf_var: self._save_buffer(v),
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

        est_row(f"Buffer cost  ({remaining_days} days × €{daily_buffer:.0f}/day)",
                f"–{fmt_eur(buffer_cost)}", _RED)

        expenses_hdr = ctk.CTkFrame(inner, fg_color="transparent")
        expenses_hdr.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(expenses_hdr,
                     text=f"Fixed expenses this month  ({len(all_fx)} items)",
                     anchor="w", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(expenses_hdr, text=f"–{fmt_eur(fx_total)}",
                     anchor="e", text_color=_RED,
                     font=ctk.CTkFont(size=12)).pack(side="right")

        for e in all_fx:
            d     = e["day_of_month"]
            eff_d = effective_charge_day(today.year, today.month, d, last_day)
            day_label = "end of month" if (d == 31 and last_day < 31) else f"day {eff_d}"
            est_row(f"  · {e['name']}  ({day_label})",
                    f"–{fmt_eur(e['amount'])}", _RED, small=True)

        ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(8, 8)
        )

        eom_row = ctk.CTkFrame(inner, fg_color="transparent")
        eom_row.pack(fill="x")
        ctk.CTkLabel(eom_row, text="Estimated end-of-month net worth",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        current_total = 0.0
        for r in self._rows:
            if not r["is_investment_var"].get():
                try:
                    current_total += float(r["balance_var"].get())
                except ValueError:
                    pass
        estimated_eom = current_total - self._est_total_cost

        self._est_eom_label = ctk.CTkLabel(
            eom_row,
            text=fmt_eur(estimated_eom),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_GREEN if estimated_eom >= 0 else _RED,
        )
        self._est_eom_label.pack(side="right")

        ctk.CTkCheckBox(
            inner,
            text="Show adjusted net worth alongside actual total",
            variable=self._include_estimation_var,
            command=self._on_estimation_toggle,
        ).pack(anchor="w", pady=(10, 0))

    def _update_estimation_values(self, current_total: float):
        if self._est_eom_label is None:
            return
        try:
            estimated_eom = current_total - self._est_total_cost
            self._est_eom_label.configure(
                text=fmt_eur(estimated_eom),
                text_color=_GREEN if estimated_eom >= 0 else _RED,
            )
        except Exception:
            pass
        self._update_adjusted_display(current_total)

    def _update_adjusted_display(self, current_total: float | None = None):
        if current_total is None:
            current_total = 0.0
            for r in self._rows:
                if not r["is_investment_var"].get():
                    try:
                        current_total += float(r["balance_var"].get())
                    except ValueError:
                        pass
        if self._include_estimation_var.get() and self._est_total_cost > 0:
            adjusted = current_total - self._est_total_cost
            color    = _GREEN if adjusted >= current_total else "gray"
            self._adjusted_label.configure(
                text=fmt_eur(adjusted), text_color=color,
            )
        else:
            self._adjusted_label.configure(text="")

    def _on_estimation_toggle(self):
        self._update_adjusted_display()

    def _start_buffer_edit(self):
        self._editing_buffer = True
        self._render_estimation()

    def _save_buffer(self, buf_var: ctk.StringVar):
        try:
            value = float(buf_var.get().strip())
            if value <= 0:
                raise ValueError
        except ValueError:
            return
        set_setting("daily_buffer", str(value))
        self._editing_buffer = False
        self._render_estimation()

    def _cancel_buffer_edit(self):
        self._editing_buffer = False
        self._render_estimation()

    # ── Post-save deduction dialog ────────────────────────────────────────────

    def _maybe_show_deduction_dialog(
        self,
        year: int,
        month: int,
        balances: dict[str, float],
        investment_flags: dict[str, bool],
    ):
        today = date.today()
        if year != today.year or month != today.month:
            return
        last_day = calendar.monthrange(year, month)[1]
        if today.day >= last_day:
            return

        daily_buffer   = float(get_setting("daily_buffer") or "20.0")
        remaining_days = last_day - today.day
        expenses       = list(get_all_expenses())

        remaining_fx: list = []
        for e in expenses:
            d     = e["day_of_month"]
            eff_d = effective_charge_day(today.year, today.month, d, last_day)
            if eff_d > today.day:
                remaining_fx.append(e)

        buffer_cost = remaining_days * daily_buffer
        fx_total    = sum(e["amount"] for e in remaining_fx)
        total_cost  = buffer_cost + fx_total

        if total_cost <= 0:
            return

        # Only offer non-investment accounts for deduction
        deduct_accounts = {k: v for k, v in balances.items() if not investment_flags.get(k)}
        if not deduct_accounts:
            return

        confirmed, account_name, actual_total = self._show_deduction_dialog(
            year, month, deduct_accounts, remaining_days, daily_buffer,
            remaining_fx, total_cost, last_day,
        )

        if confirmed and account_name in balances:
            account_balance = balances[account_name]
            if account_balance < actual_total:
                resulting = account_balance - actual_total
                if not self._confirm_dialog(
                    f"Warning: {account_name} only has {fmt_eur(account_balance)}. "
                    f"Deducting {fmt_eur(actual_total)} will result in a negative balance "
                    f"of {fmt_eur(resulting)}. Do you want to continue anyway?",
                    confirm_text="Continue",
                ):
                    return
            new_balances = dict(balances)
            new_balances[account_name] = new_balances[account_name] - actual_total
            save_snapshot(year, month, new_balances)
            self._load_existing()
            net_new = sum(v for k, v in new_balances.items() if not investment_flags.get(k))
            self._set_status(
                f"Snapshot saved for {MONTHS[month - 1]} {year}."
                f"  Estimated remaining costs of {fmt_eur(actual_total)} deducted from {account_name}."
                f"  Adjusted net worth: {fmt_eur(net_new)}",
                color=_GREEN,
            )

    def _show_deduction_dialog(
        self,
        year: int,
        month: int,
        balances: dict[str, float],
        remaining_days: int,
        daily_buffer: float,
        remaining_fx: list,
        total_cost: float,
        last_day: int,
    ) -> tuple[bool, str, float]:
        result: list = [False, "", 0.0]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Deduct Estimated Remaining Costs?")
        dialog.resizable(False, False)
        center_on_parent(dialog, self, 580, 520)
        dialog.grab_set()
        dialog.focus_set()

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(scroll, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            inner, text="Deduct estimated remaining costs?",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            inner,
            text=f"{remaining_days} day{'s' if remaining_days != 1 else ''} remaining "
                 f"in {MONTHS[month - 1]} {year}",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", pady=(0, 12))

        def dlg_row(label: str, value: str, color=("gray90", "gray95"), small: bool = False):
            r  = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=1)
            fs = ctk.CTkFont(size=11) if small else ctk.CTkFont(size=12)
            ctk.CTkLabel(r, text=label, anchor="w", text_color="gray", font=fs).pack(side="left")
            ctk.CTkLabel(r, text=value, anchor="e", text_color=color, font=fs).pack(side="right")

        buffer_cost = remaining_days * daily_buffer
        dlg_row(
            f"Daily Spending Allowance  ({remaining_days} × €{daily_buffer:.0f}/day)",
            f"–{fmt_eur(buffer_cost)}", _RED,
        )

        fx_total = sum(e["amount"] for e in remaining_fx)
        exp_hdr  = ctk.CTkFrame(inner, fg_color="transparent")
        exp_hdr.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(exp_hdr,
                     text=f"Remaining fixed expenses  ({len(remaining_fx)} items)",
                     anchor="w", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkLabel(exp_hdr, text=f"–{fmt_eur(fx_total)}",
                     anchor="e", text_color=_RED,
                     font=ctk.CTkFont(size=12)).pack(side="right")

        for e in remaining_fx:
            d     = e["day_of_month"]
            eff_d = effective_charge_day(year, month, d, last_day)
            day_label = "end of month" if (d == 31 and last_day < 31) else f"day {eff_d}"
            dlg_row(f"  · {e['name']}  ({day_label})",
                    f"–{fmt_eur(e['amount'])}", _RED, small=True)

        ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(8, 8)
        )
        subtotal_row = ctk.CTkFrame(inner, fg_color="transparent")
        subtotal_row.pack(fill="x")
        ctk.CTkLabel(subtotal_row, text="Estimated costs subtotal",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkLabel(subtotal_row, text=f"–{fmt_eur(total_cost)}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=_RED).pack(side="right")

        ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(10, 8)
        )
        extra_row = ctk.CTkFrame(inner, fg_color="transparent")
        extra_row.pack(fill="x")
        ctk.CTkLabel(extra_row, text="Extra one-time cost:",
                     font=ctk.CTkFont(size=13), anchor="w").pack(side="left", padx=(0, 8))
        extra_var = ctk.StringVar(value="0.00")
        ctk.CTkEntry(extra_row, textvariable=extra_var, width=110).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(extra_row, text="EUR",
                     font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkLabel(inner, text="e.g. car insurance, dentist, travel",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 8))

        grand_row = ctk.CTkFrame(inner, fg_color="transparent")
        grand_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(grand_row, text="TOTAL TO DEDUCT",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        grand_label = ctk.CTkLabel(grand_row, text=f"–{fmt_eur(total_cost)}",
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   text_color=_RED)
        grand_label.pack(side="right")

        def _update_grand(*_):
            try:
                extra = max(0.0, float(extra_var.get().strip() or "0"))
            except ValueError:
                extra = 0.0
            grand_label.configure(text=f"–{fmt_eur(total_cost + extra)}")

        extra_var.trace_add("write", _update_grand)

        ctk.CTkFrame(inner, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(10, 8)
        )
        account_names = list(balances.keys())
        account_var   = ctk.StringVar(value=account_names[0] if account_names else "")

        sel_row = ctk.CTkFrame(inner, fg_color="transparent")
        sel_row.pack(fill="x")
        ctk.CTkLabel(sel_row, text="Deduct from:",
                     font=ctk.CTkFont(size=13), anchor="w").pack(side="left", padx=(0, 12))
        ctk.CTkOptionMenu(sel_row, values=account_names, variable=account_var,
                          width=220).pack(side="left")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=12)

        def on_yes():
            try:
                extra = max(0.0, float(extra_var.get().strip() or "0"))
            except ValueError:
                extra = 0.0
            result[0] = True
            result[1] = account_var.get()
            result[2] = total_cost + extra
            dialog.destroy()

        def on_skip():
            dialog.destroy()

        ctk.CTkButton(btn_row, text="Yes, deduct", width=130, command=on_yes).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(btn_row, text="Skip", width=80,
                      fg_color="transparent", border_width=1,
                      command=on_skip).pack(side="left")

        dialog.wait_window()
        return result[0], result[1], result[2]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _confirm_dialog(
        self, message: str, *, confirm_text: str = "Confirm", cancel_text: str = "Cancel"
    ) -> bool:
        result = [False]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.resizable(False, False)
        center_on_parent(dialog, self, 460, 150)
        dialog.grab_set()
        dialog.focus_set()
        ctk.CTkLabel(
            dialog, text=message, wraplength=420, justify="left",
            font=ctk.CTkFont(size=13),
        ).pack(padx=20, pady=(20, 16))
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def on_confirm():
            result[0] = True
            dialog.destroy()

        ctk.CTkButton(btn_row, text=confirm_text, width=110, command=on_confirm).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(
            btn_row, text=cancel_text, width=80,
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).pack(side="left")
        dialog.wait_window()
        return result[0]

    def _set_status(self, text: str, color: str = "gray"):
        self._status_label.configure(text=text, text_color=color)
