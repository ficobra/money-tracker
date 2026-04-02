#!/usr/bin/env python3
"""
Money Tracker — Snapshot Reminder Notifier (GitHub Actions)

Reads config from environment variables set by the workflow.
Exits 0 on success or skip; exits 1 on hard error.
Writes GitHub Actions step outputs when an email is sent.
"""
import calendar
import os
import sys
from datetime import date


def _write_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT if running in Actions."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"{key}={value}\n")


def main() -> None:
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    days_left = last_day - today.day

    # ── 1. Check date window ───────────────────────────────────────────────────
    try:
        notification_days = int(os.environ.get("NOTIFICATION_DAYS", "3"))
    except ValueError:
        notification_days = 3

    if days_left > notification_days:
        print(
            f"Skipping: {days_left} days left in month, "
            f"threshold is {notification_days}."
        )
        return

    # ── 2. Check already sent this month ──────────────────────────────────────
    period_key = today.strftime("%Y-%m")
    last_sent = os.environ.get("LAST_NOTIFICATION_SENT", "").strip()
    if last_sent == period_key:
        print(f"Skipping: notification already sent for {period_key}.")
        return

    # ── 3. Gather credentials ─────────────────────────────────────────────────
    api_key   = os.environ.get("RESEND_API_KEY", "").strip()
    recipient = os.environ.get("NOTIFICATION_EMAIL", "").strip()

    if not api_key:
        print("Error: RESEND_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)
    if not recipient:
        print("Error: NOTIFICATION_EMAIL is not set.", file=sys.stderr)
        sys.exit(1)

    # ── 4. Send email ──────────────────────────────────────────────────────────
    import resend  # noqa: PLC0415 — intentional late import

    resend.api_key = api_key

    month_name = calendar.month_name[today.month]
    day_word   = "day" if days_left == 1 else "days"

    resend.Emails.send({
        "from": "Money Tracker <onboarding@resend.dev>",
        "to":   [recipient],
        "subject": "Money Tracker \u2014 Snapshot Reminder",
        "html": (
            "<p>Hi,</p>"
            f"<p><b>{month_name}</b> is ending in "
            f"<b>{days_left} {day_word}</b>.</p>"
            f"<p>Don\u2019t forget to enter your {month_name} snapshot "
            "in Money Tracker!</p>"
            "<p>\u2014 Money Tracker</p>"
        ),
    })

    print(f"Reminder email sent to {recipient} for {period_key}.")

    # Signal the workflow so it can update LAST_NOTIFICATION_SENT
    _write_output("sent", "true")
    _write_output("sent_month", period_key)


if __name__ == "__main__":
    main()
