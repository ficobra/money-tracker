# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Python desktop GUI application for monthly personal finance tracking, built with CustomTkinter and Matplotlib. Designed for general use.

### Core Concept
The app uses a "snapshot" model — the user enters account balances once per month (at the end of the month), and the app calculates the difference between months to determine net worth change. No individual transaction tracking.

## Features

### Monthly Snapshot
- User enters balance of all accounts once per month (end of month preferred)
- First entry produces no results (need at least 2 months to calculate)
- All account fields are dynamic — user can add/remove accounts freely
- **Account name editing**: A single "Edit Accounts" toggle button sits alongside "+ Add Account". When ON (shows "Done"): all name fields become editable entries. When OFF: all fields return to read-only labels. Clicking "+ Add Account" auto-enables edit mode for all rows before adding the new row. The toggle resets to OFF on every period change (`_load_existing`).
- **Account persistence**: When a snapshot is saved with any new account, that account is stored in the `accounts` table. When the user navigates to any unsaved current or future month, all known accounts are pre-populated (empty balance). Past unsaved months fall back to `_DEFAULT_ACCOUNTS`.
- **Future month warning**: Saving a snapshot for a month that hasn't started yet shows a confirmation dialog with Continue/Cancel buttons.
- **Remove account confirmation**: Clicking × on an account row shows a confirmation dialog before removing it (no "This cannot be undone." suffix).
- **Post-save deduction dialog**: After saving a snapshot mid-month, a modal dialog appears asking whether to deduct estimated remaining costs from a non-investment account. Includes an "Extra one-time cost (EUR)" input. On confirm, the account balance is reduced, the snapshot is re-saved, and the status bar updates.
- **Layout order** in `_build()`: period selector → account rows → Add/Edit buttons → divider → totals → Income This Month → Save Snapshot → Delete Snapshot → estimation card
- **Delete Snapshot button**: A red "Delete Snapshot" button (border style) appears below "Save Snapshot" only when a snapshot exists for the selected period.
- **× remove buttons**: Only visible when "Edit Accounts" mode is active. Rendered inside `edit_controls` frame via `_refresh_edit_controls(row)`.
- **Investment accounts**: In "Edit Accounts" mode, each row shows an "INV" checkbox. Marking an account as INV excludes it from Net Worth; it's shown separately as "Investment Portfolio". `_editing_accounts=False` is set BEFORE creating rows in `_load_existing()` (timing fix).
- **Income This Month card**: Shown in Monthly Snapshot ABOVE the Save Snapshot button when income sources have that month in their `active_months`. User enters actual amounts received; saved to `snapshot_income` table. `_render_income_section()` converts each `sqlite3.Row` to `dict` before calling `.get()`.
- **Income amount validation**: 0.00 and empty fields are valid (treated as 0.00); only negative values are rejected.

### Budget (tab)
The "Budget" tab is split into two sections:

**Fixed Monthly Expenses**
- User can define recurring monthly expenses with name, amount, and day of month
- **Batch-save edit mode**: "Edit" toggle in section header. When ON (shows "Done"): ALL rows immediately show as entry widgets simultaneously. "×" button appears per row for deletion (with confirmation). Clicking "Done" validates + saves all changed rows at once. If validation fails, an error label appears next to the "Done" button and edit mode stays active.
- `_expenses_edit_mode: bool` and `_expenses_row_vars: dict[int, dict]` (id → {day, name, amount StringVars})
- `_save_all_expenses()` iterates `_expenses_row_vars`, validates, calls `update_expense()` for each

**Monthly Income**
- Stored in `recurring_income` table; `income_type` column exists in DB but UI no longer uses it (always stored as "fixed")
- `active_months`: comma-separated month numbers (e.g. "1,3,6") or NULL = active every month
- Add form: Name + EUR + 12 month checkboxes (all checked by default). If all 12 checked, `active_months = NULL`.
- **Batch-save edit mode**: same "Edit"/"Done" toggle pattern. In edit mode: name entry + amount entry + 12 month checkboxes per row + "×" button. Done saves all changes.
- `_income_edit_mode: bool` and `_income_row_vars: dict[int, dict]` (id → {name, amount StringVars + months dict[int, BoolVar]})
- `_save_all_income()` validates all rows, calls `update_income(iid, name, amount, 0, "fixed", active_months_str)`
- Display row: Name | Active Months (text) | Amount. `_format_active_months()` returns "All months" or "Jan, Mar, Jun" etc.
- Total = sum of all income amounts; shown as "Expected monthly income:"
- Daily Spending Allowance has been **moved to Settings tab** — no longer in Budget tab

**Snapshot income logging** (in Monthly Snapshot view)
- `snapshot_income` table: `(year, month, income_id, actual_amount)` — stores per-month actual income
- `_render_income_section()` finds all income sources where `active_months` is NULL or contains current month
- On Save Snapshot, `set_snapshot_income()` is called for each entry in `_income_amount_vars`

