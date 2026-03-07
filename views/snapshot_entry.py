import calendar
import customtkinter as ctk
from datetime import date

from database.db import (
    get_snapshot,
    save_snapshot,
    delete_snapshot,
    get_all_expenses,
    get_all_accounts,
    get_all_income,
    get_snapshot_income,
    set_snapshot_income,
    get_extra_income,
    add_extra_income,
    clear_extra_income,
    get_setting,
)
from utils import fmt_eur, fmt_eur_signed, center_on_parent, effective_charge_day, lock_scroll, unlock_scroll, open_dialog, bind_numeric_entry

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

_DEFAULT_ACCOUNTS = ["Main Bank Account", "Revolut", "Cash", "Flatex"]

# ── Theme palette ──────────────────────────────────────────────────────────────
_BG_CARD  = "#161f2e"
_TEXT_PRI = "#e6edf3"
_TEXT_SEC = "#8b949e"
_BORDER   = "#2a3a52"
_BG_ELEM  = "#21262d"
_ACCENT   = "#00b4d8"
_GREEN    = "#3fb950"
_RED      = "#f85149"
_F        = "Helvetica Neue"


class SnapshotEntryView(ctk.CTkScrollableFrame):
    # Class variable: set by Dashboard "Go to Snapshot" button to pre-select a period
    _pending_period: tuple[int, int] | None = None

    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._rows: list[dict] = []
        self._editing_accounts                        = False
        self._edit_accounts_btn: ctk.CTkButton | None = None
        self._delete_snap_btn:   ctk.CTkButton | None = None
        self._income_amount_vars: dict[int, ctk.StringVar] = {}
        self._extra_income_rows:  dict[int, list[dict]]   = {}
        self._build()

    # ── Refresh (called by main.py when navigating to this view) ──────────────

    def refresh(self):
        pending = SnapshotEntryView._pending_period
        if pending:
            SnapshotEntryView._pending_period = None
            self._year_var.set(str(pending[0]))
            self._month_var.set(MONTHS[pending[1] - 1])
            self._load_existing()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        today = date.today()

        ctk.CTkLabel(
            self, text="Monthly Snapshot",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(28, 2))
        ctk.CTkLabel(
            self,
            text="Enter end-of-month balances. Accounts are fully dynamic — add or remove as needed.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # Period selector card
        period_card = ctk.CTkFrame(self, fg_color=_BG_CARD, corner_radius=14,
                                   border_width=1, border_color=_BORDER)
        period_card.pack(fill="x", padx=24, pady=(0, 24))
        period_row = ctk.CTkFrame(period_card, fg_color="transparent")
        period_row.pack(anchor="w", padx=20, pady=16)

        ctk.CTkLabel(period_row, text="Period:", width=56, anchor="w",
                     text_color=_TEXT_PRI).pack(side="left")

        self._month_var = ctk.StringVar(value=MONTHS[today.month - 1])
        ctk.CTkOptionMenu(
            period_row, values=MONTHS, variable=self._month_var,
            width=150, command=self._on_period_change,
            fg_color=_BG_ELEM, button_color=_BG_ELEM, button_hover_color="#3d4d63",
            text_color=_TEXT_PRI,
        ).pack(side="left", padx=(0, 8))

        self._year_var = ctk.StringVar(value=str(today.year))
        year_entry = ctk.CTkEntry(period_row, textvariable=self._year_var, width=80,
                                  fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI)
        year_entry.pack(side="left")
        year_entry.bind("<Return>",   self._on_period_change)
        year_entry.bind("<FocusOut>", self._on_period_change)

        # Column headers
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkLabel(
            header_row, text="Account",
            width=300, anchor="w", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=12),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            header_row, text="Balance (EUR)",
            width=150, anchor="w", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=12),
        ).pack(side="left")

        # Account rows container
        self._rows_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._rows_frame.pack(anchor="w", padx=24, fill="x")

        # Add Account + Edit Accounts buttons
        add_btn_row = ctk.CTkFrame(self, fg_color="transparent")
        add_btn_row.pack(anchor="w", padx=24, pady=(10, 0))
        ctk.CTkButton(
            add_btn_row, text="+ Add Account",
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8, width=140,
            command=self._add_account_and_edit,
        ).pack(side="left", padx=(0, 8))
        self._edit_accounts_btn = ctk.CTkButton(
            add_btn_row, text="Edit Accounts", width=130,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=self._toggle_account_editing,
        )
        self._edit_accounts_btn.pack(side="left")

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=_BORDER).pack(fill="x", padx=24, pady=(20, 12))

        # Net worth total
        total_row = ctk.CTkFrame(self, fg_color="transparent")
        total_row.pack(anchor="w", padx=24, pady=(0, 2))
        ctk.CTkLabel(
            total_row, text="Net Worth:",
            font=ctk.CTkFont(family=_F, size=14, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(side="left", padx=(0, 10))
        self._total_label = ctk.CTkLabel(
            total_row, text="€0,00",
            font=ctk.CTkFont(family=_F, size=14, weight="bold"),
            text_color=_TEXT_PRI,
        )
        self._total_label.pack(side="left")

        # Income this month
        self._income_container = ctk.CTkFrame(self, fg_color="transparent")
        self._income_container.pack(fill="x", padx=24, pady=(0, 0))

        # Save + status
        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.pack(anchor="w", padx=24, pady=(0, 2))
        ctk.CTkButton(save_row, text="Save Snapshot", width=140,
                      fg_color=_ACCENT, hover_color="#0096b4",
                      text_color="white", corner_radius=8,
                      command=self._save).pack(side="left", padx=(0, 16))
        self._status_label = ctk.CTkLabel(save_row, text="", text_color=_TEXT_SEC)
        self._status_label.pack(side="left")

        # Delete snapshot button (row not packed until a snapshot exists)
        self._del_row = ctk.CTkFrame(self, fg_color="transparent")
        self._delete_snap_btn = ctk.CTkButton(
            self._del_row, text="Delete Snapshot", width=140,
            fg_color=_BG_ELEM, hover_color="#3d1a1a",
            text_color=_RED, corner_radius=8,
            command=self._delete_snapshot,
        )

        self._load_existing()

    # ── Account rows ──────────────────────────────────────────────────────────

    def _add_row(self, name: str = "", balance: str = "") -> dict:
        row_frame = ctk.CTkFrame(self._rows_frame, fg_color="transparent")
        row_frame.pack(anchor="w", pady=3, fill="x")

        name_var    = ctk.StringVar(value=name)
        balance_var = ctk.StringVar(value=balance)

        balance_var.trace_add("write", lambda *_: self._update_total())

        name_container = ctk.CTkFrame(row_frame, fg_color="transparent", corner_radius=0)
        name_container.pack(side="left", padx=(0, 8))

        bal_entry = ctk.CTkEntry(
            row_frame, textvariable=balance_var,
            placeholder_text="0.00", width=150,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
        )
        bal_entry.pack(side="left", padx=(0, 8))
        bind_numeric_entry(bal_entry)

        edit_controls = ctk.CTkFrame(row_frame, fg_color="transparent", corner_radius=0)

        row = {
            "frame":          row_frame,
            "name_container": name_container,
            "name_var":       name_var,
            "balance_var":    balance_var,
            "edit_controls":  edit_controls,
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
                fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
            ).pack(side="left")
        else:
            display_name = row["name_var"].get() or "Unnamed"
            ctk.CTkLabel(
                row["name_container"], text=display_name,
                anchor="w", width=300, text_color=_TEXT_PRI,
            ).pack(side="left")

    def _refresh_edit_controls(self, row: dict):
        for w in row["edit_controls"].winfo_children():
            w.destroy()
        if self._editing_accounts:
            ctk.CTkButton(
                row["edit_controls"], text="×", width=36, height=36,
                fg_color=_BG_ELEM, hover_color="#3d1a1a",
                text_color=_RED, corner_radius=8,
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

        self._editing_accounts = False
        if self._edit_accounts_btn:
            self._edit_accounts_btn.configure(text="Edit Accounts")

        existing = get_snapshot(year, month)

        self._clear_rows()

        if existing:
            for name, balance in existing.items():
                self._add_row(name, f"{balance:.2f}")
            self._set_status(
                f"Showing saved data for {MONTHS[month - 1]} {year}. Edit fields and re-save to update.",
                color=_TEXT_SEC,
            )
            self._del_row.pack(anchor="w", padx=24, pady=(8, 0))
            self._delete_snap_btn.pack(side="left")
        else:
            today = date.today()
            if year > today.year or (year == today.year and month >= today.month):
                known = get_all_accounts()
                accounts_to_use = known if known else _DEFAULT_ACCOUNTS
            else:
                accounts_to_use = _DEFAULT_ACCOUNTS
            for name in accounts_to_use:
                self._add_row(name)
            self._set_status("")
            self._delete_snap_btn.pack_forget()
            self._del_row.pack_forget()

        self._update_total()
        self._render_income_section()

    # ── Income this month ─────────────────────────────────────────────────────

    def _render_income_section(self):
        for w in self._income_container.winfo_children():
            w.destroy()
        self._income_amount_vars.clear()
        self._extra_income_rows.clear()

        period = self._get_period()
        if period is None:
            return
        year, month = period

        all_income = list(get_all_income())
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

        saved = get_snapshot_income(year, month)

        # Group saved extras by income_id
        extras_by_id: dict[int, list[dict]] = {}
        for e in get_extra_income(year, month):
            extras_by_id.setdefault(e["income_id"], []).append(e)

        card  = ctk.CTkFrame(self._income_container, fg_color=_BG_CARD, corner_radius=14,
                             border_width=1, border_color=_BORDER)
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(
            inner, text="INCOME THIS MONTH",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=11),
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Enter the actual amount received for each income source below.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
        ).pack(anchor="w", pady=(2, 10))

        for item in relevant:
            iid       = item["id"]
            saved_val = saved.get(iid)
            default   = f"{saved_val:.2f}" if saved_val is not None else f"{item['amount']:.2f}"

            var = ctk.StringVar(value=default)
            self._income_amount_vars[iid] = var
            self._extra_income_rows[iid] = []

            # Main income row
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=(2, 0))
            ctk.CTkLabel(
                row, text=item["name"], width=260, anchor="w",
                text_color=_TEXT_PRI,
            ).pack(side="left")
            ctk.CTkLabel(row, text="EUR", anchor="w",
                         text_color=_TEXT_SEC).pack(side="left", padx=(0, 4))
            inc_entry = ctk.CTkEntry(row, textvariable=var, width=110,
                                     fg_color=_BG_ELEM, border_color=_BORDER,
                                     text_color=_TEXT_PRI)
            inc_entry.pack(side="left")
            bind_numeric_entry(inc_entry)

            # Sub-frame that holds all extra rows for this income source
            extras_frame = ctk.CTkFrame(inner, fg_color="transparent", corner_radius=0)
            # Don't pack yet - will be packed when first extra row is added

            # Helper to add one extra row
            def _add_extra_row(
                income_id: int,
                frame: ctk.CTkFrame,
                desc: str = "",
                amount: str = "",
            ):
                desc_var   = ctk.StringVar(value=desc)
                amount_var = ctk.StringVar(value=amount)
                entry_dict: dict = {}

                if not frame.winfo_ismapped():
                    frame.pack(fill="x", pady=0)

                xrow = ctk.CTkFrame(frame, fg_color="transparent")
                xrow.pack(fill="x", pady=1)

                # 20px indent spacer
                ctk.CTkFrame(xrow, fg_color="transparent", width=20).pack(side="left")

                ctk.CTkEntry(
                    xrow, textvariable=desc_var,
                    placeholder_text="Description e.g. Bonus, Weihnachtsgeld",
                    width=260,
                    fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
                ).pack(side="left", padx=(0, 6))
                ctk.CTkLabel(xrow, text="EUR", anchor="w",
                             text_color=_TEXT_SEC).pack(side="left", padx=(0, 4))
                extra_amt_entry = ctk.CTkEntry(
                    xrow, textvariable=amount_var,
                    placeholder_text="0.00", width=90,
                    fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
                )
                extra_amt_entry.pack(side="left")
                bind_numeric_entry(extra_amt_entry)

                entry_dict["frame"]      = xrow
                entry_dict["desc_var"]   = desc_var
                entry_dict["amount_var"] = amount_var
                self._extra_income_rows[income_id].append(entry_dict)

                def _remove(ed=entry_dict, iid=income_id):
                    ed["frame"].destroy()
                    self._extra_income_rows[iid].remove(ed)

                ctk.CTkButton(
                    xrow, text="×", width=28, height=28,
                    fg_color=_BG_ELEM, hover_color="#3d1a1a",
                    text_color=_RED, corner_radius=6,
                    font=ctk.CTkFont(family=_F, size=13),
                    command=_remove,
                ).pack(side="left", padx=(6, 0))

            # Pre-populate saved extras
            for e in extras_by_id.get(iid, []):
                _add_extra_row(iid, extras_frame,
                               desc=e["description"],
                               amount=f"{e['amount']:.2f}")

            # "+ Add bonus" button on the main row
            ctk.CTkButton(
                row, text="+ Add bonus", width=90,
                fg_color=_BG_ELEM, hover_color="#3d4d63",
                text_color=_TEXT_SEC, corner_radius=8,
                font=ctk.CTkFont(family=_F, size=11),
                command=lambda i=iid, f=extras_frame: _add_extra_row(i, f),
            ).pack(side="left", padx=(8, 0))

    # ── Totals ────────────────────────────────────────────────────────────────

    def _update_total(self):
        total = 0.0
        for row in self._rows:
            try:
                total += float(row["balance_var"].get())
            except ValueError:
                pass
        self._total_label.configure(text=fmt_eur(total))

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self):
        period = self._get_period()
        if period is None:
            self._set_status("Invalid year.", color=_RED)
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

        balances: dict[str, float] = {}

        for row in self._rows:
            name = row["name_var"].get().strip()
            if not name:
                self._set_status("Account name cannot be empty.", color=_RED)
                return
            try:
                balance = float(row["balance_var"].get().strip() or "0")
            except ValueError:
                self._set_status(f'Invalid balance for "{name}".', color=_RED)
                return
            balances[name] = balance

        if not balances:
            self._set_status("Add at least one account before saving.", color=_RED)
            return

        if get_snapshot(year, month) is not None:
            confirmed = [False]
            month_name_str = date(year, month, 1).strftime("%B")
            ow_dialog = open_dialog(self, 460, 160)
            ow_dialog.title("Overwrite Snapshot")
            ctk.CTkLabel(
                ow_dialog,
                text=f"A snapshot for {month_name_str} {year} already exists.\nDo you want to overwrite it?",
                wraplength=420, justify="left",
                font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_PRI,
            ).pack(padx=20, pady=(20, 12))
            ow_btn_row = ctk.CTkFrame(ow_dialog, fg_color="transparent")
            ow_btn_row.pack()
            ctk.CTkButton(ow_btn_row, text="Overwrite", width=110,
                fg_color=_ACCENT, hover_color="#0096b4", text_color="white", corner_radius=8,
                command=lambda: [confirmed.__setitem__(0, True), ow_dialog.destroy()],
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(ow_btn_row, text="Cancel", width=80,
                fg_color=_BG_ELEM, hover_color="#3d4d63",
                text_color=_TEXT_PRI, corner_radius=8,
                command=ow_dialog.destroy,
            ).pack(side="left")
            ow_dialog.wait_window()
            unlock_scroll()
            if not confirmed[0]:
                return

        total_snapshots = save_snapshot(year, month, balances)

        for income_id, var in self._income_amount_vars.items():
            try:
                amount = float(var.get().strip() or "0")
                set_snapshot_income(year, month, income_id, amount)
            except ValueError:
                pass

        for income_id, rows in self._extra_income_rows.items():
            clear_extra_income(year, month, income_id)
            for rd in rows:
                desc = rd["desc_var"].get().strip()
                try:
                    amount = float(rd["amount_var"].get().strip() or "0")
                except ValueError:
                    amount = 0.0
                if desc or amount > 0:
                    add_extra_income(year, month, income_id, desc, amount)

        month_name = MONTHS[month - 1]

        if total_snapshots == 1:
            self._set_status(
                f"Snapshot saved for {month_name} {year}."
                "  Add next month's data to see your first net worth change.",
                color=_GREEN,
            )
        else:
            self._set_status(
                f"Snapshot saved for {month_name} {year}.  Net Worth: {fmt_eur(sum(balances.values()))}",
                color=_GREEN,
            )

        self._del_row.pack(anchor="w", padx=24, pady=(8, 0))
        self._delete_snap_btn.pack(side="left")
        self._update_total()
        self._maybe_show_deduction_dialog(year, month, balances)

    # ── Delete Snapshot ───────────────────────────────────────────────────────

    def _delete_snapshot(self):
        period = self._get_period()
        if period is None:
            return
        year, month = period
        month_name = MONTHS[month - 1]
        if not self._confirm_dialog(
            f"Are you sure you want to delete the snapshot for {month_name} {year}?",
            confirm_text="Delete",
        ):
            return
        delete_snapshot(year, month)
        self._load_existing()
        self._set_status(f"Snapshot for {month_name} {year} deleted.", color=_TEXT_SEC)

    # ── Post-save deduction dialog ────────────────────────────────────────────

    def _maybe_show_deduction_dialog(
        self,
        year: int,
        month: int,
        balances: dict[str, float],
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

        if not balances:
            return
        deduct_accounts = balances

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
            self._set_status(
                f"Snapshot saved for {MONTHS[month - 1]} {year}."
                f"  Estimated remaining costs of {fmt_eur(actual_total)} deducted from {account_name}."
                f"  Adjusted net worth: {fmt_eur(sum(new_balances.values()))}",
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

        dialog = open_dialog(self, 580, 520)
        dialog.title("Deduct Estimated Remaining Costs?")

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(scroll, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            inner, text="Deduct estimated remaining costs?",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            inner,
            text=f"{remaining_days} day{'s' if remaining_days != 1 else ''} remaining "
                 f"in {MONTHS[month - 1]} {year}",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
        ).pack(anchor="w", pady=(0, 12))

        def dlg_row(label: str, value: str, color=_TEXT_PRI, small: bool = False):
            r  = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=1)
            fs = ctk.CTkFont(family=_F, size=11) if small else ctk.CTkFont(family=_F, size=12)
            ctk.CTkLabel(r, text=label, anchor="w", text_color=_TEXT_SEC, font=fs).pack(side="left")
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
                     anchor="w", text_color=_TEXT_SEC,
                     font=ctk.CTkFont(family=_F, size=12)).pack(side="left")
        ctk.CTkLabel(exp_hdr, text=f"–{fmt_eur(fx_total)}",
                     anchor="e", text_color=_RED,
                     font=ctk.CTkFont(family=_F, size=12)).pack(side="right")

        for e in remaining_fx:
            d     = e["day_of_month"]
            eff_d = effective_charge_day(year, month, d, last_day)
            day_label = "end of month" if (d == 31 and last_day < 31) else f"day {eff_d}"
            dlg_row(f"  · {e['name']}  ({day_label})",
                    f"–{fmt_eur(e['amount'])}", _RED, small=True)

        ctk.CTkFrame(inner, height=1, fg_color=_BORDER).pack(fill="x", pady=(8, 8))
        subtotal_row = ctk.CTkFrame(inner, fg_color="transparent")
        subtotal_row.pack(fill="x")
        ctk.CTkLabel(subtotal_row, text="Estimated costs subtotal",
                     font=ctk.CTkFont(family=_F, size=13, weight="bold"),
                     text_color=_TEXT_PRI).pack(side="left")
        ctk.CTkLabel(subtotal_row, text=f"–{fmt_eur(total_cost)}",
                     font=ctk.CTkFont(family=_F, size=13, weight="bold"),
                     text_color=_RED).pack(side="right")

        ctk.CTkFrame(inner, height=1, fg_color=_BORDER).pack(fill="x", pady=(10, 8))
        extra_row = ctk.CTkFrame(inner, fg_color="transparent")
        extra_row.pack(fill="x")
        ctk.CTkLabel(extra_row, text="Extra one-time cost:",
                     font=ctk.CTkFont(family=_F, size=13), anchor="w",
                     text_color=_TEXT_PRI).pack(side="left", padx=(0, 8))
        extra_var = ctk.StringVar(value="0.00")
        ctk.CTkEntry(extra_row, textvariable=extra_var, width=110,
                     fg_color=_BG_ELEM, border_color=_BORDER,
                     text_color=_TEXT_PRI).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(extra_row, text="EUR",
                     font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_PRI).pack(side="left")
        ctk.CTkLabel(inner, text="e.g. car insurance, dentist, travel",
                     text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=11)).pack(anchor="w", pady=(2, 8))

        grand_row = ctk.CTkFrame(inner, fg_color="transparent")
        grand_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(grand_row, text="TOTAL TO DEDUCT",
                     font=ctk.CTkFont(family=_F, size=13, weight="bold"),
                     text_color=_TEXT_PRI).pack(side="left")
        grand_label = ctk.CTkLabel(grand_row, text=f"–{fmt_eur(total_cost)}",
                                   font=ctk.CTkFont(family=_F, size=13, weight="bold"),
                                   text_color=_RED)
        grand_label.pack(side="right")

        def _update_grand(*_):
            try:
                extra = max(0.0, float(extra_var.get().strip() or "0"))
            except ValueError:
                extra = 0.0
            grand_label.configure(text=f"–{fmt_eur(total_cost + extra)}")

        extra_var.trace_add("write", _update_grand)

        ctk.CTkFrame(inner, height=1, fg_color=_BORDER).pack(fill="x", pady=(10, 8))
        account_names = list(balances.keys())
        account_var   = ctk.StringVar(value=account_names[0] if account_names else "")

        sel_row = ctk.CTkFrame(inner, fg_color="transparent")
        sel_row.pack(fill="x")
        ctk.CTkLabel(sel_row, text="Deduct from:",
                     font=ctk.CTkFont(family=_F, size=13), anchor="w",
                     text_color=_TEXT_PRI).pack(side="left", padx=(0, 12))
        ctk.CTkOptionMenu(sel_row, values=account_names, variable=account_var,
                          width=220,
                          fg_color=_BG_ELEM, button_color=_BG_ELEM,
                          button_hover_color="#3d4d63", text_color=_TEXT_PRI).pack(side="left")

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

        ctk.CTkButton(btn_row, text="Yes, deduct", width=130,
                      fg_color=_ACCENT, hover_color="#0096b4",
                      text_color="white", corner_radius=8,
                      command=on_yes).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Skip", width=80,
                      fg_color=_BG_ELEM, hover_color="#3d4d63",
                      text_color=_TEXT_PRI, corner_radius=8,
                      command=on_skip).pack(side="left")

        dialog.wait_window()
        unlock_scroll()
        return result[0], result[1], result[2]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _confirm_dialog(
        self, message: str, *, confirm_text: str = "Confirm", cancel_text: str = "Cancel"
    ) -> bool:
        result = [False]
        dialog = open_dialog(self, 460, 150)
        dialog.title("Confirm")
        ctk.CTkLabel(
            dialog, text=message, wraplength=420, justify="left",
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_PRI,
        ).pack(padx=20, pady=(20, 16))
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def on_confirm():
            result[0] = True
            dialog.destroy()

        ctk.CTkButton(btn_row, text=confirm_text, width=110,
                      fg_color=_ACCENT, hover_color="#0096b4",
                      text_color="white", corner_radius=8,
                      command=on_confirm).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text=cancel_text, width=80,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=dialog.destroy,
        ).pack(side="left")
        dialog.wait_window()
        unlock_scroll()
        return result[0]

    def _set_status(self, text: str, color: str = _TEXT_SEC):
        self._status_label.configure(text=text, text_color=color)
