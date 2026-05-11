from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QCheckBox,
    QDialog, QSizePolicy, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from database.db import (
    get_all_expenses, add_expense, update_expense, delete_expense,
    get_all_income, add_income, update_income, delete_income,
)
from styles.theme import (
    BG_MAIN, BG_CARD, BG_ELEM, ACCENT, TEXT_PRI, TEXT_SEC,
    BORDER, GREEN, RED, FONT,
)
from utils import fmt_eur, bind_numeric_entry

FIXED_CATEGORIES = [
    "Housing", "Investing", "Subscriptions", "Utilities", "Health & Fitness", "Other"
]

# ── Color constants ────────────────────────────────────────────────────────────
TEXT_DIM = "#3d5a70"

# ── Width constants (kept for logic methods) ───────────────────────────────────
_W_DAY    = 60
_W_NAME   = 220
_W_AMOUNT = 130
_W_INC_NAME   = 260
_W_INC_MONTHS = 270
_W_INC_AMOUNT = 130

_MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_L4_ENTRY = (
    "background: #1c2d4a; border: 1px solid #1a2e45; border-radius: 8px;"
    f" color: {TEXT_PRI}; padding: 6px 10px; font-size: 13px;"
)

_TOGGLE_BTN_STYLE = (
    "QPushButton { background: #1a2332; border: 1px solid #1e3448; border-radius: 6px;"
    " color: #6b8fa8; font-size: 12px; padding: 4px 12px; }"
    " QPushButton:hover { background: #1e2d3d; border-color: #00b4d8; color: #00d4ff; }"
)

_ACCENT_BTN_STYLE = (
    "QPushButton { background: #00b4d8; color: #0d1117; border: none; border-radius: 6px;"
    " font-size: 13px; font-weight: 600; padding: 6px 14px; }"
    " QPushButton:hover { background: #00d4ff; }"
    " QPushButton:pressed { background: #0088a8; }"
)

_DEL_BTN_STYLE = (
    "QPushButton { background: transparent; border: 1px solid #2a1a1a;"
    " border-radius: 6px; color: #f85149; }"
    " QPushButton:hover { background: #2a1a1a; border-color: #f85149; }"
)


# ── Module-level helpers ───────────────────────────────────────────────────────

def _clear_layout(layout) -> None:
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub:
                _clear_layout(sub)


def make_label(text: str, size: int = 13, bold: bool = False, color: str = TEXT_PRI) -> QLabel:
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    lbl.setFont(QFont(FONT, size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none; outline: none;")
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    return lbl


def make_card_l3() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #162440;"
        " border-top: 1px solid #1e3a58;"
        " border-left: 1px solid #1e3a58;"
        " border-right: 1px solid #0f1e30;"
        " border-bottom: 1px solid #0f1e30;"
        " border-radius: 14px;"
    )
    return f


def make_card_l2() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #111d2e;"
        " border: 1px solid #1a2e45;"
        " border-radius: 14px;"
    )
    return f


def make_card_l1() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #0d1520;"
        " border: 1px solid #0f1e30;"
        " border-radius: 10px;"
    )
    return f


def make_divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setLineWidth(0)
    f.setFixedHeight(1)
    f.setProperty("class", "divider")
    f.setStyleSheet("background: #1a2e45; border: none;")
    return f


def make_eyebrow(left_text: str, right_text: str = "") -> QHBoxLayout:
    h = QHBoxLayout()
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    left = QLabel(left_text)
    left.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    left.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    left.setFont(QFont(FONT, 10))
    left.setStyleSheet(
        "color: #6b8fa8; background: transparent; border: none;"
        " letter-spacing: 2px; text-transform: uppercase;"
    )
    h.addWidget(left)
    h.addStretch()
    if right_text:
        right = QLabel(right_text)
        right.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        right.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        right.setFont(QFont(FONT, 10))
        right.setStyleSheet(
            "color: #3d5a70; background: transparent; border: none;"
            " font-family: 'Courier New';"
        )
        h.addWidget(right)
    return h