### Mid-Month Estimation
- Shown in both Monthly Snapshot view and Dashboard when: selected period = current month, today is not the last day of the month, and no snapshot has been saved yet for this month
- **Daily Spending Allowance line**: `remaining_days × daily_buffer`; **Fixed expenses this month**: ALL fixed expenses for the entire month (no "remaining" filter — all are shown and subtracted). Formula: `estimated_eom = latest_nw - fx_total - buffer_cost`
- **Dashboard estimation**: shows 3 collapsed lines (no per-expense breakdown): "Daily Spending Allowance (X days × €Y/day)", "Fixed expenses this month (N items)", then "Estimated end-of-month net worth". **Monthly Snapshot estimation**: shows full per-expense breakdown with banking day labels.
- **Banking day logic**: `effective_charge_day(year, month, day_of_month, last_day)` in `utils.py`. Saturday → following Monday (+2), Sunday → following Monday (+1), clamped to last_day. Applied to day labels in estimation cards (both dashboard.py and snapshot_entry.py). Day-31 special case: always shown in months shorter than 31 days (label: "end of month").
- **Post-save deduction dialog** (`_maybe_show_deduction_dialog`): still filters to REMAINING expenses only (effective_charge_day > today.day) since it's for balance adjustment after saving mid-month
- **Daily buffer** (default: 20 EUR/day) is editable directly in the estimation card (Edit button) and from the Settings tab; stored in `settings` table under key `daily_buffer`
- In Monthly Snapshot: checkbox "Show adjusted net worth alongside actual total" driven by `_include_estimation_var`

### Dashboard
- **Metric cards**: NET WORTH (non-investment), MONTHLY CHANGE, FIXED EXPENSES, DISPOSABLE INCOME
- **Extra cards** (conditional): INVESTMENT PORTFOLIO (when investment accounts exist), EXPECTED MONTHLY INCOME (when income exists)
- **Reminder banner**: if `today.day > 20` and no snapshot for previous month → yellow banner. Only shown when `get_earliest_snapshot()` is not None AND previous month is strictly after the earliest snapshot (no reminders before data started).
- **Snapshot History**: compact year × month grid. ✓ = saved snapshot (clickable button → navigates to Monthly Snapshot for that period). · = no snapshot. `_render_snapshot_history()` calls `get_all_snapshots()`. `_go_to_snapshot(year, month)` sets `SnapshotEntryView._pending_period` and calls `navigate("snapshot")`.
- **Annual Overview**: best/worst/avg monthly change and total saved for current year
- **Investment Portfolio section**: shown when investment accounts exist
- **Account Breakdown**: latest vs prev snapshot balances; investment accounts marked with `*` (asterisk); footnote: "* Investment account (excluded from Net Worth)"
- **Dashboard layout order**: metric cards → extra cards → estimation → Annual Overview → Investment Portfolio → Account Breakdown → Snapshot History → CSV Export
- **Export to CSV**: button at bottom; exports Year/Month/Account/Balance/Is_Investment rows

### Visualizations (Charts tab)
- **Net Worth Over Time** (line chart) — ≥2 snapshots
- **Monthly Net Worth Change** (bar chart) — ≥2 snapshots; green/red bars; `ax.margins(y=0.30)`
- **Account Tracker** (line chart, dynamic) — ≥1 snapshot; accounts shown as solid lines with `_tracker_vars: dict[str, BooleanVar]`; income sources shown as dashed lines with `_income_tracker_vars: dict[int, BooleanVar]` and `_income_names: dict[int, str]`; income data loaded via `get_snapshot_income(year, month)` for each snapshot into `_income_snap_data`
- **Investment Performance** (line chart) — when investment data exists

### Notes (tab)
- **My Notes**: free-text CTkTextbox; saved to `settings.my_notes`
- **Debt / Credit Notes**: each note has description, amount, direction ("they_owe"/"i_owe"), date; summary cards show net position; not included in any calculations

### Settings (tab)
- **Daily Spending Allowance**: editable EUR/day field (Edit/Save/Cancel); stored as `settings.daily_buffer`
- **Appearance**: segmented button (System / Light / Dark); calls `ctk.set_appearance_mode()`; saved to `settings.appearance_mode`; applied on app startup in `main.py` after `init_db()`
- **Backup Data**: `filedialog.asksaveasfilename`; copies `DB_PATH` via `shutil.copy2`
- **Restore Data**: `filedialog.askopenfilename`; confirmation dialog; copies file over `DB_PATH`; calls `self.winfo_toplevel().destroy()`
- **Reset All Data**: user must type "DELETE" in confirmation dialog; calls `reset_all_data()` from db.py; closes app. `reset_all_data()` deletes all rows from: snapshot_income, snapshot_balances, snapshots, accounts, fixed_expenses, notes, recurring_income; resets daily_buffer to 20.0, my_notes to ''.

### Sidebar Layout (main.py)
- **Top group** (main tabs): Dashboard, Monthly Snapshot, Budget, Charts, Notes
- **Divider line** (1px CTkFrame, gray)
- **Bottom group** (utility): Settings, Help
- `_nav_buttons` dict covers all 7 entries for highlight management
- All nav buttons have `text_color=("gray10", "gray90")` for correct contrast in both light and dark mode

### Currency Formatting
- All display values use European format: `€1.234,56`
- `fmt_eur(value)` and `fmt_eur_signed(value)` in `utils.py`
- Chart y-axis uses `_eu_axis_fmt(v)`

