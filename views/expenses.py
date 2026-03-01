import customtkinter as ctk

from database.db import (
    get_all_expenses,
    add_expense,
    update_expense,
    delete_expense,
    get_all_income,
    add_income,
    update_income,
    delete_income,
)
from utils import fmt_eur, center_on_parent

# Fixed expenses column widths
_W_DAY    = 60
_W_NAME   = 220
_W_AMOUNT = 130

# Income column widths
_W_INC_NAME   = 260
_W_INC_MONTHS = 270
_W_INC_AMOUNT = 130

_GREEN = "#2CC985"
_RED   = "#E74C3C"

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ExpensesView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")

        # Fixed expenses state
        self._expenses_edit_mode: bool = False
        self._expenses_row_vars:  dict[int, dict] = {}  # id → {day, name, amount StringVars}
        self._expenses_toggle_btn: ctk.CTkButton | None = None
        self._expenses_error_lbl:  ctk.CTkLabel | None = None

        # Income state
        self._income_edit_mode: bool = False
        self._income_row_vars:  dict[int, dict] = {}  # id → {name, amount StringVars + month BoolVars}
        self._income_toggle_btn: ctk.CTkButton | None = None
        self._income_error_lbl:  ctk.CTkLabel | None = None

        # Income add-form month checkbox vars (all True by default)
        self._inc_add_months_vars: dict[int, ctk.BooleanVar] = {
            m: ctk.BooleanVar(value=True) for m in range(1, 13)
        }

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Budget",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Manage your fixed recurring expenses and monthly income sources.",
            text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # ══ Fixed Monthly Expenses ════════════════════════════════════════════

        exp_hdr = ctk.CTkFrame(self, fg_color="transparent")
        exp_hdr.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(
            exp_hdr, text="Fixed Monthly Expenses",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        self._expenses_error_lbl = ctk.CTkLabel(
            exp_hdr, text="", text_color=_RED, font=ctk.CTkFont(size=12),
        )
        self._expenses_error_lbl.pack(side="right", padx=(0, 8))
        self._expenses_toggle_btn = ctk.CTkButton(
            exp_hdr, text="Edit", width=64,
            fg_color="transparent", border_width=1,
            command=self._toggle_expenses_edit,
        )
        self._expenses_toggle_btn.pack(side="right")

        # Add expense form
        add_card = ctk.CTkFrame(self)
        add_card.pack(fill="x", padx=24, pady=(0, 16))
        form = ctk.CTkFrame(add_card, fg_color="transparent")
        form.pack(anchor="w", padx=16, pady=14)

        ctk.CTkLabel(form, text="Day", anchor="w").pack(side="left", padx=(0, 4))
        self._add_day = ctk.CTkEntry(form, placeholder_text="1–31", width=60)
        self._add_day.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(form, text="Name", anchor="w").pack(side="left", padx=(0, 4))
        self._add_name = ctk.CTkEntry(form, placeholder_text="Expense name", width=220)
        self._add_name.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(form, text="EUR", anchor="w").pack(side="left", padx=(0, 4))
        self._add_amount = ctk.CTkEntry(form, placeholder_text="0.00", width=110)
        self._add_amount.pack(side="left", padx=(0, 14))
        self._add_amount.bind("<Return>", lambda _: self._add_expense())
        ctk.CTkButton(form, text="Add", width=80, command=self._add_expense).pack(
            side="left", padx=(0, 12)
        )
        self._add_status = ctk.CTkLabel(form, text="")
        self._add_status.pack(side="left")

        # Column headers
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(anchor="w", padx=24, pady=(0, 2))
        for text, width, anchor in [
            ("Day",    _W_DAY,    "w"),
            ("Name",   _W_NAME,   "w"),
            ("Amount", _W_AMOUNT, "e"),
        ]:
            ctk.CTkLabel(
                header, text=text, width=width, anchor=anchor,
                text_color="gray", font=ctk.CTkFont(size=12),
            ).pack(side="left")

        self._list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._list_frame.pack(anchor="w", padx=24, fill="x")

        # Monthly total
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(16, 10)
        )
        total_row = ctk.CTkFrame(self, fg_color="transparent")
        total_row.pack(anchor="w", padx=24, pady=(0, 28))
        ctk.CTkLabel(
            total_row, text="Monthly total:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        self._total_label = ctk.CTkLabel(
            total_row, text="€0,00",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._total_label.pack(side="left")

        # ══ Monthly Income ════════════════════════════════════════════════════
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(0, 20)
        )

        inc_hdr = ctk.CTkFrame(self, fg_color="transparent")
        inc_hdr.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkLabel(
            inc_hdr, text="Monthly Income",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        self._income_error_lbl = ctk.CTkLabel(
            inc_hdr, text="", text_color=_RED, font=ctk.CTkFont(size=12),
        )
        self._income_error_lbl.pack(side="right", padx=(0, 8))
        self._income_toggle_btn = ctk.CTkButton(
            inc_hdr, text="Edit", width=64,
            fg_color="transparent", border_width=1,
            command=self._toggle_income_edit,
        )
        self._income_toggle_btn.pack(side="right")

        ctk.CTkLabel(
            self,
            text="Regular income sources. Active months determine which months show in the snapshot for amount entry.",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=24, pady=(0, 12))

        # Add income form
        inc_add_card = ctk.CTkFrame(self)
        inc_add_card.pack(fill="x", padx=24, pady=(0, 16))
        inc_form_outer = ctk.CTkFrame(inc_add_card, fg_color="transparent")
        inc_form_outer.pack(anchor="w", padx=16, pady=14, fill="x")

        # Row 1: name + amount + add button
        inc_form = ctk.CTkFrame(inc_form_outer, fg_color="transparent")
        inc_form.pack(anchor="w")
        ctk.CTkLabel(inc_form, text="Name", anchor="w").pack(side="left", padx=(0, 4))
        self._inc_add_name = ctk.CTkEntry(inc_form, placeholder_text="Income source", width=220)
        self._inc_add_name.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(inc_form, text="EUR", anchor="w").pack(side="left", padx=(0, 4))
        self._inc_add_amount = ctk.CTkEntry(inc_form, placeholder_text="0.00", width=110)
        self._inc_add_amount.pack(side="left", padx=(0, 14))
        self._inc_add_amount.bind("<Return>", lambda _: self._add_income_item())
        ctk.CTkButton(inc_form, text="Add", width=80, command=self._add_income_item).pack(
            side="left", padx=(0, 12)
        )
        self._inc_add_status = ctk.CTkLabel(inc_form, text="")
        self._inc_add_status.pack(side="left")

        # Row 2: month checkboxes
        months_row = ctk.CTkFrame(inc_form_outer, fg_color="transparent")
        months_row.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(months_row, text="Active months:", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        for m in range(1, 13):
            ctk.CTkCheckBox(
                months_row, text=_MONTHS_SHORT[m - 1], width=54,
                variable=self._inc_add_months_vars[m],
            ).pack(side="left", padx=(0, 2))

        # Income column headers
        inc_col_hdr = ctk.CTkFrame(self, fg_color="transparent")
        inc_col_hdr.pack(anchor="w", padx=24, pady=(0, 2))
        for text, width, anchor in [
            ("Name",          _W_INC_NAME,   "w"),
            ("Active Months", _W_INC_MONTHS, "w"),
            ("Amount",        _W_INC_AMOUNT, "e"),
        ]:
            ctk.CTkLabel(
                inc_col_hdr, text=text, width=width, anchor=anchor,
                text_color="gray", font=ctk.CTkFont(size=12),
            ).pack(side="left")

        self._income_list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._income_list_frame.pack(anchor="w", padx=24, fill="x")

        # Income total
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(16, 10)
        )
        inc_total_row = ctk.CTkFrame(self, fg_color="transparent")
        inc_total_row.pack(anchor="w", padx=24, pady=(0, 32))
        ctk.CTkLabel(
            inc_total_row, text="Expected monthly income:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        self._income_total_label = ctk.CTkLabel(
            inc_total_row, text="€0,00",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._income_total_label.pack(side="left")

        self._refresh()
        self._refresh_income()

    # ── Fixed expenses edit toggle ─────────────────────────────────────────────

    def _toggle_expenses_edit(self):
        if self._expenses_edit_mode:
            # "Done" clicked — save all changes
            if not self._save_all_expenses():
                return  # Validation failed; stay in edit mode
            self._expenses_edit_mode = False
            if self._expenses_toggle_btn:
                self._expenses_toggle_btn.configure(text="Edit")
        else:
            self._expenses_edit_mode = True
            if self._expenses_toggle_btn:
                self._expenses_toggle_btn.configure(text="Done")
            if self._expenses_error_lbl:
                self._expenses_error_lbl.configure(text="")
        self._refresh()

    def _save_all_expenses(self) -> bool:
        for eid, v in self._expenses_row_vars.items():
            try:
                day = int(v["day"].get().strip())
                if not 1 <= day <= 31:
                    raise ValueError
            except ValueError:
                if self._expenses_error_lbl:
                    self._expenses_error_lbl.configure(text="Day must be 1–31.")
                return False
            name = v["name"].get().strip()
            if not name:
                if self._expenses_error_lbl:
                    self._expenses_error_lbl.configure(text="Name cannot be empty.")
                return False
            try:
                amount = float(v["amount"].get().strip())
            except ValueError:
                if self._expenses_error_lbl:
                    self._expenses_error_lbl.configure(text="Invalid amount.")
                return False
            update_expense(eid, name, amount, day)
        if self._expenses_error_lbl:
            self._expenses_error_lbl.configure(text="")
        return True

    # ── Income edit toggle ─────────────────────────────────────────────────────

    def _toggle_income_edit(self):
        if self._income_edit_mode:
            if not self._save_all_income():
                return
            self._income_edit_mode = False
            if self._income_toggle_btn:
                self._income_toggle_btn.configure(text="Edit")
        else:
            self._income_edit_mode = True
            if self._income_toggle_btn:
                self._income_toggle_btn.configure(text="Done")
            if self._income_error_lbl:
                self._income_error_lbl.configure(text="")
        self._refresh_income()

    def _save_all_income(self) -> bool:
        for iid, v in self._income_row_vars.items():
            name = v["name"].get().strip()
            if not name:
                if self._income_error_lbl:
                    self._income_error_lbl.configure(text="Name cannot be empty.")
                return False
            try:
                amount = float(v["amount"].get().strip() or "0")
                if amount < 0:
                    raise ValueError
            except ValueError:
                if self._income_error_lbl:
                    self._income_error_lbl.configure(text="Invalid amount.")
                return False
            active = [m for m in range(1, 13) if v["months"][m].get()]
            if not active:
                if self._income_error_lbl:
                    self._income_error_lbl.configure(text="Select at least one active month.")
                return False
            active_months_str = None if len(active) == 12 else ",".join(str(m) for m in active)
            update_income(iid, name, amount, 0, "fixed", active_months_str)
        if self._income_error_lbl:
            self._income_error_lbl.configure(text="")
        return True

    # ── Fixed expenses list ────────────────────────────────────────────────────

    def refresh(self):
        self._refresh()
        self._refresh_income()

    def _refresh(self):
        for child in self._list_frame.winfo_children():
            child.destroy()
        self._expenses_row_vars.clear()

        expenses = get_all_expenses()
        for exp in expenses:
            self._render_expense_row(dict(exp))

        total = sum(e["amount"] for e in expenses)
        self._total_label.configure(text=fmt_eur(total))

    def _render_expense_row(self, exp: dict):
        row = ctk.CTkFrame(self._list_frame, fg_color="transparent")
        row.pack(anchor="w", pady=2, fill="x")

        if self._expenses_edit_mode:
            day_var    = ctk.StringVar(value=str(exp["day_of_month"]))
            name_var   = ctk.StringVar(value=exp["name"])
            amount_var = ctk.StringVar(value=f"{exp['amount']:.2f}")
            self._expenses_row_vars[exp["id"]] = {
                "day": day_var, "name": name_var, "amount": amount_var,
            }
            ctk.CTkEntry(row, textvariable=day_var,    width=_W_DAY).pack(   side="left", padx=(0, 6))
            ctk.CTkEntry(row, textvariable=name_var,   width=_W_NAME).pack(  side="left", padx=(0, 6))
            ctk.CTkEntry(row, textvariable=amount_var, width=_W_AMOUNT).pack(side="left", padx=(0, 10))
            ctk.CTkButton(
                row, text="×", width=36, height=32,
                fg_color="transparent", border_width=1,
                text_color=("gray40", "gray60"),
                hover_color=("gray85", "gray25"),
                command=lambda eid=exp["id"], n=exp["name"]: self._delete(eid, n),
            ).pack(side="left")
        else:
            ctk.CTkLabel(row, text=str(exp["day_of_month"]), width=_W_DAY,    anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=exp["name"],              width=_W_NAME,   anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=fmt_eur(exp["amount"]),   width=_W_AMOUNT, anchor="e").pack(side="left")

    # ── Income list ────────────────────────────────────────────────────────────

    def _refresh_income(self):
        for child in self._income_list_frame.winfo_children():
            child.destroy()
        self._income_row_vars.clear()

        income_items = get_all_income()
        for item in income_items:
            self._render_income_row(dict(item))

        total = sum(i["amount"] for i in income_items)
        self._income_total_label.configure(text=fmt_eur(total))

    @staticmethod
    def _format_active_months(item: dict) -> str:
        active_str = item.get("active_months") or ""
        if not active_str.strip():
            return "All months"
        nums = sorted(int(x) for x in active_str.split(",") if x.strip().isdigit())
        if len(nums) == 12:
            return "All months"
        return ", ".join(_MONTHS_SHORT[m - 1] for m in nums if 1 <= m <= 12)

    def _render_income_row(self, item: dict):
        if self._income_edit_mode:
            self._render_income_edit_row(item)
        else:
            self._render_income_display_row(item)

    def _render_income_display_row(self, item: dict):
        row = ctk.CTkFrame(self._income_list_frame, fg_color="transparent")
        row.pack(anchor="w", pady=2, fill="x")

        months_display = self._format_active_months(item)
        ctk.CTkLabel(row, text=item["name"],           width=_W_INC_NAME,   anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=months_display,         width=_W_INC_MONTHS, anchor="w",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkLabel(row, text=fmt_eur(item["amount"]), width=_W_INC_AMOUNT, anchor="e").pack(side="left")

    def _render_income_edit_row(self, item: dict):
        outer = ctk.CTkFrame(self._income_list_frame, fg_color=("gray88", "gray22"))
        outer.pack(anchor="w", pady=2, fill="x")
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(anchor="w", padx=8, pady=6, fill="x")

        name_var   = ctk.StringVar(value=item["name"])
        amount_var = ctk.StringVar(value=f"{item['amount']:.2f}")

        # Parse existing active_months
        active_str = item.get("active_months") or ""
        active_set = {int(x) for x in active_str.split(",") if x.strip().isdigit()} if active_str else set(range(1, 13))
        month_vars: dict[int, ctk.BooleanVar] = {
            m: ctk.BooleanVar(value=(m in active_set)) for m in range(1, 13)
        }

        self._income_row_vars[item["id"]] = {
            "name": name_var, "amount": amount_var, "months": month_vars,
        }

        # Line 1: name + amount + × button
        line1 = ctk.CTkFrame(inner, fg_color="transparent")
        line1.pack(anchor="w")
        ctk.CTkEntry(line1, textvariable=name_var, width=260).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(line1, text="EUR").pack(side="left", padx=(0, 4))
        ctk.CTkEntry(line1, textvariable=amount_var, width=110).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            line1, text="×", width=36, height=32,
            fg_color="transparent", border_width=1,
            text_color=("gray40", "gray60"),
            hover_color=("gray85", "gray25"),
            command=lambda iid=item["id"], n=item["name"]: self._delete_income_item(iid, n),
        ).pack(side="left")

        # Line 2: month checkboxes
        line2 = ctk.CTkFrame(inner, fg_color="transparent")
        line2.pack(anchor="w", pady=(6, 0))
        ctk.CTkLabel(line2, text="Active months:", text_color="gray",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 6))
        for m in range(1, 13):
            ctk.CTkCheckBox(
                line2, text=_MONTHS_SHORT[m - 1], width=54,
                variable=month_vars[m],
            ).pack(side="left", padx=(0, 2))

    # ── Fixed expense actions ──────────────────────────────────────────────────

    def _add_expense(self):
        day_str    = self._add_day.get().strip()
        name       = self._add_name.get().strip()
        amount_str = self._add_amount.get().strip()
        try:
            day = int(day_str)
            if not 1 <= day <= 31:
                raise ValueError
        except ValueError:
            self._set_add_status("Day must be 1–31.", error=True)
            return
        if not name:
            self._set_add_status("Name is required.", error=True)
            return
        try:
            amount = float(amount_str)
        except ValueError:
            self._set_add_status("Invalid amount.", error=True)
            return
        add_expense(name, amount, day)
        self._add_day.delete(0, "end")
        self._add_name.delete(0, "end")
        self._add_amount.delete(0, "end")
        self._set_add_status(f'"{name}" added.', error=False)
        self._refresh()

    def _delete(self, expense_id: int, name: str):
        if not self._confirm_dialog(
            f'Delete "{name}"? This cannot be undone.', confirm_text="Delete"
        ):
            return
        delete_expense(expense_id)
        self._expenses_row_vars.pop(expense_id, None)
        self._refresh()

    # ── Income actions ─────────────────────────────────────────────────────────

    def _add_income_item(self):
        name       = self._inc_add_name.get().strip()
        amount_str = self._inc_add_amount.get().strip()
        if not name:
            self._set_inc_add_status("Name is required.", error=True)
            return
        try:
            amount = float(amount_str or "0")
            if amount < 0:
                raise ValueError
        except ValueError:
            self._set_inc_add_status("Invalid amount.", error=True)
            return
        active = [m for m in range(1, 13) if self._inc_add_months_vars[m].get()]
        if not active:
            self._set_inc_add_status("Select at least one active month.", error=True)
            return
        active_months_str = None if len(active) == 12 else ",".join(str(m) for m in active)
        add_income(name, amount, 0, "fixed", active_months_str)
        self._inc_add_name.delete(0, "end")
        self._inc_add_amount.delete(0, "end")
        for v in self._inc_add_months_vars.values():
            v.set(True)
        self._set_inc_add_status(f'"{name}" added.', error=False)
        self._refresh_income()

    def _delete_income_item(self, income_id: int, name: str):
        if not self._confirm_dialog(
            f'Delete "{name}"? This cannot be undone.', confirm_text="Delete"
        ):
            return
        delete_income(income_id)
        self._income_row_vars.pop(income_id, None)
        self._refresh_income()

    # ── Status helpers ─────────────────────────────────────────────────────────

    def _set_add_status(self, text: str, *, error: bool):
        color = _RED if error else _GREEN
        self._add_status.configure(text=text, text_color=color)
        if not error:
            self.after(3000, lambda: self._add_status.configure(text=""))

    def _set_inc_add_status(self, text: str, *, error: bool):
        color = _RED if error else _GREEN
        self._inc_add_status.configure(text=text, text_color=color)
        if not error:
            self.after(3000, lambda: self._inc_add_status.configure(text=""))

    def _confirm_dialog(
        self, message: str, *, confirm_text: str = "Confirm", cancel_text: str = "Cancel"
    ) -> bool:
        result = [False]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.resizable(False, False)
        center_on_parent(dialog, self, 440, 150)
        dialog.grab_set()
        dialog.focus_set()
        ctk.CTkLabel(
            dialog, text=message, wraplength=400, justify="left",
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