def make_pill(text: str, color: str = "#00b4d8", bg_alpha: float = 0.12) -> QLabel:
    c = QColor(color)
    bg = f"rgba({c.red()},{c.green()},{c.blue()},{bg_alpha})"
    border = f"rgba({c.red()},{c.green()},{c.blue()},0.35)"
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    lbl.setFont(QFont(FONT, 11))
    lbl.setStyleSheet(
        f"color: {color}; background: {bg};"
        f" border: 1px solid {border};"
        f" border-radius: 10px; padding: 2px 10px;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return lbl


# ── Main view ──────────────────────────────────────────────────────────────────

class ExpensesView(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        self._expenses_edit_mode: bool = False
        self._expenses_row_vars: dict[int, dict] = {}
        self._income_edit_mode: bool = False
        self._income_row_vars: dict[int, dict] = {}
        self._inc_add_months_checks: dict[int, QCheckBox] = {}

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setStyleSheet("background: #0d1117;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(20)
        self.setWidget(content)
        self._layout = layout

        self._build()
        self._refresh()
        self._refresh_income()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header row ────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)
        hdr_row.setSpacing(12)

        hdr_left = QVBoxLayout()
        hdr_left.setSpacing(4)
        hdr_left.addWidget(make_label("Budget", 24, bold=True))
        hdr_left.addWidget(
            make_label("Configure recurring expenses and monthly income sources.", 13, color=TEXT_SEC)
        )
        hdr_row.addLayout(hdr_left)
        hdr_row.addStretch()

        self._header_pill = make_pill("€0 / mo", color=ACCENT)
        hdr_row.addWidget(self._header_pill)

        self._layout.addLayout(hdr_row)

        # ── Fixed Expenses card ────────────────────────────────────────────────
        exp_card = make_card_l2()
        exp_card_v = QVBoxLayout(exp_card)
        exp_card_v.setContentsMargins(20, 18, 20, 18)
        exp_card_v.setSpacing(14)

        # Eyebrow
        exp_card_v.addLayout(make_eyebrow("FIXED MONTHLY EXPENSES"))

        # Subtitle
        exp_card_v.addWidget(
            make_label("Recurring charges deducted in end-of-month estimates.", 12, color=TEXT_DIM)
        )

        # Edit toggle row
        exp_toggle_row = QHBoxLayout()
        exp_toggle_row.setContentsMargins(0, 0, 0, 0)
        exp_toggle_row.setSpacing(8)
        exp_toggle_row.addStretch()
        self._expenses_error_lbl = make_label("", 12, color=RED)
        exp_toggle_row.addWidget(self._expenses_error_lbl)
        self._expenses_toggle_btn = QPushButton("Edit")
        self._expenses_toggle_btn.setFixedWidth(64)
        self._expenses_toggle_btn.setFont(QFont(FONT, 12))
        self._expenses_toggle_btn.setStyleSheet(_TOGGLE_BTN_STYLE)
        self._expenses_toggle_btn.clicked.connect(self._toggle_expenses_edit)
        exp_toggle_row.addWidget(self._expenses_toggle_btn)
        exp_card_v.addLayout(exp_toggle_row)

        # Table header
        hdr_frame = QFrame()
        hdr_frame.setFixedHeight(32)
        hdr_frame.setStyleSheet("background: #1a2332; border-radius: 8px; border: none;")
        hdr_h = QHBoxLayout(hdr_frame)
        hdr_h.setContentsMargins(12, 0, 12, 0)
        hdr_h.setSpacing(0)
        _name_hdr = QLabel("NAME")
        _name_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        _name_hdr.setFont(QFont(FONT, 11))
        _name_hdr.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        _name_hdr.setFixedWidth(220)
        hdr_h.addWidget(_name_hdr)
        _day_hdr = QLabel("DAY")
        _day_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        _day_hdr.setFont(QFont(FONT, 11))
        _day_hdr.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        _day_hdr.setFixedWidth(80)
        hdr_h.addWidget(_day_hdr)
        _amt_hdr = QLabel("AMOUNT EUR")
        _amt_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        _amt_hdr.setFont(QFont(FONT, 11))
        _amt_hdr.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        _amt_hdr.setFixedWidth(120)
        _amt_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hdr_h.addWidget(_amt_hdr)
        _cat_hdr = QLabel("CATEGORY")
        _cat_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        _cat_hdr.setFont(QFont(FONT, 11))
        _cat_hdr.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        _cat_hdr.setFixedWidth(140)
        hdr_h.addWidget(_cat_hdr)
        _del_placeholder = QLabel("")
        _del_placeholder.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        _del_placeholder.setFixedWidth(40)
        _del_placeholder.setStyleSheet("background: transparent; border: none;")
        hdr_h.addWidget(_del_placeholder)
        hdr_h.addStretch()
        exp_card_v.addWidget(hdr_frame)

        # Expense list container
        self._list_frame = QWidget()
        self._list_frame.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._list_frame.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_frame)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        exp_card_v.addWidget(self._list_frame)

        # Add expense inset form
        add_form_card = make_card_l1()
        add_form_v = QVBoxLayout(add_form_card)
        add_form_v.setContentsMargins(16, 14, 16, 14)
        add_form_v.setSpacing(10)
        add_form_v.addLayout(make_eyebrow("ADD EXPENSE"))

        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(make_label("Name", 11, color=TEXT_DIM))
        self._add_name = QLineEdit()
        self._add_name.setFixedWidth(200)
        self._add_name.setStyleSheet(_L4_ENTRY)
        name_col.addWidget(self._add_name)
        fields_row.addLayout(name_col)

        day_col = QVBoxLayout()
        day_col.setSpacing(4)
        day_col.addWidget(make_label("Day (1-31)", 11, color=TEXT_DIM))
        self._add_day = QLineEdit()
        self._add_day.setFixedWidth(60)
        self._add_day.setPlaceholderText("1–31")
        self._add_day.setStyleSheet(_L4_ENTRY)
        day_col.addWidget(self._add_day)
        fields_row.addLayout(day_col)

        amt_col = QVBoxLayout()
        amt_col.setSpacing(4)
        amt_col.addWidget(make_label("Amount (EUR)", 11, color=TEXT_DIM))
        self._add_amount = QLineEdit()
        self._add_amount.setFixedWidth(100)
        self._add_amount.setPlaceholderText("0.00")
        self._add_amount.setStyleSheet(_L4_ENTRY)
        bind_numeric_entry(self._add_amount)
        self._add_amount.returnPressed.connect(self._add_expense)
        amt_col.addWidget(self._add_amount)
        fields_row.addLayout(amt_col)

        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        cat_col.addWidget(make_label("Category", 11, color=TEXT_DIM))
        self._add_category = QComboBox()
        self._add_category.addItems(FIXED_CATEGORIES)
        self._add_category.setFixedWidth(140)
        self._add_category.setStyleSheet(
            "QComboBox { background: #1c2d4a; border: 1px solid #1a2e45; border-radius: 8px;"
            " color: #e7eef7; padding: 6px 10px; font-size: 13px; }"
            " QComboBox::drop-down { border: none; }"
            " QComboBox QAbstractItemView { background: #1c2d4a; color: #e7eef7; selection-background-color: #00b4d8; }"
        )
        cat_col.addWidget(self._add_category)
        fields_row.addLayout(cat_col)

        add_btn = QPushButton("Add")
        add_btn.setFixedWidth(80)
        add_btn.setFont(QFont(FONT, 13))
        add_btn.setStyleSheet(_ACCENT_BTN_STYLE)
        add_btn.clicked.connect(self._add_expense)
        # align button to bottom of fields row
        add_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fields_row.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        self._add_status = make_label("", 12, color=GREEN)
        fields_row.addWidget(self._add_status, alignment=Qt.AlignmentFlag.AlignBottom)
        fields_row.addStretch()

        add_form_v.addLayout(fields_row)
        exp_card_v.addWidget(add_form_card)

        # Total row at bottom of expense card
        exp_card_v.addWidget(make_divider())
        exp_total_row = QHBoxLayout()
        exp_total_row.setContentsMargins(0, 0, 0, 0)
        exp_total_row.setSpacing(8)
        exp_total_row.addWidget(make_label("Monthly total:", 13, bold=True))
        exp_total_row.addStretch()
        self._total_label = make_label("€0,00", 13, bold=True, color=ACCENT)
        exp_total_row.addWidget(self._total_label)
        exp_card_v.addLayout(exp_total_row)

        self._layout.addWidget(exp_card)

        # ── Monthly Income card ────────────────────────────────────────────────
        inc_card = make_card_l2()
        inc_card_v = QVBoxLayout(inc_card)
        inc_card_v.setContentsMargins(20, 18, 20, 18)
        inc_card_v.setSpacing(14)

        # Eyebrow
        inc_card_v.addLayout(make_eyebrow("MONTHLY INCOME"))

        # Subtitle
        inc_card_v.addWidget(
            make_label(
                "Track regular income per source. Uncheck months where it doesn't apply.",
                12, color=TEXT_DIM,
            )
        )

        # Edit toggle row
        inc_toggle_row = QHBoxLayout()
        inc_toggle_row.setContentsMargins(0, 0, 0, 0)
        inc_toggle_row.setSpacing(8)
        inc_toggle_row.addStretch()
        self._income_error_lbl = make_label("", 12, color=RED)
        inc_toggle_row.addWidget(self._income_error_lbl)
        self._income_toggle_btn = QPushButton("Edit")
        self._income_toggle_btn.setFixedWidth(64)
        self._income_toggle_btn.setFont(QFont(FONT, 12))
        self._income_toggle_btn.setStyleSheet(_TOGGLE_BTN_STYLE)
        self._income_toggle_btn.clicked.connect(self._toggle_income_edit)
        inc_toggle_row.addWidget(self._income_toggle_btn)
        inc_card_v.addLayout(inc_toggle_row)

        # Income list container
        self._income_list_frame = QWidget()
        self._income_list_frame.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._income_list_frame.setStyleSheet("background: transparent;")
        self._income_list_layout = QVBoxLayout(self._income_list_frame)
        self._income_list_layout.setContentsMargins(0, 0, 0, 0)
        self._income_list_layout.setSpacing(2)
        inc_card_v.addWidget(self._income_list_frame)

        # Add income inset form
        inc_form_card = make_card_l1()
        inc_form_v = QVBoxLayout(inc_form_card)
        inc_form_v.setContentsMargins(16, 14, 16, 14)
        inc_form_v.setSpacing(10)
        inc_form_v.addLayout(make_eyebrow("ADD INCOME SOURCE"))

        inc_fields_row = QHBoxLayout()
        inc_fields_row.setSpacing(12)

        inc_name_col = QVBoxLayout()
        inc_name_col.setSpacing(4)
        inc_name_col.addWidget(make_label("Name", 11, color=TEXT_DIM))
        self._inc_add_name = QLineEdit()
        self._inc_add_name.setFixedWidth(200)
        self._inc_add_name.setStyleSheet(_L4_ENTRY)
        inc_name_col.addWidget(self._inc_add_name)
        inc_fields_row.addLayout(inc_name_col)

        inc_amt_col = QVBoxLayout()
        inc_amt_col.setSpacing(4)
        inc_amt_col.addWidget(make_label("Amount (EUR)", 11, color=TEXT_DIM))
        self._inc_add_amount = QLineEdit()
        self._inc_add_amount.setFixedWidth(100)
        self._inc_add_amount.setPlaceholderText("0.00")
        self._inc_add_amount.setStyleSheet(_L4_ENTRY)
        bind_numeric_entry(self._inc_add_amount)
        self._inc_add_amount.returnPressed.connect(self._add_income_item)
        inc_amt_col.addWidget(self._inc_add_amount)
        inc_fields_row.addLayout(inc_amt_col)

        inc_add_btn = QPushButton("Add")
        inc_add_btn.setFixedWidth(80)
        inc_add_btn.setFont(QFont(FONT, 13))
        inc_add_btn.setStyleSheet(_ACCENT_BTN_STYLE)
        inc_add_btn.clicked.connect(self._add_income_item)
        inc_add_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        inc_fields_row.addWidget(inc_add_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        self._inc_add_status = make_label("", 12, color=GREEN)
        inc_fields_row.addWidget(self._inc_add_status, alignment=Qt.AlignmentFlag.AlignBottom)
        inc_fields_row.addStretch()
        inc_form_v.addLayout(inc_fields_row)

        # Active months checkboxes row
        months_row = QHBoxLayout()
        months_row.setSpacing(4)
        months_row.addWidget(make_label("Active months:", 11, color=TEXT_DIM))
        for m in range(1, 13):
            cb = QCheckBox(_MONTHS_SHORT[m - 1])
            cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color: {TEXT_PRI}; background: transparent; border: none; }}")
            cb.setFont(QFont(FONT, 11))
            self._inc_add_months_checks[m] = cb
            months_row.addWidget(cb)
        months_row.addStretch()
        inc_form_v.addLayout(months_row)

        inc_card_v.addWidget(inc_form_card)

        # Income total row at bottom of income card
        inc_card_v.addWidget(make_divider())
        inc_total_row = QHBoxLayout()
        inc_total_row.setContentsMargins(0, 0, 0, 0)
        inc_total_row.setSpacing(8)
        inc_total_row.addWidget(make_label("Expected monthly income:", 13, bold=True))
        inc_total_row.addStretch()
        self._income_total_label = make_label("€0,00", 13, bold=True, color=ACCENT)
        inc_total_row.addWidget(self._income_total_label)
        inc_card_v.addLayout(inc_total_row)

        self._layout.addWidget(inc_card)

        self._layout.addStretch()

    # ── Public refresh ─────────────────────────────────────────────────────────

    def refresh(self):
        self._refresh()
        self._refresh_income()

    # ── Fixed expenses ─────────────────────────────────────────────────────────

    def _toggle_expenses_edit(self):
        if self._expenses_edit_mode:
            if not self._save_all_expenses():
                return
            self._expenses_edit_mode = False
            self._expenses_toggle_btn.setText("Edit")
        else:
            self._expenses_edit_mode = True
            self._expenses_toggle_btn.setText("Done")
            self._expenses_error_lbl.setText("")
        self._refresh()

    def _save_all_expenses(self) -> bool:
        for eid, v in self._expenses_row_vars.items():
            try:
                day = int(v["day"].text())
                if not 1 <= day <= 31:
                    raise ValueError
            except ValueError:
                self._expenses_error_lbl.setText("Day must be 1–31.")
                return False
            name = v["name"].text().strip()
            if not name:
                self._expenses_error_lbl.setText("Name cannot be empty.")
                return False
            try:
                amount = float(v["amount"].text().replace(",", "."))
            except ValueError:
                self._expenses_error_lbl.setText("Invalid amount.")
                return False
            category = v["category"].currentText()
            update_expense(eid, name, amount, day, category)
        self._expenses_error_lbl.setText("")
        return True

    def _refresh(self):
        _clear_layout(self._list_layout)
        self._expenses_row_vars.clear()
        expenses = [dict(e) for e in get_all_expenses()]
        for idx, exp in enumerate(expenses):
            self._render_expense_row(exp, idx)
        total = sum(float(e["amount"]) for e in expenses)
        self._total_label.setText(fmt_eur(total))
        self._header_pill.setText(f"€{total:.0f} / mo")

    def _render_expense_row(self, exp: dict, idx: int = 0):
        if self._expenses_edit_mode:
            row = QWidget()
            row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row.setStyleSheet("background: #111d2e; border-radius: 6px;")
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(12, 6, 12, 6)
            row_h.setSpacing(8)

            day_edit = QLineEdit(str(exp["day_of_month"]))
            day_edit.setFixedWidth(80)
            day_edit.setStyleSheet(_L4_ENTRY)
            row_h.addWidget(day_edit)

            name_edit = QLineEdit(exp["name"])
            name_edit.setFixedWidth(220)
            name_edit.setStyleSheet(_L4_ENTRY)
            row_h.addWidget(name_edit)

            amt_edit = QLineEdit(str(exp["amount"]))
            amt_edit.setFixedWidth(120)
            amt_edit.setStyleSheet(_L4_ENTRY)
            bind_numeric_entry(amt_edit)
            row_h.addWidget(amt_edit)

            cat_combo = QComboBox()
            cat_combo.addItems(FIXED_CATEGORIES)
            current_cat = exp.get("category", "Other") or "Other"
            idx = FIXED_CATEGORIES.index(current_cat) if current_cat in FIXED_CATEGORIES else len(FIXED_CATEGORIES) - 1
            cat_combo.setCurrentIndex(idx)
            cat_combo.setFixedWidth(140)
            cat_combo.setStyleSheet(
                "QComboBox { background: #1c2d4a; border: 1px solid #1a2e45; border-radius: 8px;"
                " color: #e7eef7; padding: 6px 10px; font-size: 13px; }"
                " QComboBox::drop-down { border: none; }"
                " QComboBox QAbstractItemView { background: #1c2d4a; color: #e7eef7; selection-background-color: #00b4d8; }"
            )
            row_h.addWidget(cat_combo)
            del_btn = QPushButton("×")
            del_btn.setFixedSize(28, 28)
            del_btn.setFont(QFont(FONT, 13))
            del_btn.setStyleSheet(_DEL_BTN_STYLE)
            del_btn.clicked.connect(
                lambda _=False, eid=exp["id"], n=exp["name"]: self._delete_expense(eid, n)
            )
            row_h.addWidget(del_btn)
            row_h.addStretch()

            self._expenses_row_vars[exp["id"]] = {
                "day": day_edit, "name": name_edit, "amount": amt_edit, "category": cat_combo,
            }
        else:
            bg = "#111d2e" if idx % 2 == 0 else "#0d1520"
            row = QWidget()
            row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row.setStyleSheet(f"background: {bg}; border-radius: 6px;")
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(12, 8, 12, 8)
            row_h.setSpacing(8)

            name_lbl = make_label(exp["name"], 13)
            name_lbl.setFixedWidth(220)
            row_h.addWidget(name_lbl)

            day_text = "End of month" if exp["day_of_month"] == 31 else str(exp["day_of_month"])
            day_lbl = make_label(day_text, 12, color=TEXT_SEC)
            day_lbl.setFont(QFont("Courier New", 12))
            day_lbl.setFixedWidth(80)
            row_h.addWidget(day_lbl)

            amt_lbl = make_label(fmt_eur(float(exp["amount"])), 13)
            amt_lbl.setFixedWidth(120)
            amt_lbl.setFont(QFont("Courier New", 13))
            amt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_h.addWidget(amt_lbl)
            cat = exp.get("category", "Other") or "Other"
            cat_lbl = make_label(cat, 11, color=TEXT_SEC)
            cat_lbl.setFixedWidth(140)
            row_h.addWidget(cat_lbl)
            row_h.addStretch()

        self._list_layout.addWidget(row)

    # ── Income ─────────────────────────────────────────────────────────────────

    def _toggle_income_edit(self):
        if self._income_edit_mode:
            if not self._save_all_income():
                return
            self._income_edit_mode = False
            self._income_toggle_btn.setText("Edit")
        else:
            self._income_edit_mode = True
            self._income_toggle_btn.setText("Done")
            self._income_error_lbl.setText("")
        self._refresh_income()

    def _save_all_income(self) -> bool:
        for iid, v in self._income_row_vars.items():
            name = v["name"].text().strip()
            if not name:
                self._income_error_lbl.setText("Name cannot be empty.")
                return False
            try:
                amount = float(v["amount"].text().replace(",", ".") or "0")
            except ValueError:
                self._income_error_lbl.setText("Invalid amount.")
                return False
            checked = [m for m, cb in v["months"].items() if cb.isChecked()]
            if not checked:
                self._income_error_lbl.setText("Select at least one active month.")
                return False
            active_months_str = "" if len(checked) == 12 else ",".join(str(m) for m in sorted(checked))
            update_income(iid, name, amount, 0, "fixed", active_months_str)
        self._income_error_lbl.setText("")
        return True

    def _refresh_income(self):
        _clear_layout(self._income_list_layout)
        self._income_row_vars.clear()
        items = [dict(i) for i in get_all_income()]
        for idx, item in enumerate(items):
            self._render_income_row(item, idx)
        total = sum(float(i["amount"]) for i in items)
        self._income_total_label.setText(fmt_eur(total))

    def _render_income_row(self, item: dict, idx: int = 0):
        if self._income_edit_mode:
            self._render_income_edit_row(item)
        else:
            self._render_income_display_row(item, idx)

    def _render_income_display_row(self, item: dict, idx: int = 0):
        bg = "#111d2e" if idx % 2 == 0 else "#0d1520"
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row.setStyleSheet(f"background: {bg}; border-radius: 6px;")
        row_h = QHBoxLayout(row)
        row_h.setContentsMargins(12, 8, 12, 8)
        row_h.setSpacing(8)

        name_lbl = make_label(item["name"], 13)
        name_lbl.setFixedWidth(180)
        row_h.addWidget(name_lbl)

        # Month pills
        am = (item.get("active_months") or "").strip()
        if am:
            try:
                active_set = {int(x.strip()) for x in am.split(",") if x.strip()}
            except ValueError:
                active_set = set(range(1, 13))
        else:
            active_set = set(range(1, 13))

        months_w = QWidget()
        months_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        months_w.setStyleSheet("background: transparent;")
        months_h = QHBoxLayout(months_w)
        months_h.setContentsMargins(0, 0, 0, 0)
        months_h.setSpacing(3)
        for m in range(1, 13):
            is_active = m in active_set
            pill_btn = QPushButton(_MONTHS_SHORT[m - 1])
            pill_btn.setFixedSize(28, 22)
            pill_btn.setFont(QFont(FONT, 10))
            pill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_active:
                pill_btn.setStyleSheet(
                    "QPushButton { background: rgba(0,180,216,0.15); border: 1px solid rgba(0,180,216,0.4);"
                    " border-radius: 4px; color: #00b4d8; }"
                    " QPushButton:hover { background: rgba(0,180,216,0.25); }"
                )
            else:
                pill_btn.setStyleSheet(
                    "QPushButton { background: transparent; border: 1px solid #1a2e45;"
                    " border-radius: 4px; color: #6b8fa8; }"
                    " QPushButton:hover { background: rgba(255,255,255,0.04); }"
                )
            pill_btn.clicked.connect(
                lambda _=False, iid=item["id"], month=m, am_set=active_set:
                    self._toggle_income_month(iid, month, am_set)
            )
            months_h.addWidget(pill_btn)
        row_h.addWidget(months_w)

        row_h.addStretch()

        amt_lbl = make_label(fmt_eur(float(item["amount"])), 12, color=TEXT_SEC)
        amt_lbl.setFixedWidth(100)
        amt_lbl.setFont(QFont("Courier New", 12))
        amt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row_h.addWidget(amt_lbl)

        self._income_list_layout.addWidget(row)

    def _render_income_edit_row(self, item: dict):
        outer = QFrame()
        outer.setFrameShape(QFrame.Shape.NoFrame)
        outer.setLineWidth(0)
        outer.setStyleSheet(
            "background: #1a2332; border-radius: 8px; border: 1px solid #1e3448;"
        )
        outer_v = QVBoxLayout(outer)
        outer_v.setContentsMargins(12, 10, 12, 10)
        outer_v.setSpacing(8)

        # Line 1: name + EUR + amount + × + stretch
        line1_h = QHBoxLayout()
        line1_h.setSpacing(8)

        name_edit = QLineEdit(item["name"])
        name_edit.setFixedWidth(_W_INC_NAME)
        name_edit.setStyleSheet(_L4_ENTRY)
        line1_h.addWidget(name_edit)

        line1_h.addWidget(make_label("EUR", 12, color=TEXT_SEC))

        amt_edit = QLineEdit(str(item["amount"]))
        amt_edit.setFixedWidth(_W_INC_AMOUNT)
        amt_edit.setStyleSheet(_L4_ENTRY)
        bind_numeric_entry(amt_edit)
        line1_h.addWidget(amt_edit)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(28, 28)
        del_btn.setFont(QFont(FONT, 13))
        del_btn.setStyleSheet(_DEL_BTN_STYLE)
        del_btn.clicked.connect(
            lambda _=False, iid=item["id"], n=item["name"]: self._delete_income_item(iid, n)
        )
        line1_h.addWidget(del_btn)
        line1_h.addStretch()
        outer_v.addLayout(line1_h)

        # Line 2: active months checkboxes
        line2_h = QHBoxLayout()
        line2_h.setSpacing(6)
        line2_h.addWidget(make_label("Active months:", 12, color=TEXT_SEC))

        am = (item.get("active_months") or "").strip()
        if am:
            try:
                active_months_set = {int(x.strip()) for x in am.split(",") if x.strip()}
            except ValueError:
                active_months_set = set(range(1, 13))
        else:
            active_months_set = set(range(1, 13))

        months_checks: dict[int, QCheckBox] = {}
        for m in range(1, 13):
            cb = QCheckBox(_MONTHS_SHORT[m - 1])
            cb.setChecked(m in active_months_set)
            cb.setStyleSheet(f"QCheckBox {{ color: {TEXT_PRI}; background: transparent; border: none; }}")
            cb.setFont(QFont(FONT, 12))
            months_checks[m] = cb
            line2_h.addWidget(cb)
        line2_h.addStretch()
        outer_v.addLayout(line2_h)

        self._income_row_vars[item["id"]] = {
            "name": name_edit, "amount": amt_edit, "months": months_checks,
        }
        self._income_list_layout.addWidget(outer)

    def _toggle_income_month(self, income_id: int, month: int, current_set: set) -> None:
        new_set = set(current_set)
        if month in new_set:
            new_set.discard(month)
        else:
            new_set.add(month)
        if not new_set:
            return  # don't allow empty
        active_months_str = "" if len(new_set) == 12 else ",".join(str(m) for m in sorted(new_set))
        items = [dict(i) for i in get_all_income()]
        item = next((i for i in items if i["id"] == income_id), None)
        if item:
            update_income(income_id, item["name"], float(item["amount"]), 0, "fixed", active_months_str)
        self._refresh_income()

    def _format_active_months(self, item: dict) -> str:
        am = (item.get("active_months") or "").strip()
        if not am:
            return "All months"
        try:
            nums = [int(x.strip()) for x in am.split(",") if x.strip()]
            return ", ".join(_MONTHS_SHORT[m - 1] for m in sorted(nums) if 1 <= m <= 12)
        except ValueError:
            return "All months"

    # ── Action methods ─────────────────────────────────────────────────────────

    def _add_expense(self):
        try:
            day = int(self._add_day.text())
            if not 1 <= day <= 31:
                raise ValueError
        except ValueError:
            self._set_add_status("Day must be 1–31.", error=True)
            return
        name = self._add_name.text().strip()
        if not name:
            self._set_add_status("Name required.", error=True)
            return
        try:
            amount = float(self._add_amount.text().replace(",", "."))
        except ValueError:
            self._set_add_status("Invalid amount.", error=True)
            return
        category = self._add_category.currentText()
        add_expense(name, amount, day, category)
        self._add_category.setCurrentIndex(FIXED_CATEGORIES.index("Other"))
        self._add_day.clear()
        self._add_name.clear()
        self._add_amount.clear()
        self._set_add_status("Added.", error=False)
        self._refresh()

    def _delete_expense(self, expense_id: int, name: str):
        if self._confirm_dialog(f'Delete "{name}"?', "Delete", "Cancel"):
            delete_expense(expense_id)
            self._refresh()

    def _add_income_item(self):
        name = self._inc_add_name.text().strip()
        if not name:
            self._set_inc_add_status("Name required.", error=True)
            return
        try:
            amount = float(self._inc_add_amount.text().replace(",", ".") or "0")
        except ValueError:
            self._set_inc_add_status("Invalid amount.", error=True)
            return
        checked = [m for m, cb in self._inc_add_months_checks.items() if cb.isChecked()]
        active_months = "" if len(checked) == 12 else ",".join(str(m) for m in sorted(checked))
        add_income(name, amount, 0, "fixed", active_months)
        self._inc_add_name.clear()
        self._inc_add_amount.clear()
        for cb in self._inc_add_months_checks.values():
            cb.setChecked(True)
        self._set_inc_add_status("Added.", error=False)
        self._refresh_income()

    def _delete_income_item(self, income_id: int, name: str):
        if self._confirm_dialog(f'Delete "{name}"?', "Delete", "Cancel"):
            delete_income(income_id)
            self._refresh_income()

    # ── Status helpers ─────────────────────────────────────────────────────────

    def _set_add_status(self, text: str, error: bool = False):
        color = RED if error else GREEN
        self._add_status.setText(text)
        self._add_status.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        if not error:
            QTimer.singleShot(3000, lambda: self._add_status.setText(""))

    def _set_inc_add_status(self, text: str, error: bool = False):
        color = RED if error else GREEN
        self._inc_add_status.setText(text)
        self._inc_add_status.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        if not error:
            QTimer.singleShot(3000, lambda: self._inc_add_status.setText(""))

    # ── Confirm dialog ─────────────────────────────────────────────────────────

    def _confirm_dialog(self, message: str, confirm_text: str = "Confirm", cancel_text: str = "Cancel") -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm")
        dlg.setFixedSize(360, 160)
        dlg.setStyleSheet(f"background: #0d1117; color: {TEXT_PRI};")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        lbl = QLabel(message)
        lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        lbl.setWordWrap(True)
        lbl.setFont(QFont(FONT, 13))
        lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
        layout.addWidget(lbl)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setProperty("class", "accent")
        confirm_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        return dlg.exec() == QDialog.DialogCode.Accepted
