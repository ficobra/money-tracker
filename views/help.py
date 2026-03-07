import customtkinter as ctk

# Premium dark theme palette
_TEXT_PRI  = "#e6edf3"
_TEXT_SEC  = "#8b949e"
_BORDER    = "#2a3a52"
_ACCENT    = "#00b4d8"
_BG_CARD   = "#161f2e"
_BG_ELEM   = "#21262d"
_HIGHLIGHT   = "#0d2035"   # subtle teal background for matched items
_MATCH_COLOR = "#f0c040"   # yellow text for matched content
_F         = "Helvetica Neue"


# ── Help content data ─────────────────────────────────────────────────────────
# Each section has a title and a list of items.
# Item types: "body", "heading", "bullet"

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


class HelpView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        self._content_frame: ctk.CTkFrame | None = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Header row: title (left) + search (right) ─────────────────────────
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=24, pady=(24, 2))
        top_row.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top_row, text="Help & User Guide",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).grid(row=0, column=0, sticky="w")

        # Search field container (right-aligned, max 300px)
        search_container = ctk.CTkFrame(
            top_row, fg_color=_BG_ELEM, corner_radius=8,
            border_width=1, border_color=_BORDER,
        )
        search_container.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            search_container, text="🔍",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
        ).pack(side="left", padx=(8, 2), pady=4)

        self._search_entry = ctk.CTkEntry(
            search_container, textvariable=self._search_var,
            placeholder_text="Search...",
            placeholder_text_color="#6b7280",
            fg_color="transparent", border_width=0,
            text_color=_TEXT_PRI,
            font=ctk.CTkFont(family=_F, size=13),
            width=220,
        )
        self._search_entry.pack(side="left", pady=4)

        self._clear_btn = ctk.CTkButton(
            search_container, text="×", width=28, height=28,
            fg_color="transparent", hover_color="#3d4d63",
            text_color=_TEXT_SEC, corner_radius=6,
            font=ctk.CTkFont(family=_F, size=14),
            command=self._clear_search,
        )
        self._clear_btn.pack(side="left", padx=(0, 4))
        self._clear_btn.pack_forget()  # hidden when search is empty

        ctk.CTkLabel(
            self, text="Everything you need to know about using Money Tracker.",
            text_color=_TEXT_SEC,
        ).pack(anchor="w", padx=24, pady=(4, 12))

        self._no_results_lbl = ctk.CTkLabel(
            self, text="", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=13),
        )

        # ── Content frame ─────────────────────────────────────────────────────
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="x")

        self._render_content("")

        ctk.CTkFrame(self, height=32, fg_color="transparent").pack()

    # ── Search handlers ───────────────────────────────────────────────────────

    def _on_search_change(self, *_):
        term = self._search_var.get()
        if term.strip():
            self._clear_btn.pack(side="left", padx=(0, 4))
        else:
            self._clear_btn.pack_forget()
        self._render_content(term)

    def _clear_search(self):
        self._search_var.set("")

    # ── Content rendering ─────────────────────────────────────────────────────

    def _render_content(self, term: str):
        if self._content_frame is None:
            return
        for w in self._content_frame.winfo_children():
            w.destroy()
        if self._no_results_lbl.winfo_manager():
            self._no_results_lbl.pack_forget()

        term_lower = term.strip().lower()
        no_filter  = not term_lower
        any_result = False

        for sec in _HELP_DATA:
            sec_match   = not no_filter and term_lower in sec["section"].lower()
            items_match = any(term_lower in item["text"].lower() for item in sec["items"])

            if not no_filter and not sec_match and not items_match:
                continue

            any_result = True

            # Section divider + title
            ctk.CTkFrame(
                self._content_frame, height=1, fg_color=_BORDER,
            ).pack(fill="x", padx=24, pady=(16, 0))

            if not no_filter and sec_match:
                title_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
                title_row.pack(anchor="w", padx=24, pady=(14, 6))
                self._pack_text_segments(
                    title_row, sec["section"], term_lower, 17, _TEXT_PRI, bold=True)
            else:
                ctk.CTkLabel(
                    self._content_frame, text=sec["section"],
                    font=ctk.CTkFont(family=_F, size=17, weight="bold"),
                    text_color=_TEXT_PRI,
                ).pack(anchor="w", padx=24, pady=(14, 6))

            for item in sec["items"]:
                item_match = not no_filter and term_lower in item["text"].lower()
                if item["type"] == "heading":
                    self._w_heading(item["text"], item_match, term_lower)
                elif item["type"] == "body":
                    self._w_body(item["text"], item_match, term_lower)
                elif item["type"] == "bullet":
                    self._w_bullet(item["text"], item_match, term_lower)

        if not no_filter and not any_result:
            self._no_results_lbl.configure(text=f"No results for '{term}'")
            self._no_results_lbl.pack(anchor="w", padx=24, pady=(20, 0))

    # ── Item widget renderers ─────────────────────────────────────────────────

    def _pack_text_segments(
        self, parent, text: str, term_lower: str,
        font_size: int, normal_color: str, bold: bool = False,
    ):
        """Pack inline CTkLabel segments with the search term highlighted in yellow."""
        text_lower  = text.lower()
        normal_font = ctk.CTkFont(family=_F, size=font_size, weight="bold" if bold else "normal")
        match_font  = ctk.CTkFont(family=_F, size=font_size, weight="bold")
        last = 0
        while True:
            idx = text_lower.find(term_lower, last)
            if idx == -1:
                remaining = text[last:]
                if remaining:
                    ctk.CTkLabel(parent, text=remaining, text_color=normal_color,
                                 font=normal_font, anchor="w").pack(side="left", anchor="w")
                break
            if idx > last:
                ctk.CTkLabel(parent, text=text[last:idx], text_color=normal_color,
                             font=normal_font, anchor="w").pack(side="left", anchor="w")
            ctk.CTkLabel(
                parent, text=text[idx:idx + len(term_lower)], text_color=_MATCH_COLOR,
                font=match_font, anchor="w",
            ).pack(side="left", anchor="w")
            last = idx + len(term_lower)

    def _w_heading(self, text: str, highlighted: bool, term_lower: str = ""):
        if highlighted:
            row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", padx=24, pady=(10, 2))
            self._pack_text_segments(row, text, term_lower, 14, _TEXT_PRI, bold=True)
        else:
            ctk.CTkLabel(
                self._content_frame, text=text,
                font=ctk.CTkFont(family=_F, size=14, weight="bold"),
                text_color=_TEXT_PRI,
            ).pack(anchor="w", padx=24, pady=(10, 2))

    def _w_body(self, text: str, highlighted: bool, term_lower: str = ""):
        if highlighted:
            row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", padx=24, pady=(0, 4))
            self._pack_text_segments(row, text, term_lower, 13, _TEXT_SEC)
        else:
            ctk.CTkLabel(
                self._content_frame, text=text, text_color=_TEXT_SEC,
                wraplength=800, justify="left",
                font=ctk.CTkFont(family=_F, size=13),
            ).pack(anchor="w", padx=24, pady=(0, 4))

    def _w_bullet(self, text: str, highlighted: bool, term_lower: str = ""):
        row = ctk.CTkFrame(self._content_frame, fg_color="transparent", corner_radius=4)
        row.pack(anchor="w", padx=24, pady=(1, 1), fill="x")
        ctk.CTkLabel(
            row, text="•", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=13), width=16,
        ).pack(side="left", anchor="n", padx=(0, 6))
        if highlighted:
            self._pack_text_segments(row, text, term_lower, 13, _TEXT_SEC)
        else:
            ctk.CTkLabel(
                row, text=text, text_color=_TEXT_SEC,
                wraplength=760, justify="left",
                font=ctk.CTkFont(family=_F, size=13),
            ).pack(side="left", anchor="w")
