import calendar
from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QLineEdit, QComboBox,
    QDialog,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from database.db import (
    get_snapshot, save_snapshot, delete_snapshot,
    get_all_expenses, get_all_accounts, get_all_income,
    get_snapshot_income, set_snapshot_income, get_extra_income,
    add_extra_income, clear_extra_income, get_setting,
    get_portfolio_positions, get_portfolio_cache, update_snapshot_portfolio,
)
from styles.theme import (
    BG_MAIN, ACCENT, TEXT_PRI, TEXT_SEC,
    GREEN, RED, FONT,
)
from utils import fmt_eur, fmt_eur_signed, effective_charge_day, bind_numeric_entry, open_dialog

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

_DEFAULT_ACCOUNTS = ["Main Bank Account", "Revolut", "Cash", "Flatex"]


# ── Visual helpers (duplicated from dashboard to avoid circular imports) ──────

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
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #162440;"
        "border-top: 1px solid #2a4a6a;"
        "border-left: 1px solid #1e3a55;"
        "border-right: 1px solid #0d1a28;"
        "border-bottom: 1px solid #0d1a28;"
        "border-radius: 14px;"
    )
    f.setContentsMargins(0, 0, 0, 0)
    return f


def make_card_l2() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #111d2e;"
        "border: 1px solid #1a2e45;"
        "border-radius: 14px;"
    )
    f.setContentsMargins(0, 0, 0, 0)
    return f


def make_card_l1() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        "background: #0d1520;"
        "border: 1px solid #0f1e30;"
        "border-radius: 12px;"
    )
    f.setContentsMargins(0, 0, 0, 0)
    return f


def make_card() -> QFrame:
    return make_card_l2()


def make_divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setFixedHeight(1)
    f.setStyleSheet("background: #1a2e45; border: none;")
    return f


