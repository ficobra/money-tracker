# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Python desktop GUI application for monthly personal finance tracking, built with PyQt6 and Matplotlib. Designed for general use. CustomTkinter migration is complete — no CTK imports remain anywhere.

**PyQt6 Migration status**: COMPLETE. All views migrated to PyQt6. No CTK imports remain in any file.

**UI fixes applied**: Save Snapshot button in `views/snapshot_entry.py` uses explicit inline `setStyleSheet()` (teal `#00b4d8` bg, dark text, rounded corners, hover/pressed states) — no `setProperty("class", "accent")`. `QDoubleValidator` in `utils.py` `bind_numeric_entry()` has locale forced to `en_US` via `QLocale` to prevent German/system-locale decimal reformatting. `bind_numeric_entry(widget, decimals: int = 2)` accepts an optional `decimals` parameter (default 2); portfolio shares field calls `bind_numeric_entry(shares_entry, decimals=8)` to allow fractional share quantities. After saving a snapshot, `_show_portfolio_reminder()` in `snapshot_entry.py` makes a dismissible banner visible for 30 s ("Snapshot saved. Don't forget to update your portfolio value…" + "Go to Portfolio →" teal button); navigation uses `getattr(self, '_navigate', None)` to no-op safely if not wired. `SnapshotEntryView.__init__` accepts `navigate_callback=None`; stored as `self._navigate`. `main.py` instantiates it via `lambda: SnapshotEntryView(navigate_callback=self.show_view)` so the "Go to Portfolio →" button navigates correctly. `views/portfolio.py` `_render_hero_stats()` calls `update_snapshot_portfolio` on the latest snapshot whenever a fresh (non-cache) price fetch completes and `total_eur > 0`; requires `get_latest_snapshots` and `update_snapshot_portfolio` imported from `database.db`. Portfolio refresh button moved to top-right VStack; `_nw_portfolio_lbl` has `setFixedHeight(18)`. All three metric cards (`nw_card`, `ch_card`, `alloc_card`) `setFixedHeight(240)`. Monthly Change card sparkline is vertically centered via `ch_v.addStretch()` before and after the spark container (no fixed spacing). Period label in `_render_comparison()` uses inline `<span>` styles — latest month in white `#e8f4f8` bold, "vs prev" in dim `#6b8fa8`. NET WORTH card has `_nw_pill_row` (QWidget + QHBoxLayout) below `_nw_portfolio_lbl`; populated by `_render_comparison()` with a pill showing ▲/▼ + EUR change followed by a separate `make_label` for the pct (e.g. `+2.3%`), both in the change color. Monthly Change card has `_avg_mo_label` (11px, TEXT_SEC) inserted after `_change_spark_container`; set in `refresh()` with AVG/MO across all snapshots. Allocation donut canvas height is 160px (not 180px); a `total_row` with "Total" label and formatted EUR value is added below the canvas in `_render_donut_chart()`. Snapshot History redesigned: cells show `€Xk` values as QPushButton (teal on `#162440` bg, `#1e3a55` border, 52×32px); year label 48px wide; month header uses single-char abbreviations; empty cells are dimmer dots (`#1e3448`).

**Visual redesign (theme.py + main.py)**: Premium terminal palette — `BG_SIDEBAR=#060c15`, `BG_MAIN=#0d1117`, `BG_CARD=#111922`, `BG_ELEM=#1a2332`, `BORDER=#1e3448`, `TEXT_PRI=#e8f4f8`, `TEXT_SEC=#6b8fa8`. Sidebar 200px wide, `#060c15` bg, `1px #0f1e30` right border. Logo area 80px height with app icon (36px) + "Money Tracker" bold 13px + "V 2.4" dim 10px + 1px `#0f1e30` separator. Nav buttons use ONLY inline `setStyleSheet()` — NO `setProperty("class")`, NO QSS nav rules in theme.py. `_NAV_ACTIVE` / `_NAV_INACTIVE` class-level constants on App. Nav text is just the label (no dot prefix). Active state indicated purely by `border-left: 3px solid #00b4d8` and `rgba(0,180,216,0.10)` background. Inactive: border-left transparent, color `#9fb0c5`. Dividers: 1px `#0f1e30`, 16px left/right margins. Exit button: red `#f85149`, border-left style, left-aligned. QPalette: `Window=#0d1117`, `Base=#0d1117`, `AlternateBase=#0d1117`, `Button=#0d1117` — all background roles set to the page color so Fusion engine never paints white over cards. After `app.setPalette()`, call `app.setAttribute(Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles, True)` to ensure stylesheet color overrides propagate correctly. Scrollbar 6px with `min-height: 40px` handle.

