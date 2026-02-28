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
_W_NAME   = 220
_W_TYPE   = 100
_W_AMOUNT = 130

_GREEN = "#2CC985"
_RED   = "#E74C3C"

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_INCOME_TYPES = ["Fixed", "Seasonal", "Variable"]


class ExpensesView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")

        # Fixed expenses state
        self._expenses_edit_mode: bool = False
        self._editing_id:         int | None = None
        self._edit_status_label:  ctk.CTkLabel | None = None
        self._expenses_toggle_btn: ctk.CTkButton | None = None

        # Income state
        self._income_edit_mode:        bool = False
        self._income_editing_id:       int | None = None
        self._income_edit_status_label: ctk.CTkLabel | None = None
        self._income_toggle_btn:       ctk.CTkButton | None = None

        # Income add-form dynamic state
        self._income_type_var: ctk.StringVar = ctk.StringVar(value="Fixed")
        self._inc_add_months_vars: dict[int, ctk.BooleanVar] = {
            m: ctk.BooleanVar(value=False) for m in range(1, 13)
        }
        self._inc_month_checkboxes_frame: ctk.CTkFrame | None = None
        self._inc_add_day_entry: ctk.CTkEntry | None = None
        self._inc_day_label: ctk.CTkLabel | None = None

        self._editing_allowance = False
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Budget",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Manage your fixed recurring expenses, monthly income, and daily spending allowance.",
            text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # ══ Fixed Monthly Expenses section ════════════════════════════════════

        # Section header row with Edit toggle
        exp_hdr = ctk.CTkFrame(self, fg_color="transparent")
        exp_hdr.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(
            exp_hdr, text="Fixed Monthly Expenses",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        self._expenses_toggle_btn = ctk.CTkButton(
            exp_hdr, text="Edit", width=64,
            fg_color="transparent", border_width=1,
            command=self._toggle_expenses_edit,
        )
        self._expenses_toggle_btn.pack(side="right")

        # ── Add expense form ──────────────────────────────────────────────────
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

        # ── Column headers ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(anchor="w", padx=24, pady=(0, 2))
        for text, width, anchor in [
            ("Day",    _W_DAY,    "w"),
            ("Name",   _W_NAME,   "w"),
            ("",       _W_TYPE,   "w"),   # spacer for type column
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

        # Section header row with Edit toggle
        inc_hdr = ctk.CTkFrame(self, fg_color="transparent")
        inc_hdr.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkLabel(
            inc_hdr, text="Monthly Income",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        self._income_toggle_btn = ctk.CTkButton(
            inc_hdr, text="Edit", width=64,
            fg_color="transparent", border_width=1,
            command=self._toggle_income_edit,
        )
        self._income_toggle_btn.pack(side="right")

        ctk.CTkLabel(
            self,
            text="Regular income sources. Fixed = every month, Seasonal = selected months, Variable = reminder only.",
            text_color="gray", font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        # ── Add income form ───────────────────────────────────────────────────
        inc_add_card = ctk.CTkFrame(self)
        inc_add_card.pack(fill="x", padx=24, pady=(0, 16))

        inc_form_outer = ctk.CTkFrame(inc_add_card, fg_color="transparent")
        inc_form_outer.pack(anchor="w", padx=16, pady=14, fill="x")

        # Row 1: type selector
        type_row = ctk.CTkFrame(inc_form_outer, fg_color="transparent")
        type_row.pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(type_row, text="Type:", anchor="w").pack(side="left", padx=(0, 8))
        ctk.CTkSegmentedButton(
            type_row,
            values=_INCOME_TYPES,
            variable=self._income_type_var,
            command=self._on_income_type_change,
            width=240,
        ).pack(side="left")

        # Row 2: fields
        inc_form = ctk.CTkFrame(inc_form_outer, fg_color="transparent")
        inc_form.pack(anchor="w")

        self._inc_day_label = ctk.CTkLabel(inc_form, text="Day", anchor="w")
        self._inc_day_label.pack(side="left", padx=(0, 4))
        self._inc_add_day = ctk.CTkEntry(inc_form, placeholder_text="0–31", width=60)
        self._inc_add_day.pack(side="left", padx=(0, 14))

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

        # Row 3: month checkboxes (shown for Seasonal only)
        self._inc_month_checkboxes_frame = ctk.CTkFrame(inc_form_outer, fg_color="transparent")
        # Not packed initially (shown only when Seasonal is selected)

        months_inner = ctk.CTkFrame(self._inc_month_checkboxes_frame, fg_color="transparent")
        months_inner.pack(anchor="w")
        ctk.CTkLabel(months_inner, text="Active months:", anchor="w",
                     text_color="gray", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        for m in range(1, 13):
            ctk.CTkCheckBox(
                months_inner, text=_MONTHS_SHORT[m - 1], width=56,
                variable=self._inc_add_months_vars[m],
            ).pack(side="left", padx=(0, 4))

        # ── Income column headers ─────────────────────────────────────────────
        inc_col_hdr = ctk.CTkFrame(self, fg_color="transparent")
        inc_col_hdr.pack(anchor="w", padx=24, pady=(0, 2))
        for text, width, anchor in [
            ("Day",    _W_DAY,    "w"),
            ("Name",   _W_NAME,   "w"),
            ("Type",   _W_TYPE,   "w"),
            ("Amount", _W_AMOUNT, "e"),
        ]:
            ctk.CTkLabel(
                inc_col_hdr, text=text, width=width, anchor=anchor,
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

    # ── Income type change ────────────────────────────────────────────────────

    def _on_income_type_change(self, value: str):
        is_seasonal = (value == "Seasonal")
        is_fixed    = (value == "Fixed")

        # Show/hide month checkboxes
        if is_seasonal:
            if self._inc_month_checkboxes_frame and \
               self._inc_month_checkboxes_frame.winfo_manager() != "pack":
                self._inc_month_checkboxes_frame.pack(anchor="w", pady=(8, 0))
        else:
            if self._inc_month_checkboxes_frame and \
               self._inc_month_checkboxes_frame.winfo_manager() == "pack":
                self._inc_month_checkboxes_frame.pack_forget()

        # Show/hide Day field (only for Fixed type)
        if self._inc_day_label and self._inc_add_day:
            if is_fixed:
                if self._inc_day_label.winfo_manager() != "pack":
                    self._inc_day_label.pack(side="left", padx=(0, 4), before=self._inc_add_day)
                if self._inc_add_day.winfo_manager() != "pack":
                    self._inc_add_day.pack(side="left", padx=(0, 14))
            else:
                if self._inc_day_label.winfo_manager() == "pack":
                    self._inc_day_label.pack_forget()
                if self._inc_add_day.winfo_manager() == "pack":
                    self._inc_add_day.pack_forget()

    def _get_inc_active_months_str(self) -> str | None:
        active = [str(m) for m in range(1, 13) if self._inc_add_months_vars[m].get()]
        return ",".join(active) if active else None

    # ── Fixed expenses section edit toggle ────────────────────────────────────

    def _toggle_expenses_edit(self):
        self._expenses_edit_mode = not self._expenses_edit_mode
        if self._expenses_toggle_btn:
            self._expenses_toggle_btn.configure(
                text="Done" if self._expenses_edit_mode else "Edit"
            )
        if not self._expenses_edit_mode:
            self._editing_id = None
        self._refresh()

    # ── Income section edit toggle ────────────────────────────────────────────

    def _toggle_income_edit(self):
        self._income_edit_mode = not self._income_edit_mode
        if self._income_toggle_btn:
            self._income_toggle_btn.configure(
                text="Done" if self._income_edit_mode else "Edit"
            )
        if not self._income_edit_mode:
            self._income_editing_id = None
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
        row = ctk.CTkFrame(self._list_frame, fg_color="transparent")
        row.pack(anchor="w", pady=2, fill="x")

        ctk.CTkLabel(row, text=str(exp["day_of_month"]), width=_W_DAY,    anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=exp["name"],              width=_W_NAME,   anchor="w").pack(side="left")
        ctk.CTkLabel(row, text="",                       width=_W_TYPE,   anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=fmt_eur(exp["amount"]),   width=_W_AMOUNT, anchor="e").pack(side="left", padx=(0, 8))

        if self._expenses_edit_mode:
            ctk.CTkButton(
                row, text="Edit", width=56,
                fg_color="transparent", border_width=1,
                font=ctk.CTkFont(size=11),
                command=lambda eid=exp["id"]: self._start_edit(eid),
            ).pack(side="left", padx=(4, 4))
            ctk.CTkButton(
                row, text="×", width=36, height=32,
                fg_color="transparent", border_width=1,
                text_color=("gray40", "gray60"),
                hover_color=("gray85", "gray25"),
                command=lambda eid=exp["id"], n=exp["name"]: self._delete(eid, n),
            ).pack(side="left")

    def _render_edit_row(self, exp: dict):
        row = ctk.CTkFrame(self._list_frame, fg_color=("gray88", "gray22"))
        row.pack(anchor="w", pady=2, fill="x")

        day_var    = ctk.StringVar(value=str(exp["day_of_month"]))
        name_var   = ctk.StringVar(value=exp["name"])
        amount_var = ctk.StringVar(value=f"{exp['amount']:.2f}")

        ctk.CTkEntry(row, textvariable=day_var,    width=_W_DAY).pack(   side="left", padx=(8, 6), pady=6)
        ctk.CTkEntry(row, textvariable=name_var,   width=_W_NAME).pack(  side="left", padx=(0, 6), pady=6)
        ctk.CTkLabel(row, text="",                 width=_W_TYPE).pack(  side="left")
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

    def refresh(self):
        self._refresh()
        self._refresh_income()

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

        # Expected monthly income = sum of fixed incomes + seasonal incomes (all months avg)
        total = sum(i["amount"] for i in income_items)
        self._income_total_label.configure(text=fmt_eur(total))

    def _income_type_label(self, item: dict) -> str:
        t = item.get("income_type", "fixed")
        if t == "fixed":
            return "Fixed"
        if t == "seasonal":
            active = item.get("active_months") or ""
            if active:
                nums = [int(x) for x in active.split(",") if x.strip().isdigit()]
                abbrs = [_MONTHS_SHORT[m - 1] for m in nums if 1 <= m <= 12]
                return "Seasonal: " + ", ".join(abbrs)
            return "Seasonal"
        return "Variable"

    def _render_income_display_row(self, item: dict):
        row = ctk.CTkFrame(self._income_list_frame, fg_color="transparent")
        row.pack(anchor="w", pady=2, fill="x")

        income_type = item.get("income_type", "fixed")
        if income_type == "fixed":
            day_text = "Variable" if item["day_of_month"] == 0 else str(item["day_of_month"])
        else:
            day_text = "—"

        type_display = self._income_type_label(item)
        type_color   = ("gray60", "gray50")

        ctk.CTkLabel(row, text=day_text,               width=_W_DAY,    anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=item["name"],           width=_W_NAME,   anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=type_display,           width=_W_TYPE,   anchor="w",
                     text_color=type_color, font=ctk.CTkFont(size=11),
                     wraplength=_W_TYPE).pack(side="left")
        ctk.CTkLabel(row, text=fmt_eur(item["amount"]), width=_W_AMOUNT, anchor="e").pack(side="left", padx=(0, 8))

        if self._income_edit_mode:
            ctk.CTkButton(
                row, text="Edit", width=56,
                fg_color="transparent", border_width=1,
                font=ctk.CTkFont(size=11),
                command=lambda iid=item["id"]: self._income_start_edit(iid),
            ).pack(side="left", padx=(4, 4))
            ctk.CTkButton(
                row, text="×", width=36, height=32,
                fg_color="transparent", border_width=1,
                text_color=("gray40", "gray60"),
                hover_color=("gray85", "gray25"),
                command=lambda iid=item["id"], n=item["name"]: self._delete_income_item(iid, n),
            ).pack(side="left")

    def _render_income_edit_row(self, item: dict):
        row = ctk.CTkFrame(self._income_list_frame, fg_color=("gray88", "gray22"))
        row.pack(anchor="w", pady=2, fill="x")

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(anchor="w", padx=8, pady=8, fill="x")

        income_type = item.get("income_type", "fixed")
        type_var    = ctk.StringVar(value=income_type.capitalize())
        day_var     = ctk.StringVar(value=str(item["day_of_month"]))
        name_var    = ctk.StringVar(value=item["name"])
        amount_var  = ctk.StringVar(value=f"{item['amount']:.2f}")

        active_months_str = item.get("active_months") or ""
        month_vars: dict[int, ctk.BooleanVar] = {}
        for m in range(1, 13):
            active = str(m) in active_months_str.split(",")
            month_vars[m] = ctk.BooleanVar(value=active)

        # Row 1: type + fields
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(anchor="w")

        type_btn = ctk.CTkSegmentedButton(row1, values=_INCOME_TYPES, variable=type_var, width=220)
        type_btn.pack(side="left", padx=(0, 10))

        ctk.CTkEntry(row1, textvariable=name_var, width=220).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(row1, text="EUR").pack(side="left", padx=(0, 4))
        ctk.CTkEntry(row1, textvariable=amount_var, width=100).pack(side="left", padx=(0, 10))

        day_lbl   = ctk.CTkLabel(row1, text="Day")
        day_entry = ctk.CTkEntry(row1, textvariable=day_var, width=60)

        def refresh_type_fields(*_):
            t = type_var.get()
            if t == "Fixed":
                if day_lbl.winfo_manager() != "pack":
                    day_lbl.pack(side="left", padx=(0, 4))
                if day_entry.winfo_manager() != "pack":
                    day_entry.pack(side="left", padx=(0, 10))
            else:
                if day_lbl.winfo_manager() == "pack":
                    day_lbl.pack_forget()
                if day_entry.winfo_manager() == "pack":
                    day_entry.pack_forget()
            if t == "Seasonal":
                if months_row.winfo_manager() != "pack":
                    months_row.pack(anchor="w", pady=(6, 0))
            else:
                if months_row.winfo_manager() == "pack":
                    months_row.pack_forget()

        type_var.trace_add("write", refresh_type_fields)

        # Row 2: month checkboxes (Seasonal)
        months_row = ctk.CTkFrame(inner, fg_color="transparent")
        months_inner = ctk.CTkFrame(months_row, fg_color="transparent")
        months_inner.pack(anchor="w")
        ctk.CTkLabel(months_inner, text="Active months:", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
        for m in range(1, 13):
            ctk.CTkCheckBox(
                months_inner, text=_MONTHS_SHORT[m - 1], width=56,
                variable=month_vars[m],
            ).pack(side="left", padx=(0, 4))

        # Row 3: Save / Cancel
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(6, 0))

        self._income_edit_status_label = ctk.CTkLabel(btn_row, text="")

        def do_save():
            active_str: str | None = None
            if type_var.get() == "Seasonal":
                active = [str(m) for m in range(1, 13) if month_vars[m].get()]
                active_str = ",".join(active) if active else None
            day_val = 0
            if type_var.get() == "Fixed":
                try:
                    day_val = int(day_var.get().strip())
                    if not 0 <= day_val <= 31:
                        raise ValueError
                except ValueError:
                    if self._income_edit_status_label:
                        self._income_edit_status_label.configure(
                            text="Day must be 0–31.", text_color=_RED
                        )
                    return
            name = name_var.get().strip()
            if not name:
                if self._income_edit_status_label:
                    self._income_edit_status_label.configure(
                        text="Name required.", text_color=_RED
                    )
                return
            try:
                amount = float(amount_var.get().strip())
                if amount < 0:
                    raise ValueError
            except ValueError:
                if self._income_edit_status_label:
                    self._income_edit_status_label.configure(
                        text="Invalid amount.", text_color=_RED
                    )
                return
            income_type_db = type_var.get().lower()
            update_income(item["id"], name, amount, day_val, income_type_db, active_str)
            self._income_editing_id = None
            self._refresh_income()

        ctk.CTkButton(btn_row, text="Save", width=64, command=do_save).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row, text="Cancel", width=72,
            fg_color="transparent", border_width=1,
            command=self._income_cancel_edit,
        ).pack(side="left", padx=(0, 8))
        self._income_edit_status_label.pack(side="left")

        # Apply initial type-specific visibility
        refresh_type_fields()

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
        self._refresh()

    # ── Income actions ────────────────────────────────────────────────────────

    def _add_income_item(self):
        income_type = self._income_type_var.get().lower()
        name        = self._inc_add_name.get().strip()
        amount_str  = self._inc_add_amount.get().strip()

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

        day = 0
        active_months_str: str | None = None

        if income_type == "fixed":
            day_str = self._inc_add_day.get().strip()
            try:
                day = int(day_str)
                if not 0 <= day <= 31:
                    raise ValueError
            except ValueError:
                self._set_inc_add_status("Day must be 0–31 (0 = Variable).", error=True)
                return
        elif income_type == "seasonal":
            active_months_str = self._get_inc_active_months_str()
            if not active_months_str:
                self._set_inc_add_status("Select at least one active month.", error=True)
                return

        add_income(name, amount, day, income_type, active_months_str)
        self._inc_add_name.delete(0, "end")
        self._inc_add_amount.delete(0, "end")
        self._inc_add_day.delete(0, "end")
        for v in self._inc_add_months_vars.values():
            v.set(False)
        self._set_inc_add_status(f'"{name}" added.', error=False)
        self._refresh_income()

    def _income_start_edit(self, income_id: int):
        self._income_editing_id = income_id
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
