import base64
import shutil
import threading
from datetime import date
from tkinter import filedialog

import customtkinter as ctk

from database.db import DB_PATH, get_setting, set_setting, reset_all_data
from utils import center_on_parent, lock_scroll, unlock_scroll, open_dialog

# Premium dark theme palette
_BG_CARD  = "#161f2e"
_ACCENT   = "#00b4d8"
_TEXT_PRI = "#e6edf3"
_TEXT_SEC = "#8b949e"
_BORDER   = "#2a3a52"
_BG_ELEM  = "#21262d"
_GREEN    = "#3fb950"
_RED      = "#f85149"
_F        = "Helvetica Neue"


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._editing_allowance  = False
        self._backup_status:  ctk.CTkLabel | None = None
        self._restore_status: ctk.CTkLabel | None = None
        self._allowance_row:  ctk.CTkFrame | None = None
        # Notification section state
        self._notif_enabled_var:  ctk.BooleanVar | None = None
        self._notif_email_var:    ctk.StringVar  | None = None
        self._resend_key_var:     ctk.StringVar  | None = None
        self._email_days_var:     ctk.StringVar  | None = None
        self._banner_days_var:    ctk.StringVar  | None = None
        self._notif_save_status:  ctk.CTkLabel   | None = None
        self._build()

    def refresh(self):
        pass  # Static layout; allowance row re-reads DB when edited

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Settings",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self, text="Configure spending allowance, appearance, and data management.",
            text_color=_TEXT_SEC,
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # ── Daily Spending Allowance ──────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Daily Spending Allowance",
            font=ctk.CTkFont(family=_F, size=17, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(14, 6))

        allowance_card = ctk.CTkFrame(
            self, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        allowance_card.pack(fill="x", padx=24, pady=(0, 8))
        allowance_inner = ctk.CTkFrame(allowance_card, fg_color="transparent")
        allowance_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            allowance_inner,
            text="Your estimated budget per day for variable spending (food, transport, leisure, etc.). "
                 "Used in mid-month estimation calculations.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self._allowance_row = ctk.CTkFrame(allowance_inner, fg_color="transparent")
        self._allowance_row.pack(anchor="w")
        self._refresh_allowance_row()

        # ── Appearance ────────────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Appearance",
            font=ctk.CTkFont(family=_F, size=17, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(14, 6))

        app_card = ctk.CTkFrame(
            self, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        app_card.pack(fill="x", padx=24, pady=(0, 8))
        app_inner = ctk.CTkFrame(app_card, fg_color="transparent")
        app_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            app_inner, text="Color theme:",
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_PRI,
        ).pack(anchor="w", pady=(0, 8))

        current_mode = get_setting("appearance_mode") or "System"
        mode_var = ctk.StringVar(value=current_mode)
        ctk.CTkSegmentedButton(
            app_inner,
            values=["System", "Light", "Dark"],
            variable=mode_var,
            command=self._on_appearance_change,
            width=240,
        ).pack(anchor="w")

        self._appearance_var = mode_var

        # ── Notifications ─────────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Notifications",
            font=ctk.CTkFont(family=_F, size=17, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(14, 6))
        ctk.CTkLabel(
            self,
            text="Get reminded to enter your monthly snapshot via email and an in-app banner.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 8))

        notif_card = ctk.CTkFrame(
            self, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        notif_card.pack(fill="x", padx=24, pady=(0, 8))
        notif_inner = ctk.CTkFrame(notif_card, fg_color="transparent")
        notif_inner.pack(fill="x", padx=16, pady=14)

        # ── Enable toggle ─────────────────────────────────────────────────────
        self._notif_enabled_var = ctk.BooleanVar(value=get_setting("notif_enabled") == "1")
        toggle_row = ctk.CTkFrame(notif_inner, fg_color="transparent")
        toggle_row.pack(anchor="w", fill="x", pady=(0, 10))
        ctk.CTkLabel(
            toggle_row, text="Enable email notifications",
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_PRI,
        ).pack(side="left")
        ctk.CTkSwitch(
            toggle_row, text="", variable=self._notif_enabled_var,
            width=44, progress_color=_ACCENT,
            command=self._on_notif_toggle,
        ).pack(side="left", padx=(12, 0))

        # ── Email field ───────────────────────────────────────────────────────
        email_row = ctk.CTkFrame(notif_inner, fg_color="transparent")
        email_row.pack(anchor="w", fill="x", pady=(0, 6))
        ctk.CTkLabel(
            email_row, text="Send to email:", width=140,
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_SEC, anchor="w",
        ).pack(side="left")
        self._notif_email_var = ctk.StringVar(value=get_setting("notif_email") or "")
        ctk.CTkEntry(
            email_row, textvariable=self._notif_email_var, width=280,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
            placeholder_text="you@example.com",
        ).pack(side="left")

        # ── Resend API Key ────────────────────────────────────────────────────
        key_row = ctk.CTkFrame(notif_inner, fg_color="transparent")
        key_row.pack(anchor="w", fill="x", pady=(0, 6))
        ctk.CTkLabel(
            key_row, text="Resend API key:", width=140,
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_SEC, anchor="w",
        ).pack(side="left")
        _stored_key = get_setting("resend_api_key") or ""
        _decoded_key = ""
        if _stored_key:
            try:
                _decoded_key = base64.b64decode(_stored_key.encode()).decode()
            except Exception:
                _decoded_key = ""
        self._resend_key_var = ctk.StringVar(value=_decoded_key)
        ctk.CTkEntry(
            key_row, textvariable=self._resend_key_var, width=280,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
            placeholder_text="re_...", show="•",
        ).pack(side="left")

        # ── Days before end of month ──────────────────────────────────────────
        days_row = ctk.CTkFrame(notif_inner, fg_color="transparent")
        days_row.pack(anchor="w", fill="x", pady=(0, 6))
        ctk.CTkLabel(
            days_row, text="Email reminder (days before end of month):", width=300,
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_SEC, anchor="w",
        ).pack(side="left")
        self._email_days_var = ctk.StringVar(value=get_setting("email_days") or "3")
        ctk.CTkEntry(
            days_row, textvariable=self._email_days_var, width=60,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
        ).pack(side="left")

        banner_days_row = ctk.CTkFrame(notif_inner, fg_color="transparent")
        banner_days_row.pack(anchor="w", fill="x", pady=(0, 10))
        ctk.CTkLabel(
            banner_days_row, text="In-app banner (days before end of month):", width=300,
            font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_SEC, anchor="w",
        ).pack(side="left")
        self._banner_days_var = ctk.StringVar(value=get_setting("banner_days") or "7")
        ctk.CTkEntry(
            banner_days_row, textvariable=self._banner_days_var, width=60,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
        ).pack(side="left")

        # ── Save + Test row ───────────────────────────────────────────────────
        notif_btn_row = ctk.CTkFrame(notif_inner, fg_color="transparent")
        notif_btn_row.pack(anchor="w", fill="x", pady=(4, 0))
        ctk.CTkButton(
            notif_btn_row, text="Save", width=80,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            font=ctk.CTkFont(family=_F, size=13),
            command=self._save_notif_settings,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            notif_btn_row, text="Send test email", width=130,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            font=ctk.CTkFont(family=_F, size=13),
            command=self._send_test_email,
        ).pack(side="left", padx=(0, 10))
        self._notif_save_status = ctk.CTkLabel(
            notif_btn_row, text="", font=ctk.CTkFont(family=_F, size=12),
        )
        self._notif_save_status.pack(side="left")

        # ── Backup & Restore ──────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Data Management",
            font=ctk.CTkFont(family=_F, size=17, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(14, 6))

        ctk.CTkLabel(
            self,
            text="Back up your tracker database or restore from a previous backup. "
                 "The database contains all snapshots, expenses, income, and notes.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        backup_row = ctk.CTkFrame(self, fg_color="transparent")
        backup_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkButton(
            backup_row, text="Backup Data", width=140,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            command=self._backup,
        ).pack(side="left", padx=(0, 12))
        self._backup_status = ctk.CTkLabel(
            backup_row, text="", font=ctk.CTkFont(family=_F, size=12),
        )
        self._backup_status.pack(side="left")

        restore_row = ctk.CTkFrame(self, fg_color="transparent")
        restore_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkButton(
            restore_row, text="Restore Data", width=140,
            fg_color=_BG_ELEM, hover_color="#3d1a1a",
            text_color=_RED, corner_radius=8,
            command=self._restore,
        ).pack(side="left", padx=(0, 12))
        self._restore_status = ctk.CTkLabel(
            restore_row, text="", font=ctk.CTkFont(family=_F, size=12),
        )
        self._restore_status.pack(side="left")

        ctk.CTkLabel(
            self,
            text="Restore replaces your current database with the backup and closes the app. "
                 "Reopen the app to see the restored data.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(4, 0))

        # ── Reset All Data ────────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Reset All Data",
            font=ctk.CTkFont(family=_F, size=17, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(14, 6))

        ctk.CTkLabel(
            self,
            text="Permanently delete all snapshots, accounts, expenses, income, and notes. "
                 "Settings are reset to defaults. The app will close after reset.",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        reset_row = ctk.CTkFrame(self, fg_color="transparent")
        reset_row.pack(anchor="w", padx=24, pady=(0, 32))
        ctk.CTkButton(
            reset_row, text="Reset All Data", width=160,
            fg_color=_BG_ELEM, hover_color="#3d1a1a",
            text_color=_RED, corner_radius=8,
            command=self._reset_data,
        ).pack(side="left")

    # ── Daily Spending Allowance ───────────────────────────────────────────────

    def _refresh_allowance_row(self):
        if self._allowance_row is None:
            return
        for w in self._allowance_row.winfo_children():
            w.destroy()
        daily = float(get_setting("daily_buffer") or "20.0")
        if self._editing_allowance:
            allowance_var = ctk.StringVar(value=f"{daily:.2f}")
            ctk.CTkEntry(
                self._allowance_row, textvariable=allowance_var, width=100,
                fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                self._allowance_row, text="EUR / day",
                font=ctk.CTkFont(family=_F, size=13), text_color=_TEXT_SEC,
            ).pack(side="left", padx=(0, 14))
            ctk.CTkButton(
                self._allowance_row, text="Save", width=72,
                fg_color=_ACCENT, hover_color="#0096b4",
                text_color="white", corner_radius=8,
                command=lambda v=allowance_var: self._save_allowance(v),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                self._allowance_row, text="Cancel", width=72,
                fg_color=_BG_ELEM, hover_color="#3d4d63",
                text_color=_TEXT_PRI, corner_radius=8,
                command=self._cancel_allowance_edit,
            ).pack(side="left")
        else:
            from utils import fmt_eur
            ctk.CTkLabel(
                self._allowance_row,
                text=f"{fmt_eur(daily)} / day",
                font=ctk.CTkFont(family=_F, size=20, weight="bold"),
                text_color=_TEXT_PRI,
            ).pack(side="left", padx=(0, 14))
            ctk.CTkButton(
                self._allowance_row, text="Edit", width=64,
                fg_color=_BG_ELEM, hover_color="#3d4d63",
                text_color=_TEXT_PRI, corner_radius=8,
                command=self._start_allowance_edit,
            ).pack(side="left")

    def _start_allowance_edit(self):
        self._editing_allowance = True
        self._refresh_allowance_row()

    def _save_allowance(self, var: ctk.StringVar):
        try:
            value = float(var.get().strip())
            if value <= 0:
                raise ValueError
        except ValueError:
            return
        set_setting("daily_buffer", str(value))
        self._editing_allowance = False
        self._refresh_allowance_row()

    def _cancel_allowance_edit(self):
        self._editing_allowance = False
        self._refresh_allowance_row()

    # ── Appearance ────────────────────────────────────────────────────────────

    def _on_appearance_change(self, value: str):
        set_setting("appearance_mode", value)
        import darkdetect
        if value == "System":
            ctk.set_appearance_mode("dark" if darkdetect.isDark() else "light")
        else:
            ctk.set_appearance_mode(value.lower())

    # ── Backup & Restore ──────────────────────────────────────────────────────

    def _backup(self):
        today        = date.today()
        default_name = f"money-tracker-backup-{today.strftime('%Y-%m-%d')}.db"
        filepath = filedialog.asksaveasfilename(
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
            initialfile=default_name,
        )
        if not filepath:
            return
        shutil.copy2(DB_PATH, filepath)
        if self._backup_status:
            self._backup_status.configure(text="Backup saved!", text_color=_GREEN)
            self.after(4000, lambda: self._backup_status.configure(text="") if self._backup_status else None)

    def _restore(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
        )
        if not filepath:
            return
        result = [False]
        dialog = open_dialog(self, 480, 180)
        dialog.title("Confirm Restore")
        ctk.CTkLabel(
            dialog,
            text=(
                "Restore data from the selected backup?\n\n"
                "This will replace ALL current data. The app will close — "
                "reopen it to see the restored data."
            ),
            wraplength=440, justify="left", font=ctk.CTkFont(family=_F, size=13),
            text_color=_TEXT_PRI,
        ).pack(padx=20, pady=(20, 16))
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def on_confirm():
            result[0] = True
            dialog.destroy()

        ctk.CTkButton(
            btn_row, text="Restore & Close", width=140,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            command=on_confirm,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=dialog.destroy,
        ).pack(side="left")
        dialog.wait_window()
        unlock_scroll()
        if result[0]:
            shutil.copy2(filepath, DB_PATH)
            self.winfo_toplevel().destroy()

    # ── Reset All Data ────────────────────────────────────────────────────────

    def _reset_data(self):
        result = [False]
        dialog = open_dialog(self, 500, 220)
        dialog.title("Reset All Data")

        ctk.CTkLabel(
            dialog,
            text="This will permanently delete ALL your data:\nsnapshots, accounts, expenses, income, and notes.\n\nType DELETE to confirm:",
            wraplength=460, justify="left", font=ctk.CTkFont(family=_F, size=13),
            text_color=_TEXT_PRI,
        ).pack(padx=20, pady=(20, 8))

        confirm_var = ctk.StringVar()
        entry = ctk.CTkEntry(
            dialog, textvariable=confirm_var, width=160,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
        )
        entry.pack(padx=20, pady=(0, 12))
        entry.focus_set()

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        reset_btn = ctk.CTkButton(
            btn_row, text="Reset All Data", width=140,
            fg_color=_BG_ELEM, hover_color="#3d1a1a",
            text_color=_RED, corner_radius=8,
            state="disabled",
            command=lambda: [result.__setitem__(0, True), dialog.destroy()],
        )
        reset_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=dialog.destroy,
        ).pack(side="left")

        def on_change(*_):
            reset_btn.configure(state="normal" if confirm_var.get() == "DELETE" else "disabled")

        confirm_var.trace_add("write", on_change)
        dialog.wait_window()
        unlock_scroll()

        if result[0]:
            reset_all_data()
            self.winfo_toplevel().destroy()

    # ── Notifications ─────────────────────────────────────────────────────────

    def _on_notif_toggle(self):
        set_setting("notif_enabled", "1" if self._notif_enabled_var.get() else "0")

    def _save_notif_settings(self):
        try:
            ed = int(self._email_days_var.get().strip())
            bd = int(self._banner_days_var.get().strip())
            if not (1 <= ed <= 15) or not (1 <= bd <= 15):
                raise ValueError
        except ValueError:
            if self._notif_save_status:
                self._notif_save_status.configure(
                    text="Days must be between 1 and 15.", text_color=_RED,
                )
            return

        set_setting("notif_email", self._notif_email_var.get().strip())
        set_setting("email_days",  str(ed))
        set_setting("banner_days", str(bd))

        key = self._resend_key_var.get().strip()
        encoded_key = base64.b64encode(key.encode()).decode() if key else ""
        set_setting("resend_api_key", encoded_key)

        if self._notif_save_status:
            self._notif_save_status.configure(text="Saved!", text_color=_GREEN)
            self.after(3000, lambda: self._notif_save_status.configure(text="")
                       if self._notif_save_status else None)

    def _send_test_email(self):
        if self._notif_save_status:
            self._notif_save_status.configure(text="Sending…", text_color=_TEXT_SEC)

        def do_send():
            try:
                import resend  # noqa: PLC0415
                recipient = self._notif_email_var.get().strip()
                key       = self._resend_key_var.get().strip()

                if not recipient or not key:
                    raise ValueError("Enter your email address and Resend API key first.")

                resend.api_key = key
                resend.Emails.send({
                    "from": "Money Tracker <onboarding@resend.dev>",
                    "to": [recipient],
                    "subject": "Money Tracker — Test Email",
                    "html": (
                        "<p>This is a test email from <b>Money Tracker</b>.</p>"
                        "<p>If you received this, your notification settings are working correctly.</p>"
                        "<p>— Money Tracker</p>"
                    ),
                })

                self.after(0, lambda: self._notif_save_status.configure(
                    text="Test email sent!", text_color=_GREEN) if self._notif_save_status else None)
                self.after(4000, lambda: self._notif_save_status.configure(text="")
                           if self._notif_save_status else None)
            except Exception as exc:
                err = str(exc)[:80]
                self.after(0, lambda e=err: self._notif_save_status.configure(
                    text=f"Error: {e}", text_color=_RED) if self._notif_save_status else None)

        threading.Thread(target=do_send, daemon=True).start()

    # ── Helper ────────────────────────────────────────────────────────────────

    def _divider(self):
        ctk.CTkFrame(self, height=1, fg_color=_BORDER).pack(
            fill="x", padx=24, pady=(16, 0)
        )
