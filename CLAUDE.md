# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Python desktop GUI application for monthly personal finance tracking, built with CustomTkinter and Matplotlib. Designed for general use.

### Core Concept
The app uses a "snapshot" model — the user enters account balances once per month (at the end of the month), and the app calculates the difference between months to determine net worth change. No individual transaction tracking.

## Commands

```bash
# Activate venv
source venv/bin/activate

# Run the app
python main.py

# Install dependencies
pip install -r requirements.txt
```

There are no tests. No linter is configured.

## Context Management

Context is your most important resource.
Proactively use subagents (Task tool)
to keep exploration, research, and verbose
operations out of the main conversation.

**Default to spawning agents for:**
- Codebase exploration
  (reading 3+ files to answer a question)
- Research tasks
  (investigating how something works)
- Code review or analysis
  (produces verbose output)
- Any investigation where only the
  summary matters

**Stay in main context for:**
- Direct file edits the user requested
- Short, targeted reads (1-2 files)
- Conversations requiring back-and-forth
- Tasks where user needs intermediate steps

**MANDATORY rule:** Before implementing any change 
that touches 3+ files, spawn a subagent (Task tool) 
to read and analyze the relevant files first. 
Return only a summary to main context.
Never read 3+ files directly in main conversation.

## Features

### Monthly Snapshot
- User enters balance of all accounts once per month (end of month preferred)
- First entry produces no results (need at least 2 months to calculate)
- All account fields are dynamic — user can add/remove accounts freely
- **Account name editing**: A single "Edit Accounts" toggle button sits alongside "+ Add Account". When ON (shows "Done"): all name fields become editable entries. When OFF: all fields return to read-only labels. Clicking "+ Add Account" auto-enables edit mode for all rows before adding the new row. The toggle resets to OFF on every period change (`_load_existing`).
- **Account persistence**: When a snapshot is saved with any new account, that account is stored in the `accounts` table. When the user navigates to any unsaved current or future month, all known accounts are pre-populated (empty balance). Past unsaved months fall back to `_DEFAULT_ACCOUNTS`.
- **Future month warning**: Saving a snapshot for a month that hasn't started yet shows a confirmation dialog with Continue/Cancel buttons.
- **Remove account confirmation**: Clicking × on an account row shows a confirmation dialog before removing it (no "This cannot be undone." suffix).
- **Post-save deduction dialog**: After saving a snapshot mid-month, a modal dialog appears asking whether to deduct estimated remaining costs from one of the accounts. Includes an "Extra one-time cost (EUR)" input. On confirm, the account balance is reduced, the snapshot is re-saved, and the status bar updates.
- **Layout order** in `_build()`: period selector → account rows → Add/Edit buttons → divider → totals → Income This Month → Save Snapshot → Delete Snapshot
- **Delete Snapshot button**: A red "Delete Snapshot" button (border style) appears below "Save Snapshot" with `pady=(8, 0)` gap, only when a snapshot exists for the selected period.
- **× remove buttons**: Only visible when "Edit Accounts" mode is active. Rendered inside `edit_controls` frame via `_refresh_edit_controls(row)`.
- **Decimal input**: All numeric CTkEntry fields (account balances, income amounts, expense amounts, portfolio shares/prices) auto-convert comma to dot via `bind_numeric_entry(entry)` from `utils.py`, bound to `<KeyRelease>` and `<FocusOut>`.
- **Income This Month card**: Shown in Monthly Snapshot ABOVE the Save Snapshot button when income sources have that month in their `active_months`. User enters actual amounts received; saved to `snapshot_income` table. `_render_income_section()` converts each `sqlite3.Row` to `dict` before calling `.get()`. No INV system — all accounts contribute to Net Worth equally.
- **Extra income**: `+ Add bonus` button per income row opens sub-rows with description + amount fields. Multiple extras per source per month allowed. Saved to `extra_income` table via `clear_extra_income()` + `add_extra_income()` on each save. Dashboard income card shows "+€X in extras" sub-line when `extra_total > 0`.
- **Overwrite warning**: Before `save_snapshot()`, if `get_snapshot(year, month) is not None`, a CTkToplevel confirmation dialog asks "Overwrite?" — Overwrite/Cancel buttons. `lock_scroll()` before `grab_set()`, `unlock_scroll()` after `wait_window()`.
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

