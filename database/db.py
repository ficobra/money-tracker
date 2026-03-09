import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tracker.db"

_DEFAULT_EXPENSES: list[tuple[int, str, float]] = [
    # (day_of_month, name, amount)
    (1,  "Uniqa Versicherung", 5.60),
    (1,  "UK Miete",           761.00),
    (1,  "3D Fitness Club",    23.90),
    (2,  "YouTube Premium",    16.99),
    (7,  "StromNetz",          16.00),
    (11, "ORF Beitrag",        20.00),
    (13, "Netflix (own)",      8.99),
    (15, "T-Mobile",           47.94),
    (15, "MaxEnergy",          20.00),
    (17, "Spotify",            12.99),
    (21, "Netflix (mom)",      8.99),
    (22, "Apple iCloud",       2.99),
    (25, "Claude",             21.60),
    (31, "Kontoführung",       11.32),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL UNIQUE,
                is_investment INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                year       INTEGER NOT NULL,
                month      INTEGER NOT NULL,
                created_at TEXT    DEFAULT (datetime('now')),
                UNIQUE(year, month)
            );

            CREATE TABLE IF NOT EXISTS snapshot_balances (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                account_id      INTEGER NOT NULL REFERENCES accounts(id)  ON DELETE CASCADE,
                balance         REAL    NOT NULL,
                invested_amount REAL
            );

            CREATE TABLE IF NOT EXISTS fixed_expenses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                amount       REAL    NOT NULL,
                day_of_month INTEGER NOT NULL CHECK(day_of_month BETWEEN 1 AND 31)
            );

            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT NOT NULL,
                amount     REAL NOT NULL DEFAULT 0.0,
                direction  TEXT NOT NULL DEFAULT 'they_owe',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recurring_income (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                amount       REAL    NOT NULL,
                day_of_month INTEGER NOT NULL DEFAULT 0,
                income_type  TEXT    NOT NULL DEFAULT 'fixed',
                active_months TEXT   DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshot_income (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                year          INTEGER NOT NULL,
                month         INTEGER NOT NULL,
                income_id     INTEGER NOT NULL REFERENCES recurring_income(id) ON DELETE CASCADE,
                actual_amount REAL    NOT NULL,
                UNIQUE(year, month, income_id)
            );

            CREATE TABLE IF NOT EXISTS extra_income (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                year        INTEGER NOT NULL,
                month       INTEGER NOT NULL,
                income_id   INTEGER NOT NULL REFERENCES recurring_income(id) ON DELETE CASCADE,
                description TEXT    NOT NULL DEFAULT '',
                amount      REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker        TEXT    NOT NULL UNIQUE,
                shares        REAL    NOT NULL,
                avg_buy_price REAL    NOT NULL,
                currency      TEXT    NOT NULL DEFAULT 'USD',
                notes         TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS portfolio_cache (
                ticker         TEXT PRIMARY KEY,
                price          REAL NOT NULL,
                currency       TEXT NOT NULL DEFAULT 'USD',
                day_change     REAL,
                day_change_pct REAL,
                name           TEXT,
                updated_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS portfolio_reminders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_date TEXT    NOT NULL,
                is_enabled    INTEGER NOT NULL DEFAULT 1
            );

            INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_buffer', '20.0');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('my_notes', '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('appearance_mode', 'System');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('notif_enabled', '0');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('notif_email', '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('resend_api_key', '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('email_days', '3');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('banner_days', '7');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('last_notification_sent', '');
        """)
        # Migrate notes table for existing databases (add columns if missing)
        note_cols = {row[1] for row in conn.execute("PRAGMA table_info(notes)").fetchall()}
        if "amount" not in note_cols:
            conn.execute("ALTER TABLE notes ADD COLUMN amount REAL NOT NULL DEFAULT 0.0")
        if "direction" not in note_cols:
            conn.execute("ALTER TABLE notes ADD COLUMN direction TEXT NOT NULL DEFAULT 'they_owe'")

        # Migrate accounts table for investment flag
        acc_cols = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
        if "is_investment" not in acc_cols:
            conn.execute("ALTER TABLE accounts ADD COLUMN is_investment INTEGER NOT NULL DEFAULT 0")

        # Migrate snapshot_balances table for invested_amount
        sb_cols = {row[1] for row in conn.execute("PRAGMA table_info(snapshot_balances)").fetchall()}
        if "invested_amount" not in sb_cols:
            conn.execute("ALTER TABLE snapshot_balances ADD COLUMN invested_amount REAL")

        # Migrate recurring_income for income_type and active_months
        ri_cols = {row[1] for row in conn.execute("PRAGMA table_info(recurring_income)").fetchall()}
        if "income_type" not in ri_cols:
            conn.execute("ALTER TABLE recurring_income ADD COLUMN income_type TEXT NOT NULL DEFAULT 'fixed'")
        if "active_months" not in ri_cols:
            conn.execute("ALTER TABLE recurring_income ADD COLUMN active_months TEXT DEFAULT NULL")

        # Migrate portfolio_cache for price_eur
        pc_cols = {row[1] for row in conn.execute("PRAGMA table_info(portfolio_cache)").fetchall()}
        if "price_eur" not in pc_cols:
            conn.execute("ALTER TABLE portfolio_cache ADD COLUMN price_eur REAL")

        # Seed default expenses on first run
        count = conn.execute("SELECT COUNT(*) FROM fixed_expenses").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO fixed_expenses (name, amount, day_of_month) VALUES (?, ?, ?)",
                [(name, amount, day) for day, name, amount in _DEFAULT_EXPENSES],
            )


def get_snapshot(year: int, month: int) -> dict[str, float] | None:
    """Return {account_name: balance} for the given month, or None if not saved."""
    with get_connection() as conn:
        snap = conn.execute(
            "SELECT id FROM snapshots WHERE year=? AND month=?", (year, month)
        ).fetchone()
        if not snap:
            return None
        rows = conn.execute(
            """SELECT a.name, sb.balance
               FROM snapshot_balances sb
               JOIN accounts a ON a.id = sb.account_id
               WHERE sb.snapshot_id = ?
               ORDER BY a.name""",
            (snap["id"],),
        ).fetchall()
        return {r["name"]: r["balance"] for r in rows}


def save_snapshot(
    year: int, month: int, balances: dict[str, float],
    invested_amounts: dict[str, float] | None = None,
) -> int:
    """Upsert a snapshot. Returns the total number of snapshots after saving."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO snapshots (year, month) VALUES (?, ?) ON CONFLICT(year, month) DO NOTHING",
            (year, month),
        )
        snap_id = conn.execute(
            "SELECT id FROM snapshots WHERE year=? AND month=?", (year, month)
        ).fetchone()["id"]

        conn.execute("DELETE FROM snapshot_balances WHERE snapshot_id=?", (snap_id,))

        for name, balance in balances.items():
            conn.execute("INSERT OR IGNORE INTO accounts (name) VALUES (?)", (name,))
            acc_id = conn.execute(
                "SELECT id FROM accounts WHERE name=?", (name,)
            ).fetchone()["id"]
            invested = invested_amounts.get(name) if invested_amounts else None
            conn.execute(
                "INSERT INTO snapshot_balances"
                " (snapshot_id, account_id, balance, invested_amount) VALUES (?, ?, ?, ?)",
                (snap_id, acc_id, balance, invested),
            )

        return conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]


def _build_snapshot_dict(snap: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    """Helper: build a full snapshot dict including balances and total net worth."""
    rows = conn.execute(
        """SELECT a.name, sb.balance
           FROM snapshot_balances sb
           JOIN accounts a ON a.id = sb.account_id
           WHERE sb.snapshot_id = ?
           ORDER BY a.name""",
        (snap["id"],),
    ).fetchall()
    balances = {r["name"]: r["balance"] for r in rows}
    return {
        "id":       snap["id"],
        "year":     snap["year"],
        "month":    snap["month"],
        "balances": balances,
        "total":    sum(r["balance"] for r in rows),
    }


def get_all_snapshots() -> list[dict]:
    """Return every snapshot in chronological order (oldest first) with balances and total."""
    with get_connection() as conn:
        snaps = conn.execute(
            "SELECT id, year, month FROM snapshots ORDER BY year ASC, month ASC"
        ).fetchall()
        return [_build_snapshot_dict(s, conn) for s in snaps]


def get_latest_snapshots(limit: int = 2) -> list[dict]:
    """Return the N most recent snapshots (newest first) with balances and total."""
    with get_connection() as conn:
        snaps = conn.execute(
            "SELECT id, year, month FROM snapshots ORDER BY year DESC, month DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_build_snapshot_dict(s, conn) for s in snaps]


def count_snapshots() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]


def get_all_accounts() -> list[str]:
    """Return all account names ever saved, in insertion order."""
    with get_connection() as conn:
        rows = conn.execute("SELECT name FROM accounts ORDER BY id").fetchall()
        return [r["name"] for r in rows]


def get_all_accounts_with_flags() -> list[dict]:
    """Return all accounts with their is_investment flag, in insertion order."""
    with get_connection() as conn:
        rows = conn.execute("SELECT name, is_investment FROM accounts ORDER BY id").fetchall()
        return [{"name": r["name"], "is_investment": bool(r["is_investment"])} for r in rows]


def set_account_investment(name: str, is_investment: bool):
    """Set the investment flag for an account by name."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE accounts SET is_investment=? WHERE name=?",
            (1 if is_investment else 0, name),
        )


def get_snapshot_invested(year: int, month: int) -> dict[str, float]:
    """Return {account_name: invested_amount} for investment accounts in the given snapshot."""
    with get_connection() as conn:
        snap = conn.execute(
            "SELECT id FROM snapshots WHERE year=? AND month=?", (year, month)
        ).fetchone()
        if not snap:
            return {}
        rows = conn.execute(
            """SELECT a.name, sb.invested_amount
               FROM snapshot_balances sb
               JOIN accounts a ON a.id = sb.account_id
               WHERE sb.snapshot_id = ? AND sb.invested_amount IS NOT NULL
               ORDER BY a.name""",
            (snap["id"],),
        ).fetchall()
        return {r["name"]: r["invested_amount"] for r in rows}


def delete_snapshot(year: int, month: int):
    """Delete a snapshot and all its balances (CASCADE handles balances)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM snapshots WHERE year=? AND month=?", (year, month))


def get_setting(key: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ── Fixed expenses ─────────────────────────────────────────────────────────────

def get_all_expenses() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, amount, day_of_month"
            " FROM fixed_expenses ORDER BY day_of_month, name"
        ).fetchall()


def add_expense(name: str, amount: float, day_of_month: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO fixed_expenses (name, amount, day_of_month) VALUES (?, ?, ?)",
            (name, amount, day_of_month),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_expense(expense_id: int, name: str, amount: float, day_of_month: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE fixed_expenses SET name=?, amount=?, day_of_month=? WHERE id=?",
            (name, amount, day_of_month, expense_id),
        )


def delete_expense(expense_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM fixed_expenses WHERE id=?", (expense_id,))


# ── Notes ──────────────────────────────────────────────────────────────────────

def get_all_notes() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, content, amount, direction, created_at"
            " FROM notes ORDER BY created_at DESC"
        ).fetchall()


def add_note(content: str, amount: float, direction: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO notes (content, amount, direction) VALUES (?, ?, ?)",
            (content, amount, direction),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_note(note_id: int, content: str, amount: float, direction: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE notes SET content=?, amount=?, direction=? WHERE id=?",
            (content, amount, direction, note_id),
        )


def delete_note(note_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM notes WHERE id=?", (note_id,))


# ── Recurring income ───────────────────────────────────────────────────────────

def get_all_income() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, amount, day_of_month, income_type, active_months"
            " FROM recurring_income ORDER BY name"
        ).fetchall()


def delete_income(income_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM recurring_income WHERE id=?", (income_id,))


def add_income(
    name: str,
    amount: float,
    day_of_month: int,
    income_type: str = "fixed",
    active_months: str | None = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO recurring_income (name, amount, day_of_month, income_type, active_months)"
            " VALUES (?, ?, ?, ?, ?)",
            (name, amount, day_of_month, income_type, active_months),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_income(
    income_id: int,
    name: str,
    amount: float,
    day_of_month: int,
    income_type: str = "fixed",
    active_months: str | None = None,
):
    with get_connection() as conn:
        conn.execute(
            "UPDATE recurring_income SET name=?, amount=?, day_of_month=?,"
            " income_type=?, active_months=? WHERE id=?",
            (name, amount, day_of_month, income_type, active_months, income_id),
        )


# ── Snapshot income (actual amounts received per month) ────────────────────────

def get_snapshot_income(year: int, month: int) -> dict[int, float]:
    """Return {income_id: actual_amount} for the given snapshot period."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT income_id, actual_amount FROM snapshot_income WHERE year=? AND month=?",
            (year, month),
        ).fetchall()
        return {r["income_id"]: r["actual_amount"] for r in rows}


def set_snapshot_income(year: int, month: int, income_id: int, actual_amount: float):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO snapshot_income (year, month, income_id, actual_amount) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(year, month, income_id) DO UPDATE SET actual_amount=excluded.actual_amount",
            (year, month, income_id, actual_amount),
        )


# ── Extra income (one-time per-snapshot additions) ─────────────────────────────

def get_extra_income(year: int, month: int) -> list[dict]:
    """Return all extra income entries for the given snapshot period."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, income_id, description, amount"
            " FROM extra_income WHERE year=? AND month=? ORDER BY id",
            (year, month),
        ).fetchall()
        return [dict(r) for r in rows]


def add_extra_income(
    year: int, month: int, income_id: int, description: str, amount: float
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO extra_income (year, month, income_id, description, amount)"
            " VALUES (?, ?, ?, ?, ?)",
            (year, month, income_id, description, amount),
        )
        return cur.lastrowid  # type: ignore[return-value]


def delete_extra_income(entry_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM extra_income WHERE id=?", (entry_id,))


def clear_extra_income(year: int, month: int, income_id: int):
    """Delete all extra income entries for one income source in one month."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM extra_income WHERE year=? AND month=? AND income_id=?",
            (year, month, income_id),
        )


# ── Earliest snapshot ──────────────────────────────────────────────────────────

def get_earliest_snapshot() -> tuple[int, int] | None:
    """Return (year, month) of the earliest saved snapshot, or None if no snapshots."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT year, month FROM snapshots ORDER BY year ASC, month ASC LIMIT 1"
        ).fetchone()
        return (row["year"], row["month"]) if row else None


# ── Reset ──────────────────────────────────────────────────────────────────────

# ── Portfolio positions ────────────────────────────────────────────────────────

def get_portfolio_positions() -> list[dict]:
    """Return all portfolio positions ordered by ticker."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, ticker, shares, avg_buy_price, currency, notes"
            " FROM portfolio_positions ORDER BY ticker"
        ).fetchall()
        return [dict(r) for r in rows]


def add_position(ticker: str, shares: float, avg_buy_price: float,
                 currency: str = "USD", notes: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO portfolio_positions (ticker, shares, avg_buy_price, currency, notes)"
            " VALUES (?, ?, ?, ?, ?)",
            (ticker.upper(), shares, avg_buy_price, currency, notes),
        )
        return cur.lastrowid  # type: ignore[return-value]


def update_position(position_id: int, ticker: str, shares: float,
                    avg_buy_price: float, currency: str, notes: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET ticker=?, shares=?, avg_buy_price=?,"
            " currency=?, notes=? WHERE id=?",
            (ticker.upper(), shares, avg_buy_price, currency, notes, position_id),
        )


def delete_position(position_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM portfolio_positions WHERE id=?", (position_id,))


def get_portfolio_cache() -> dict[str, dict]:
    """Return {ticker: {price, price_eur, currency, day_change, day_change_pct, name, updated_at}}."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker, price, price_eur, currency, day_change, day_change_pct, name, updated_at"
            " FROM portfolio_cache"
        ).fetchall()
        return {r["ticker"]: dict(r) for r in rows}


def upsert_portfolio_cache(ticker: str, price: float, currency: str,
                           day_change: float | None, day_change_pct: float | None,
                           name: str | None, price_eur: float | None = None):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_cache"
            " (ticker, price, price_eur, currency, day_change, day_change_pct, name, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))"
            " ON CONFLICT(ticker) DO UPDATE SET"
            " price=excluded.price, price_eur=excluded.price_eur, currency=excluded.currency,"
            " day_change=excluded.day_change, day_change_pct=excluded.day_change_pct,"
            " name=excluded.name, updated_at=datetime('now')",
            (ticker, price, price_eur, currency, day_change, day_change_pct, name),
        )


# ── Portfolio reminders ────────────────────────────────────────────────────────

def get_portfolio_reminder() -> dict | None:
    """Return {id, reminder_date, is_enabled} for the stored reminder, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, reminder_date, is_enabled FROM portfolio_reminders LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def upsert_portfolio_reminder(reminder_date: str, is_enabled: int):
    """Create or update the single portfolio reminder entry."""
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM portfolio_reminders LIMIT 1").fetchone()
        if existing:
            conn.execute(
                "UPDATE portfolio_reminders SET reminder_date=?, is_enabled=? WHERE id=?",
                (reminder_date, is_enabled, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO portfolio_reminders (reminder_date, is_enabled) VALUES (?, ?)",
                (reminder_date, is_enabled),
            )


# ── Reset ──────────────────────────────────────────────────────────────────────

def reset_all_data():
    """Delete all user data (snapshots, accounts, expenses, income, notes) and reset settings."""
    with get_connection() as conn:
        conn.executescript("""
            DELETE FROM extra_income;
            DELETE FROM snapshot_income;
            DELETE FROM snapshot_balances;
            DELETE FROM snapshots;
            DELETE FROM accounts;
            DELETE FROM fixed_expenses;
            DELETE FROM notes;
            DELETE FROM recurring_income;
            UPDATE settings SET value = '20.0' WHERE key = 'daily_buffer';
            UPDATE settings SET value = ''    WHERE key = 'my_notes';
        """)
