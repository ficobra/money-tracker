import customtkinter as ctk


class HelpView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._title("Help & User Guide")
        self._subtitle("Everything you need to know about using Money Tracker.")

        self._divider()
        self._section("Getting Started")
        self._body(
            "Money Tracker uses a snapshot model: once per month (ideally on the last day), "
            "you enter the current balance of each of your accounts. The app calculates "
            "the difference between consecutive months to determine your net worth change, "
            "income, savings rate, and more."
        )
        self._body(
            "After saving your first snapshot, you won't see comparison stats yet — "
            "you need at least two monthly snapshots before the app can calculate changes. "
            "Once you have two or more snapshots, the Dashboard, Charts, and all stats "
            "become fully populated."
        )

        self._divider()
        self._section("Monthly Snapshot")

        self._heading("Account rows")
        self._body(
            "Each row represents one account (bank account, cash, brokerage, etc.). "
            "Enter the current balance in EUR. You can add or remove accounts at any time — "
            "the account list is fully dynamic."
        )
        self._body(
            "To rename or remove accounts, click Edit Accounts. All name fields become "
            "editable entries and × remove buttons appear. Click Done when finished. "
            "Clicking + Add Account automatically enables edit mode."
        )
        self._body(
            "When you navigate to a current or future month with no saved snapshot yet, "
            "all accounts you've ever saved are pre-filled with empty balances so you don't "
            "have to re-type account names every month."
        )

        self._heading("Investment accounts")
        self._body(
            "In Edit Accounts mode, tick the INV checkbox next to an account to mark it as "
            "an investment account (e.g. a brokerage or ETF portfolio). Investment accounts "
            "are excluded from the Net Worth calculation and shown separately as "
            "'Investment Portfolio' on the Dashboard."
        )
        self._body(
            "Net Worth in the snapshot is labelled 'Net Worth (excl. investments)'. "
            "A separate 'Investment Portfolio' line shows the total value of all investment "
            "accounts. Both appear in the Snapshot summary and Dashboard cards. Investment "
            "accounts are marked with * in the Account Breakdown table."
        )

        self._heading("Income This Month")
        self._body(
            "When you open Monthly Snapshot for a period where you have active income sources, "
            "an 'Income This Month' section appears above the Save Snapshot button. Enter the "
            "actual amount received for each income source. This is saved per month and used "
            "for tracking actual vs. expected income over time."
        )

        self._heading("Saving a snapshot")
        self._body(
            "Click Save Snapshot when you've entered all balances and income amounts. "
            "If today is not the last day of the month, a mid-month estimation card also "
            "appears (see below). A confirmation message shows your net worth."
        )
        self._body(
            "Saving a snapshot for a future month shows a warning. This is allowed but not "
            "recommended — wait until the end of the month for accurate data."
        )

        self._heading("Deleting a snapshot")
        self._body(
            "When a snapshot has been saved for a period, a red Delete Snapshot button "
            "appears below Save Snapshot. Clicking it asks for confirmation before "
            "permanently deleting the snapshot and all its balance data."
        )

        self._heading("Mid-month deduction")
        self._body(
            "After saving a snapshot mid-month, a dialog asks if you'd like to deduct "
            "estimated remaining costs from one of your non-investment accounts. This adjusts "
            "the saved balance to reflect what you expect to spend by month end. You can also "
            "add a one-time extra cost (e.g. upcoming large expense). Skip this dialog if you "
            "prefer to enter exact balances at month end instead."
        )

        self._divider()
        self._section("Mid-Month Estimation")
        self._body(
            "When you select the current month and no snapshot has been saved yet, a "
            "Mid-Month Estimation card appears automatically. It shows:"
        )
        self._bullet("Daily Spending Allowance: remaining days × your EUR/day rate")
        self._bullet(
            "Fixed expenses this month: all fixed monthly expenses for the entire month "
            "(regardless of whether they have already passed). Each expense shows its effective "
            "banking day — Saturday and Sunday charges shift to the following Monday."
        )
        self._bullet(
            "Estimated end-of-month net worth: your current entered total (excl. investments) "
            "minus all fixed expenses minus the buffer cost"
        )
        self._body(
            "The Daily Spending Allowance is editable directly in the estimation card via "
            "the Edit button, or from the Settings tab. Changes are saved immediately and "
            "reflected across the app."
        )
        self._body(
            "Tick the checkbox 'Show adjusted net worth alongside actual total' to see "
            "the estimated adjusted total displayed next to the raw total row as you type."
        )

        self._divider()
        self._section("Budget Tab")

        self._heading("Fixed Monthly Expenses")
        self._body(
            "Fixed expenses are recurring charges that happen every month on a predictable "
            "day (rent, subscriptions, insurance, etc.). Add them once and they stay "
            "permanently in the list. They are used in mid-month estimation calculations."
        )
        self._body(
            "Click Edit in the section header to enter edit mode. In edit mode, all rows "
            "become editable entries simultaneously. Click × to delete a row (with "
            "confirmation). Click Done to save all changes and exit edit mode."
        )
        self._body(
            "Expenses with day 31 are treated as end-of-month charges and are always "
            "counted as remaining in months that have fewer than 31 days."
        )

        self._heading("Monthly Income")
        self._body(
            "Track your regular income sources (salary, freelance income, seasonal work, etc.). "
            "Each income source has a name, expected amount, and a set of active months."
        )
        self._body(
            "Active months determine which months show this income source in the "
            "'Income This Month' section of Monthly Snapshot. If all 12 months are checked, "
            "the income appears every month. Uncheck months where the income doesn't apply "
            "(e.g. summer-only work, quarterly payments)."
        )
        self._body(
            "Click Edit in the Monthly Income section header to enter edit mode. All rows "
            "become editable simultaneously — change the name, amount, and active months. "
            "Click × to delete a source (with confirmation). Click Done to save all changes."
        )
        self._body(
            "The total of all income sources appears as 'Expected Monthly Income' on the "
            "Dashboard. The Dashboard also shows your 'Spending Budget' = Expected Income "
            "minus Fixed Expenses."
        )

        self._divider()
        self._section("Dashboard")

        self._heading("Metric cards")
        self._body("The cards at the top show your most recent month's key numbers:")
        self._bullet("Net Worth — total balance of non-investment accounts in the latest snapshot")
        self._bullet(
            "Monthly Change — difference between latest and previous snapshot net worths, "
            "with percentage"
        )
        self._bullet("Fixed Expenses — sum of all your fixed monthly expenses (from the Budget tab)")
        self._bullet(
            "Disposable Income — Monthly Change minus Fixed Expenses. Positive means you "
            "earned more than your fixed costs; negative means a shortfall."
        )
        self._bullet(
            "Investment Portfolio — current total value of all investment accounts "
            "(shown only when investment accounts exist)"
        )
        self._bullet(
            "Expected Monthly Income — sum of all recurring income sources, with Spending "
            "Budget shown below (shown only when income sources are added)"
        )

        self._heading("Reminder banner")
        self._body(
            "If today is after the 20th and no snapshot has been saved for the previous "
            "month, a yellow reminder banner appears at the top of the Dashboard. "
            "Click Go to Snapshot to jump directly to the snapshot entry for that month. "
            "The reminder only appears for months after your first ever recorded snapshot — "
            "it will never prompt you for periods before you started tracking."
        )

        self._heading("Snapshot History")
        self._body(
            "A compact grid at the bottom of the Dashboard showing all months across all "
            "years. A ✓ button indicates a saved snapshot — click it to navigate directly "
            "to that month in the Monthly Snapshot view. A · indicates no snapshot for that month."
        )

        self._heading("Annual Overview")
        self._body(
            "Below the metric cards, the Annual Overview shows statistics for the current "
            "calendar year: best month, worst month, average monthly change, and total saved "
            "(sum of all positive months). Requires at least two snapshots in the year."
        )

        self._heading("Account Breakdown")
        self._body(
            "A table showing each account's balance in the latest snapshot, compared to "
            "the previous snapshot, with the change highlighted in green or red. "
            "Investment accounts are marked with *."
        )

        self._heading("Export to CSV")
        self._body(
            "The Export to CSV button at the bottom of the Dashboard saves all your snapshot "
            "data to a CSV file. Each row contains year, month, account name, balance, and "
            "whether the account is an investment account."
        )

        self._divider()
        self._section("Charts Tab")
        self._body(
            "All charts are generated from your saved snapshots. At least two snapshots "
            "are required for most charts to appear."
        )
        self._bullet("Net Worth Over Time — line chart of your net worth (excl. investments) across all snapshots")
        self._bullet(
            "Monthly Net Worth Change — bar chart of month-on-month changes; "
            "green = growth, red = decline"
        )
        self._bullet(
            "Account Tracker — select one or more accounts and/or income sources with the "
            "checkboxes to plot their values over time. Account balances are shown as solid "
            "lines; actual income amounts (as entered in each month's snapshot) are shown as "
            "dashed lines. Your selection is remembered while the app is running."
        )
        self._bullet(
            "Investment Performance — shown when investment accounts exist. Plots current "
            "value vs. total amount deposited over time."
        )

        self._divider()
        self._section("Notes Tab")

        self._heading("My Notes")
        self._body(
            "A free-text area where you can write anything — reminders, financial goals, "
            "context for unusual months, etc. Click Save Notes to persist your text."
        )

        self._heading("Debt / Credit Notes")
        self._body(
            "Track money owed between you and others. Each note has a description, an "
            "amount, and a direction: They owe me or I owe them. The summary cards show "
            "your net position. These notes are for reference only — they are not included "
            "in net worth or any other calculations."
        )

        self._divider()
        self._section("Settings Tab")

        self._heading("Daily Spending Allowance")
        self._body(
            "Your estimated budget per day for variable spending (food, transport, leisure, "
            "etc.). Used only in mid-month estimations. You can also edit it directly from "
            "the estimation card in Monthly Snapshot or Dashboard."
        )

        self._heading("Appearance")
        self._body(
            "Choose between System (follows your OS setting), Light, or Dark mode. "
            "The setting is saved and applied automatically on the next launch."
        )

        self._heading("Backup & Restore")
        self._body(
            "Backup saves a copy of your tracker database (tracker.db) to a location you "
            "choose. Restore replaces the current database with a backup file and closes "
            "the app — reopen it to see the restored data."
        )

        self._heading("Reset All Data")
        self._body(
            "Permanently deletes all snapshots, accounts, expenses, income, and notes, and "
            "resets settings to defaults. The app closes after reset. Type DELETE in the "
            "confirmation dialog to proceed. This cannot be undone."
        )

        self._divider()
        self._section("Tips & Best Practices")
        self._bullet(
            "Enter your snapshot on the last day of each month for the most accurate data."
        )
        self._bullet(
            "Mark your brokerage or ETF account as an investment account so the Dashboard "
            "shows it separately from your liquid net worth."
        )
        self._bullet(
            "Add all your regular income sources to the Monthly Income section (Budget tab) "
            "so the Dashboard can calculate your Spending Budget. Uncheck months where a "
            "source is not active to keep the 'Income This Month' section in snapshots clean."
        )
        self._bullet(
            "Use the Extra one-time cost field in the mid-month deduction dialog for known "
            "upcoming expenses so the adjusted balance reflects your real expected position."
        )
        self._bullet(
            "If you missed a month, you can still enter a snapshot for any past month — "
            "just select the correct period in the period selector, or click the · cell "
            "in the Snapshot History grid on the Dashboard."
        )
        self._bullet(
            "Fixed expenses with day 31 (e.g. end-of-month bank fees) are always shown in the "
            "mid-month estimation for months shorter than 31 days. Expenses falling on a "
            "Saturday or Sunday are shown with their effective Monday banking date."
        )
        self._bullet(
            "Export to CSV regularly as an extra backup of your financial history."
        )

        # Bottom padding
        ctk.CTkFrame(self, height=32, fg_color="transparent").pack()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _title(self, text: str):
        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))

    def _subtitle(self, text: str):
        ctk.CTkLabel(self, text=text, text_color="gray").pack(anchor="w", padx=24, pady=(0, 4))

    def _divider(self):
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(16, 0)
        )

    def _section(self, text: str):
        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(14, 6))

    def _heading(self, text: str):
        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(10, 2))

    def _body(self, text: str):
        ctk.CTkLabel(
            self, text=text, text_color=("gray20", "gray85"),
            wraplength=800, justify="left",
            font=ctk.CTkFont(size=13),
        ).pack(anchor="w", padx=24, pady=(0, 4))

    def _bullet(self, text: str):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=24, pady=(1, 1), fill="x")
        ctk.CTkLabel(
            row, text="•", text_color="gray",
            font=ctk.CTkFont(size=13), width=16,
        ).pack(side="left", anchor="n", padx=(0, 6))
        ctk.CTkLabel(
            row, text=text, text_color=("gray20", "gray85"),
            wraplength=780, justify="left",
            font=ctk.CTkFont(size=13),
        ).pack(side="left", anchor="w")