### End-of-Month Estimation (Dashboard only)
- Shown on Dashboard when: selected period = current month, today is not the last day of the month, and no snapshot has been saved yet for this month. **Not shown in Monthly Snapshot tab** (removed).
- **Formula (constant, does not change with passing days)**:
  - `estimated_eom = latest_nw - (last_day × daily_buffer) - fx_total`
- **Dashboard card** ("END-OF-MONTH ESTIMATE"): shows "Latest net worth", "Daily allowance (N days × €X/day)" using full month days (constant), "Fixed expenses this month (N items)", then "Estimated end-of-month net worth". No Edit button for daily allowance here.
- **Banking day logic**: `effective_charge_day(year, month, day_of_month, last_day)` in `utils.py`. Saturday → following Monday (+2), Sunday → following Monday (+1), clamped to last_day. Day-31 special case: always shown in months shorter than 31 days (label: "end of month").
- **Post-save deduction dialog** (`_maybe_show_deduction_dialog`): filters to REMAINING expenses only (effective_charge_day > today.day) since it's for balance adjustment after saving mid-month
- **Daily buffer** (default: 20 EUR/day) editable from the Settings tab; stored in `settings` table under key `daily_buffer`.

### Dashboard
- **Metric cards**: NET WORTH, MONTHLY CHANGE, FIXED EXPENSES (3 static cards in `cards_frame`). Extra cards rendered by `_render_extra_cards()` into `_extra_cards_frame`: PORTFOLIO + ALLOCATION DONUT (conditional), LAST MONTH INCOME (conditional).
- **NET WORTH card secondary line**: `_nw_portfolio_lbl` is a `CTkLabel` child of `_nw_inner` (4th return value of `_make_card()`), created in `_build()` unpacked. `pack(before=_nw_spark)` / `pack_forget()` in `_render_extra_cards()` based on portfolio data.
- **ALLOCATION donut card**: Follows Portfolio in slot sequence. `_render_donut_chart()` uses `Figure(figsize=(3.4, 2.0))` with `ax.pie(..., wedgeprops=dict(width=0.52))` + legend `bbox_to_anchor=(1.02, 0.5)`. Colors: `_DONUT_COLORS`. Empty state if `< 2 valued positions`.
- **Reminder badge**: `_render_reminder_badge(inner)` called inside Portfolio card — shows subtle text from `get_portfolio_reminder()` (teal when > 30 days, yellow `#f0c040` when ≤ 30 days or overdue).
- **Reminder banner**: if `today.day > 20` and no snapshot for previous month → yellow banner. Only shown when `get_earliest_snapshot()` is not None AND previous month is strictly after the earliest snapshot (no reminders before data started).
- **Snapshot History**: compact year × month grid. ✓ = saved snapshot (clickable button → navigates to Monthly Snapshot for that period). · = no snapshot. `_render_snapshot_history()` calls `get_all_snapshots()`. `_go_to_snapshot(year, month)` sets `SnapshotEntryView._pending_period` and calls `navigate("snapshot")`.
- **Annual Overview**: best/worst/avg monthly change and total saved for current year
- **Account Breakdown**: latest vs prev snapshot balances, change highlighted green/red
- **Dashboard layout order**: metric cards (`cards_frame`) → extra cards (`_extra_cards_frame`) → estimation → Annual Overview → Account Breakdown → Snapshot History → CSV Export
- **Export to CSV**: button at bottom; exports Year/Month/Account/Balance rows

