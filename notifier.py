#!/usr/bin/env python3
"""
Money Tracker — Snapshot Reminder Notifier
Run daily at 17:00 via launchd (com.moneytracker.notifier).

Checks whether an email reminder should be sent for the current month's
snapshot, and sends it via the Resend API if all conditions are met.
"""
import base64
import calendar
import logging
import sqlite3
import sys
from datetime import date
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_DB_PATH     = _SCRIPT_DIR / "database" / "tracker.db"
_LOG_DIR     = Path.home() / "Library" / "Logs" / "MoneyTracker"
_LOG_FILE    = _LOG_DIR / "notifier.log"

# ── Logging ────────────────────────────────────────────────────────────────────
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_setting(key: str) -> str:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else ""


def _set_setting(key: str, value: str):
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def _snapshot_exists(year: int, month: int) -> bool:
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM snapshots WHERE year=? AND month=?", (year, month)
        ).fetchone()
        return row is not None


def _get_latest_snapshot_label() -> str:
    """Return 'Month YYYY' for the most recent snapshot, or 'none'."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT year, month FROM snapshots ORDER BY year DESC, month DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "none"
        return f"{calendar.month_name[row['month']]} {row['year']}"


# ── Email via Resend ───────────────────────────────────────────────────────────

def _send_email(api_key: str, recipient: str,
                month_name: str, days_left: int, prev_label: str):
    import resend  # local import so launchd errors are caught cleanly
    resend.api_key = api_key
    resend.Emails.send({
        "from": "Money Tracker <onboarding@resend.dev>",
        "to": [recipient],
        "subject": "Money Tracker \u2014 Snapshot Reminder",
        "html": (
            "<p>Hi,</p>"
            f"<p><b>{month_name}</b> is ending in <b>{days_left} day{'s' if days_left != 1 else ''}</b>.<br>"
            f"Your last recorded snapshot was <b>{prev_label}</b>.</p>"
            f"<p>Don\u2019t forget to enter your {month_name} snapshot in Money Tracker!</p>"
            "<p>\u2014 Money Tracker</p>"
        ),
    })


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not _DB_PATH.exists():
        log.warning("Database not found at %s — skipping.", _DB_PATH)
        return

    # 1. Check notifications enabled
    if _get_setting("notif_enabled") != "1":
        log.info("Notifications disabled — nothing to do.")
        return

    # 2. Check date condition
    today = date.today()
    try:
        email_days = int(_get_setting("email_days") or "3")
    except ValueError:
        email_days = 3

    last_day  = calendar.monthrange(today.year, today.month)[1]
    days_left = last_day - today.day

    if days_left > email_days:
        log.info(
            "Not yet within reminder window (%d days left, threshold %d).",
            days_left, email_days,
        )
        return

    # 3. Check if already sent this month
    period_key = today.strftime("%Y-%m")
    if _get_setting("last_notification_sent") == period_key:
        log.info("Email already sent for %s — skipping.", period_key)
        return

    # 4. Check if snapshot already saved
    if _snapshot_exists(today.year, today.month):
        log.info("Snapshot already saved for %s/%s — no reminder needed.",
                 today.year, today.month)
        return

    # 5. Gather Resend settings
    recipient   = _get_setting("notif_email").strip()
    key_encoded = _get_setting("resend_api_key").strip()

    if not recipient or not key_encoded:
        log.warning("Incomplete notification settings (email or API key missing).")
        return

    try:
        api_key = base64.b64decode(key_encoded.encode()).decode()
    except Exception:
        log.warning("Failed to decode Resend API key.")
        return

    month_name = calendar.month_name[today.month]
    prev_label = _get_latest_snapshot_label()

    # 6. Send email
    try:
        _send_email(api_key, recipient, month_name, days_left, prev_label)
        _set_setting("last_notification_sent", period_key)
        log.info("Reminder email sent to %s for %s.", recipient, period_key)
    except Exception as exc:
        log.error("Failed to send email: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
