"""Help tab — searchable user guide (PyQt6)."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QLineEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from styles.theme import (
    BG_CARD, BG_ELEM, BG_MAIN, ACCENT, TEXT_PRI, TEXT_SEC,
    BORDER, GREEN, RED, FONT
)

_HIGHLIGHT   = "#0d2035"   # kept but unused
_MATCH_COLOR = "#f0c040"   # yellow highlight for matched text


# ── Help content data ─────────────────────────────────────────────────────────

_HELP_DATA = [
    {
        "section": "Getting Started",
        "items": [
            {"type": "body", "text": (
                "Money Tracker uses a snapshot model: once per month (ideally on the last day), "
                "you enter the current balance of each of your accounts. The app calculates "
                "the difference between consecutive months to determine your net worth change, "
                "income, savings rate, and more."
            )},
            {"type": "body", "text": (
                "After saving your first snapshot, you won't see comparison stats yet — "
                "you need at least two monthly snapshots before the app can calculate changes. "
                "Once you have two or more snapshots, the Dashboard, Analytics, and all stats "
                "become fully populated."
            )},
        ],
    },
    {
        "section": "Monthly Snapshot",
        "items": [
            {"type": "heading", "text": "Account rows"},
            {"type": "body", "text": (
                "Each row represents one account (bank account, cash, brokerage, etc.). "
                "Enter the current balance in EUR. You can add or remove accounts at any time — "
                "the account list is fully dynamic."
            )},
            {"type": "body", "text": (
                "To rename or remove accounts, click Edit Accounts. All name fields become "
                "editable entries and × remove buttons appear. Click Done when finished. "
                "Clicking + Add Account automatically enables edit mode."
            )},
            {"type": "body", "text": (
                "When you navigate to a current or future month with no saved snapshot yet, "
                "all accounts you've ever saved are pre-filled with empty balances so you don't "
                "have to re-type account names every month."
            )},
            {"type": "heading", "text": "Income This Month"},
            {"type": "body", "text": (
                "When you open Monthly Snapshot for a period where you have active income sources, "
                "an 'Income This Month' section appears above the Save Snapshot button. Enter the "
                "actual amount received for each income source. This is saved per month and used "
                "for tracking actual vs. expected income over time."
            )},
            {"type": "body", "text": (
                "To log a one-time extra payment (e.g. bonus, holiday pay) for any income source, "
                "click + Add bonus next to that source. Enter a description and the amount. You can "
                "add multiple bonuses per source. Extras are saved with the snapshot and shown on the "
                "Dashboard income card."
            )},
            {"type": "heading", "text": "Saving a snapshot"},
            {"type": "body", "text": (
                "Click Save Snapshot when you've entered all balances and income amounts. "
                "A confirmation message shows your net worth."
            )},
            {"type": "body", "text": (
                "If a snapshot for the selected period already exists, a confirmation dialog "
                "appears asking whether to overwrite it. Click Overwrite to replace it or "
                "Cancel to keep the existing data."
            )},
            {"type": "body", "text": (
                "Saving a snapshot for a future month shows a warning. This is allowed but not "
                "recommended — wait until the end of the month for accurate data."
            )},
            {"type": "heading", "text": "Deleting a snapshot"},
            {"type": "body", "text": (
                "When a snapshot has been saved for a period, a red Delete Snapshot button "
                "appears below Save Snapshot. Clicking it asks for confirmation before "
                "permanently deleting the snapshot and all its balance data."
            )},
            {"type": "heading", "text": "Mid-month deduction"},
            {"type": "body", "text": (
                "After saving a snapshot mid-month, a dialog asks if you'd like to deduct "
                "estimated remaining costs from one of your accounts. This adjusts "
                "the saved balance to reflect what you expect to spend by month end. You can also "
                "add a one-time extra cost (e.g. upcoming large expense). Skip this dialog if you "
                "prefer to enter exact balances at month end instead."
            )},
        ],
    },
    {
        "section": "Budget Tab",
        "items": [
            {"type": "heading", "text": "Fixed Monthly Expenses"},
            {"type": "body", "text": (
                "Fixed expenses are recurring charges that happen every month on a predictable "
                "day (rent, subscriptions, insurance, etc.). Add them once and they stay "
                "permanently in the list. They feed into the end-of-month estimate on the Dashboard."
            )},
            {"type": "body", "text": (
                "Click Edit in the section header to enter edit mode. In edit mode, all rows "
                "become editable entries simultaneously. Click × to delete a row (with "
                "confirmation). Click Done to save all changes and exit edit mode."
            )},
            {"type": "body", "text": (
                "Expenses with day 31 are treated as end-of-month charges and are always "
                "counted as remaining in months that have fewer than 31 days."
            )},
            {"type": "heading", "text": "Monthly Income"},
            {"type": "body", "text": (
                "Track your regular income sources (salary, freelance income, seasonal work, etc.). "
                "Each income source has a name, expected amount, and a set of active months."
            )},
            {"type": "body", "text": (
                "Active months determine which months show this income source in the "
                "'Income This Month' section of Monthly Snapshot. If all 12 months are checked, "
                "the income appears every month. Uncheck months where the income doesn't apply "
                "(e.g. summer-only work, quarterly payments)."
            )},
            {"type": "body", "text": (
                "Click Edit in the Monthly Income section header to enter edit mode. All rows "
                "become editable simultaneously — change the name, amount, and active months. "
                "Click × to delete a source (with confirmation). Click Done to save all changes."
            )},
        ],
    },
    {
        "section": "Dashboard",
        "items": [
            {"type": "heading", "text": "Net Worth card"},
            {"type": "body", "text": (
                "Shows your total balance across all accounts in the latest snapshot. "
                "If you have portfolio positions with cached prices, a secondary line shows "
                "the total net worth including your portfolio value."
            )},
            {"type": "heading", "text": "Metric cards"},
            {"type": "body", "text": "The cards at the top show your most recent month's key numbers:"},
            {"type": "bullet", "text": "Net Worth — total balance across all accounts in the latest snapshot"},
            {"type": "bullet", "text": (
                "Monthly Change — difference between latest and previous snapshot net worths, "
                "with percentage"
            )},
            {"type": "bullet", "text": "Fixed Expenses — sum of all your fixed monthly expenses (from the Budget tab)"},
            {"type": "bullet", "text": (
                "Portfolio — current total value of your portfolio positions (from live prices), "
                "with overall P&L in EUR and percentage. Shown only when you have positions and "
                "cached prices in the Portfolio tab."
            )},
            {"type": "bullet", "text": (
                "Allocation — a doughnut chart showing each position's share of total portfolio "
                "value. Shown next to the Portfolio card when positions have cached prices."
            )},
            {"type": "bullet", "text": (
                "Last Month Income — actual income recorded for the previous month "
                "(snapshot income + any bonuses), with percentage change vs. the month before. "
                "Shown only when income has been logged for at least one prior month."
            )},
            {"type": "heading", "text": "Reminder banner"},
            {"type": "body", "text": (
                "If today is after the 20th and no snapshot has been saved for the previous "
                "month, a yellow reminder banner appears at the top of the Dashboard. "
                "Click Go to Snapshot to jump directly to the snapshot entry for that month. "
                "The reminder only appears for months after your first ever recorded snapshot."
            )},
            {"type": "heading", "text": "Snapshot History"},
            {"type": "body", "text": (
                "A compact grid at the bottom of the Dashboard showing all months across all "
                "years. A ✓ button indicates a saved snapshot — click it to navigate directly "
                "to that month in the Monthly Snapshot view. A · indicates no snapshot for that month."
            )},
            {"type": "heading", "text": "Annual Overview"},
            {"type": "body", "text": (
                "Below the metric cards, the Annual Overview shows statistics for the current "
                "calendar year: best month, worst month, average monthly change, and total saved "
                "(sum of all positive months). Requires at least two snapshots in the year."
            )},
            {"type": "heading", "text": "Account Breakdown"},
            {"type": "body", "text": (
                "A table showing each account's balance in the latest snapshot, compared to "
                "the previous snapshot, with the change highlighted in green or red."
            )},
            {"type": "heading", "text": "Export to CSV"},
            {"type": "body", "text": (
                "The Export to CSV button at the bottom of the Dashboard saves all your snapshot "
                "data to a CSV file. Each row contains year, month, account name, and balance."
            )},
        ],
    },
    {
        "section": "Portfolio Tab",
        "items": [
            {"type": "body", "text": (
                "Track your investment positions with live prices fetched automatically. "
                "Each position stores a ticker symbol, number of shares, average buy price, "
                "and the price currency."
            )},
            {"type": "heading", "text": "Position cards"},
            {"type": "body", "text": (
                "Each card shows the ticker, company name, current price (in original currency "
                "and EUR equivalent), today's price change, current value, and P&L vs. your "
                "average buy price. EUR conversion uses the live exchange rate."
            )},
            {"type": "heading", "text": "Portfolio summary"},
            {"type": "body", "text": (
                "The summary card at the top shows total portfolio value in EUR and total P&L "
                "across all positions combined."
            )},
            {"type": "heading", "text": "Refreshing prices"},
            {"type": "body", "text": (
                "Prices are fetched automatically when you open the tab. Click Refresh to "
                "update at any time. If the live fetch fails, the app falls back to the last "
                "cached prices and shows a warning banner."
            )},
            {"type": "heading", "text": "Adding and editing positions"},
            {"type": "body", "text": (
                "Click + Add Position and enter the ticker symbol (e.g. AAPL, MSFT, VWRL.L), "
                "number of shares, average buy price, and currency. Click Edit on any card to "
                "update an existing position, or × to remove it."
            )},
            {"type": "heading", "text": "Rebalance Reminder"},
            {"type": "body", "text": (
                "Click 'Set reminder ▾' next to the Add Position button and choose "
                "'In 1 year' to set a reminder one year from today, or 'Custom...' to enter "
                "a specific date in DD.MM.YYYY format."
            )},
            {"type": "body", "text": (
                "When the reminder date is within 30 days, a yellow warning banner appears at "
                "the top of the Portfolio tab and a badge appears on the Portfolio card in the "
                "Dashboard. When more than 30 days away, the status is shown in teal."
            )},
        ],
    },
    {
        "section": "Analytics Tab",
        "items": [
            {"type": "body", "text": (
                "Snapshot-based charts are generated from your saved snapshots. At least two "
                "snapshots are required for most charts to appear."
            )},
            {"type": "body", "text": (
                "Each chart has a row of time filter buttons (All, YTD, 1Y, 6M, 3M, 1M) that "
                "let you zoom into a specific period. Filters are independent — changing one "
                "chart's filter does not affect the others."
            )},
            {"type": "bullet", "text": (
                "Net Worth Over Time — smooth line chart of your net worth across all accounts. "
                "Shows current value and change from the previous data point."
            )},
            {"type": "bullet", "text": (
                "Monthly Net Worth Change — bar chart of month-on-month changes; "
                "green = growth, red = decline."
            )},
            {"type": "bullet", "text": (
                "Cash Flow — grouped bar chart with income (green) and spending (red) per month, "
                "plus a net savings overlay line. Spending is shown for any month that has a "
                "previous snapshot to compare against. The first snapshot never shows a spending bar."
            )},
            {"type": "bullet", "text": (
                "Account Tracker — select one or more accounts and/or income sources with the "
                "checkboxes to plot their values over time. Account balances are shown as solid "
                "lines; actual income amounts are shown as dashed lines."
            )},
        ],
    },
    {
        "section": "Notes Tab",
        "items": [
            {"type": "heading", "text": "My Notes"},
            {"type": "body", "text": (
                "A free-text area where you can write anything — reminders, financial goals, "
                "context for unusual months, etc. Click Save Notes to persist your text."
            )},
            {"type": "heading", "text": "Debt / Credit Notes"},
            {"type": "body", "text": (
                "Track money owed between you and others. Each note has a description, an "
                "amount, and a direction: They owe me or I owe them. The summary cards show "
                "your net position. These notes are for reference only — they are not included "
                "in net worth or any other calculations."
            )},
        ],
    },
    {
        "section": "Settings Tab",
        "items": [
            {"type": "heading", "text": "Daily Spending Allowance"},
            {"type": "body", "text": (
                "Your estimated budget per day for variable spending (food, transport, leisure, "
                "etc.). Used in the end-of-month estimate shown on the Dashboard."
            )},
            {"type": "heading", "text": "Appearance"},
            {"type": "body", "text": (
                "Choose between System (follows your OS setting), Light, or Dark mode. "
                "The setting is saved and applied automatically on the next launch."
            )},
            {"type": "heading", "text": "Backup & Restore"},
            {"type": "body", "text": (
                "Backup saves a copy of your tracker database (tracker.db) to a location you "
                "choose. Restore replaces the current database with a backup file and closes "
                "the app — reopen it to see the restored data."
            )},
            {"type": "heading", "text": "Reset All Data"},
            {"type": "body", "text": (
                "Permanently deletes all snapshots, accounts, expenses, income, and notes, and "
                "resets settings to defaults. The app closes after reset. Type DELETE in the "
                "confirmation dialog to proceed."
            )},
        ],
    },
    {
        "section": "Notifications",
        "items": [
            {"type": "body", "text": (
                "Money Tracker can remind you to enter your monthly snapshot via email and "
                "an in-app banner. Configure both in Settings → Notifications."
            )},
            {"type": "heading", "text": "In-App Banner"},
            {"type": "body", "text": (
                "A yellow banner appears at the top of the app when you are within the "
                "configured number of days before the end of the month and no snapshot has "
                "been saved yet. Click the banner to go directly to Monthly Snapshot, or "
                "dismiss it with ×. The banner is session-only — it reappears on the next "
                "launch if the conditions are still met."
            )},
            {"type": "heading", "text": "Email Reminder"},
            {"type": "body", "text": (
                "Email reminders are sent via Resend (resend.com), a transactional email "
                "service. Enable the toggle, enter your email address, and paste your "
                "Resend API key. The reminder is sent once per month at 17:00 when you "
                "are within the configured number of days before the end of the month "
                "and no snapshot exists for that month yet."
            )},
            {"type": "heading", "text": "Resend API Key"},
            {"type": "bullet", "text": "Create a free account at resend.com and generate an API key from the dashboard."},
            {"type": "bullet", "text": "The free tier allows up to 100 emails/day and 3,000/month — more than enough for one reminder per month."},
            {"type": "bullet", "text": "The default sender (onboarding@resend.dev) works without domain verification but can only deliver to your verified Resend account email."},
            {"type": "bullet", "text": "To send to any email address, add and verify your own domain in Resend and update the sender in notifier.py."},
            {"type": "heading", "text": "Reminder Days"},
            {"type": "bullet", "text": "Email days (1–15): how many days before the end of the month the email is sent."},
            {"type": "bullet", "text": "Banner days (1–15): how many days before the end of the month the in-app banner appears."},
            {"type": "heading", "text": "Background Service (launchd)"},
            {"type": "body", "text": (
                "The email is sent by notifier.py, a standalone script run daily by macOS "
                "launchd. The plist file is at "
                "~/Library/LaunchAgents/com.moneytracker.notifier.plist. "
                "Load it once with:"
            )},
            {"type": "bullet", "text": "launchctl load ~/Library/LaunchAgents/com.moneytracker.notifier.plist"},
            {"type": "bullet", "text": "Verify: launchctl list | grep moneytracker"},
            {"type": "bullet", "text": "Unload: launchctl unload ~/Library/LaunchAgents/com.moneytracker.notifier.plist"},
            {"type": "body", "text": (
                "Logs are written to ~/Library/Logs/MoneyTracker/notifier.log. "
                "Use 'Send test email' in Settings to verify your API key before "
                "relying on the scheduled service."
            )},
        ],
    },
    {
        "section": "Tips & Best Practices",
        "items": [
            {"type": "bullet", "text": "Enter your snapshot on the last day of each month for the most accurate data."},
            {"type": "bullet", "text": (
                "Add all your regular income sources to the Monthly Income section (Budget tab). "
                "Uncheck months where a source is not active to keep the 'Income This Month' "
                "section in snapshots clean."
            )},
            {"type": "bullet", "text": (
                "Use the Extra one-time cost field in the post-save deduction dialog for known "
                "upcoming expenses so the adjusted balance reflects your real expected position."
            )},
            {"type": "bullet", "text": (
                "If you missed a month, you can still enter a snapshot for any past month — "
                "just select the correct period in the period selector, or click the · cell "
                "in the Snapshot History grid on the Dashboard."
            )},
            {"type": "bullet", "text": (
                "Fixed expenses with day 31 (e.g. end-of-month bank fees) are always counted in "
                "the end-of-month estimate for months shorter than 31 days."
            )},
            {"type": "bullet", "text": "Export to CSV regularly as an extra backup of your financial history."},
            {"type": "bullet", "text": (
                "Set a Rebalance Reminder in the Portfolio tab to get a timely prompt when your "
                "investment allocation needs attention."
            )},
        ],
    },
]


# ── Inline text-segment helper ────────────────────────────────────────────────

def _pack_text_segments(
    parent_layout,
    text: str,
    term_lower: str,
    font_size: int,
    normal_color: str,
    bold: bool = False,
) -> None:
    """Add inline QLabel segments with the search term highlighted in yellow."""
    if not term_lower or term_lower not in text.lower():
        lbl = QLabel(text)
        lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl.setFont(QFont(FONT, font_size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
        lbl.setStyleSheet(f"color: {normal_color}; background: transparent; border: none;")
        lbl.setWordWrap(True)
        parent_layout.addWidget(lbl)
        return

    row_widget = QWidget()
    row_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    row_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    row_widget.setStyleSheet("background: transparent; border: none;")
    row_h = QHBoxLayout(row_widget)
    row_h.setContentsMargins(0, 0, 0, 0)
    row_h.setSpacing(0)

    lower_text = text.lower()
    idx = 0
    while idx < len(text):
        pos = lower_text.find(term_lower, idx)
        if pos == -1:
            segment = text[idx:]
            if segment:
                lbl = QLabel(segment)
                lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                lbl.setFont(QFont(FONT, font_size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
                lbl.setStyleSheet(f"color: {normal_color}; background: transparent; border: none;")
                row_h.addWidget(lbl)
            break
        if pos > idx:
            segment = text[idx:pos]
            lbl = QLabel(segment)
            lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            lbl.setFont(QFont(FONT, font_size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            lbl.setStyleSheet(f"color: {normal_color}; background: transparent; border: none;")
            row_h.addWidget(lbl)
        match_segment = text[pos:pos + len(term_lower)]
        lbl = QLabel(match_segment)
        lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl.setFont(QFont(FONT, font_size, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #f0c040; background: transparent; border: none;")
        row_h.addWidget(lbl)
        idx = pos + len(term_lower)

    row_h.addStretch()
    parent_layout.addWidget(row_widget)


# ── View ──────────────────────────────────────────────────────────────────────

class HelpView(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        self._search_term: str = ""

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setStyleSheet("background: #0d1117;")
        self._outer_layout = QVBoxLayout(content)
        self._outer_layout.setContentsMargins(24, 24, 24, 24)
        self._outer_layout.setSpacing(4)
        self.setWidget(content)

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Header row: title (left) + search (right)
        top_row_w = QWidget()
        top_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        top_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        top_row_w.setStyleSheet("background: transparent; border: none;")
        top_row = QHBoxLayout(top_row_w)
        top_row.setContentsMargins(0, 0, 0, 2)
        top_row.setSpacing(12)

        title_lbl = QLabel("Help & User Guide")
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        title_lbl.setFont(QFont(FONT, 22, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        # Search container
        search_container = QFrame()
        search_container.setFrameShape(QFrame.Shape.NoFrame)
        search_container.setFrameShadow(QFrame.Shadow.Plain)
        search_container.setLineWidth(0)
        search_container.setStyleSheet(
            f"QFrame {{ background: {BG_ELEM}; border: 1px solid {BORDER}; border-radius: 8px; }}"
            f"QFrame QWidget {{ background: transparent; border: none; }}"
            f"QFrame QLabel {{ border: none; background: transparent; }}"
        )
        sc_layout = QHBoxLayout(search_container)
        sc_layout.setContentsMargins(8, 4, 4, 4)
        sc_layout.setSpacing(2)

        icon_lbl = QLabel("🔍")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        icon_lbl.setFont(QFont(FONT, 13))
        icon_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        sc_layout.addWidget(icon_lbl)

        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText("Search...")
        self._search_entry.setFont(QFont(FONT, 13))
        self._search_entry.setFixedWidth(220)
        self._search_entry.setFixedHeight(28)
        self._search_entry.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #e6edf3; padding: 0 4px; }"
        )
        self._search_entry.textChanged.connect(self._on_search_change)
        sc_layout.addWidget(self._search_entry)

        self._clear_btn = QPushButton("×")
        self._clear_btn.setFixedSize(24, 24)
        self._clear_btn.setFont(QFont(FONT, 14))
        self._clear_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SEC}; border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background: #3d4d63; }}"
        )
        self._clear_btn.clicked.connect(self._clear_search)
        self._clear_btn.setVisible(False)
        sc_layout.addWidget(self._clear_btn)

        top_row.addWidget(search_container)
        self._outer_layout.addWidget(top_row_w)

        # Subtitle
        sub_lbl = QLabel("Everything you need to know about using Money Tracker.")
        sub_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        sub_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        sub_lbl.setFont(QFont(FONT, 13))
        sub_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        sub_lbl.setContentsMargins(0, 0, 0, 8)
        self._outer_layout.addWidget(sub_lbl)

        # No-results label (hidden by default)
        self._no_results_lbl = QLabel("")
        self._no_results_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._no_results_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._no_results_lbl.setFont(QFont(FONT, 13))
        self._no_results_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        self._no_results_lbl.setContentsMargins(0, 16, 0, 0)
        self._no_results_lbl.setVisible(False)
        self._outer_layout.addWidget(self._no_results_lbl)

        # Content container
        self._content_widget = QWidget()
        self._content_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._content_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._content_widget.setStyleSheet("background: transparent; border: none;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._outer_layout.addWidget(self._content_widget)

        self._outer_layout.addStretch()

        self._render_content("")

    # ── Search handlers ───────────────────────────────────────────────────────

    def _on_search_change(self, text: str) -> None:
        self._search_term = text
        self._clear_btn.setVisible(bool(text.strip()))
        self._render_content(text)

    def _clear_search(self) -> None:
        self._search_entry.clear()

    # ── Content rendering ─────────────────────────────────────────────────────

    def _render_content(self, term: str) -> None:
        # Clear existing content
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        term_lower = term.strip().lower()
        no_filter = not term_lower
        any_result = False

        for sec in _HELP_DATA:
            sec_match   = not no_filter and term_lower in sec["section"].lower()
            items_match = any(term_lower in item["text"].lower() for item in sec["items"])

            if not no_filter and not sec_match and not items_match:
                continue

            any_result = True

            # Section divider
            div = QFrame()
            div.setFrameShape(QFrame.Shape.NoFrame)
            div.setFrameShadow(QFrame.Shadow.Plain)
            div.setLineWidth(0)
            div.setFixedHeight(1)
            div.setStyleSheet("background: #2a3a52; border: none;")
            div.setContentsMargins(0, 8, 0, 0)
            div_wrapper = QWidget()
            div_wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            div_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            div_wrapper.setStyleSheet("background: transparent; border: none;")
            dw_layout = QVBoxLayout(div_wrapper)
            dw_layout.setContentsMargins(0, 12, 0, 0)
            dw_layout.addWidget(div)
            self._content_layout.addWidget(div_wrapper)

            # Section title
            if not no_filter and sec_match:
                title_row_w = QWidget()
                title_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                title_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                title_row_w.setStyleSheet("background: transparent; border: none;")
                title_row = QHBoxLayout(title_row_w)
                title_row.setContentsMargins(0, 10, 0, 4)
                title_row.setSpacing(0)
                _pack_text_segments(title_row, sec["section"], term_lower, 17, TEXT_PRI, bold=True)
                title_row.addStretch()
                self._content_layout.addWidget(title_row_w)
            else:
                sec_lbl = QLabel(sec["section"])
                sec_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                sec_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                sec_lbl.setFont(QFont(FONT, 17, QFont.Weight.Bold))
                sec_lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
                sec_lbl.setContentsMargins(0, 10, 0, 4)
                self._content_layout.addWidget(sec_lbl)

            # Items
            for item in sec["items"]:
                item_match = not no_filter and term_lower in item["text"].lower()
                if item["type"] == "heading":
                    self._w_heading(item["text"], item_match, term_lower)
                elif item["type"] == "body":
                    self._w_body(item["text"], item_match, term_lower)
                elif item["type"] == "bullet":
                    self._w_bullet(item["text"], item_match, term_lower)

        self._no_results_lbl.setVisible(not no_filter and not any_result)
        if not no_filter and not any_result:
            self._no_results_lbl.setText(f"No results for '{term}'")

    # ── Item widget renderers ─────────────────────────────────────────────────

    def _w_heading(self, text: str, highlighted: bool, term_lower: str = "") -> None:
        if highlighted:
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent; border: none;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 8, 0, 2)
            row.setSpacing(0)
            _pack_text_segments(row, text, term_lower, 14, TEXT_PRI, bold=True)
            row.addStretch()
            self._content_layout.addWidget(row_w)
        else:
            lbl = QLabel(text)
            lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            lbl.setFont(QFont(FONT, 14, QFont.Weight.Bold))
            lbl.setStyleSheet(f"color: {TEXT_PRI}; background: transparent; border: none;")
            lbl.setContentsMargins(0, 8, 0, 2)
            self._content_layout.addWidget(lbl)

    def _w_body(self, text: str, highlighted: bool, term_lower: str = "") -> None:
        if highlighted:
            row_w = QWidget()
            row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            row_w.setStyleSheet("background: transparent; border: none;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 0, 0, 4)
            row.setSpacing(0)
            _pack_text_segments(row, text, term_lower, 13, TEXT_SEC)
            row.addStretch()
            self._content_layout.addWidget(row_w)
        else:
            lbl = QLabel(text)
            lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            lbl.setFont(QFont(FONT, 13))
            lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
            lbl.setWordWrap(True)
            lbl.setContentsMargins(0, 0, 0, 4)
            self._content_layout.addWidget(lbl)

    def _w_bullet(self, text: str, highlighted: bool, term_lower: str = "") -> None:
        row_w = QWidget()
        row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_w.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(6)

        bullet_lbl = QLabel("•")
        bullet_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        bullet_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        bullet_lbl.setFont(QFont(FONT, 13))
        bullet_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
        bullet_lbl.setFixedWidth(16)
        bullet_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        row.addWidget(bullet_lbl)

        if highlighted:
            _pack_text_segments(row, text, term_lower, 13, TEXT_SEC)
        else:
            txt_lbl = QLabel(text)
            txt_lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            txt_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            txt_lbl.setFont(QFont(FONT, 13))
            txt_lbl.setStyleSheet(f"color: {TEXT_SEC}; background: transparent; border: none;")
            txt_lbl.setWordWrap(True)
            row.addWidget(txt_lbl)

        row.addStretch()
        self._content_layout.addWidget(row_w)
