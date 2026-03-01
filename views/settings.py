import shutil
from datetime import date
from tkinter import filedialog

import customtkinter as ctk

from database.db import DB_PATH, get_setting, set_setting, reset_all_data
from utils import center_on_parent

_GREEN = "#2CC985"
_RED   = "#E74C3C"


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._editing_allowance  = False
        self._backup_status:  ctk.CTkLabel | None = None
        self._restore_status: ctk.CTkLabel | None = None
        self._allowance_row:  ctk.CTkFrame | None = None
        self._build()

    def refresh(self):
        pass  # Static layout; allowance row re-reads DB when edited

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self, text="Configure spending allowance, appearance, and data management.",
            text_color="gray",
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # ── Daily Spending Allowance ──────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Daily Spending Allowance",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(14, 6))

        allowance_card = ctk.CTkFrame(self)
        allowance_card.pack(fill="x", padx=24, pady=(0, 8))
        allowance_inner = ctk.CTkFrame(allowance_card, fg_color="transparent")
        allowance_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            allowance_inner,
            text="Your estimated budget per day for variable spending (food, transport, leisure, etc.). "
                 "Used in mid-month estimation calculations.",
            text_color="gray", font=ctk.CTkFont(size=12),
            wraplength=700, justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self._allowance_row = ctk.CTkFrame(allowance_inner, fg_color="transparent")
        self._allowance_row.pack(anchor="w")
        self._refresh_allowance_row()

        # ── Appearance ────────────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Appearance",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(14, 6))

        app_card = ctk.CTkFrame(self)
        app_card.pack(fill="x", padx=24, pady=(0, 8))
        app_inner = ctk.CTkFrame(app_card, fg_color="transparent")
        app_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            app_inner, text="Color theme:",
            font=ctk.CTkFont(size=13),
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

        # ── Backup & Restore ──────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Data Management",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(14, 6))

        ctk.CTkLabel(
            self,
            text="Back up your tracker database or restore from a previous backup. "
                 "The database contains all snapshots, expenses, income, and notes.",
            text_color="gray", font=ctk.CTkFont(size=13),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        backup_row = ctk.CTkFrame(self, fg_color="transparent")
        backup_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkButton(
            backup_row, text="Backup Data", width=140, command=self._backup,
        ).pack(side="left", padx=(0, 12))
        self._backup_status = ctk.CTkLabel(backup_row, text="", font=ctk.CTkFont(size=12))
        self._backup_status.pack(side="left")

        restore_row = ctk.CTkFrame(self, fg_color="transparent")
        restore_row.pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkButton(
            restore_row, text="Restore Data", width=140,
            fg_color="transparent", border_width=1,
            text_color=(_RED, _RED),
            hover_color=("gray85", "gray20"),
            command=self._restore,
        ).pack(side="left", padx=(0, 12))
        self._restore_status = ctk.CTkLabel(restore_row, text="", font=ctk.CTkFont(size=12))
        self._restore_status.pack(side="left")

        ctk.CTkLabel(
            self,
            text="Restore replaces your current database with the backup and closes the app. "
                 "Reopen the app to see the restored data.",
            text_color="gray", font=ctk.CTkFont(size=12),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(4, 0))

        # ── Reset All Data ────────────────────────────────────────────────────
        self._divider()
        ctk.CTkLabel(
            self, text="Reset All Data",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(14, 6))

        ctk.CTkLabel(
            self,
            text="Permanently delete all snapshots, accounts, expenses, income, and notes. "
                 "Settings are reset to defaults. The app will close after reset.",
            text_color="gray", font=ctk.CTkFont(size=13),
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        reset_row = ctk.CTkFrame(self, fg_color="transparent")
        reset_row.pack(anchor="w", padx=24, pady=(0, 32))
        ctk.CTkButton(
            reset_row, text="Reset All Data", width=160,
            fg_color="transparent", border_width=1,
            text_color=(_RED, _RED),
            hover_color=("gray85", "gray20"),
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
            ctk.CTkEntry(self._allowance_row, textvariable=allowance_var, width=100).pack(
                side="left", padx=(0, 6)
            )
            ctk.CTkLabel(self._allowance_row, text="EUR / day",
                         font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 14))
            ctk.CTkButton(
                self._allowance_row, text="Save", width=72,
                command=lambda v=allowance_var: self._save_allowance(v),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                self._allowance_row, text="Cancel", width=72,
                fg_color="transparent", border_width=1,
                command=self._cancel_allowance_edit,
            ).pack(side="left")
        else:
            from utils import fmt_eur
            ctk.CTkLabel(
                self._allowance_row,
                text=f"{fmt_eur(daily)} / day",
                font=ctk.CTkFont(size=20, weight="bold"),
            ).pack(side="left", padx=(0, 14))
            ctk.CTkButton(
                self._allowance_row, text="Edit", width=64,
                fg_color="transparent", border_width=1,
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
            defaultextension=".db",
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
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Restore")
        dialog.resizable(False, False)
        center_on_parent(dialog, self, 480, 180)
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

    # ── Reset All Data ────────────────────────────────────────────────────────

    def _reset_data(self):
        result = [False]
        dialog = ctk.CTkToplevel(self)
        dialog.title("Reset All Data")
        dialog.resizable(False, False)
        center_on_parent(dialog, self, 500, 220)
        dialog.grab_set()
        dialog.focus_set()

        ctk.CTkLabel(
            dialog,
            text="This will permanently delete ALL your data:\nsnapshots, accounts, expenses, income, and notes.\n\nType DELETE to confirm:",
            wraplength=460, justify="left", font=ctk.CTkFont(size=13),
        ).pack(padx=20, pady=(20, 8))

        confirm_var = ctk.StringVar()
        entry = ctk.CTkEntry(dialog, textvariable=confirm_var, width=160)
        entry.pack(padx=20, pady=(0, 12))
        entry.focus_set()

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        reset_btn = ctk.CTkButton(
            btn_row, text="Reset All Data", width=140,
            fg_color="transparent", border_width=1,
            text_color=(_RED, _RED),
            hover_color=("gray85", "gray20"),
            state="disabled",
            command=lambda: [result.__setitem__(0, True), dialog.destroy()],
        )
        reset_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color="transparent", border_width=1,
            command=dialog.destroy,
        ).pack(side="left")

        def on_change(*_):
            reset_btn.configure(state="normal" if confirm_var.get() == "DELETE" else "disabled")

        confirm_var.trace_add("write", on_change)
        dialog.wait_window()

        if result[0]:
            reset_all_data()
            self.winfo_toplevel().destroy()

    # ── Helper ────────────────────────────────────────────────────────────────

    def _divider(self):
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=24, pady=(16, 0)
        )