### Portfolio (tab)
- **DB tables**: `portfolio_positions` (id, ticker, shares, avg_buy_price, currency, notes), `portfolio_cache` (ticker PK, price, price_eur, currency, day_change, day_change_pct, name, updated_at), and `portfolio_reminders` (id, reminder_date TEXT "DD.MM.YYYY", is_enabled INTEGER)
- **Rebalance Reminder**: "Set reminder ▾" CTkOptionMenu (values: "In 1 year", "Custom...") placed in the action row right-aligned next to "+ Add Position". "In 1 year" saves today+365 immediately; "Custom..." opens a 340×170 dialog with date entry (DD.MM.YYYY) + Save/Cancel. `_on_set_reminder(choice)` handles both. Status line shown below action row via `_render_reminder_status()`. Called from `refresh()`. Default date = today + 1 year.
- **Reminder banner**: `_render_reminder_banner()` dynamically packs/unpacks `_reminder_banner` frame `before=self._summary_frame` when reminder is due ≤ 30 days. Called from `refresh()`.
- **DB functions**: `get_portfolio_reminder()` → dict or None; `upsert_portfolio_reminder(date_str, is_enabled)`
- **DB functions**: `get_portfolio_positions()`, `add_position()`, `update_position()`, `delete_position()`, `get_portfolio_cache()`, `upsert_portfolio_cache()` (accepts optional `price_eur` parameter)
- **Live prices**: `_fetch_prices(tickers)` in `views/portfolio.py` — calls `yf.Ticker(t).fast_info` for each ticker; converts to EUR using `yf.Ticker("{CURR}EUR=X").fast_info.last_price`; run in background thread via `threading.Thread(target=do_fetch, daemon=True)`
- **Fallback**: if live fetch fails, reads `portfolio_cache` table and re-applies EUR rate; shows warning status label
- **Position cards**: 2-column grid; shows ticker, company name, current price (original + EUR), today's change, shares, current value, P&L in EUR + % return
- **Summary card**: total portfolio value EUR + total P&L + P&L%
- **Dialogs**: Add position (`open_dialog(self, 460, 350)`) with helper text below Ticker field (`wraplength=280`, `padx=(140,0)`) and background ticker validation ("Checking…" state, `winfo_exists()` guard); Edit position (`open_dialog(self, 460, 310)`, ticker field disabled, no validation); Delete confirm (`open_dialog(self, 400, 140)`)
- **Refresh button**: icon only — text="↻", width=36, size=18. Disabled during fetch (shows "·"), re-enabled in `_on_fetch_done()` with "Prices updated" status for 3s (live fetch only), then reverts to "Last updated: HH:MM"
- **`refresh()`** called by `show_view()` — renders positions from DB with cached prices; starts background fetch if `_price_data` is empty
- yfinance installed in venv; in `requirements.txt`

### Visualizations (Analytics tab)
- **Net Worth Over Time** (smooth line chart) — ≥1 snapshot; 300-point numpy linear interp (`np.interp`) for smooth curve; gradient fill via `fill_between(..., alpha=0.15)`; stats header (current value + change/%)
- **Monthly Net Worth Change** (bar chart) — ≥2 snapshots; green/red bars; `ax.margins(y=0.30)`; stats header (latest change + comparison to previous)
- **Cash Flow** (income bar + spending bar + net savings line) — spending bar shown for ANY month where a previous snapshot exists (`key in prev_nw`). First snapshot never gets a spending bar (no prev). `spent_per_month: list[float | None]` (None = first snapshot, no previous); formula: `spent(N) = prev_nw(N-1) + income(N) - nw(N)`; stats from confirmed months only; filter: `_cashflow_filter` (default "All")
- **Account Tracker** (line chart, dynamic) — ≥1 snapshot; accounts shown as solid lines with `_tracker_vars: dict[str, BooleanVar]`; income sources shown as dashed lines with `_income_tracker_vars: dict[int, BooleanVar]` and `_income_names: dict[int, str]`; income data loaded via `get_snapshot_income(year, month)` for each snapshot into `_income_snap_data`
- **Time filter buttons** per chart: `1M → 3M → 6M → 1Y → YTD → All` (shortest first). Independent state: `_nw_filter`, `_change_filter`, `_tracker_filter`, `_cashflow_filter`. Clicking a filter calls `self.refresh()`. `_filter_snaps(snaps, key)` handles the cutoff logic.
- **Chart style**: figure + axes background `#0d1117`; all spines hidden (`spine.set_visible(False)`); horizontal grid only (`color="#1c2333"`, `alpha=0.6`, `linestyle="--"`); tick color `_TEXT_SEC`