def make_eyebrow(left_text: str, right_text: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    left = QLabel(left_text.upper())
    left.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    left.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    left.setStyleSheet("color: #6b7d94; font-size: 11px; letter-spacing: 2px; background: transparent; border: none;")
    row.addWidget(left)
    if right_text:
        right = QLabel(right_text)
        right.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        right.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        right.setStyleSheet("color: #6b7d94; font-size: 11px; font-family: 'Courier New'; background: transparent; border: none;")
        right.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(right)
    return row


def make_pill(text: str, color: str = "#00b4d8", bg_alpha: float = 0.12) -> QLabel:
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    lbl.setStyleSheet(
        f"color: {color}; background: rgba({r},{g},{b},{int(bg_alpha * 255)}); "
        "border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 500; border: none;"
    )
    return lbl


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


# ── Main view ─────────────────────────────────────────────────────────────────

class SnapshotEntryView(QScrollArea):
    # Class variable: set by Dashboard when navigating to a specific period
    _pending_period: tuple[int, int] | None = None

    def __init__(self, navigate_callback=None):
        super().__init__()
        self._navigate = navigate_callback
        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        self._rows: list[dict] = []
        self._editing_accounts: bool = False
        self._income_amount_widgets: dict[int, QLineEdit] = {}
        self._extra_income_rows: dict[int, list[dict]] = {}
        self._month_btns: list[QPushButton] = []
        self._sidebar_layout: QVBoxLayout | None = None

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setStyleSheet("background: #0d1117;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(8)
        self.setWidget(content)

        self._build()
        self._load_existing()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        cls = SnapshotEntryView
        if cls._pending_period is not None:
            year, month = cls._pending_period
            cls._pending_period = None
            self._month_combo.blockSignals(True)
            self._year_edit.blockSignals(True)
            self._month_combo.setCurrentIndex(month - 1)
            self._year_edit.setText(str(year))
            self._month_combo.blockSignals(False)
            self._year_edit.blockSignals(False)
        self._load_existing()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        today = date.today()
        cl = self._content_layout

        # ── Header row ────────────────────────────────────────────────────────
        hdr_row = QWidget()
        hdr_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_row.setStyleSheet("background: transparent;")
        hdr_h = QHBoxLayout(hdr_row)
        hdr_h.setContentsMargins(0, 4, 0, 4)
        hdr_h.setSpacing(12)

        hdr_left = QWidget()
        hdr_left.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_left.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_left.setStyleSheet("background: transparent;")
        hdr_left_v = QVBoxLayout(hdr_left)
        hdr_left_v.setContentsMargins(0, 0, 0, 0)
        hdr_left_v.setSpacing(2)
        hdr_left_v.addWidget(make_label("Monthly Snapshot", 22, bold=True))
        sub = make_label(
            "Enter end-of-month balances. Accounts are fully dynamic — add or remove as needed.",
            13, color=TEXT_SEC,
        )
        sub.setWordWrap(True)
        hdr_left_v.addWidget(sub)
        hdr_h.addWidget(hdr_left, stretch=1)

        # Right: days pill + last saved label
        from database.db import get_latest_snapshots
        _snaps = get_latest_snapshots(1)
        _last_month_name = MONTHS[_snaps[0]["month"] - 1] + " " + str(_snaps[0]["year"]) if _snaps else "—"
        days_remaining = calendar.monthrange(today.year, today.month)[1] - today.day

        hdr_right = QWidget()
        hdr_right.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_right.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_right.setStyleSheet("background: transparent;")
        hdr_right_h = QHBoxLayout(hdr_right)
        hdr_right_h.setContentsMargins(0, 0, 0, 0)
        hdr_right_h.setSpacing(6)
        hdr_right_h.addWidget(make_pill(f"{days_remaining} days", color=ACCENT))
        hdr_right_h.addWidget(make_label(f"Last saved: {_last_month_name}", 11, color=TEXT_SEC))
        hdr_h.addWidget(hdr_right)
        cl.addWidget(hdr_row)

        # ── Period card (L2) ──────────────────────────────────────────────────
        period_card = make_card_l2()
        period_v = QVBoxLayout(period_card)
        period_v.setContentsMargins(20, 16, 20, 16)
        period_v.setSpacing(10)
        period_v.addLayout(make_eyebrow("PERIOD"))

        # Month pills row
        months_row = QWidget()
        months_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        months_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        months_row.setStyleSheet("background: transparent;")
        months_h = QHBoxLayout(months_row)
        months_h.setContentsMargins(0, 0, 0, 0)
        months_h.setSpacing(4)
        self._month_btns = []
        for i, m in enumerate(MONTHS):
            btn = QPushButton(m[:3])
            btn.setFixedHeight(28)
            btn.setFont(QFont(FONT, 11))
            btn.setCheckable(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("_month_idx", i)
            btn.clicked.connect(lambda _=False, idx=i: self._on_month_pill_click(idx))
            self._month_btns.append(btn)
            months_h.addWidget(btn)
        months_h.addStretch()
        period_v.addWidget(months_row)

        # Year row
        year_row = QWidget()
        year_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        year_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        year_row.setStyleSheet("background: transparent;")
        year_h = QHBoxLayout(year_row)
        year_h.setContentsMargins(0, 0, 0, 0)
        year_h.setSpacing(8)
        year_h.addWidget(make_label("Year:", 12, color=TEXT_SEC))
        self._year_edit = QLineEdit()
        self._year_edit.setFixedWidth(80)
        self._year_edit.setText(str(today.year))
        self._year_edit.setStyleSheet(
            "background: #1c2d4a; border: 1px solid #1a2e45; border-radius: 8px;"
            "color: #e7eef7; padding: 6px 10px; font-size: 13px;"
        )
        year_h.addWidget(self._year_edit)
        year_h.addStretch()
        period_v.addWidget(year_row)

        # Hidden QComboBox kept for compatibility with _get_period() and refresh()
        self._month_combo = QComboBox()
        self._month_combo.addItems(MONTHS)
        self._month_combo.setCurrentIndex(today.month - 1)
        self._month_combo.setVisible(False)
        period_v.addWidget(self._month_combo)

        # Info banner (shown when no snapshot — updated in _load_existing)
        self._info_banner = make_card_l1()
        info_banner_v = QVBoxLayout(self._info_banner)
        info_banner_v.setContentsMargins(16, 10, 16, 10)
        self._info_banner_lbl = make_label("", 12, color=TEXT_SEC)
        self._info_banner_lbl.setWordWrap(True)
        info_banner_v.addWidget(self._info_banner_lbl)
        self._info_banner.setVisible(False)
        period_v.addWidget(self._info_banner)

        cl.addWidget(period_card)

        # Connect period change signals
        self._month_combo.currentIndexChanged.connect(self._on_period_change)
        self._year_edit.returnPressed.connect(self._on_period_change)
        self._year_edit.editingFinished.connect(self._on_period_change)

        # ── Accounts + sidebar row ────────────────────────────────────────────
        body_row = QWidget()
        body_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        body_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        body_row.setStyleSheet("background: transparent;")
        body_h = QHBoxLayout(body_row)
        body_h.setContentsMargins(0, 0, 0, 0)
        body_h.setSpacing(8)

        # ── Left: Accounts card (L2) ──────────────────────────────────────────
        accounts_card = make_card_l2()
        accounts_v = QVBoxLayout(accounts_card)
        accounts_v.setContentsMargins(20, 16, 20, 16)
        accounts_v.setSpacing(8)

        self._accounts_eyebrow_layout = make_eyebrow("ACCOUNTS", "EUR · 0 active accounts")
        accounts_v.addLayout(self._accounts_eyebrow_layout)

        # Filter pills row (cosmetic)
        filter_row = QWidget()
        filter_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        filter_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        filter_row.setStyleSheet("background: transparent;")
        filter_h = QHBoxLayout(filter_row)
        filter_h.setContentsMargins(0, 0, 0, 0)
        filter_h.setSpacing(4)
        for flabel in ("All", "Cash", "Bank"):
            fp = QPushButton(flabel)
            fp.setFixedHeight(22)
            fp.setFont(QFont(FONT, 10))
            fp.setStyleSheet(
                "QPushButton { background: transparent; color: #5a7a94; border: 1px solid #1a2e45;"
                " border-radius: 11px; padding: 0px 8px; }"
                " QPushButton:hover { color: #eef2f7; border-color: #2a4a6a; }"
            )
            filter_h.addWidget(fp)
        filter_h.addStretch()
        accounts_v.addWidget(filter_row)

        # Column headers
        col_hdr = QWidget()
        col_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        col_hdr.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        col_hdr.setStyleSheet("background: transparent;")
        col_h = QHBoxLayout(col_hdr)
        col_h.setContentsMargins(0, 0, 0, 0)
        col_h.setSpacing(8)
        acct_hdr = make_label("Account", 11, color=TEXT_SEC)
        acct_hdr.setFixedWidth(260)
        col_h.addWidget(acct_hdr)
        bal_hdr = make_label("Balance", 11, color=TEXT_SEC)
        col_h.addWidget(bal_hdr)
        col_h.addStretch()
        accounts_v.addWidget(col_hdr)

        # Account rows container
        self._rows_widget = QWidget()
        self._rows_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._rows_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._rows_widget.setStyleSheet("background: transparent;")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        accounts_v.addWidget(self._rows_widget)

        # Add/Edit buttons
        btn_row = QWidget()
        btn_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row.setStyleSheet("background: transparent;")
        btn_h = QHBoxLayout(btn_row)
        btn_h.setContentsMargins(0, 4, 0, 0)
        btn_h.setSpacing(8)
        add_btn = QPushButton("+ Add Account")
        add_btn.setFont(QFont(FONT, 12))
        add_btn.clicked.connect(self._add_account_and_edit)
        btn_h.addWidget(add_btn)
        self._edit_accounts_btn = QPushButton("Edit Accounts")
        self._edit_accounts_btn.setFont(QFont(FONT, 12))
        self._edit_accounts_btn.clicked.connect(self._toggle_account_editing)
        btn_h.addWidget(self._edit_accounts_btn)
        btn_h.addStretch()
        accounts_v.addWidget(btn_row)

        body_h.addWidget(accounts_card, stretch=2)

        # ── Right: Net worth sidebar card (L3) ────────────────────────────────
        sidebar_card = make_card_l3()
        sidebar_v = QVBoxLayout(sidebar_card)
        sidebar_v.setContentsMargins(20, 16, 20, 16)
        sidebar_v.setSpacing(6)
        self._sidebar_layout = sidebar_v

        period = self._get_period() or (today.year, today.month)
        self._sidebar_eyebrow_lbl = QLabel(f"NET WORTH · {MONTHS[period[1]-1].upper()} {period[0]}")
        self._sidebar_eyebrow_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._sidebar_eyebrow_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._sidebar_eyebrow_lbl.setStyleSheet(
            "color: #6b7d94; font-size: 11px; letter-spacing: 2px; background: transparent; border: none;"
        )
        sidebar_v.addWidget(self._sidebar_eyebrow_lbl)

        self._total_label = QLabel("€0,00")
        self._total_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._total_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._total_label.setFont(QFont(FONT, 28, QFont.Weight.Bold))
        font = self._total_label.font()
        font.setPixelSize(34)
        self._total_label.setFont(font)
        self._total_label.setStyleSheet(f"color: {ACCENT}; background: transparent; border: none;")
        sidebar_v.addWidget(self._total_label)

        sidebar_v.addWidget(make_divider())

        self._sidebar_stats_widget = QWidget()
        self._sidebar_stats_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._sidebar_stats_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._sidebar_stats_widget.setStyleSheet("background: transparent;")
        self._sidebar_stats_layout = QVBoxLayout(self._sidebar_stats_widget)
        self._sidebar_stats_layout.setContentsMargins(0, 0, 0, 0)
        self._sidebar_stats_layout.setSpacing(4)
        sidebar_v.addWidget(self._sidebar_stats_widget)
        sidebar_v.addStretch()

        body_h.addWidget(sidebar_card, stretch=1)
        cl.addWidget(body_row)

        # ── Divider between total and income ─────────────────────────────────
        div_wrapper = QWidget()
        div_wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        div_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        div_wrapper.setStyleSheet("background: transparent;")
        div_wv = QVBoxLayout(div_wrapper)
        div_wv.setContentsMargins(0, 6, 0, 4)
        div_wv.addWidget(make_divider())
        cl.addWidget(div_wrapper)

        # ── Income container ──────────────────────────────────────────────────
        self._income_container = QWidget()
        self._income_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._income_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._income_container.setStyleSheet("background: transparent;")
        income_layout = QVBoxLayout(self._income_container)
        income_layout.setContentsMargins(0, 0, 0, 0)
        income_layout.setSpacing(8)
        cl.addWidget(self._income_container)

        # ── Save row ──────────────────────────────────────────────────────────
        save_row = QWidget()
        save_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        save_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        save_row.setStyleSheet("background: transparent;")
        save_h = QHBoxLayout(save_row)
        save_h.setContentsMargins(0, 4, 0, 0)
        save_h.setSpacing(16)
        save_btn = QPushButton("Save Snapshot")
        save_btn.setFont(QFont(FONT, 13))
        save_btn.setFixedWidth(150)
        save_btn.setStyleSheet(
            "QPushButton { background: #00b4d8; color: #0d1117; border: none;"
            " border-radius: 8px; padding: 8px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #00d4ff; }"
            "QPushButton:pressed { background: #0088a8; }"
        )
        save_btn.clicked.connect(self._save)
        save_h.addWidget(save_btn)
        self._status_label = QLabel("")
        self._status_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._status_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._status_label.setFont(QFont(FONT, 12))
        self._status_label.setStyleSheet(f"color: {TEXT_SEC}; background: transparent;")
        self._status_label.setWordWrap(True)
        save_h.addWidget(self._status_label, 1)
        cl.addWidget(save_row)

        # Portfolio reminder banner (hidden by default)
        self._portfolio_reminder_widget = QWidget()
        self._portfolio_reminder_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._portfolio_reminder_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._portfolio_reminder_widget.setStyleSheet("background: transparent;")
        self._portfolio_reminder_widget.setVisible(False)
        pr_h = QHBoxLayout(self._portfolio_reminder_widget)
        pr_h.setContentsMargins(0, 4, 0, 0)
        pr_h.setSpacing(12)
        pr_banner = QFrame()
        pr_banner.setStyleSheet(
            "QFrame { background: #0d1f35; border: 1px solid #1e3a55; border-radius: 8px; }"
        )
        pr_inner = QHBoxLayout(pr_banner)
        pr_inner.setContentsMargins(16, 10, 16, 10)
        pr_lbl = QLabel("Snapshot saved. Don't forget to update your portfolio value for this month.")
        pr_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        pr_lbl.setFont(QFont(FONT, 12))
        pr_lbl.setStyleSheet("color: #9fb0c5; background: transparent; border: none;")
        pr_inner.addWidget(pr_lbl, stretch=1)
        pr_btn = QPushButton("Go to Portfolio →")
        pr_btn.setFont(QFont(FONT, 12))
        pr_btn.setFixedWidth(150)
        pr_btn.setStyleSheet(
            "QPushButton { background: #00b4d8; color: #0d1117; border: none;"
            " border-radius: 8px; padding: 6px 12px; font-weight: 600; }"
            "QPushButton:hover { background: #00d4ff; }"
        )
        pr_btn.clicked.connect(lambda: (
            self._portfolio_reminder_widget.setVisible(False),
            getattr(self, '_navigate', None) and self._navigate("portfolio"),
        ))
        pr_inner.addWidget(pr_btn)
        pr_h.addWidget(pr_banner)
        cl.addWidget(self._portfolio_reminder_widget)

        # ── Delete widget ─────────────────────────────────────────────────────
        self._del_widget = QWidget()
        self._del_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._del_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._del_widget.setStyleSheet("background: transparent;")
        del_h = QHBoxLayout(self._del_widget)
        del_h.setContentsMargins(0, 0, 0, 0)
        del_btn = QPushButton("Delete Snapshot")
        del_btn.setFont(QFont(FONT, 13))
        del_btn.setProperty("class", "danger")
        del_btn.setFixedWidth(150)
        del_btn.clicked.connect(self._delete_snapshot)
        del_h.addWidget(del_btn)
        del_h.addStretch()
        self._del_widget.setVisible(False)
        cl.addWidget(self._del_widget)

        cl.addStretch()

        # Set initial month pill active state
        self._update_month_pills(today.month - 1)

    # ── Month pill helpers ────────────────────────────────────────────────────

    def _on_month_pill_click(self, idx: int) -> None:
        self._month_combo.blockSignals(True)
        self._month_combo.setCurrentIndex(idx)
        self._month_combo.blockSignals(False)
        self._update_month_pills(idx)
        self._on_period_change()

    def _update_month_pills(self, active_idx: int) -> None:
        for i, btn in enumerate(self._month_btns):
            if i == active_idx:
                btn.setStyleSheet(
                    "QPushButton { background: rgba(0,180,216,38); color: #00b4d8;"
                    " border: 1px solid rgba(0,180,216,128); border-radius: 14px; padding: 2px 10px; }"
                    " QPushButton:hover { background: rgba(0,180,216,60); }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: transparent; color: #6b8fa8;"
                    " border: 1px solid #1a2e45; border-radius: 14px; padding: 2px 10px; }"
                    " QPushButton:hover { color: #eef2f7; border-color: #2a4a6a; }"
                )

    def _update_sidebar_stats(self) -> None:
        if self._sidebar_stats_layout is None:
            return
        while self._sidebar_stats_layout.count():
            item = self._sidebar_stats_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        today = date.today()
        period = self._get_period() or (today.year, today.month)
        year, month = period
        days_remaining = calendar.monthrange(today.year, today.month)[1] - today.day

        from database.db import get_latest_snapshots, get_setting as _gs
        daily_buffer = float(_gs("daily_buffer") or "20.0")

        snaps = get_latest_snapshots(3)
        prev_snap = snaps[1] if len(snaps) >= 2 else (snaps[0] if snaps else None)
        prev_total = prev_snap["total"] if prev_snap else None
        prev_label = (MONTHS[prev_snap["month"] - 1][:3].upper() + " " + str(prev_snap["year"])[-2:]) if prev_snap else ""

        def _stat_row(label: str, value: str) -> QWidget:
            w = QWidget()
            w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            w.setStyleSheet("background: transparent;")
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 1, 0, 1)
            h.addWidget(make_label(label, 11, color=TEXT_SEC))
            h.addStretch()
            h.addWidget(make_label(value, 11, color=TEXT_SEC))
            return w

        current_total = 0.0
        for row in self._rows:
            try:
                current_total += float(row["bal_edit"].text().replace(",", ".") or "0")
            except ValueError:
                pass

        if current_total == 0.0:
            self._sidebar_stats_layout.addWidget(
                make_label("No balances entered yet", 12, color="#3d5a70")
            )
        else:
            if prev_total is not None:
                self._sidebar_stats_layout.addWidget(_stat_row(f"LAST ({prev_label})", fmt_eur(prev_total)))

            # Portfolio value
            try:
                positions = get_portfolio_positions()
                cache = get_portfolio_cache()
                port_eur = sum(
                    pos["shares"] * (cache[pos["ticker"]].get("price_eur") or cache[pos["ticker"]]["price"])
                    for pos in positions if pos["ticker"] in cache
                )
                if port_eur > 0:
                    self._sidebar_stats_layout.addWidget(_stat_row("PORTFOLIO", fmt_eur(port_eur)))
            except Exception:
                pass

            self._sidebar_stats_layout.addWidget(_stat_row("DAYS REMAINING", str(days_remaining)))
            self._sidebar_stats_layout.addWidget(_stat_row("DAILY ALLOWANCE", f"€{daily_buffer:.0f}/day"))

    # ── Account rows ──────────────────────────────────────────────────────────

    def _add_row(self, name: str = "", balance: str = "") -> dict:
        row_widget = QWidget()
        row_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_widget.setStyleSheet("background: transparent; border: none;")
        row_h = QHBoxLayout(row_widget)
        row_h.setContentsMargins(0, 0, 0, 0)
        row_h.setSpacing(8)

        # name_var is a mutable list so lambdas can mutate it
        name_var: list[str] = [name]

        # name_container holds either a label or a QLineEdit
        name_container = QWidget()
        name_container.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        name_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        name_container.setStyleSheet("background: transparent; border: none;")
        nc_layout = QHBoxLayout(name_container)
        nc_layout.setContentsMargins(0, 0, 0, 0)
        nc_layout.setSpacing(0)
        row_h.addWidget(name_container)

        # Balance entry
        bal_edit = QLineEdit()
        bal_edit.setFixedWidth(120)
        bal_edit.setPlaceholderText("0.00")
        if balance:
            bal_edit.setText(balance)
        bal_edit.setStyleSheet(
            "background: #1c2d4a; border: 1px solid #1a2e45; border-radius: 8px;"
            "color: #e7eef7; padding: 6px 10px; font-size: 13px;"
        )
        bind_numeric_entry(bal_edit)
        bal_edit.textChanged.connect(self._update_total)
        row_h.addWidget(bal_edit)

        eur_lbl = make_label("EUR", 12, color=TEXT_SEC)
        row_h.addWidget(eur_lbl)

        # Edit controls (× button area)
        edit_controls = QWidget()
        edit_controls.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        edit_controls.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        edit_controls.setStyleSheet("background: transparent; border: none;")
        ec_layout = QHBoxLayout(edit_controls)
        ec_layout.setContentsMargins(0, 0, 0, 0)
        ec_layout.setSpacing(0)
        row_h.addWidget(edit_controls)

        row_h.addStretch()

        row_dict = {
            "widget": row_widget,
            "name_var": name_var,
            "name_container": name_container,
            "bal_edit": bal_edit,
            "edit_controls": edit_controls,
        }

        self._rows.append(row_dict)
        self._rows_layout.addWidget(row_widget)
        self._refresh_name_widget(row_dict)
        self._refresh_edit_controls(row_dict)
        return row_dict

    def _refresh_name_widget(self, row: dict) -> None:
        nc = row["name_container"]
        layout = nc.layout()
        _clear_layout(layout)
        if self._editing_accounts:
            entry = QLineEdit(row["name_var"][0])
            entry.setFixedWidth(260)
            entry.setPlaceholderText("Account name")
            entry.textChanged.connect(lambda t, r=row: r["name_var"].__setitem__(0, t))
            layout.addWidget(entry)
        else:
            display = row["name_var"][0] or "Unnamed"
            lbl = make_label(display, 13)
            lbl.setFixedWidth(260)
            layout.addWidget(lbl)

    def _refresh_edit_controls(self, row: dict) -> None:
        ec = row["edit_controls"]
        layout = ec.layout()
        _clear_layout(layout)
        if self._editing_accounts:
            btn = QPushButton("×")
            btn.setFixedWidth(28)
            btn.setFixedHeight(28)
            btn.setProperty("class", "danger")
            btn.setFont(QFont(FONT, 13))
            btn.clicked.connect(lambda _=False, r=row: self._remove_row(r))
            layout.addWidget(btn)
            ec.setVisible(True)
        else:
            ec.setVisible(False)

    def _toggle_account_editing(self) -> None:
        self._editing_accounts = not self._editing_accounts
        self._edit_accounts_btn.setText("Done" if self._editing_accounts else "Edit Accounts")
        for row in self._rows:
            self._refresh_name_widget(row)
            self._refresh_edit_controls(row)

    def _add_account_and_edit(self) -> None:
        if not self._editing_accounts:
            self._editing_accounts = True
            self._edit_accounts_btn.setText("Done")
            for row in self._rows:
                self._refresh_name_widget(row)
                self._refresh_edit_controls(row)
        self._add_row()

    def _remove_row(self, row: dict) -> None:
        name = row["name_var"][0].strip() or "this account"
        if not self._confirm_dialog(f'Remove "{name}" from this snapshot?', "Remove", "Cancel"):
            return
        row["widget"].setParent(None)
        row["widget"].deleteLater()
        self._rows.remove(row)
        self._update_total()

    def _clear_rows(self) -> None:
        for row in self._rows:
            row["widget"].setParent(None)
            row["widget"].deleteLater()
        self._rows.clear()

    # ── Period handling ───────────────────────────────────────────────────────

    def _get_period(self) -> tuple[int, int] | None:
        try:
            year = int(self._year_edit.text())
            month = self._month_combo.currentIndex() + 1
            return (year, month)
        except (ValueError, IndexError):
            return None

    def _on_period_change(self, *_) -> None:
        self._load_existing()

    def _load_existing(self, *_) -> None:
        # Reset edit mode
        self._editing_accounts = False
        self._edit_accounts_btn.setText("Edit Accounts")

        # Sync month pills to current combo index
        self._update_month_pills(self._month_combo.currentIndex())

        period = self._get_period()
        if period is None:
            return
        year, month = period

        self._clear_rows()

        snap = get_snapshot(year, month)
        if snap is not None:
            for name, bal in snap.items():
                self._add_row(name=name, balance=f"{bal:.2f}" if bal is not None else "")
            self._del_widget.setVisible(True)
            self._set_status(
                f"Showing saved data for {MONTHS[month - 1]} {year}. Edit fields and re-save to update.",
                TEXT_SEC,
            )
        else:
            today = date.today()
            if year > today.year or (year == today.year and month >= today.month):
                known = get_all_accounts()
                accounts = known if known else _DEFAULT_ACCOUNTS
            else:
                accounts = _DEFAULT_ACCOUNTS
            for name in accounts:
                self._add_row(name=name, balance="")
            self._del_widget.setVisible(False)
            self._set_status("", TEXT_SEC)

        # Info banner
        if snap is not None:
            self._info_banner.setVisible(False)
        else:
            prev_month_str = MONTHS[(month - 2) % 12] + (" " + str(year - 1) if month == 1 else " " + str(year))
            self._info_banner_lbl.setText(
                f"Empty draft — fill in your end-of-month balances for {MONTHS[month-1]} {year}. "
                f"Last saved snapshot was {prev_month_str}."
            )
            self._info_banner.setVisible(True)

        if hasattr(self, '_sidebar_eyebrow_lbl'):
            self._sidebar_eyebrow_lbl.setText(f"NET WORTH · {MONTHS[month-1].upper()} {year}")
        self._update_total()
        self._render_income_section()

    # ── Income section ────────────────────────────────────────────────────────

    def _render_income_section(self) -> None:
        _clear_layout(self._income_container.layout())
        self._income_amount_widgets.clear()
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
                try:
                    months_list = [int(x.strip()) for x in active_str.split(",") if x.strip()]
                    if month in months_list:
                        relevant.append(item)
                except ValueError:
                    relevant.append(item)

        if not relevant:
            return

        saved_income = get_snapshot_income(year, month)  # dict[income_id -> amount]

        # Group saved extras by income_id
        extras_by_id: dict[int, list[dict]] = {}
        for e in get_extra_income(year, month):
            e = dict(e)
            extras_by_id.setdefault(e["income_id"], []).append(e)

        # Section header
        income_hdr = QWidget()
        income_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        income_hdr.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        income_hdr.setStyleSheet("background: transparent;")
        income_hdr_v = QVBoxLayout(income_hdr)
        income_hdr_v.setContentsMargins(0, 0, 0, 0)
        income_hdr_v.setSpacing(2)
        income_hdr_v.addWidget(make_label("Income This Month", 15, bold=True))
        income_hdr_v.addWidget(make_label(
            f"Active income lines for {MONTHS[month-1]} {year} · {len(relevant)} sources",
            12, color=TEXT_SEC,
        ))
        self._income_container.layout().addWidget(income_hdr)

        card = make_card_l2()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        for inc in relevant:
            iid = inc["id"]
            saved_val = saved_income.get(iid)
            default_amt = f"{saved_val:.2f}" if saved_val is not None else f"{inc['amount']:.2f}"

            self._extra_income_rows[iid] = []

            # Main income row
            row_widget = QWidget()
            row_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_widget.setStyleSheet("background: transparent; border: none;")
            row_h = QHBoxLayout(row_widget)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(8)

            name_lbl = make_label(inc["name"], 13)
            name_lbl.setFixedWidth(260)
            row_h.addWidget(name_lbl)

            row_h.addWidget(make_label("EUR", 12, color=TEXT_SEC))

            amt_edit = QLineEdit()
            amt_edit.setFixedWidth(110)
            amt_edit.setPlaceholderText("0.00")
            amt_edit.setText(default_amt)
            bind_numeric_entry(amt_edit)
            self._income_amount_widgets[iid] = amt_edit
            row_h.addWidget(amt_edit)
            row_h.addStretch()
            card_layout.addWidget(row_widget)

            # Extras frame (hidden until first extra is added)
            extras_frame = QWidget()
            extras_frame.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            extras_frame.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            extras_frame.setStyleSheet("background: transparent; border: none;")
            extras_vlayout = QVBoxLayout(extras_frame)
            extras_vlayout.setContentsMargins(0, 0, 0, 0)
            extras_vlayout.setSpacing(4)
            extras_frame.setVisible(False)
            card_layout.addWidget(extras_frame)

            # Pre-populate saved extras
            for ex in extras_by_id.get(iid, []):
                self._add_extra_row(
                    iid, extras_frame,
                    desc=ex.get("description", ""),
                    amount=str(ex.get("amount", "")),
                )

            # "+ Add bonus" button
            bonus_btn = QPushButton("+ Add bonus")
            bonus_btn.setFixedWidth(100)
            bonus_btn.setFont(QFont(FONT, 11))
            bonus_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {TEXT_SEC}; border: none;"
                f" text-align: left; padding: 0; }}"
                f"QPushButton:hover {{ color: {TEXT_PRI}; }}"
            )
            bonus_btn.clicked.connect(
                lambda _=False, i=iid, f=extras_frame: self._add_extra_row(i, f)
            )
            card_layout.addWidget(bonus_btn)

        self._income_container.layout().addWidget(card)

    def _add_extra_row(self, income_id: int, frame: QWidget, desc: str = "", amount: str = "") -> None:
        frame.setVisible(True)

        row_widget = QWidget()
        row_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_widget.setStyleSheet("background: transparent; border: none;")
        row_h = QHBoxLayout(row_widget)
        row_h.setContentsMargins(0, 0, 0, 0)
        row_h.setSpacing(8)

        # Indent spacer
        spacer = QWidget()
        spacer.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        spacer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        spacer.setFixedWidth(20)
        spacer.setStyleSheet("background: transparent; border: none;")
        row_h.addWidget(spacer)

        desc_edit = QLineEdit()
        desc_edit.setFixedWidth(200)
        desc_edit.setPlaceholderText("Description")
        if desc:
            desc_edit.setText(desc)
        row_h.addWidget(desc_edit)

        row_h.addWidget(make_label("EUR", 12, color=TEXT_SEC))

        amt_edit = QLineEdit()
        amt_edit.setFixedWidth(90)
        amt_edit.setPlaceholderText("0.00")
        bind_numeric_entry(amt_edit)
        if amount:
            amt_edit.setText(amount)
        row_h.addWidget(amt_edit)

        extra_dict = {"desc_edit": desc_edit, "amt_edit": amt_edit, "widget": row_widget}
        self._extra_income_rows.setdefault(income_id, []).append(extra_dict)

        rm_btn = QPushButton("×")
        rm_btn.setFixedWidth(28)
        rm_btn.setFixedHeight(28)
        rm_btn.setProperty("class", "danger")
        rm_btn.setFont(QFont(FONT, 13))

        def _rm(checked: bool = False, ed: dict = extra_dict, iid: int = income_id, fw: QWidget = frame) -> None:
            ed["widget"].setParent(None)
            ed["widget"].deleteLater()
            self._extra_income_rows[iid].remove(ed)
            if not self._extra_income_rows[iid]:
                fw.setVisible(False)

        rm_btn.clicked.connect(_rm)
        row_h.addWidget(rm_btn)
        row_h.addStretch()

        frame.layout().addWidget(row_widget)

    # ── Totals ────────────────────────────────────────────────────────────────

    def _update_total(self) -> None:
        total = 0.0
        for row in self._rows:
            try:
                val = float(row["bal_edit"].text().replace(",", "."))
                total += val
            except (ValueError, AttributeError):
                pass
        self._total_label.setText(fmt_eur(total))
        self._update_sidebar_stats()

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        period = self._get_period()
        if period is None:
            self._set_status("Invalid period.", RED)
            return
        year, month = period

        # Future month warning
        today = date.today()
        if year > today.year or (year == today.year and month > today.month):
            if not self._confirm_dialog(
                f"You are entering data for a future month ({MONTHS[month - 1]} {year}). "
                "This month has not started yet. Do you want to continue?",
                "Continue", "Cancel",
            ):
                return

        # Collect balances
        balances: dict[str, float] = {}
        for row in self._rows:
            name = row["name_var"][0].strip()
            if not name:
                self._set_status("Account name cannot be empty.", RED)
                return
            try:
                val = float(row["bal_edit"].text().replace(",", ".") or "0")
            except ValueError:
                self._set_status(f'Invalid balance for "{name}".', RED)
                return
            balances[name] = val

        if not balances:
            self._set_status("Add at least one account before saving.", RED)
            return

        # Overwrite warning
        if get_snapshot(year, month) is not None:
            month_name_str = MONTHS[month - 1]
            if not self._confirm_dialog(
                f"A snapshot for {month_name_str} {year} already exists.\nDo you want to overwrite it?",
                "Overwrite", "Cancel",
            ):
                return

        total_snapshots = save_snapshot(year, month, balances)

        # Store current portfolio value with the snapshot
        # Only update portfolio_eur for the current month — never overwrite historical months
        today = date.today()
        if year == today.year and month == today.month:
            try:
                positions = get_portfolio_positions()
                cache = get_portfolio_cache()
                port_total_eur = 0.0
                for pos in positions:
                    t = pos["ticker"]
                    if t not in cache:
                        continue
                    c = cache[t]
                    price_eur = c.get("price_eur") or c.get("price", 0.0)
                    port_total_eur += pos["shares"] * price_eur
                # Only write if we actually have priced positions — never zero out a good value
                if port_total_eur > 0:
                    update_snapshot_portfolio(year, month, port_total_eur)
            except Exception:
                pass

        # Save income amounts
        for iid, widget in self._income_amount_widgets.items():
            try:
                amt = float(widget.text().replace(",", ".") or "0")
            except ValueError:
                amt = 0.0
            set_snapshot_income(year, month, iid, amt)

        # Save extra income
        for iid, extras in self._extra_income_rows.items():
            clear_extra_income(year, month, iid)
            for ex in extras:
                desc = ex["desc_edit"].text().strip()
                try:
                    amt = float(ex["amt_edit"].text().replace(",", ".") or "0")
                except ValueError:
                    amt = 0.0
                if desc or amt > 0:
                    add_extra_income(year, month, iid, desc, amt)

        month_name = MONTHS[month - 1]
        if total_snapshots == 1:
            self._set_status(
                f"Snapshot saved for {month_name} {year}."
                "  Add next month's data to see your first net worth change.",
                GREEN,
            )
        else:
            self._set_status(
                f"Snapshot saved for {month_name} {year}.  Net Worth: {fmt_eur(sum(balances.values()))}",
                GREEN,
            )

        self._del_widget.setVisible(True)
        self._show_portfolio_reminder()
        self._update_total()
        self._maybe_show_deduction_dialog(year, month, balances)

    # ── Delete snapshot ───────────────────────────────────────────────────────

    def _delete_snapshot(self) -> None:
        period = self._get_period()
        if period is None:
            return
        year, month = period
        month_name = MONTHS[month - 1]
        if not self._confirm_dialog(
            f"Are you sure you want to delete the snapshot for {month_name} {year}?",
            "Delete", "Cancel",
        ):
            return
        delete_snapshot(year, month)
        self._load_existing()
        self._set_status(f"Snapshot for {month_name} {year} deleted.", TEXT_SEC)

    # ── Post-save deduction dialog ────────────────────────────────────────────

    def _maybe_show_deduction_dialog(
        self, year: int, month: int, balances: dict[str, float]
    ) -> None:
        today = date.today()
        if year != today.year or month != today.month:
            return
        last_day = calendar.monthrange(year, month)[1]
        if today.day >= last_day:
            return

        daily_buffer = float(get_setting("daily_buffer") or "20.0")
        remaining_days = last_day - today.day
        expenses = list(get_all_expenses())

        remaining_fx: list = []
        for e in expenses:
            d = e["day_of_month"]
            eff_d = effective_charge_day(today.year, today.month, d, last_day)
            if eff_d > today.day:
                remaining_fx.append(e)

        buffer_cost = remaining_days * daily_buffer
        fx_total = sum(e["amount"] for e in remaining_fx)
        total_cost = buffer_cost + fx_total

        if total_cost <= 0 or not balances:
            return

        confirmed, account_name, actual_total = self._show_deduction_dialog(
            year, month, balances, remaining_days, daily_buffer,
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
                    "Continue", "Cancel",
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
                GREEN,
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

        dlg = open_dialog(self, 580, 520)
        dlg.setWindowTitle("Deduct Estimated Remaining Costs?")

        outer_layout = QVBoxLayout(dlg)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scrollable inner area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll_content.setStyleSheet(f"background: {BG_MAIN}; border: none;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(20, 16, 20, 8)
        scroll_layout.setSpacing(6)
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll, 1)

        scroll_layout.addWidget(make_label("Deduct estimated remaining costs?", 15, bold=True))
        days_lbl = make_label(
            f"{remaining_days} day{'s' if remaining_days != 1 else ''} remaining in {MONTHS[month - 1]} {year}",
            12, color=TEXT_SEC,
        )
        scroll_layout.addWidget(days_lbl)

        def _dlg_row(label_text: str, value_text: str, value_color: str = TEXT_PRI) -> QWidget:
            w = QWidget()
            w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            w.setStyleSheet("background: transparent; border: none;")
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 1, 0, 1)
            lbl = make_label(label_text, 12, color=TEXT_SEC)
            h.addWidget(lbl)
            h.addStretch()
            val = make_label(value_text, 12, color=value_color)
            h.addWidget(val)
            return w

        buffer_cost = remaining_days * daily_buffer
        scroll_layout.addWidget(
            _dlg_row(
                f"Daily Spending Allowance  ({remaining_days} × €{daily_buffer:.0f}/day)",
                f"–{fmt_eur(buffer_cost)}", RED,
            )
        )

        fx_total = sum(e["amount"] for e in remaining_fx)
        fx_hdr = QWidget()
        fx_hdr.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        fx_hdr.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        fx_hdr.setStyleSheet("background: transparent; border: none;")
        fx_hdr_h = QHBoxLayout(fx_hdr)
        fx_hdr_h.setContentsMargins(0, 2, 0, 0)
        fx_hdr_h.addWidget(make_label(f"Remaining fixed expenses  ({len(remaining_fx)} items)", 12, color=TEXT_SEC))
        fx_hdr_h.addStretch()
        fx_hdr_h.addWidget(make_label(f"–{fmt_eur(fx_total)}", 12, color=RED))
        scroll_layout.addWidget(fx_hdr)

        for e in remaining_fx:
            d = e["day_of_month"]
            eff_d = effective_charge_day(year, month, d, last_day)
            day_label = "end of month" if (d == 31 and last_day < 31) else f"day {eff_d}"
            scroll_layout.addWidget(
                _dlg_row(f"  · {e['name']}  ({day_label})", f"–{fmt_eur(e['amount'])}", RED)
            )

        scroll_layout.addWidget(make_divider())

        subtotal_w = QWidget()
        subtotal_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        subtotal_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        subtotal_w.setStyleSheet("background: transparent; border: none;")
        sub_h = QHBoxLayout(subtotal_w)
        sub_h.setContentsMargins(0, 4, 0, 4)
        sub_h.addWidget(make_label("Estimated costs subtotal", 13, bold=True))
        sub_h.addStretch()
        sub_h.addWidget(make_label(f"–{fmt_eur(total_cost)}", 13, bold=True, color=RED))
        scroll_layout.addWidget(subtotal_w)

        scroll_layout.addWidget(make_divider())

        # Extra one-time cost
        extra_row = QWidget()
        extra_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        extra_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        extra_row.setStyleSheet("background: transparent; border: none;")
        extra_h = QHBoxLayout(extra_row)
        extra_h.setContentsMargins(0, 4, 0, 0)
        extra_h.setSpacing(8)
        extra_h.addWidget(make_label("Extra one-time cost:", 13))
        extra_edit = QLineEdit("0.00")
        extra_edit.setFixedWidth(110)
        bind_numeric_entry(extra_edit)
        extra_h.addWidget(extra_edit)
        extra_h.addWidget(make_label("EUR", 13))
        extra_h.addStretch()
        scroll_layout.addWidget(extra_row)

        hint_lbl = make_label("e.g. car insurance, dentist, travel", 11, color=TEXT_SEC)
        scroll_layout.addWidget(hint_lbl)

        # Grand total label
        grand_w = QWidget()
        grand_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        grand_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        grand_w.setStyleSheet("background: transparent; border: none;")
        grand_h = QHBoxLayout(grand_w)
        grand_h.setContentsMargins(0, 4, 0, 4)
        grand_h.addWidget(make_label("TOTAL TO DEDUCT", 13, bold=True))
        grand_h.addStretch()
        self._grand_total_lbl = make_label(f"–{fmt_eur(total_cost)}", 13, bold=True, color=RED)
        grand_h.addWidget(self._grand_total_lbl)
        scroll_layout.addWidget(grand_w)

        def _update_grand(text: str) -> None:
            try:
                extra = max(0.0, float(text.replace(",", ".") or "0"))
            except ValueError:
                extra = 0.0
            self._grand_total_lbl.setText(f"–{fmt_eur(total_cost + extra)}")

        extra_edit.textChanged.connect(_update_grand)

        scroll_layout.addWidget(make_divider())

        # Account selector
        sel_w = QWidget()
        sel_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        sel_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        sel_w.setStyleSheet("background: transparent; border: none;")
        sel_h = QHBoxLayout(sel_w)
        sel_h.setContentsMargins(0, 4, 0, 4)
        sel_h.setSpacing(12)
        sel_h.addWidget(make_label("Deduct from:", 13))
        account_combo = QComboBox()
        account_combo.addItems(list(balances.keys()))
        account_combo.setFixedWidth(220)
        sel_h.addWidget(account_combo)
        sel_h.addStretch()
        scroll_layout.addWidget(sel_w)
        scroll_layout.addStretch()

        # Button row (outside scroll area)
        btn_row = QWidget()
        btn_row.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row.setStyleSheet(f"background: {BG_MAIN}; border: none;")
        btn_h = QHBoxLayout(btn_row)
        btn_h.setContentsMargins(20, 8, 20, 12)
        btn_h.setSpacing(8)

        yes_btn = QPushButton("Yes, deduct")
        yes_btn.setProperty("class", "accent")
        yes_btn.setFixedWidth(130)
        yes_btn.setFont(QFont(FONT, 12))

        skip_btn = QPushButton("Skip")
        skip_btn.setFixedWidth(80)
        skip_btn.setFont(QFont(FONT, 12))

        btn_h.addWidget(yes_btn)
        btn_h.addWidget(skip_btn)
        btn_h.addStretch()
        outer_layout.addWidget(btn_row)

        def on_yes() -> None:
            try:
                extra = max(0.0, float(extra_edit.text().replace(",", ".") or "0"))
            except ValueError:
                extra = 0.0
            result[0] = True
            result[1] = account_combo.currentText()
            result[2] = total_cost + extra
            dlg.accept()

        def on_skip() -> None:
            dlg.reject()

        yes_btn.clicked.connect(on_yes)
        skip_btn.clicked.connect(on_skip)

        dlg.exec()
        return result[0], result[1], result[2]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _confirm_dialog(
        self, message: str, confirm_text: str = "Confirm", cancel_text: str = "Cancel"
    ) -> bool:
        dlg = open_dialog(self, 380, 160)
        dlg.setWindowTitle("Confirm")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        lbl = QLabel(message)
        lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl.setWordWrap(True)
        lbl.setFont(QFont(FONT, 13))
        lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
        layout.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setFont(QFont(FONT, 12))
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setFont(QFont(FONT, 12))
        confirm_btn.setProperty("class", "accent")
        confirm_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(confirm_btn)

        layout.addLayout(btn_row)
        return dlg.exec() == QDialog.DialogCode.Accepted

    def _set_status(self, text: str, color: str = TEXT_SEC) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; background: transparent;")

    def _show_portfolio_reminder(self) -> None:
        if not hasattr(self, '_portfolio_reminder_widget'):
            return
        self._portfolio_reminder_widget.setVisible(True)
        QTimer.singleShot(30000, lambda: self._portfolio_reminder_widget.setVisible(False))