**Analytics scroll**: `eventFilter` intercepts `QEvent.Type.Wheel` on viewport + all canvas widgets (`setFocusPolicy(NoFocus)` + `installEventFilter(self)`); `setFocusPolicy(StrongFocus)` on ChartsView. Content widget `setSizePolicy(Expanding, Preferred)`. Dashboard metric cards `setFixedHeight(200)`, sparkline placed before `_nw_portfolio_lbl` in layout so all three cards align identically.

**styles/theme.py**: Global rules — `* { outline: none; }`, `QMainWindow { background: #0d1117; }`, `QWidget { color: #e8f4f8; background: transparent; }` — `background: transparent` on QWidget prevents Qt double-fill; safe because palette sets all background roles to `#0d1117` and per-view root widgets set explicit backgrounds. `QScrollArea > QWidget > QWidget { background: transparent; }`. NO nav button rules in theme.py — nav uses inline `setStyleSheet()` only. Dividers: `QFrame[class="divider"] { background: #1a2e45; border: none; max-height: 1px; }`. `font-family: monospace` must NOT be used — use `font-family: 'Courier New'` instead.

**Transparent child widgets**: `make_label()` and `make_pill()` in `dashboard.py` do NOT set any WA attributes — the stylesheet `background: transparent` is sufficient and WA attributes on plain labels/pills cause rendering issues. `make_eyebrow()` still sets `WA_NoSystemBackground` + `WA_TranslucentBackground` on its QLabel children. Container QWidgets (non-label, non-pill) may still use `WA_NoSystemBackground` where needed. **Exception**: card frame widgets (`QFrame` returned by `make_card_l1/l2/l3`) must NOT have any WA attributes — they need to paint their background and border. Pill `addWidget` calls use `alignment=Qt.AlignmentFlag.AlignLeft` to prevent stretching.

**Card factories** (dashboard.py): `make_card_l3/l2/l1()` use bare-property `setStyleSheet()` with NO `QFrame { }` selector — widget-level `setStyleSheet()` without a selector applies to that widget only, so no nesting/specificity issues. Card frames must NOT have WA attributes — WA attributes belong only on child widgets inside the card. `make_card()` aliases `make_card_l2()`. Docstrings removed. `register_fonts()` in `styles/theme.py` registers DM Sans with matplotlib if a `.ttf` file is found in common macOS font paths; called from `main.py` after all imports.

**Matplotlib global config**: All three chart files (`charts.py`, `dashboard.py`, `portfolio.py`) set `matplotlib.rcParams` after imports — `font.family=DejaVu Sans`, `text.color=#eef2f7`, `axes.labelcolor=#eef2f7`, `xtick.color=#5a7a94`, `ytick.color=#5a7a94`. If DM Sans is found by `register_fonts()`, it overrides `font.family` globally. All `fontfamily="DM Sans"` references in matplotlib calls have been replaced with `fontfamily="DejaVu Sans"` as the safe fallback.

**Donut chart canvas background**: All donut/sparkline canvas colors match the exact card they sit in. `_add_sparkline(container, values, chart_type, bg=BG_CARD, labels=None, figsize=(1.7, 0.42))` — NET WORTH sparkline passes `bg="#162440"`, `labels=month_labels`, `figsize=(1.7, 0.9)`, container height 90px (= 0.9 × 100 dpi). MONTHLY CHANGE passes `bg="#111d2e"`, container height 44px, default figsize. Dashboard: donut `setFixedHeight(180)` (= 1.8 × 100 dpi), figure `(2.8, 1.8)`, `subplots_adjust(left=0.0, right=0.55, top=1.0, bottom=0.0)`. `alloc_v.setContentsMargins(20, 10, 20, 10)` — 10px top/bottom leaves exactly 180px for the canvas inside a 200px card. Sparkline `subplots_adjust`: no-labels `top=1.0, bottom=0.05`; with-labels `top=1.0, bottom=0.30`. Container height must always equal `figsize_height × dpi` to leave no gap for Qt to paint. `_add_sparkline` uses `figsize` param — pass `figsize=(1.7, 0.9)` for NW sparkline only. Dashboard ALLOCATION card uses bare-property `setStyleSheet()` (no `QFrame { }` selector). NW sparkline gradient: `imshow` with `LinearSegmentedColormap` from teal-transparent to teal-0.35, clipped to the area under the line via `PathPatch`; `extent` must be a tuple not a list. Requires `import numpy as np`, `import matplotlib.colors` at top of dashboard.py. Portfolio allocation canvas: `canvas.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)` added after `canvas.setPalette(pal)` — no `WA_TranslucentBackground` on canvas. Layout access uses `if lay is not None:` (not `if lay:`) — Qt layouts are falsy when empty, so `if lay:` silently skips a valid empty layout.

