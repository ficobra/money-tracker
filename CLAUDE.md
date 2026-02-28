# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Python desktop GUI application for personal monthly finance tracking, built with CustomTkinter and Matplotlib. The app is for personal use only.

### Core Concept
The app uses a "snapshot" model — the user enters account balances once per month (at the end of the month), and the app calculates the difference between months to determine net worth change. No individual transaction tracking.

### User & Context
- User lives in Austria, earns income in EUR
- Two income sources: primary job (fixed salary) and secondary job (basketball statistics via FibaLiveStats/Synergy, paid in cash or bank transfer)
- Accounts to track: main bank account, Revolut, cash, Flatex (ETF/stock portfolio)
- Monthly standing order into ETFs via Flatex

## Features

### Monthly Snapshot
- User enters balance of all accounts once per month (end of month preferred)
- First entry produces no results (need at least 2 months to calculate)
- All account fields are dynamic — user can add/remove accounts freely
- **Account name editing**: A single "Edit Accounts" toggle button sits alongside "+ Add Account". When ON (shows "Done"): all name fields become editable entries. When OFF: all fields return to read-only labels. Clicking "+ Add Account" auto-enables edit mode for all rows before adding the new row. The toggle resets to OFF on every period change (`_load_existing`).
- **Account persistence**: When a snapshot is saved with any new account, that account is stored in the `accounts` table. When the user navigates to any unsaved current or future month, all known accounts are pre-populated (empty balance). Past unsaved months fall back to `_DEFAULT_ACCOUNTS`.
- **Future month warning**: Saving a snapshot for a month that hasn't started yet shows a confirmation dialog: "You are entering data for a future month (Month Year). This month has not started yet. Do you want to continue?" with Continue/Cancel buttons.
- **Remove account confirmation**: Clicking × on an account row shows a confirmation dialog before removing it (no "This cannot be undone." suffix).
- **Post-save deduction dialog**: After saving a snapshot for the current mid-month, a modal dialog appears asking whether to deduct estimated remaining costs from a non-investment account. Includes an "Extra one-time cost (EUR)" input that adds to the grand total dynamically. If the selected account has insufficient funds, a second warning dialog is shown before proceeding. On confirm, the selected account's balance is reduced, the snapshot is re-saved, and status bar updates with the adjusted net worth.
- **Delete Snapshot button**: A red "Delete Snapshot" button (border style) appears below "Save Snapshot" only when a snapshot exists for the selected period. Clicking shows a confirmation dialog. On confirm, calls `delete_snapshot(year, month)` and reloads the view.
- **× remove buttons**: Only visible when "Edit Accounts" mode is active (i.e., the "Done" button is showing). Hidden otherwise. Rendered inside `edit_controls` frame via `_refresh_edit_controls(row)`.
- **Investment accounts**: In "Edit Accounts" mode, each row shows an "INV" checkbox (hidden in normal mode; timing fix: `_editing_accounts=False` is set BEFORE creating rows in `_load_existing()`). Marking an account as INV excludes it from Net Worth; it's shown separately as "Investment Portfolio". Investment accounts have ONE balance field "Balance (EUR)" — no monthly deposit tracking. `_refresh_edit_controls(row)` uses `pack()`/`pack_forget()` with a geometry-manager check to avoid empty frames causing layout spacing issues.
- **Net Worth vs Investment Portfolio**: `total` in snapshot dicts = sum of non-investment accounts (Net Worth). `investment_total` = sum of investment accounts. Both displayed in the Snapshot and Dashboard.
- **refresh() method**: `SnapshotEntryView` has a `refresh()` method that checks `SnapshotEntryView._pending_period` (class variable). If set by another view (e.g., Dashboard reminder), it pre-selects that period and clears the variable.

### Expenses (tab)
The "Expenses" tab is split into three sections:

**Fixed Monthly Expenses**
- User can define recurring monthly expenses with name, amount, and day of month
- These are stored permanently and don't need to be re-entered each month
- **Row selection**: Per-row Edit/Delete buttons have been replaced with a shared toolbar (Edit + Delete buttons) above the list. Clicking a row highlights it (`_selected_id`). The toolbar Edit/Delete buttons act on the selected row. If no row is selected, a hint message appears. The inline edit form (entries + Save/Cancel) still appears in-row when editing.
- Deleting an expense shows a confirmation dialog: "Delete [name]? This cannot be undone." with Delete/Cancel buttons

