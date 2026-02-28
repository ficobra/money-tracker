import shutil
from datetime import date
from tkinter import filedialog

import customtkinter as ctk

from database.db import DB_PATH


class HelpView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._backup_status:  ctk.CTkLabel | None = None
        self._restore_status: ctk.CTkLabel | None = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._title("Help & User Guide")
        self._subtitle("Everything you need to know about using Money Tracker.")

        self._divider()
        self._section("Getting Started")
        self._body(
            "Money Tracker uses a snapshot model: once per month (ideally on the last day), "
            "you enter the current balance of each of your accounts. The app then calculates "
            "the difference between consecutive months to determine your net worth change, "
            "income, savings rate, and more."
        )
        self._body(
            "After saving your first snapshot, you won't see any comparison stats yet — "
            "you need at least two monthly snapshots before the app can calculate changes. "
            "Once you have two or more snapshots, the Dashboard, Charts, and all stats will "
            "become fully populated."
        )

        self._divider()
        self._section("Monthly Snapshot")

        self._heading("Account rows")
        self._body(
            "Each row represents one account (bank account, cash, broker, etc.). "
            "Enter the current balance in EUR. You can add or remove accounts at any time — "
            "the account list is fully dynamic."
        )
        self._body(
            "To rename or remove accounts, click Edit Accounts. All name fields become "
            "editable entries and × remove buttons appear. Click Done when finished. "
            "Clicking + Add Account automatically enables edit mode."
        )
        self._body(
            "When you navigate to a current or future month that has no saved snapshot yet, "
            "all accounts you've ever saved are pre-filled with empty balances so you don't "
            "have to re-type account names every month."
        )

        self._heading("Investment accounts")
        self._body(
            "In Edit Accounts mode, tick the INV checkbox next to an account to mark it as "
            "an investment account. Investment accounts are excluded from the Net Worth "
            "calculation and shown separately as 'Investment Portfolio' on the Dashboard. "
            "They still appear in the Account Breakdown and Account Tracker chart."
        )
        self._body(
            "Net Worth shown in the snapshot is labelled 'Net Worth (excl. investments)'. "
            "A separate 'Investment Portfolio' line shows the total value of all investment "
            "accounts. Both appear in the Snapshot summary and Dashboard cards."
        )

        self._heading("Saving a snapshot")
        self._body(
            "Click Save Snapshot when you've entered all balances. If today is not the last "
            "day of the month, a mid-month estimation card also appears (see below). "
            "A confirmation message shows your net worth."
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
            "add a one-time extra cost (e.g. upcoming dentist bill, car insurance). Skip this "
            "dialog if you prefer to enter exact balances at month end instead."
        )

        self._divider()
        self._section("Mid-Month Estimation")
        self._body(
            "When you select the current month and no snapshot has been saved yet, a "
            "Mid-Month Estimation card appears automatically. It shows:"
        )
        self._bullet("Buffer cost: remaining days × your Daily Spending Allowance")
        self._bullet("Remaining fixed expenses: all fixed expenses due after today")
        self._bullet(
            "Estimated end-of-month net worth: your current entered total (excl. investments) "
            "minus all estimated remaining costs"
        )
        self._body(
            "The Daily Spending Allowance (default: €20/day) is editable directly in the "
            "card via the Edit button. Changes are saved immediately and reflected across "
            "the app. You can also edit it from the Expenses tab."
        )
        self._body(
            "Tick the checkbox Show adjusted net worth alongside actual total to see "
            "the estimated adjusted total displayed next to the raw total row as you type."
        )

        self._divider()
        self._section("Expenses Tab")

        self._heading("Fixed Monthly Expenses")
        self._body(
            "Fixed expenses are recurring charges that happen every month on a predictable "
            "day (rent, subscriptions, insurance, etc.). Add them once and they stay "
            "permanently in the list. They are used in mid-month estimation calculations."
        )
        self._body(
            "To select an expense, click on its row — it will be highlighted. Then use "
            "the Edit or Delete buttons in the toolbar above the list. Edit opens an "
            "inline form in the same row; Save commits the change."
        )
        self._body(
            "Expenses with day 31 are treated as end-of-month charges and are always "
            "counted as remaining in months that have fewer than 31 days."
        )

        self._heading("Monthly Income")
        self._body(
            "Track your regular income sources (salary, freelance, side income, etc.). "
            "Each entry has a name, amount, and day of month when it typically arrives. "
            "Use day 0 for variable or irregular payments."
        )
        self._body(
            "The total of all income sources appears as 'Expected Monthly Income' on the "
            "Dashboard. The Dashboard also shows your 'Spending Budget' = Expected Income "
            "minus Fixed Expenses."
        )

        self._heading("Daily Spending Allowance")
        self._body(
            "The Daily Spending Allowance is your estimated budget for variable spending "
            "each day (food, transport, leisure, etc.). It is not a fixed expense — it is "
            "used only in mid-month estimations. The default is €20/day. Edit it in this "
            "tab or directly from the estimation card in Monthly Snapshot or Dashboard."
        )

        self._divider()
        self._section("Dashboard")

        self._heading("Metric cards")
        self._body(
            "The cards at the top show your most recent month's key numbers:"
        )
        self._bullet(
            "Net Worth — total balance of non-investment accounts in the latest snapshot"
        )
        self._bullet(
            "Monthly Change — difference between latest and previous snapshot net worths, "
            "with percentage"
        )
        self._bullet(
            "Fixed Expenses — sum of all your fixed monthly expenses (from the Expenses tab)"
        )
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
            "Click Go to Snapshot to jump directly to the snapshot entry for that month."
        )

        self._heading("Investment Portfolio section")
        self._body(
            "If any accounts are marked as investment accounts, an Investment Portfolio "
            "section appears below the annual overview showing the total current value "
            "and a per-account breakdown."
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
            "Investment accounts are marked with ★."
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
        self._bullet(
            "Net Worth Over Time — line chart of your net worth (excl. investments) across all snapshots"
        )
        self._bullet(
            "Monthly Net Worth Change — bar chart of month-on-month changes; "
            "green = growth, red = decline"
        )
        self._bullet(
            "Account Tracker — select one or more accounts with the checkboxes to plot "
            "their balance over time. Your selection is remembered while the app is running."
        )

        self._divider()
        self._section("Notes Tab")

        self._heading("My Notes")
        self._body(
            "A free-text area where you can write anything — reminders, financial goals, "
            "context for unusual months, etc. Click Save Notes to persist your text. "
            "Content is saved immediately and survives app restarts."
        )

        self._heading("Debt / Credit Notes")
        self._body(
            "Track money owed between you and others. Each note has a description, an "
            "amount, and a direction: They owe me or I owe them. The summary cards at the "
            "top show your net position. These notes are for reference only — they are "
            "not included in net worth or any other calculations."
        )

        self._divider()
        self._section("Data Management")
        self._body(
            "Back up your tracker database or restore from a previous backup. "
            "The database file (tracker.db) contains all your snapshots, expenses, income, "
            "and notes."
        )

        # ── Backup button ────────────────────────────────────────────────────
        backup_row = ctk.CTkFrame(self, fg_color="transparent")
        backup_row.pack(anchor="w", padx=24, pady=(6, 4))
        ctk.CTkButton(
            backup_row, text="Backup Data", width=140,
            command=self._backup,
        ).pack(side="left", padx=(0, 12))
        self._backup_status = ctk.CTkLabel(backup_row, text="", font=ctk.CTkFont(size=12))
        self._backup_status.pack(side="left")

        # ── Restore button ───────────────────────────────────────────────────
        restore_row = ctk.CTkFrame(self, fg_color="transparent")
        restore_row.pack(anchor="w", padx=24, pady=(0, 8))
        ctk.CTkButton(
            restore_row, text="Restore Data", width=140,
            fg_color="transparent", border_width=1,
            text_color=("#C0392B", "#E74C3C"),
            hover_color=("gray85", "gray20"),
            command=self._restore,
        ).pack(side="left", padx=(0, 12))
        self._restore_status = ctk.CTkLabel(restore_row, text="", font=ctk.CTkFont(size=12))
        self._restore_status.pack(side="left")

        self._body(
            "Backup saves a copy of tracker.db. Restore replaces your current database "
            "with the backup and closes the app — you must reopen it to see the restored data."
        )

        self._divider()
        self._section("Tips & Best Practices")
        self._bullet(
            "Enter your snapshot on the last day of each month for the most accurate data."
        )
        self._bullet(
            "Mark your ETF or stock brokerage account (e.g. Flatex) as an investment account "
            "so the Dashboard shows it separately from your liquid net worth."
        )
        self._bullet(
            "Add your salary and any other regular income to the Monthly Income section so "
            "the Dashboard can calculate your Spending Budget."
        )
        self._bullet(
            "Use the Extra one-time cost field in the mid-month deduction dialog for known "
            "upcoming expenses (dentist, car service, travel) so the adjusted balance "
            "reflects your real expected position at month end."
        )
        self._bullet(
            "If you missed a month, you can still enter a snapshot for any past month — "
            "just select the correct period in the period selector."
        )
        self._bullet(
            "The Daily Spending Allowance only affects mid-month estimations. Adjust it "
            "whenever your spending habits change."
        )
        self._bullet(
            "Fixed expenses with day 31 (e.g. end-of-month bank fees) are always counted "
            "in the mid-month estimation for months shorter than 31 days."
        )
        self._bullet(
            "Export to CSV regularly as an extra backup of your financial history."
        )

        # Bottom padding
        ctk.CTkFrame(self, height=32, fg_color="transparent").pack()

    # ── Backup & Restore ──────────────────────────────────────────────────────

    def _backup(self):
        today        = date.today()
        default_name = f"money-tracker-backup-{today.strftime('%Y-%m-%d')}.db"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
            initialfile=default_name,
        )
        if not filepath:
            return

        shutil.copy2(DB_PATH, filepath)
        if self._backup_status:
            self._backup_status.configure(text="Backup saved!", text_color="#2CC985")
            self.after(4000, lambda: self._backup_status.configure(text="") if self._backup_status else None)

    def _restore(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
        )
        if not filepath:
            return

        result = [False]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Restore")
        dialog.geometry("480x180")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()
        ctk.CTkLabel(
            dialog,
            text=(
                "Restore data from the selected backup?\n\n"
                "This will replace ALL current data. The app will close — "
                "reopen it to see the restored data."
            ),
            wraplength=440, justify="left", font=ctk.CTkFont(size=13),
        ).pack(padx=20, pady=(20, 16))
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def on_confirm():
            result[0] = True
            dialog.destroy()

        ctk.CTkButton(btn_row, text="Restore & Close", width=140, command=on_confirm).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).pack(side="left")
        dialog.wait_window()

        if result[0]:
            shutil.copy2(filepath, DB_PATH)
            self.winfo_toplevel().destroy()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _title(self, text: str):
        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))

    def _subtitle(self, text: str):
        ctk.CTkLabel(
            self, text=text, text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 4))

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