### Help (tab)
- **Search bar**: Right-aligned in the header row (title left, search right). Implemented as a `CTkFrame` container (`_BG_ELEM`, border, corner_radius=8) with a 🔍 label + `CTkEntry` (transparent bg, no border, width=220, `placeholder_text="Search..."`) + `×` clear button (hidden when empty). `_search_var` traces changes → `_render_content(term)` rebuilds `_content_frame`.
- **Content as data**: All help text stored in module-level `_HELP_DATA` list of `{section, items[]}` dicts. Item types: `"heading"`, `"body"`, `"bullet"`. No hardcoded widgets.
- **Filtering**: Section shown if `term` found in section title or any item text. `_render_content("")` renders all sections (normal mode).
- **Highlighting**: Only the matching substring is highlighted — no background on the whole block. Each matched item is split into multiple inline `CTkLabel` widgets (side="left") via `_pack_text_segments()`: non-matching text in normal color, matching text in `_MATCH_COLOR = "#f0c040"` (yellow, bold). `_HIGHLIGHT = "#0d2035"` constant kept but no longer used. `_no_results_lbl` shown when no matches.

### Notes (tab)
- **My Notes**: free-text CTkTextbox; saved to `settings.my_notes`
- **Debt / Credit Notes**: each note has description, amount, direction ("they_owe"/"i_owe"), date; summary cards show net position; not included in any calculations

### Settings (tab)
- **Daily Spending Allowance**: editable EUR/day field (Edit/Save/Cancel); stored as `settings.daily_buffer`
- **Appearance**: segmented button (System / Light / Dark); calls `ctk.set_appearance_mode()`; saved to `settings.appearance_mode`; applied on app startup in `main.py` after `init_db()`
- **Notifications**: toggle (auto-saves), email field, Resend API key field (masked, `show="•"`), email_days + banner_days entries (1–15), Save button, Send test email button. API key stored as `base64.b64encode(key.encode()).decode()` in `settings.resend_api_key`; decoded on load. Test email and scheduled notifications sent via `resend` Python SDK in background thread. Settings keys: `notif_enabled` (0/1), `notif_email`, `resend_api_key` (base64), `email_days` (default 3), `banner_days` (default 7), `last_notification_sent` (YYYY-MM).
- **Backup Data**: `filedialog.asksaveasfilename` WITHOUT `defaultextension` (omit it — `initialfile` already contains `.db`; adding `defaultextension=".db"` causes double extension on macOS); copies `DB_PATH` via `shutil.copy2`
- **Restore Data**: `filedialog.askopenfilename`; confirmation dialog; copies file over `DB_PATH`; calls `self.winfo_toplevel().destroy()`
- **Reset All Data**: user must type "DELETE" in confirmation dialog; calls `reset_all_data()` from db.py; closes app. `reset_all_data()` deletes all rows from: snapshot_income, snapshot_balances, snapshots, accounts, fixed_expenses, notes, recurring_income; resets daily_buffer to 20.0, my_notes to ''.

### In-App Banner (main.py)
- Shown on startup when: `notif_enabled=1`, today is within `banner_days` of end of month, and no snapshot for current month.
- `_check_startup_banner()` called in `__init__` after `_build_layout()`. Creates a `_banner_frame` (fg_color `#3d3000`) packed at top of `self.content` before `self._view_container`.
- Banner text is clickable (`cursor="hand2"`) → navigates to snapshot. Dismiss × button destroys the frame for the session.
- Views are created inside `self._view_container` (not directly in `self.content`) so the banner can sit above them.