## Environment

- Python 3.13 virtual environment at `./venv/`
- Activate with: `source venv/bin/activate`
- Run: `python main.py`

## Key Dependencies (already installed in venv)

- `customtkinter` — modern Tkinter wrapper for the GUI
- `matplotlib` — charts and financial visualizations
- `numpy` — numerical operations
- `pillow` — image handling
- `darkdetect` — automatic dark/light mode detection

## Architecture

### File Structure
```
money-tracker/
├── main.py                  — App entry, sidebar nav (top/bottom groups), appearance init, global scroll
├── utils.py                 — fmt_eur(), fmt_eur_signed(), center_on_parent(), effective_charge_day()
├── database/
│   ├── db.py                — All DB ops; settings keys: daily_buffer, my_notes, appearance_mode
│   └── tracker.db
├── views/
│   ├── dashboard.py         — Dashboard; Snapshot History grid; reminder banner
│   ├── snapshot_entry.py    — Monthly Snapshot; income section (active_months based)
│   ├── expenses.py          — Budget tab; batch-save edit mode for both sections
│   ├── charts.py            — Charts/visualizations
│   ├── notes.py             — My Notes + Debt/Credit Notes
│   ├── settings.py          — Settings tab (allowance, appearance, backup/restore, reset)
│   └── help.py              — Help tab (generic, no personal references)
└── requirements.txt
```

## Key DB Functions
- `get_snapshot(year, month)` → dict[name→balance] or None
- `get_snapshot_invested(year, month)` → dict[name→invested_amount]
- `save_snapshot(year, month, balances, invested_amounts=None)` → total_snapshots count
- `delete_snapshot(year, month)` → deletes snapshot + cascades to balances
- `get_all_accounts()` → list[str] (insertion order)
- `get_all_accounts_with_flags()` → list[dict] with name + is_investment bool
- `set_account_investment(name, is_investment)` → updates accounts.is_investment
- `get_all_expenses()` → list of Row objects (ordered by day_of_month, name)
- `get_setting(key)` / `set_setting(key, value)` — settings keys: daily_buffer, my_notes, appearance_mode
- `get_all_income()` → list of Row (id, name, amount, day_of_month, income_type, active_months)
- `add_income(name, amount, day, income_type, active_months)` / `update_income(id, ...)` / `delete_income(id)`
- `get_snapshot_income(year, month)` → dict[income_id→actual_amount]
- `set_snapshot_income(year, month, income_id, actual_amount)` → upsert
- `get_earliest_snapshot()` → (year, month) or None
- `reset_all_data()` → deletes all user data, resets settings to defaults
- DB migrations in `init_db()` handle all schema additions for existing databases

## Important Rules for Claude
- Always use CTk widgets (customtkinter), never raw Tkinter
- All monetary values stored and displayed in EUR; always use `fmt_eur()` / `fmt_eur_signed()` from `utils.py`
- Dynamic fields — avoid hardcoded account names or expense categories
- `sqlite3.Row` does NOT support `.get()` — always convert to `dict(row)` before calling `.get()`
- Confirmation dialogs: `result = [False]`, `CTkToplevel` + `grab_set()` + `wait_window()`; buttons set `result[0]` then `dialog.destroy()`; always call `center_on_parent(dialog, self, width, height)` BEFORE `grab_set()` so dialogs appear centered on the main window
- Mid-month estimation: ALL fixed expenses are shown/subtracted (not just remaining). Day-31 expenses always included in months shorter than 31 days (shown as "end of month").
- Banking day: use `effective_charge_day(year, month, day_of_month, last_day)` from `utils.py` for display labels. Post-save deduction dialog still filters to remaining expenses (eff_d > today.day).
- Global scroll: `_bind_global_scroll()` in `App` (main.py) uses `bind_all("<MouseWheel>")` + `<Button-4/5>` to walk widget hierarchy; pre-checks boundary (`yview()[0] <= 0` → block up-scroll) before calling `yview_scroll()`; also clamps yview to ≥0 after each scroll
- Charts scroll: `_patch_canvas_scroll()` in `ChartsView` replaces `_parent_canvas` MouseWheel bindings with a boundary-aware version that returns `"break"` to prevent the global handler from double-firing
- Sidebar: "Exit App" button anchored to very bottom via a `fill="both", expand=True` spacer frame; `text_color="#FF4444"`, `hover_color="transparent"`; calls `self.quit()` + `self.destroy()`; no confirmation, no divider above it
- `get_all_accounts()` in db.py returns all accounts ever saved, ordered by insertion (`ORDER BY id`)
- `_build_snapshot_dict`: `total` = non-investment sum, `investment_total` = investment sum
- Income active_months: NULL or empty string = active every month; otherwise comma-separated month numbers
- Daily Spending Allowance is in Settings tab only (not Budget tab)
- Backup/Restore is in Settings tab only (not Help tab)
- **Always update `views/help.py`** when adding or modifying features — the Help tab is the user-facing documentation
- Help tab must be generic — no personal references (no specific account names, specific income sources, or specific locations)