**Monthly Income**
- User can define regular income sources with name, amount, and day of month
- Day 0 means "Variable" (irregular payment timing)
- Stored in `recurring_income` table
- Same toolbar pattern as Fixed Monthly Expenses (`_income_selected_id`, `_income_editing_id`)
- Total shown as "Expected monthly income:" below the list
- Dashboard: "EXPECTED MONTHLY INCOME" card + "Spending Budget" (income − fixed expenses)

**Variable Expenses**
- Contains the **Daily Spending Allowance** setting, stored in `settings` table under key `daily_buffer`
- Shown as an editable EUR/day field with a large display value and Edit/Save/Cancel pattern
- Used for mid-month estimation calculations

### Mid-Month Estimation
- Shown in both Monthly Snapshot view and Dashboard when: selected period = current month, today is not the last day of the month, and no snapshot has been saved yet for this month
- Calculates estimated spend until month end:
  - **Buffer cost**: `remaining_days × daily_buffer` (remaining_days = last_day − today.day)
  - **Remaining fixed expenses**: expenses with `day_of_month > today.day`
  - **Day 31 special case**: expenses with `day_of_month = 31` are always included as remaining when the current month has fewer than 31 days (they represent end-of-month charges)
- Shows an itemized list of remaining fixed expenses with name, day, and amount
- Estimated end-of-month net worth = current entered net worth total (non-investment) − buffer cost − remaining fixed expenses total
- **Daily buffer** (default: 20 EUR/day) is stored in the `settings` DB table under key `daily_buffer` and is editable directly in the UI via an Edit button in both the Monthly Snapshot and Dashboard estimation cards
- In Monthly Snapshot view: the estimated EOM net worth updates live as the user types balances
- In Monthly Snapshot view: a checkbox "Show adjusted net worth alongside actual total" — when ticked, shows `current_total − est_total_cost` next to the actual total row; driven by `_include_estimation_var` (CTkBooleanVar)

### Visualizations (Charts tab)
Three charts, always in this order:

**Net Worth Over Time** (line chart) — always shown when ≥2 snapshots; uses `total` (non-investment)

**Monthly Net Worth Change** (bar chart) — always shown when ≥2 snapshots; green = positive, red = negative. Labels use `_annotate_bars()` with `ax.margins(y=0.30)` so value labels never overlap x-axis tick labels.

**Account Tracker** (line chart, dynamic) — shown when ≥1 snapshot. User selects one or more accounts via checkboxes (populated from `get_all_accounts()`); chart shows their balance over time. Selection is preserved across `refresh()` calls via `_tracker_vars: dict[str, BooleanVar]`. Chart is redrawn live on each checkbox toggle via `_on_tracker_change()` → `_draw_tracker_chart()`. Previous figure is cleaned up before drawing the new one.

### Dashboard
- **Metric cards** (always shown): NET WORTH (non-investment), MONTHLY CHANGE, FIXED EXPENSES, DISPOSABLE INCOME
- **Extra cards** (conditional): INVESTMENT PORTFOLIO (when investment accounts exist), EXPECTED MONTHLY INCOME (when income sources exist)
- **Reminder banner**: if `today.day > 20` and no snapshot for previous month → yellow banner at top with "Go to Snapshot" button. Button sets `SnapshotEntryView._pending_period = (prev_year, prev_month)` before calling navigate callback.
- **navigate callback**: `DashboardView.__init__` accepts `navigate=None`. `main.py` passes `navigate=self.show_view` via lambda in `_view_classes`.
- **Annual Overview**: best/worst/avg monthly change and total saved for current year
- **Investment Portfolio section**: shown when investment accounts exist; total current value + per-account breakdown
- **Account Breakdown**: table of latest vs prev snapshot balances; investment accounts marked with ★
- **Export to CSV**: button at bottom; `filedialog.asksaveasfilename`; exports Year/Month/Account/Balance/Is_Investment rows for all snapshots

### Annual Overview (on Dashboard)
- Best and worst month
- Average monthly change
- Total saved (sum of positive months)
- Uses `total` (non-investment) for all calculations

### Notes (tab)
Two sections:

**My Notes**
- Free-text multiline area (CTkTextbox) for anything the user wants to write
- Saved persistently to the `settings` table under key `my_notes`
- "Save Notes" button with a brief "Saved." confirmation

**Debt / Credit Notes**
- Simple debt tracking (not included in any calculations)
- Each note has: description, amount, direction ("they_owe" / "i_owe"), date added
- Summary cards show total owed to user vs. total user owes
- Example: "Marko owes me 50 EUR" or "I owe Ana 20 EUR"

### Currency Formatting
- All monetary display values use European format: `€1.234,56` (period = thousands separator, comma = decimal)
- Helper functions in `utils.py`: `fmt_eur(value)` and `fmt_eur_signed(value)` (with explicit +/- sign)
- Input fields still accept plain numbers (e.g. `1234.56`)
- Chart y-axis labels use `_eu_axis_fmt(v)` (whole numbers only, e.g. `€1.234`)

### Data Management (Help tab)
- **Backup**: `filedialog.asksaveasfilename`, copies `DB_PATH` via `shutil.copy2`
- **Restore**: `filedialog.askopenfilename`, confirmation dialog, copies file over `DB_PATH`, then `self.winfo_toplevel().destroy()` to close the app

## Environment

- Python 3.13 virtual environment at `./venv/`
- Activate with: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt` (once created)

## Key Dependencies (already installed in venv)

- `customtkinter` — modern Tkinter wrapper for the GUI
- `matplotlib` — charts and financial visualizations
- `numpy` — numerical operations
- `pillow` — image handling
- `darkdetect` — automatic dark/light mode detection

## Running the App
```bash
source venv/bin/activate
python main.py
```

## Architecture

- Entry point: `main.py`
- GUI components: `customtkinter` (CTk widgets, not raw Tkinter)
- Charts: `matplotlib` embedded in the CTk window
- Database: SQLite (single local file, no server needed)
- Dark mode support via `darkdetect`

### File Structure
```
money-tracker/
├── main.py                  — App entry, sidebar nav, show_view() passes navigate to Dashboard
├── utils.py                 — fmt_eur(), fmt_eur_signed() for European currency display
├── database/
│   ├── db.py
│   └── tracker.db
├── views/
│   ├── dashboard.py
│   ├── snapshot_entry.py
│   ├── expenses.py
│   ├── charts.py
│   ├── notes.py
│   └── help.py
└── requirements.txt
```

## Important Rules for Claude
- Always use CTk widgets (customtkinter), never raw Tkinter
- All monetary values stored and displayed in EUR
- **Currency display**: always use `fmt_eur()` / `fmt_eur_signed()` from `utils.py` — never use `f"€{value:,.2f}"` directly in views
- Dynamic fields — avoid hardcoded account names or expense categories
- First month snapshot shows no calculations, just confirms data saved
- Mid-month estimation uses configurable daily buffer (default 20 EUR/day, stored in `settings` table) and itemized remaining fixed expenses; day-31 expenses always count as remaining in months shorter than 31 days
- Confirmation dialogs use a modal pattern: `result = [False]`, create a top-level dialog with `grab_set()` + `wait_window()`, buttons set `result[0]` then `dialog.destroy()`, return `result[0]`
- Modal dialogs (deduction dialog) use `result: list = [False, "", 0.0]` with same pattern
- `get_all_accounts()` in `db.py` returns all accounts ever saved, ordered by insertion (`ORDER BY id`)
- `get_all_accounts_with_flags()` returns `list[dict]` with `name` and `is_investment` bool
- `set_account_investment(name, is_investment)` updates the `accounts.is_investment` flag
- `save_snapshot(year, month, balances)` — no longer takes `invested_amounts`; investment tracking is done via `is_investment` flag on accounts table only
- `delete_snapshot(year, month)` — deletes snapshot and cascades to balances
- `_build_snapshot_dict` in db.py: `total` = non-investment sum, `investment_total` = investment sum, `investment_balances` = {name: balance} for investment accounts
- DB migrations in `init_db()` add `is_investment` to `accounts` and `invested_amount` to `snapshot_balances` for existing databases
- Recurring income: `get_all_income()`, `add_income(name, amount, day)`, `update_income(id, name, amount, day)`, `delete_income(id)` — stored in `recurring_income` table, day=0 means Variable
- **Always update `views/help.py`** when adding or modifying features — the Help tab is the user-facing documentation for the entire app