### Background Notifier (GitHub Actions)
- **Primary notifier**: `.github/workflows/notify.yml` — runs daily at 15:00 UTC (17:00 CET) via cron.
- **Script**: `scripts/notify.py` — standalone, no app imports; reads all config from environment variables.
- **Logic**: checks `days_left <= NOTIFICATION_DAYS`; checks `LAST_NOTIFICATION_SENT` repo variable to skip if already sent this month; sends via Resend API; updates `LAST_NOTIFICATION_SENT` variable on success.
- **Secrets** (set in repo Settings → Secrets → Actions): `RESEND_API_KEY`, `NOTIFICATION_EMAIL`.
- **Variables** (set in repo Settings → Variables → Actions): `NOTIFICATION_DAYS` (default 3), `LAST_NOTIFICATION_SENT` (managed automatically by workflow).
- `workflow_dispatch` trigger allows manual test runs from the Actions tab.
- **Legacy**: `notifier.py` at project root is the old launchd-based notifier (macOS-only, reads DB directly). Superseded by the GitHub Actions workflow.

### Sidebar Layout (main.py)
- **Top group**: Dashboard, Monthly Snapshot, Budget, Portfolio, Analytics
- **Divider 1**
- **Middle group**: Notes, Help
- **Divider 2**
- **Bottom group**: Settings
- **Spacer** (fill="both", expand=True)
- **Exit** (red, anchored to very bottom)
- `_nav_buttons` dict covers all nav entries (dashboard, snapshot, expenses, portfolio, charts, notes, help, settings)
- No emoji icons in nav labels — clean text only

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
- `yfinance` — live price fetching for Portfolio tab

## Design System (Premium Dark Theme)

### Color Palette
All views use fixed hex color constants (not CTK light/dark tuples) for the custom palette:
```python
_BG_SIDEBAR    = "#161b22"   # Sidebar background
_BG_MAIN       = "#0d1117"   # Main content background
_BG_CARD       = "#161f2e"   # Card / panel background (glassmorphism)
_BG_CARD_HOVER = "#1f2d42"   # Hover state for interactive cards (portfolio.py)
_ACCENT        = "#00b4d8"   # Teal accent (primary buttons, active nav)
_TEXT_PRI      = "#e6edf3"   # Primary text
_TEXT_SEC      = "#8b949e"   # Secondary / muted text
_BORDER        = "#2a3a52"   # Borders and dividers (glass effect)
_BG_ELEM       = "#21262d"   # Input fields, secondary buttons, edit rows
_GREEN         = "#3fb950"   # Positive / success
_RED           = "#f85149"   # Negative / destructive
```

### Component Patterns
- **Cards**: `ctk.CTkFrame(parent, fg_color=_BG_CARD, corner_radius=14, border_width=1, border_color=_BORDER)` — no inner highlight strips anywhere
- **Primary buttons** (Save/Add): `fg_color=_ACCENT, hover_color="#0096b4", text_color="white", corner_radius=8`
- **Secondary buttons** (Edit/Cancel): `fg_color=_BG_ELEM, hover_color="#3d4d63", text_color=_TEXT_PRI, corner_radius=8`
- **Destructive buttons** (Delete/×): `fg_color=_BG_ELEM, hover_color="#3d1a1a", text_color=_RED, corner_radius=8`
- **Input fields**: `fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI`
- **Dividers**: `ctk.CTkFrame(parent, height=1, fg_color=_BORDER)`
- **Stat label** (card header): 11px, `text_color=_TEXT_SEC`
- **Stat value** (card value): 28px bold, `text_color=_TEXT_PRI`

### Sidebar (main.py)
- Background: `_BG_SIDEBAR`; Content area: `_BG_MAIN`
- Active nav tab: `fg_color=_ACCENT, hover_color=_ACCENT, text_color="white"`
- Inactive nav tab: `fg_color="transparent", hover_color=_BG_CARD, text_color=_TEXT_SEC`
- Hover effect: `_bind_nav_hover()` sets `text_color=_TEXT_PRI` on `<Enter>`, reverts on `<Leave>` (only when not active)
- `_active_nav_key: str | None` tracks the currently active tab
- Tab fade: `_fade_step(step)` animates `content.configure(fg_color=...)` through `["#050a12","#080f1a","#0b131e","#0d1117","#0d1117"]` via `self.after(20, ...)`