**NET WORTH value label**: created with `make_label("—", 28, bold=True)` then immediately overridden with `font.setPixelSize(48)` — pixel size avoids display-scaling inconsistencies from point size.

**Dashboard visual polish**: `make_label()` adds `border: none; outline: none;` to all labels. `_nw_portfolio_lbl` is always in layout (never hidden); text set to `""` when no portfolio data, `"€X incl. portfolio"` when data exists, color `#9fb0c5`. Extra-cards: portfolio PnL and income pct shown as `make_pill()` with ▲/▼ arrows. Eyebrow right labels: Portfolio shows `"REBALANCE DD.MM.YYYY"` if reminder enabled; Fixed Expenses shows `"N ITEMS"`; Last Month Income shows 3-letter month. NET WORTH sparkline: `_add_sparkline` accepts `labels` param; when provided, x-axis tick labels shown with `colors="#6b7d94"`, spines hidden, y-axis hidden; container height 90px; labels = `["Jan '25", ...]` from last 6 snapshots. MONTHLY CHANGE sparkline height stays 44px with no labels.

**Dashboard helpers** (module-level in `views/dashboard.py`): `make_eyebrow(left_text, right_text="")` returns a `QHBoxLayout` with a small-caps left label (`color: #6b7d94`, `letter-spacing: 2px`) and optional right label (monospace, right-aligned). `make_pill(text, color=ACCENT, bg_alpha=0.12)` returns a **`QFrame`** (not QLabel) — `QFrame.Shape.NoFrame`, `setFixedHeight(22)`, `QFrame { background: hex; border-radius: 10px; border: none; }` stylesheet, inner `QLabel` child with transparent bg. Solid hex background blended from base color `#111d2e`. No palette override. Portfolio P&L: one `make_pill` (absolute EUR with arrow) + one `make_label` (percentage) in a `pills_row` QWidget with `QHBoxLayout`, spacing 4px, trailing stretch. Income pct change: `make_pill` inside `pills_row_inc` widget with trailing stretch. Sparkline x-axis tick labels use `fontsize=7` (not 8) to prevent clipping. Period label in `_render_comparison()` uses RichText with `<b>latest_month</b>  ·  vs prev_month`. `_render_reminder_badge()` call removed from `_render_extra_cards()` — rebalance date shown only in eyebrow right label. Fixed expenses estimation row label has no item count suffix. Both helpers use `QPalette`/`QColor` imported at top of dashboard.py. All four helpers (`make_label`, `make_eyebrow`, `make_pill`, `make_divider`) plus all three card factories are **duplicated locally** in `views/snapshot_entry.py` to avoid circular imports — do not import from dashboard.py.

**Monthly Snapshot redesign** (`views/snapshot_entry.py`): Period selector uses 12 clickable month pill buttons (`self._month_btns`) instead of QComboBox — hidden QComboBox kept for compatibility with `_get_period()`/`refresh()`. Active pill: `rgba(0,180,216,38)` bg, teal border/text. Year field styled as L4 input (`#1c2d4a` bg). Info banner (`make_card_l1()`) shown when no existing snapshot. Accounts and sidebar in `QHBoxLayout(stretch=2,1)`. Sidebar card (`make_card_l3()`) shows net worth at 34px pixel size + stats (`_update_sidebar_stats()`): last month total, portfolio EUR, days remaining, daily allowance. `_update_total()` calls `_update_sidebar_stats()`. Income card uses `make_card_l2()`. `_load_existing()` calls `_update_month_pills()` to sync pills on navigation.

