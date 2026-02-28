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
    get_setting,
    set_setting,
)
from utils import fmt_eur

# Column widths — must match between header and rows
_W_DAY    = 60
_W_NAME   = 260
_W_AMOUNT = 130

_GREEN = "#2CC985"
_RED   = "#E74C3C"


class ExpensesView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._editing_id:         int | None = None
        self._selected_id:        int | None = None
        self._edit_status_label:  ctk.CTkLabel | None = None
        self._toolbar_status:     ctk.CTkLabel | None = None

        # Income section state
        self._income_editing_id:         int | None = None
        self._income_selected_id:        int | None = None
        self._income_edit_status_label:  ctk.CTkLabel | None = None
        self._income_toolbar_status:     ctk.CTkLabel | None = None

        self._editing_allowance = False
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Expenses",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Manage your fixed recurring expenses, monthly income, and daily spending allowance.",
            text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # ══ Fixed Monthly Expenses section ════════════════════════════════════
        ctk.CTkLabel(
            self, text="Fixed Monthly Expenses",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        # ── Add expense form ──────────────────────────────────────────────────
        add_card = ctk.CTkFrame(self)
        add_card.pack(fill="x", padx=24, pady=(0, 16))

        form = ctk.CTkFrame(add_card, fg_color="transparent")
        form.pack(anchor="w", padx=16, pady=14)

        ctk.CTkLabel(form, text="Day", anchor="w").pack(side="left", padx=(0, 4))
        self._add_day = ctk.CTkEntry(form, placeholder_text="1–31", width=60)
        self._add_day.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(form, text="Name", anchor="w").pack(side="left", padx=(0, 4))
        self._add_name = ctk.CTkEntry(form, placeholder_text="Expense name", width=240)
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

        # ── Shared toolbar (Edit / Delete act on selected row) ─────────────────
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(anchor="w", padx=24, pady=(0, 4))

        ctk.CTkButton(
            toolbar, text="Edit", width=64,
            fg_color="transparent", border_width=1,
            command=self._edit_selected,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            toolbar, text="Delete", width=72,
            fg_color="transparent", border_width=1,
            text_color=("#C0392B", "#E74C3C"),
            hover_color=("gray85", "gray20"),
            command=self._delete_selected,
        ).pack(side="left")
        self._toolbar_status = ctk.CTkLabel(
            toolbar, text="Click a row to select it.",
            text_color="gray", font=ctk.CTkFont(size=12),
        )
        self._toolbar_status.pack(side="left", padx=(12, 0))

        # ── Column headers ────────────────────────────────────────────────────
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

        # ── Dynamic list ──────────────────────────────────────────────────────
        self._list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._list_frame.pack(anchor="w", padx=24, fill="x")

        # ── Monthly total ─────────────────────────────────────────────────────
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

        # ══ Monthly Income section ════════════════════════════════════════════
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(0, 20)
        )
        ctk.CTkLabel(
            self, text="Monthly Income",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(0, 6))
        ctk.CTkLabel(
            self,
            text="Regular income sources. Use day 0 for variable or irregular payments.",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        # ── Add income form ───────────────────────────────────────────────────
        inc_add_card = ctk.CTkFrame(self)
        inc_add_card.pack(fill="x", padx=24, pady=(0, 16))

        inc_form = ctk.CTkFrame(inc_add_card, fg_color="transparent")
        inc_form.pack(anchor="w", padx=16, pady=14)

        ctk.CTkLabel(inc_form, text="Day", anchor="w").pack(side="left", padx=(0, 4))
        self._inc_add_day = ctk.CTkEntry(inc_form, placeholder_text="0–31", width=60)
        self._inc_add_day.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(inc_form, text="Name", anchor="w").pack(side="left", padx=(0, 4))
        self._inc_add_name = ctk.CTkEntry(inc_form, placeholder_text="Income source", width=240)
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

        # ── Income toolbar ────────────────────────────────────────────────────
        inc_toolbar = ctk.CTkFrame(self, fg_color="transparent")
        inc_toolbar.pack(anchor="w", padx=24, pady=(0, 4))

        ctk.CTkButton(
            inc_toolbar, text="Edit", width=64,
            fg_color="transparent", border_width=1,
            command=self._income_edit_selected,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            inc_toolbar, text="Delete", width=72,
            fg_color="transparent", border_width=1,
            text_color=("#C0392B", "#E74C3C"),
            hover_color=("gray85", "gray20"),
            command=self._income_delete_selected,
        ).pack(side="left")
        self._income_toolbar_status = ctk.CTkLabel(
            inc_toolbar, text="Click a row to select it.",
            text_color="gray", font=ctk.CTkFont(size=12),
        )
        self._income_toolbar_status.pack(side="left", padx=(12, 0))

        # ── Income column headers ─────────────────────────────────────────────
        inc_header = ctk.CTkFrame(self, fg_color="transparent")
        inc_header.pack(anchor="w", padx=24, pady=(0, 2))
        for text, width, anchor in [
            ("Day",    _W_DAY,    "w"),
            ("Name",   _W_NAME,   "w"),
            ("Amount", _W_AMOUNT, "e"),
        ]:
            ctk.CTkLabel(
                inc_header, text=text, width=width, anchor=anchor,
                text_color="gray", font=ctk.CTkFont(size=12),
            ).pack(side="left")

        self._income_list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._income_list_frame.pack(anchor="w", padx=24, fill="x")

        # ── Income monthly total ──────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(16, 10)
        )
        inc_total_row = ctk.CTkFrame(self, fg_color="transparent")
        inc_total_row.pack(anchor="w", padx=24, pady=(0, 28))
        ctk.CTkLabel(
            inc_total_row, text="Expected monthly income:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        self._income_total_label = ctk.CTkLabel(
            inc_total_row, text="€0,00",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._income_total_label.pack(side="left")

        # ══ Variable Expenses section ═════════════════════════════════════════
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(0, 20)
        )
        ctk.CTkLabel(
            self, text="Variable Expenses",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        var_card = ctk.CTkFrame(self)
        var_card.pack(fill="x", padx=24, pady=(0, 32))
        var_inner = ctk.CTkFrame(var_card, fg_color="transparent")
        var_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            var_inner, text="DAILY SPENDING ALLOWANCE",
            text_color="gray", font=ctk.CTkFont(size=11),
        ).pack(anchor="w")
        ctk.CTkLabel(
            var_inner,
            text="Used for mid-month estimation: the amount budgeted per day for variable spending (food, transport, leisure, etc.).",
            text_color="gray", font=ctk.CTkFont(size=12),
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(2, 10))

        self._allowance_row = ctk.CTkFrame(var_inner, fg_color="transparent")
        self._allowance_row.pack(anchor="w")

        self._refresh_allowance_row()
        self._refresh()
        self._refresh_income()

    # ── Fixed expenses list rendering ─────────────────────────────────────────

    def _refresh(self):
        for child in self._list_frame.winfo_children():
            child.destroy()
        self._edit_status_label = None

        expenses = get_all_expenses()
        for exp in expenses:
            if exp["id"] == self._editing_id:
                self._render_edit_row(dict(exp))
            else:
                self._render_display_row(dict(exp))

        total = sum(e["amount"] for e in expenses)
        self._total_label.configure(text=fmt_eur(total))

    def _render_display_row(self, exp: dict):
        is_selected = exp["id"] == self._selected_id
        bg = ("gray82", "gray28") if is_selected else "transparent"

        row = ctk.CTkFrame(self._list_frame, fg_color=bg)
        row.pack(anchor="w", pady=2, fill="x")

        lbl_day    = ctk.CTkLabel(row, text=str(exp["day_of_month"]), width=_W_DAY,    anchor="w")
        lbl_name   = ctk.CTkLabel(row, text=exp["name"],              width=_W_NAME,   anchor="w")
        lbl_amount = ctk.CTkLabel(row, text=fmt_eur(exp["amount"]),   width=_W_AMOUNT, anchor="e")

        lbl_day.pack(side="left")
        lbl_name.pack(side="left")
        lbl_amount.pack(side="left", padx=(0, 8))

        def on_click(_event=None, eid=exp["id"]):
            self._select_expense(eid)

        for widget in (row, lbl_day, lbl_name, lbl_amount):
            widget.bind("<Button-1>", on_click)

    def _render_edit_row(self, exp: dict):
        row = ctk.CTkFrame(self._list_frame, fg_color=("gray88", "gray22"))
        row.pack(anchor="w", pady=2, fill="x")

        day_var    = ctk.StringVar(value=str(exp["day_of_month"]))
        name_var   = ctk.StringVar(value=exp["name"])
        amount_var = ctk.StringVar(value=f"{exp['amount']:.2f}")

        ctk.CTkEntry(row, textvariable=day_var,    width=_W_DAY).pack(   side="left", padx=(8, 6), pady=6)
        ctk.CTkEntry(row, textvariable=name_var,   width=_W_NAME).pack(  side="left", padx=(0, 6), pady=6)
        ctk.CTkEntry(row, textvariable=amount_var, width=_W_AMOUNT).pack(side="left", padx=(0, 16), pady=6)

        ctk.CTkButton(
            row, text="Save", width=64,
            command=lambda: self._save_edit(exp["id"], day_var, name_var, amount_var),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            row, text="Cancel", width=72,
            fg_color="transparent", border_width=1,
            command=self._cancel_edit,
        ).pack(side="left", padx=(0, 8))

        self._edit_status_label = ctk.CTkLabel(row, text="")
        self._edit_status_label.pack(side="left")

    # ── Income list rendering ─────────────────────────────────────────────────

    def _refresh_income(self):
        for child in self._income_list_frame.winfo_children():
            child.destroy()
        self._income_edit_status_label = None

        income_items = get_all_income()
        for item in income_items:
            if item["id"] == self._income_editing_id:
                self._render_income_edit_row(dict(item))
            else:
                self._render_income_display_row(dict(item))

        total = sum(i["amount"] for i in income_items)
        self._income_total_label.configure(text=fmt_eur(total))

    def _render_income_display_row(self, item: dict):
        is_selected = item["id"] == self._income_selected_id
        bg = ("gray82", "gray28") if is_selected else "transparent"

        row = ctk.CTkFrame(self._income_list_frame, fg_color=bg)
        row.pack(anchor="w", pady=2, fill="x")

        day_text = "Variable" if item["day_of_month"] == 0 else str(item["day_of_month"])
        lbl_day    = ctk.CTkLabel(row, text=day_text,           width=_W_DAY,    anchor="w")
        lbl_name   = ctk.CTkLabel(row, text=item["name"],       width=_W_NAME,   anchor="w")
        lbl_amount = ctk.CTkLabel(row, text=fmt_eur(item["amount"]), width=_W_AMOUNT, anchor="e")

        lbl_day.pack(side="left")
        lbl_name.pack(side="left")
        lbl_amount.pack(side="left", padx=(0, 8))

        def on_click(_event=None, iid=item["id"]):
            self._select_income(iid)

        for widget in (row, lbl_day, lbl_name, lbl_amount):
            widget.bind("<Button-1>", on_click)

    def _render_income_edit_row(self, item: dict):
        row = ctk.CTkFrame(self._income_list_frame, fg_color=("gray88", "gray22"))
        row.pack(anchor="w", pady=2, fill="x")

        day_val    = str(item["day_of_month"])
        day_var    = ctk.StringVar(value=day_val)
        name_var   = ctk.StringVar(value=item["name"])
        amount_var = ctk.StringVar(value=f"{item['amount']:.2f}")

        ctk.CTkEntry(row, textvariable=day_var,    width=_W_DAY).pack(   side="left", padx=(8, 6), pady=6)
        ctk.CTkEntry(row, textvariable=name_var,   width=_W_NAME).pack(  side="left", padx=(0, 6), pady=6)
        ctk.CTkEntry(row, textvariable=amount_var, width=_W_AMOUNT).pack(side="left", padx=(0, 16), pady=6)

        ctk.CTkButton(
            row, text="Save", width=64,
            command=lambda: self._income_save_edit(item["id"], day_var, name_var, amount_var),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            row, text="Cancel", width=72,
            fg_color="transparent", border_width=1,
            command=self._income_cancel_edit,
        ).pack(side="left", padx=(0, 8))

        self._income_edit_status_label = ctk.CTkLabel(row, text="")
        self._income_edit_status_label.pack(side="left")

    # ── Allowance row ─────────────────────────────────────────────────────────

    def _refresh_allowance_row(self):
        for w in self._allowance_row.winfo_children():
            w.destroy()

        daily = float(get_setting("daily_buffer") or "20.0")

        if self._editing_allowance:
            allowance_var = ctk.StringVar(value=f"{daily:.2f}")
            ctk.CTkEntry(
                self._allowance_row, textvariable=allowance_var, width=100,
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                self._allowance_row, text="EUR / day",
                font=ctk.CTkFont(size=13),
            ).pack(side="left", padx=(0, 14))
            ctk.CTkButton(
                self._allowance_row, text="Save", width=72,
                command=lambda v=allowance_var: self._save_allowance(v),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                self._allowance_row, text="Cancel", width=72,
                fg_color="transparent", border_width=1,
                command=self._cancel_allowance_edit,
            ).pack(side="left")
        else:
            ctk.CTkLabel(
                self._allowance_row,
                text=f"{fmt_eur(daily)} / day",
                font=ctk.CTkFont(size=20, weight="bold"),
            ).pack(side="left", padx=(0, 14))
            ctk.CTkButton(
                self._allowance_row, text="Edit", width=64,
                fg_color="transparent", border_width=1,
                command=self._start_allowance_edit,
            ).pack(side="left")

    def _start_allowance_edit(self):
        self._editing_allowance = True
        self._refresh_allowance_row()

    def _save_allowance(self, var: ctk.StringVar):
        try:
            value = float(var.get().strip())
            if value <= 0:
                raise ValueError
        except ValueError:
            return
        set_setting("daily_buffer", str(value))
        self._editing_allowance = False
        self._refresh_allowance_row()

    def _cancel_allowance_edit(self):
        self._editing_allowance = False
        self._refresh_allowance_row()

    # ── Fixed expense row selection ───────────────────────────────────────────

    def _select_expense(self, expense_id: int):
        self._selected_id = expense_id
        self._editing_id  = None
        if self._toolbar_status:
            self._toolbar_status.configure(text="")
        self._refresh()

    def _edit_selected(self):
        if self._selected_id is None:
            if self._toolbar_status:
                self._toolbar_status.configure(
                    text="Select an expense first.", text_color="gray"
                )
            return
        self._start_edit(self._selected_id)

    def _delete_selected(self):
        if self._selected_id is None:
            if self._toolbar_status:
                self._toolbar_status.configure(
                    text="Select an expense first.", text_color="gray"
                )
            return
        expenses = list(get_all_expenses())
        exp = next((e for e in expenses if e["id"] == self._selected_id), None)
        if exp is None:
            return
        self._delete(self._selected_id, exp["name"])

    # ── Income row selection ──────────────────────────────────────────────────

    def _select_income(self, income_id: int):
        self._income_selected_id = income_id
        self._income_editing_id  = None
        if self._income_toolbar_status:
            self._income_toolbar_status.configure(text="")
        self._refresh_income()

    def _income_edit_selected(self):
        if self._income_selected_id is None:
            if self._income_toolbar_status:
                self._income_toolbar_status.configure(
                    text="Select an income source first.", text_color="gray"
                )
            return
        self._income_editing_id = self._income_selected_id
        self._refresh_income()

    def _income_delete_selected(self):
        if self._income_selected_id is None:
            if self._income_toolbar_status:
                self._income_toolbar_status.configure(
                    text="Select an income source first.", text_color="gray"
                )
            return
        items = list(get_all_income())
        item = next((i for i in items if i["id"] == self._income_selected_id), None)
        if item is None:
            return
        self._delete_income_item(self._income_selected_id, item["name"])

    # ── Fixed expense actions ─────────────────────────────────────────────────

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

    def _start_edit(self, expense_id: int):
        self._editing_id = expense_id
        self._refresh()

    def _save_edit(
        self,
        expense_id: int,
        day_var: ctk.StringVar,
        name_var: ctk.StringVar,
        amount_var: ctk.StringVar,
    ):
        try:
            day = int(day_var.get().strip())
            if not 1 <= day <= 31:
                raise ValueError
        except ValueError:
            self._set_edit_status("Day must be 1–31.", error=True)
            return
        name = name_var.get().strip()
        if not name:
            self._set_edit_status("Name is required.", error=True)
            return
        try:
            amount = float(amount_var.get().strip())
        except ValueError:
            self._set_edit_status("Invalid amount.", error=True)
            return

        update_expense(expense_id, name, amount, day)
        self._editing_id = None
        self._refresh()

    def _cancel_edit(self):
        self._editing_id = None
        self._refresh()

    def _delete(self, expense_id: int, name: str = "this expense"):
        if not self._confirm_dialog(
            f'Delete "{name}"? This cannot be undone.',
            confirm_text="Delete",
        ):
            return
        delete_expense(expense_id)
        if self._editing_id == expense_id:
            self._editing_id = None
        if self._selected_id == expense_id:
            self._selected_id = None
        self._refresh()

    # ── Income actions ────────────────────────────────────────────────────────

    def _add_income_item(self):
        day_str    = self._inc_add_day.get().strip()
        name       = self._inc_add_name.get().strip()
        amount_str = self._inc_add_amount.get().strip()

        try:
            day = int(day_str)
            if not 0 <= day <= 31:
                raise ValueError
        except ValueError:
            self._set_inc_add_status("Day must be 0–31 (0 = Variable).", error=True)
            return
        if not name:
            self._set_inc_add_status("Name is required.", error=True)
            return
        try:
            amount = float(amount_str)
            if amount < 0:
                raise ValueError
        except ValueError:
            self._set_inc_add_status("Invalid amount.", error=True)
            return

        add_income(name, amount, day)
        self._inc_add_day.delete(0, "end")
        self._inc_add_name.delete(0, "end")
        self._inc_add_amount.delete(0, "end")
        self._set_inc_add_status(f'"{name}" added.', error=False)
        self._refresh_income()

    def _income_save_edit(
        self,
        income_id: int,
        day_var: ctk.StringVar,
        name_var: ctk.StringVar,
        amount_var: ctk.StringVar,
    ):
        try:
            day = int(day_var.get().strip())
            if not 0 <= day <= 31:
                raise ValueError
        except ValueError:
            self._set_income_edit_status("Day must be 0–31.", error=True)
            return
        name = name_var.get().strip()
        if not name:
            self._set_income_edit_status("Name is required.", error=True)
            return
        try:
            amount = float(amount_var.get().strip())
            if amount < 0:
                raise ValueError
        except ValueError:
            self._set_income_edit_status("Invalid amount.", error=True)
            return

        update_income(income_id, name, amount, day)
        self._income_editing_id = None
        self._refresh_income()

    def _income_cancel_edit(self):
        self._income_editing_id = None
        self._refresh_income()

    def _delete_income_item(self, income_id: int, name: str = "this income source"):
        if not self._confirm_dialog(
            f'Delete "{name}"? This cannot be undone.',
            confirm_text="Delete",
        ):
            return
        delete_income(income_id)
        if self._income_editing_id == income_id:
            self._income_editing_id = None
        if self._income_selected_id == income_id:
            self._income_selected_id = None
        self._refresh_income()

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_add_status(self, text: str, *, error: bool):
        color = "#E74C3C" if error else "#2CC985"
        self._add_status.configure(text=text, text_color=color)
        if not error:
            self.after(3000, lambda: self._add_status.configure(text=""))

    def _set_edit_status(self, text: str, *, error: bool):
        if self._edit_status_label is None:
            return
        color = "#E74C3C" if error else "#2CC985"
        self._edit_status_label.configure(text=text, text_color=color)

    def _set_inc_add_status(self, text: str, *, error: bool):
        color = "#E74C3C" if error else "#2CC985"
        self._inc_add_status.configure(text=text, text_color=color)
        if not error:
            self.after(3000, lambda: self._inc_add_status.configure(text=""))

    def _set_income_edit_status(self, text: str, *, error: bool):
        if self._income_edit_status_label is None:
            return
        self._income_edit_status_label.configure(
            text=text, text_color="#E74C3C" if error else "#2CC985"
        )

    def _confirm_dialog(
        self, message: str, *, confirm_text: str = "Confirm", cancel_text: str = "Cancel"
    ) -> bool:
        result = [False]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm")
        dialog.geometry("440x150")
        dialog.resizable(False, False)
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