### Sparklines (dashboard.py)
- Embedded in Net Worth and Monthly Change metric cards
- `Figure(figsize=(1.7, 0.42), dpi=100)`, `ax.axis("off")`, `fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.05)`
- NW sparkline: `ax.plot(x, values, color=_ACCENT, linewidth=1.5)` + `fill_between`
- Change sparkline: `ax.bar(x, values, color=[_GREEN if v>=0 else _RED])` + `ax.axhline`
- Fig and axes backgrounds set to `_BG_CARD` to blend with card

### Font
- All CTkFont calls use `_F = "Helvetica Neue"` constant declared in each file: `ctk.CTkFont(family=_F, size=X)` or `ctk.CTkFont(family=_F, size=X, weight="bold")`
- `_F` is defined at module level in: `main.py`, `views/dashboard.py`, `views/snapshot_entry.py`, `views/charts.py`, `views/expenses.py`, `views/notes.py`, `views/settings.py`, `views/help.py`

### Scroll
- Global scroll: 3 units per event (`yview_scroll(-3/3, "units")`); guarded by `is_scroll_locked()` at top of `on_scroll()`
- Scroll lock: `lock_scroll()` / `unlock_scroll()` / `is_scroll_locked()` in `utils.py` (global `_scroll_locked` flag)
- **`open_dialog(parent, width, height)`** in `utils.py`: creates a centered, scroll-locked CTkToplevel — wraps `center_on_parent()` + `lock_scroll()` + `grab_set()` + `focus_set()`; call `dlg.wait_window()` then `unlock_scroll()` after setting up dialog content
- All CTkToplevel dialog sites use `open_dialog()` then `wait_window()` then `unlock_scroll()`

### Charts (charts.py)
- `_palette()` returns fixed dark colors (no light/dark detection)
- `_apply_style()`: fig + axes bg `#0d1117`; all spines hidden; horizontal grid only

## Architecture

### File Structure
```
money-tracker/
├── main.py                  — App entry, sidebar nav (3 groups), appearance init, global scroll
├── utils.py                 — fmt_eur(), fmt_eur_signed(), center_on_parent(), effective_charge_day(), lock_scroll(), unlock_scroll(), is_scroll_locked(), open_dialog()
├── database/
│   ├── db.py                — All DB ops; settings keys: daily_buffer, my_notes, appearance_mode
│   └── (no tracker.db — DB lives at ~/Library/Application Support/MoneyTracker/tracker.db)
├── views/
│   ├── dashboard.py         — Dashboard; Snapshot History grid; reminder banner
│   ├── snapshot_entry.py    — Monthly Snapshot; income section (active_months based)
│   ├── expenses.py          — Budget tab; batch-save edit mode for both sections
│   ├── portfolio.py         — Portfolio tab; live prices via yfinance; background thread fetch
│   ├── charts.py            — Analytics tab: Net Worth, Monthly Change, Cash Flow, Account Tracker
│   ├── notes.py             — My Notes + Debt/Credit Notes
│   ├── settings.py          — Settings tab (allowance, appearance, backup/restore, reset)
│   └── help.py              — Help tab (generic, no personal references)
└── requirements.txt
```

**DB location**: `~/Library/Application Support/MoneyTracker/tracker.db` (macOS); `%APPDATA%/MoneyTracker/tracker.db` (Windows). Created automatically on first launch. One-time migration copies old bundle DB if present.