**Sidebar nav redesign** (main.py + styles/theme.py): No section labels. 3 groups separated by 2 invisible spacers (16px `QWidget`, transparent — no visible line). Nav buttons use inline `setStyleSheet()` only — `_NAV_ACTIVE` / `_NAV_INACTIVE` class-level constants. No dot prefix — plain label text. Active state: `background: #0d1f35`, `border-radius: 8px`, `color: #00b4d8`, `margin: 0px 8px`. Inactive: `background: transparent`, `border: none`, `color: #6b7d94`, `margin: 0px 8px`. Both use `padding: 9px 16px`. `show_view()` sets `btn.setText(self._nav_labels[k])` and applies active/inactive stylesheets. Logo icon has `background: #111d2e; border-radius: 10px; padding: 4px`. Exit button: 36px tall, centered text, `border: 1px solid rgba(248,81,73,0.3)`, `border-radius: 8px`, `margin: 0px 12px` (no `setSizePolicy`).

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
- **Portfolio value on save**: after `save_snapshot()`, the current portfolio EUR value is calculated from `get_portfolio_positions()` + `get_portfolio_cache()` and stored via `update_snapshot_portfolio(year, month, portfolio_eur)`. Wrapped in try/except so missing cache never blocks the save.

### Budget (tab)
The "Budget" tab is split into two sections:

**Fixed Monthly Expenses**
- User can define recurring monthly expenses with name, amount, day of month, and **category**
- **Categories**: `FIXED_CATEGORIES = ["Housing", "Investing", "Subscriptions", "Utilities", "Health & Fitness", "Other"]` — module-level constant in `views/expenses.py`. Selected via `QComboBox` (styled dark, `#1c2d4a` bg). Default: "Other".
- **Batch-save edit mode**: "Edit" toggle in section header. When ON (shows "Done"): ALL rows immediately show as entry widgets simultaneously. "×" button appears per row for deletion (with confirmation). Clicking "Done" validates + saves all changed rows at once. If validation fails, an error label appears next to the "Done" button and edit mode stays active.
- `_expenses_edit_mode: bool` and `_expenses_row_vars: dict[int, dict]` (id → {day, name, amount, category: QComboBox})
- `_save_all_expenses()` iterates `_expenses_row_vars`, validates, calls `update_expense()` for each (including category)
- Table header includes CATEGORY column (140px wide); display rows show category as plain label; edit rows show `QComboBox`

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
- **Metric cards**: NET WORTH, MONTHLY CHANGE, FIXED EXPENSES (3 static cards in `cards_frame`). Extra cards rendered by `_render_extra_cards()` into `_extra_cards_frame`: PORTFOLIO + ALLOCATION DONUT (conditional), LAST MONTH INCOME (conditional). LAST MONTH INCOME shows income from `latest` (snapshots[0]); pct-change compares to `prev_snap` (snapshots[1]); label reads "vs {MONTHS[prev_snap['month']-1]}". `has_income_data = bool(latest)`.
- **NET WORTH card secondary line**: `_nw_portfolio_lbl` is a `CTkLabel` child of `_nw_inner` (4th return value of `_make_card()`), created in `_build()` unpacked. `pack(before=_nw_spark)` / `pack_forget()` in `_render_extra_cards()` based on portfolio data.
- **ALLOCATION donut card (dashboard)**: Top metric row card 3. `self._alloc_card_layout` (QVBoxLayout) stored in `_build()`, cleared/repopulated each refresh via `_render_donut_chart()`. Card stylesheet overrides `make_card()` default: `background: #080f1a; border: 1px solid #112035`. `Figure(figsize=(2.8, 1.8))`, all backgrounds `#080f1a` (fig patch, axes, edgecolor, canvas stylesheet, QPalette Window+Base, `setAutoFillBackground(True)`). Legend `fontsize=7`, `framealpha=0.0`, `subplots_adjust(right=0.52)`, `canvas.setFixedHeight(160)`. Labels: ticker truncated to 6 chars. Colors: `_DONUT_COLORS`. Empty state if no valued positions. dashboard.py imports `QPalette` alongside `QFont, QColor`.
- **Portfolio ALLOCATION chart**: `_render_allocation_section(positions, cache)` stores `self._valued_alloc` and `self._alloc_colors`, then delegates chart rendering to `_render_alloc_donut(mode)`. Three segment buttons stored in `self._seg_btns` list (class constants `_SEG_ACTIVE` / `_SEG_INACTIVE`); clicking one calls `_render_alloc_donut("Current"|"Target"|"Drift")`. "Current" = actual allocation donut; "Target" = equal-weight donut; "Drift" = bar chart (green/red) of deviation from equal weight. Chart: `Figure(figsize=(2.4,2.4), dpi=100)`, bg `#0d1520`, `wedgeprops width=0.52`, `canvas.setFixedSize(240,240)`. `_alloc_chart_container` has `WA_NoSystemBackground` only (no WA_TranslucentBackground) and `background: #0d1520` stylesheet — canvas must be visible. `_DONUT_COLORS` on class. `_hex_to_rgb()` helper removed — pill colors computed inline with `int(color[1:3],16)` etc. Quick-add form and `_quick_add_position()` method removed — add position via dialog only ("+Add Position" button in holdings header).
- **Reminder badge**: `_render_reminder_badge(inner)` called inside Portfolio card — shows subtle text from `get_portfolio_reminder()` (teal when > 30 days, yellow `#f0c040` when ≤ 30 days or overdue).
- **Reminder banner**: if `today.day > 20` and no snapshot for previous month → yellow banner. Only shown when `get_earliest_snapshot()` is not None AND previous month is strictly after the earliest snapshot (no reminders before data started).
- **Snapshot History**: compact year × month grid. ✓ = saved snapshot (clickable button → navigates to Monthly Snapshot for that period). · = no snapshot. `_render_snapshot_history()` calls `get_all_snapshots()`. `_go_to_snapshot(year, month)` sets `SnapshotEntryView._pending_period` and calls `navigate("snapshot")`.
- **Annual Overview**: best/worst/avg monthly change and total saved for current year
- **Account Breakdown**: latest vs prev snapshot balances, change highlighted green/red
- **Dashboard layout order**: metric cards (`cards_frame`) → extra cards (`_extra_cards_frame`) → estimation → prediction accuracy → Annual Overview → Account Breakdown → Snapshot History → CSV Export
- **Prediction Accuracy History table** (`_render_prediction_accuracy(all_snaps)`): shown when ≥2 snapshots exist. Receives `all_snaps` (oldest→newest). Builds `all_rows` newest-first; month label is month name only (no year). **Year filter**: `CTkOptionMenu` in subtitle row (right-aligned via grid col 1); options `["All"] + years desc`; default = most recent year; stored in `self._pred_year_filter`; on change calls `_render_prediction_accuracy(all_snaps)` again. When specific year selected: rows filtered to that year; "No data for {year}." shown if empty. Header row (fg `_BG_ELEM`) + alternating data rows (`_BG_CARD` / `#161b22`). Columns: Month 160w, Estimated 160e `_TEXT_SEC`, Actual 160e `_TEXT_SEC`, Difference 160e green/red. `_prediction_container` packed `before=self._annual_divider`.
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
- **Net Worth Over Time** (smooth line chart) — ≥1 snapshot; 300-point numpy linear interp (`np.interp`) for smooth curve; teal line gets 30-strip `fill_between` gradient fill (alpha 0→0.35, `y_floor` = min − 10% range); green "Incl. portfolio" line gets 30-strip `fill_between` gradient fill (alpha 0→0.35, `yp_floor` = min − 5% range). Legend `loc="lower center"`, `bbox_to_anchor=(0.5, 1.01)`, `ncol=2`, `frameon=False` — floats above the axes. Stats header (current value + change/%). **Two lines**: teal `#00b4d8` "Excl. portfolio" always plots all snapshots; green `#3fb950` "Incl. portfolio" only plots snapshots where `portfolio_eur > 0` (uses `x_port`/`y_total_port` subsets to avoid false cliffs). If `len(x_port) >= 2` → smooth interp over `[x_port[0], x_port[-1]]`; else single marker. Legend shown when portfolio line is visible. Header stats use `y_total_port[-1]`/`[-2]` when portfolio data exists.
- **Monthly Net Worth Change** (bar chart) — ≥2 snapshots; green/red bars; `ax.margins(y=0.30)`; stats header (latest change + comparison to previous)
- **Cash Flow** (income bar + spending bar + net savings line) — spending bar shown for ANY month where a previous snapshot exists (`key in prev_nw`). First snapshot never gets a spending bar (no prev). `spent_per_month: list[float | None]` (None = first snapshot, no previous); formula: `spent(N) = prev_nw(N-1) + income(N) - nw(N)`; stats from confirmed months only; filter: `_cashflow_filter` (default "All")
- **Account Tracker** (line chart, dynamic) — ≥1 snapshot; accounts shown as solid lines with `_tracker_vars: dict[str, BooleanVar]`; income sources shown as dashed lines with `_income_tracker_vars: dict[int, BooleanVar]` and `_income_names: dict[int, str]`; income data loaded via `get_snapshot_income(year, month)` for each snapshot into `_income_snap_data`
- **Time filter buttons** per chart: `1M → 3M → 6M → 1Y → YTD → All` (shortest first). Independent state: `_nw_filter`, `_change_filter`, `_tracker_filter`, `_cashflow_filter`. Clicking a filter calls `self.refresh()`. `_filter_snaps(snaps, key)` handles the cutoff logic.
- **Activity Heatmap** (chart 5) — ≥2 snapshots; year × 12-month grid of rounded rect cells; green = positive change (intensity scales with magnitude), red = negative; empty months show `#0d1520` cell with `·`; value shown as `+1.2k`/`-0.5k` inside each cell. `mpatches.FancyBboxPatch` with `boxstyle="round,pad=0.08"`. Figure height dynamic: `max(1.2, 0.55×n_years + 0.7)`. Canvas height = `int(fig_h×100) + 40`. Footer row: legend (Less/More squares) + recorded-count label.
- **Category Breakdown** (chart 6) — requires ≥1 fixed expense; reads `get_expenses_by_category()` from DB; renders one row per category: name + EUR amount + % + horizontal progress bar (`QFrame` bg `#1a2e45`, inner `QFrame` width proportional to pct of 560px). Colors per category: Housing `#00b4d8`, Investing `#A78BFA`, Subscriptions `#F59E0B`, Utilities `#10B981`, Health & Fitness `#F97316`, Other `#6b8fa8`.
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
- **Monochrome Unicode icons** in nav labels (no emoji): "⊞  Dashboard", "◷  Monthly Snapshot", "¤  Budget", "◈  Portfolio", "∿  Analytics", "✎  Notes", "?  Help", "⚙  Settings". Exit stays as-is. All buttons keep `anchor="w"`.

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
│   ├── charts.py            — Analytics tab: Net Worth, Monthly Change, Cash Flow, Account Tracker, Activity Heatmap, Category Breakdown
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
- `get_all_expenses()` → list of Row objects (ordered by day_of_month, name); SELECT includes `id, name, amount, day_of_month, category`
- `add_expense(name, amount, day_of_month, category="Other")` — includes category in INSERT
- `update_expense(expense_id, name, amount, day_of_month, category="Other")` — includes category in UPDATE
- `get_expenses_by_category()` → dict[str, float] — `{category: total_amount}`, ordered by total DESC; only categories with expenses
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
- `update_snapshot_portfolio(year, month, portfolio_eur)` → UPDATE snapshots SET portfolio_eur = ? for that month
- `get_all_snapshots()` includes `portfolio_eur` (float, defaults to 0.0) in every returned dict
- DB migrations in `init_db()` handle all schema additions for existing databases
- `snapshots` table has `portfolio_eur REAL DEFAULT 0.0` column (added via safe ALTER TABLE migration)

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
- Dashboard spacing: `_estimation_container` and `_prediction_container` are NOT pre-packed in `_build()`; each render method packs/unpacks them dynamically. `_prediction_container` packs `before=self._annual_divider`; `_estimation_container` packs `before=_annual_divider` (comes first in layout order).
- Sidebar: Exit button anchored to very bottom via `fill="both", expand=True` spacer; `text_color="#FF4444"`; sidebar has 3 groups (Top/Middle/Bottom) separated by 2 dividers
- `get_all_accounts()` in db.py returns all accounts ever saved, ordered by insertion (`ORDER BY id`)
- `_build_snapshot_dict`: `total` = sum of ALL account balances (no investment distinction)
- Income active_months: NULL or empty string = active every month; otherwise comma-separated month numbers
- Daily Spending Allowance is in Settings tab only (not Budget tab)
- Backup/Restore is in Settings tab only (not Help tab)
- **Always update `views/help.py`** when adding or modifying features — the Help tab is the user-facing documentation
- Help tab must be generic — no personal references (no specific account names, specific income sources, or specific locations)