## Key DB Functions
- `get_snapshot(year, month)` → dict[name→balance] or None
- `get_snapshot_invested(year, month)` → dict[name→invested_amount]
- `save_snapshot(year, month, balances, invested_amounts=None)` → total_snapshots count
- `delete_snapshot(year, month)` → deletes snapshot + cascades to balances
- `get_all_accounts()` → list[str] (insertion order)
- `get_all_expenses()` → list of Row objects (ordered by day_of_month, name)
- `get_setting(key)` / `set_setting(key, value)` — settings keys: daily_buffer, my_notes, appearance_mode
- `get_all_income()` → list of Row (id, name, amount, day_of_month, income_type, active_months)
- `add_income(name, amount, day, income_type, active_months)` / `update_income(id, ...)` / `delete_income(id)`
- `get_snapshot_income(year, month)` → dict[income_id→actual_amount]
- `set_snapshot_income(year, month, income_id, actual_amount)` → upsert
- `get_extra_income(year, month)` → list[dict] with id, income_id, description, amount
- `add_extra_income(year, month, income_id, description, amount)` → lastrowid
- `delete_extra_income(entry_id)` → deletes one extra row
- `clear_extra_income(year, month, income_id)` → deletes all extras for one source in one month
- `get_earliest_snapshot()` → (year, month) or None
- `reset_all_data()` → deletes all user data, resets settings to defaults
- `get_portfolio_positions()` → list[dict] (id, ticker, shares, avg_buy_price, currency, notes)
- `add_position(ticker, shares, avg_buy_price, currency, notes)` → lastrowid
- `update_position(position_id, ticker, shares, avg_buy_price, currency, notes)`
- `delete_position(position_id)`
- `get_portfolio_cache()` → dict[ticker → dict] (price, price_eur, currency, day_change, day_change_pct, name, updated_at)
- `upsert_portfolio_cache(ticker, price, currency, day_change, day_change_pct, name, price_eur=None)`
- `get_portfolio_reminder()` → dict (id, reminder_date, is_enabled) or None
- `upsert_portfolio_reminder(reminder_date: str, is_enabled: int)` — create or update single reminder row
- DB migrations in `init_db()` handle all schema additions for existing databases

## Important Rules for Claude
- Always use CTk widgets (customtkinter), never raw Tkinter
- All monetary values stored and displayed in EUR; always use `fmt_eur()` / `fmt_eur_signed()` from `utils.py`
- Dynamic fields — avoid hardcoded account names or expense categories
- `sqlite3.Row` does NOT support `.get()` — always convert to `dict(row)` before calling `.get()`
- **Modal dialogs**: use `open_dialog(parent, width, height)` from `utils.py` — creates centered, scroll-locked CTkToplevel and returns it. Then set up content, call `dialog.wait_window()`, then `unlock_scroll()`.
- End-of-month estimation (Dashboard only): ALL fixed expenses are shown/subtracted. Day-31 expenses always included in months shorter than 31 days (shown as "end of month"). Not shown in Monthly Snapshot view.
- Banking day: use `effective_charge_day(year, month, day_of_month, last_day)` from `utils.py` for display labels. Post-save deduction dialog still filters to remaining expenses (eff_d > today.day).
- Global scroll: `_bind_global_scroll()` in `App` (main.py) uses `bind_all("<MouseWheel>")` + `<Button-4/5>` to walk widget hierarchy; guards with `is_scroll_locked()` at top; pre-checks boundary (`yview()[0] <= 0` → block up-scroll) before calling `yview_scroll(-3/3, "units")`; also clamps yview to ≥0 after each scroll
- Scroll lock: use `open_dialog()` (which calls `lock_scroll()` internally); call `unlock_scroll()` after `wait_window()`. `lock_scroll()`, `unlock_scroll()`, `is_scroll_locked()` are in `utils.py`.
- Charts scroll: `_patch_canvas_scroll()` in `ChartsView` replaces `_parent_canvas` MouseWheel bindings with a boundary-aware version that returns `"break"` to prevent the global handler from double-firing
- Dashboard spacing: `_estimation_container` is NOT pre-packed in `_build()`; `_render_estimation()` packs it dynamically (before `_annual_divider`) when content exists, and calls `pack_forget()` when empty
- Sidebar: Exit button anchored to very bottom via `fill="both", expand=True` spacer; `text_color="#FF4444"`; sidebar has 3 groups (Top/Middle/Bottom) separated by 2 dividers
- `get_all_accounts()` in db.py returns all accounts ever saved, ordered by insertion (`ORDER BY id`)
- `_build_snapshot_dict`: `total` = sum of ALL account balances (no investment distinction)
- Income active_months: NULL or empty string = active every month; otherwise comma-separated month numbers
- Daily Spending Allowance is in Settings tab only (not Budget tab)
- Backup/Restore is in Settings tab only (not Help tab)
- **Always update `views/help.py`** when adding or modifying features — the Help tab is the user-facing documentation
- Help tab must be generic — no personal references (no specific account names, specific income sources, or specific locations)
