"""Settings tab — allowance, appearance, notifications, backup/restore, reset (PyQt6)."""

import base64
import shutil
import sys
import threading
from datetime import date
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QLineEdit, QComboBox,
    QDialog, QFileDialog, QApplication, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from database.db import (
    get_setting, set_setting, reset_all_data,
    DB_PATH,
)
from styles.theme import (
    BG_CARD, BG_ELEM, BG_MAIN, ACCENT, TEXT_PRI, TEXT_SEC,
    BORDER, GREEN, RED, FONT
)
from utils import fmt_eur, open_dialog


# ── Module-level helpers ──────────────────────────────────────────────────────

def _clear_layout(layout) -> None:
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        else:
            sub = item.layout()
            if sub:
                _clear_layout(sub)


def make_label(text: str, size: int = 13, bold: bool = False, color: str = TEXT_PRI) -> QLabel:
    lbl = QLabel(text)
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    lbl.setFont(QFont(FONT, size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
    lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
    lbl.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    return lbl


def make_card() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet(
        f"QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}"
        f"QFrame QFrame {{ border: none; background: transparent; }}"
        f"QFrame QWidget {{ border: none; background: transparent; }}"
    )
    return f


def make_divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setFixedHeight(1)
    f.setStyleSheet("background: #2a3a52; border: none;")
    return f


def _make_inline_frame() -> QFrame:
    """Inline transparent separator frame."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.NoFrame)
    f.setFrameShadow(QFrame.Shadow.Plain)
    f.setLineWidth(0)
    f.setStyleSheet("background: transparent; border: none;")
    return f


# ── View ──────────────────────────────────────────────────────────────────────

class SettingsView(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        self._editing_allowance: bool = False
        self._allowance_row_w: QWidget | None = None
        self._allowance_layout: QHBoxLayout | None = None

        # Notification state
        self._notif_email_entry: QLineEdit | None = None
        self._resend_key_entry: QLineEdit | None = None
        self._email_days_entry: QLineEdit | None = None
        self._banner_days_entry: QLineEdit | None = None
        self._notif_save_status: QLabel | None = None
        self._notif_toggle: QPushButton | None = None

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setStyleSheet("background: #0d1117;")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(8)
        self.setWidget(content)

        self._build()

    def refresh(self) -> None:
        pass  # Static layout; allowance row re-reads DB when edited

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._layout.addWidget(make_label("Settings", 22, bold=True))

        sub = make_label(
            "Configure spending allowance, appearance, and data management.", 13, color=TEXT_SEC
        )
        sub.setContentsMargins(0, 0, 0, 12)
        self._layout.addWidget(sub)

        self._add_divider()

        # ── Daily Spending Allowance ──────────────────────────────────────────
        self._layout.addWidget(make_label("Daily Spending Allowance", 17, bold=True))

        allowance_card = make_card()
        allowance_card_layout = QVBoxLayout(allowance_card)
        allowance_card_layout.setContentsMargins(16, 14, 16, 14)
        allowance_card_layout.setSpacing(8)

        desc = make_label(
            "Your estimated budget per day for variable spending (food, transport, leisure, etc.). "
            "Used in mid-month estimation calculations.",
            12, color=TEXT_SEC,
        )
        desc.setWordWrap(True)
        allowance_card_layout.addWidget(desc)

        self._allowance_row_w = QWidget()
        self._allowance_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._allowance_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._allowance_row_w.setStyleSheet("background: transparent; border: none;")
        self._allowance_layout = QHBoxLayout(self._allowance_row_w)
        self._allowance_layout.setContentsMargins(0, 0, 0, 0)
        self._allowance_layout.setSpacing(8)
        allowance_card_layout.addWidget(self._allowance_row_w)

        self._layout.addWidget(allowance_card)
        self._refresh_allowance_row()

        self._add_divider()

        # ── Appearance ────────────────────────────────────────────────────────
        self._layout.addWidget(make_label("Appearance", 17, bold=True))

        app_card = make_card()
        app_card_layout = QVBoxLayout(app_card)
        app_card_layout.setContentsMargins(16, 14, 16, 14)
        app_card_layout.setSpacing(8)

        app_card_layout.addWidget(make_label("Color theme:", 13))

        self._appearance_combo = QComboBox()
        self._appearance_combo.addItems(["System", "Light", "Dark"])
        self._appearance_combo.setFont(QFont(FONT, 13))
        self._appearance_combo.setFixedWidth(180)
        self._appearance_combo.setFixedHeight(32)
        current_mode = get_setting("appearance_mode") or "System"
        idx = self._appearance_combo.findText(current_mode)
        if idx >= 0:
            self._appearance_combo.setCurrentIndex(idx)
        self._appearance_combo.setStyleSheet(
            f"QComboBox {{ background-color: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{ background-color: #1c2333; color: {TEXT_PRI};"
            f" selection-background-color: {ACCENT}; border: 1px solid {BORDER}; }}"
        )
        self._appearance_combo.currentTextChanged.connect(self._on_appearance_change)
        app_card_layout.addWidget(self._appearance_combo)

        self._layout.addWidget(app_card)

        self._add_divider()

        # ── Notifications ─────────────────────────────────────────────────────
        self._layout.addWidget(make_label("Notifications", 17, bold=True))

        notif_desc = make_label(
            "Get reminded to enter your monthly snapshot via email and an in-app banner.",
            13, color=TEXT_SEC,
        )
        notif_desc.setWordWrap(True)
        notif_desc.setContentsMargins(0, 0, 0, 4)
        self._layout.addWidget(notif_desc)

        notif_card = make_card()
        notif_card_layout = QVBoxLayout(notif_card)
        notif_card_layout.setContentsMargins(16, 14, 16, 14)
        notif_card_layout.setSpacing(8)

        # Enable toggle row
        toggle_row_w = QWidget()
        toggle_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        toggle_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        toggle_row_w.setStyleSheet("background: transparent; border: none;")
        toggle_row = QHBoxLayout(toggle_row_w)
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(12)
        toggle_row.addWidget(make_label("Enable email notifications", 13))

        notif_enabled = get_setting("notif_enabled") == "1"
        self._notif_toggle = QPushButton("ON" if notif_enabled else "OFF")
        self._notif_toggle.setCheckable(True)
        self._notif_toggle.setChecked(notif_enabled)
        self._notif_toggle.setFixedSize(60, 28)
        self._notif_toggle.setFont(QFont(FONT, 11))
        self._notif_toggle.setStyleSheet(self._toggle_style(notif_enabled))
        self._notif_toggle.clicked.connect(self._on_notif_toggle)
        toggle_row.addWidget(self._notif_toggle)
        toggle_row.addStretch()
        notif_card_layout.addWidget(toggle_row_w)

        # Email field
        email_row_w = QWidget()
        email_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        email_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        email_row_w.setStyleSheet("background: transparent; border: none;")
        email_row = QHBoxLayout(email_row_w)
        email_row.setContentsMargins(0, 0, 0, 0)
        email_row.setSpacing(8)
        email_lbl = make_label("Send to email:", 13, color=TEXT_SEC)
        email_lbl.setFixedWidth(160)
        email_row.addWidget(email_lbl)
        self._notif_email_entry = QLineEdit(get_setting("notif_email") or "")
        self._notif_email_entry.setPlaceholderText("you@example.com")
        self._notif_email_entry.setFont(QFont(FONT, 13))
        self._notif_email_entry.setFixedHeight(30)
        self._notif_email_entry.setFixedWidth(280)
        self._notif_email_entry.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        email_row.addWidget(self._notif_email_entry)
        email_row.addStretch()
        notif_card_layout.addWidget(email_row_w)

        # Resend API key field
        key_row_w = QWidget()
        key_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        key_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        key_row_w.setStyleSheet("background: transparent; border: none;")
        key_row = QHBoxLayout(key_row_w)
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(8)
        key_lbl = make_label("Resend API key:", 13, color=TEXT_SEC)
        key_lbl.setFixedWidth(160)
        key_row.addWidget(key_lbl)

        _stored_key = get_setting("resend_api_key") or ""
        _decoded_key = ""
        if _stored_key:
            try:
                _decoded_key = base64.b64decode(_stored_key.encode()).decode()
            except Exception:
                _decoded_key = ""

        self._resend_key_entry = QLineEdit(_decoded_key)
        self._resend_key_entry.setPlaceholderText("re_...")
        self._resend_key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self._resend_key_entry.setFont(QFont(FONT, 13))
        self._resend_key_entry.setFixedHeight(30)
        self._resend_key_entry.setFixedWidth(280)
        self._resend_key_entry.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        key_row.addWidget(self._resend_key_entry)
        key_row.addStretch()
        notif_card_layout.addWidget(key_row_w)

        # Email days
        days_row_w = QWidget()
        days_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        days_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        days_row_w.setStyleSheet("background: transparent; border: none;")
        days_row = QHBoxLayout(days_row_w)
        days_row.setContentsMargins(0, 0, 0, 0)
        days_row.setSpacing(8)
        days_lbl = make_label("Email reminder (days before end of month):", 13, color=TEXT_SEC)
        days_lbl.setFixedWidth(320)
        days_row.addWidget(days_lbl)
        self._email_days_entry = QLineEdit(get_setting("email_days") or "3")
        self._email_days_entry.setFont(QFont(FONT, 13))
        self._email_days_entry.setFixedSize(60, 30)
        self._email_days_entry.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        days_row.addWidget(self._email_days_entry)
        days_row.addStretch()
        notif_card_layout.addWidget(days_row_w)

        # Banner days
        banner_days_row_w = QWidget()
        banner_days_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        banner_days_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        banner_days_row_w.setStyleSheet("background: transparent; border: none;")
        banner_days_row = QHBoxLayout(banner_days_row_w)
        banner_days_row.setContentsMargins(0, 0, 0, 0)
        banner_days_row.setSpacing(8)
        banner_lbl = make_label("In-app banner (days before end of month):", 13, color=TEXT_SEC)
        banner_lbl.setFixedWidth(320)
        banner_days_row.addWidget(banner_lbl)
        self._banner_days_entry = QLineEdit(get_setting("banner_days") or "7")
        self._banner_days_entry.setFont(QFont(FONT, 13))
        self._banner_days_entry.setFixedSize(60, 30)
        self._banner_days_entry.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        banner_days_row.addWidget(self._banner_days_entry)
        banner_days_row.addStretch()
        notif_card_layout.addWidget(banner_days_row_w)

        # Save + Test row
        btn_row_w = QWidget()
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row_w.setStyleSheet("background: transparent; border: none;")
        btn_row = QHBoxLayout(btn_row_w)
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(10)

        save_notif_btn = QPushButton("Save")
        save_notif_btn.setFixedSize(80, 32)
        save_notif_btn.setFont(QFont(FONT, 13))
        save_notif_btn.setProperty("class", "accent")
        save_notif_btn.clicked.connect(self._save_notif_settings)
        btn_row.addWidget(save_notif_btn)

        test_btn = QPushButton("Send test email")
        test_btn.setFixedHeight(32)
        test_btn.setFont(QFont(FONT, 13))
        test_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: #3d4d63; }}"
        )
        test_btn.clicked.connect(self._send_test_email)
        btn_row.addWidget(test_btn)

        self._notif_save_status = make_label("", 12)
        btn_row.addWidget(self._notif_save_status)
        btn_row.addStretch()
        notif_card_layout.addWidget(btn_row_w)

        self._layout.addWidget(notif_card)

        self._add_divider()

        # ── Data Management ───────────────────────────────────────────────────
        self._layout.addWidget(make_label("Data Management", 17, bold=True))

        dm_desc = make_label(
            "Back up your tracker database or restore from a previous backup. "
            "The database contains all snapshots, expenses, income, and notes.",
            13, color=TEXT_SEC,
        )
        dm_desc.setWordWrap(True)
        dm_desc.setContentsMargins(0, 0, 0, 8)
        self._layout.addWidget(dm_desc)

        backup_row_w = QWidget()
        backup_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        backup_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        backup_row_w.setStyleSheet("background: transparent; border: none;")
        backup_row = QHBoxLayout(backup_row_w)
        backup_row.setContentsMargins(0, 0, 0, 0)
        backup_row.setSpacing(12)

        backup_btn = QPushButton("Backup Data")
        backup_btn.setFixedHeight(32)
        backup_btn.setFont(QFont(FONT, 13))
        backup_btn.setProperty("class", "accent")
        backup_btn.clicked.connect(self._backup)
        backup_row.addWidget(backup_btn)

        self._backup_status = make_label("", 12)
        backup_row.addWidget(self._backup_status)
        backup_row.addStretch()
        self._layout.addWidget(backup_row_w)

        restore_row_w = QWidget()
        restore_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        restore_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        restore_row_w.setStyleSheet("background: transparent; border: none;")
        restore_row = QHBoxLayout(restore_row_w)
        restore_row.setContentsMargins(0, 0, 0, 0)
        restore_row.setSpacing(12)

        restore_btn = QPushButton("Restore Data")
        restore_btn.setFixedHeight(32)
        restore_btn.setFont(QFont(FONT, 13))
        restore_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {RED}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: #3d1a1a; }}"
        )
        restore_btn.clicked.connect(self._restore)
        restore_row.addWidget(restore_btn)

        self._restore_status = make_label("", 12)
        restore_row.addWidget(self._restore_status)
        restore_row.addStretch()
        self._layout.addWidget(restore_row_w)

        restore_note = make_label(
            "Restore replaces your current database with the backup and closes the app. "
            "Reopen the app to see the restored data.",
            12, color=TEXT_SEC,
        )
        restore_note.setWordWrap(True)
        restore_note.setContentsMargins(0, 4, 0, 0)
        self._layout.addWidget(restore_note)

        self._add_divider()

        # ── Reset All Data ────────────────────────────────────────────────────
        self._layout.addWidget(make_label("Reset All Data", 17, bold=True))

        reset_desc = make_label(
            "Permanently delete all snapshots, accounts, expenses, income, and notes. "
            "Settings are reset to defaults. The app will close after reset.",
            13, color=TEXT_SEC,
        )
        reset_desc.setWordWrap(True)
        reset_desc.setContentsMargins(0, 0, 0, 8)
        self._layout.addWidget(reset_desc)

        reset_row_w = QWidget()
        reset_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        reset_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        reset_row_w.setStyleSheet("background: transparent; border: none;")
        reset_row = QHBoxLayout(reset_row_w)
        reset_row.setContentsMargins(0, 0, 0, 32)
        reset_row.setSpacing(0)

        reset_btn = QPushButton("Reset All Data")
        reset_btn.setFixedHeight(32)
        reset_btn.setFont(QFont(FONT, 13))
        reset_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {RED}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: #3d1a1a; }}"
        )
        reset_btn.clicked.connect(self._reset_data)
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        self._layout.addWidget(reset_row_w)

        self._layout.addStretch()

    # ── Daily Spending Allowance ───────────────────────────────────────────────

    def _refresh_allowance_row(self) -> None:
        if self._allowance_layout is None or self._allowance_row_w is None:
            return
        _clear_layout(self._allowance_layout)

        daily = float(get_setting("daily_buffer") or "20.0")

        if self._editing_allowance:
            self._allowance_entry = QLineEdit(f"{daily:.2f}")
            self._allowance_entry.setFont(QFont(FONT, 13))
            self._allowance_entry.setFixedSize(100, 32)
            self._allowance_entry.setStyleSheet(
                f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
                f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
            )
            self._allowance_layout.addWidget(self._allowance_entry)

            eur_lbl = make_label("EUR / day", 13, color=TEXT_SEC)
            eur_lbl.setContentsMargins(8, 0, 14, 0)
            self._allowance_layout.addWidget(eur_lbl)

            save_btn = QPushButton("Save")
            save_btn.setFixedSize(72, 32)
            save_btn.setFont(QFont(FONT, 13))
            save_btn.setProperty("class", "accent")
            save_btn.clicked.connect(self._save_allowance)
            self._allowance_layout.addWidget(save_btn)

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedSize(72, 32)
            cancel_btn.setFont(QFont(FONT, 13))
            cancel_btn.setStyleSheet(
                f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
                f" border-radius: 8px; padding: 6px 14px; }}"
                f"QPushButton:hover {{ background: #3d4d63; }}"
            )
            cancel_btn.clicked.connect(self._cancel_allowance_edit)
            self._allowance_layout.addWidget(cancel_btn)
        else:
            val_lbl = make_label(f"{fmt_eur(daily)} / day", 20, bold=True)
            val_lbl.setContentsMargins(0, 0, 14, 0)
            self._allowance_layout.addWidget(val_lbl)

            edit_btn = QPushButton("Edit")
            edit_btn.setFixedSize(64, 32)
            edit_btn.setFont(QFont(FONT, 13))
            edit_btn.setStyleSheet(
                f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
                f" border-radius: 8px; padding: 6px 14px; }}"
                f"QPushButton:hover {{ background: #3d4d63; }}"
            )
            edit_btn.clicked.connect(self._start_allowance_edit)
            self._allowance_layout.addWidget(edit_btn)

        self._allowance_layout.addStretch()

    def _start_allowance_edit(self) -> None:
        self._editing_allowance = True
        self._refresh_allowance_row()

    def _save_allowance(self) -> None:
        try:
            value = float(self._allowance_entry.text().strip())
            if value <= 0:
                raise ValueError
        except ValueError:
            return
        set_setting("daily_buffer", str(value))
        self._editing_allowance = False
        self._refresh_allowance_row()

    def _cancel_allowance_edit(self) -> None:
        self._editing_allowance = False
        self._refresh_allowance_row()

    # ── Appearance ────────────────────────────────────────────────────────────

    def _on_appearance_change(self, value: str) -> None:
        # Save the value only — no CTK call in PyQt6
        set_setting("appearance_mode", value)

    # ── Notifications ─────────────────────────────────────────────────────────

    @staticmethod
    def _toggle_style(enabled: bool) -> str:
        bg = ACCENT if enabled else BG_ELEM
        return (
            f"QPushButton {{ background: {bg}; color: {'white' if enabled else TEXT_SEC};"
            f" border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: {'#0096b4' if enabled else '#3d4d63'}; }}"
        )

    def _on_notif_toggle(self) -> None:
        if self._notif_toggle is None:
            return
        enabled = self._notif_toggle.isChecked()
        self._notif_toggle.setText("ON" if enabled else "OFF")
        self._notif_toggle.setStyleSheet(self._toggle_style(enabled))
        set_setting("notif_enabled", "1" if enabled else "0")

    def _save_notif_settings(self) -> None:
        if self._notif_save_status is None:
            return
        try:
            ed = int(self._email_days_entry.text().strip())  # type: ignore[union-attr]
            bd = int(self._banner_days_entry.text().strip())  # type: ignore[union-attr]
            if not (1 <= ed <= 15) or not (1 <= bd <= 15):
                raise ValueError
        except ValueError:
            self._notif_save_status.setText("Days must be between 1 and 15.")
            self._notif_save_status.setStyleSheet(
                f"color: {RED}; background: transparent; border: none;"
            )
            return

        set_setting("notif_email", self._notif_email_entry.text().strip())  # type: ignore[union-attr]
        set_setting("email_days",  str(ed))
        set_setting("banner_days", str(bd))

        key = self._resend_key_entry.text().strip()  # type: ignore[union-attr]
        encoded_key = base64.b64encode(key.encode()).decode() if key else ""
        set_setting("resend_api_key", encoded_key)

        self._notif_save_status.setText("Saved!")
        self._notif_save_status.setStyleSheet(
            f"color: {GREEN}; background: transparent; border: none;"
        )
        QTimer.singleShot(3000, lambda: (
            self._notif_save_status.setText("") if self._notif_save_status else None
        ))

    def _send_test_email(self) -> None:
        if self._notif_save_status is None:
            return
        self._notif_save_status.setText("Sending…")
        self._notif_save_status.setStyleSheet(
            f"color: {TEXT_SEC}; background: transparent; border: none;"
        )

        def do_send() -> None:
            try:
                import resend  # noqa: PLC0415
                recipient = self._notif_email_entry.text().strip()  # type: ignore[union-attr]
                key       = self._resend_key_entry.text().strip()  # type: ignore[union-attr]

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

                QTimer.singleShot(0, lambda: (
                    self._notif_save_status.setText("Test email sent!")
                    if self._notif_save_status else None
                ) or (
                    self._notif_save_status.setStyleSheet(
                        f"color: {GREEN}; background: transparent; border: none;"
                    ) if self._notif_save_status else None
                ))
                QTimer.singleShot(4000, lambda: (
                    self._notif_save_status.setText("") if self._notif_save_status else None
                ))
            except Exception as exc:
                err = str(exc)[:80]
                QTimer.singleShot(0, lambda e=err: (
                    self._notif_save_status.setText(f"Error: {e}")
                    if self._notif_save_status else None
                ) or (
                    self._notif_save_status.setStyleSheet(
                        f"color: {RED}; background: transparent; border: none;"
                    ) if self._notif_save_status else None
                ))

        threading.Thread(target=do_send, daemon=True).start()

    # ── Backup & Restore ──────────────────────────────────────────────────────

    def _backup(self) -> None:
        today = date.today()
        default_name = f"money-tracker-backup-{today.strftime('%Y-%m-%d')}.db"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Backup",
            default_name,
            "Database files (*.db);;All files (*.*)",
        )
        if not filepath:
            return
        shutil.copy2(DB_PATH, filepath)
        self._backup_status.setText("Backup saved!")
        self._backup_status.setStyleSheet(
            f"color: {GREEN}; background: transparent; border: none;"
        )
        QTimer.singleShot(4000, lambda: self._backup_status.setText(""))

    def _restore(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup File",
            "",
            "Database files (*.db);;All files (*.*)",
        )
        if not filepath:
            return

        dlg = open_dialog(self, 480, 180)
        dlg.setWindowTitle("Confirm Restore")

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        dlg_layout.setSpacing(12)

        msg = make_label(
            "Restore data from the selected backup?\n\n"
            "This will replace ALL current data. The app will close — "
            "reopen it to see the restored data.",
            13,
        )
        msg.setWordWrap(True)
        dlg_layout.addWidget(msg)

        btn_row_w = QWidget()
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row_w.setStyleSheet("background: transparent; border: none;")
        btn_row = QHBoxLayout(btn_row_w)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        result: list[bool] = [False]

        confirm_btn = QPushButton("Restore & Close")
        confirm_btn.setFixedSize(140, 32)
        confirm_btn.setFont(QFont(FONT, 13))
        confirm_btn.setProperty("class", "accent")

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setFont(QFont(FONT, 13))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: #3d4d63; }}"
        )

        def on_confirm() -> None:
            result[0] = True
            dlg.accept()

        confirm_btn.clicked.connect(on_confirm)
        cancel_btn.clicked.connect(dlg.reject)

        btn_row.addWidget(confirm_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        dlg_layout.addWidget(btn_row_w)

        dlg.exec()

        if result[0]:
            shutil.copy2(filepath, DB_PATH)
            QApplication.quit()

    # ── Reset All Data ────────────────────────────────────────────────────────

    def _reset_data(self) -> None:
        dlg = open_dialog(self, 500, 220)
        dlg.setWindowTitle("Reset All Data")

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(20, 20, 20, 16)
        dlg_layout.setSpacing(8)

        msg = make_label(
            "This will permanently delete ALL your data:\n"
            "snapshots, accounts, expenses, income, and notes.\n\n"
            "Type DELETE to confirm:",
            13,
        )
        msg.setWordWrap(True)
        dlg_layout.addWidget(msg)

        confirm_entry = QLineEdit()
        confirm_entry.setFont(QFont(FONT, 13))
        confirm_entry.setFixedWidth(160)
        confirm_entry.setFixedHeight(32)
        confirm_entry.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        dlg_layout.addWidget(confirm_entry)
        confirm_entry.setFocus()

        btn_row_w = QWidget()
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        btn_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_row_w.setStyleSheet("background: transparent; border: none;")
        btn_row = QHBoxLayout(btn_row_w)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        result: list[bool] = [False]

        reset_btn = QPushButton("Reset All Data")
        reset_btn.setFixedSize(140, 32)
        reset_btn.setFont(QFont(FONT, 13))
        reset_btn.setEnabled(False)
        reset_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {RED}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover:enabled {{ background: #3d1a1a; }}"
            f"QPushButton:disabled {{ color: #555; }}"
        )

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setFont(QFont(FONT, 13))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
            f" border-radius: 8px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: #3d4d63; }}"
        )

        def on_text_changed(text: str) -> None:
            reset_btn.setEnabled(text == "DELETE")

        def on_reset() -> None:
            result[0] = True
            dlg.accept()

        confirm_entry.textChanged.connect(on_text_changed)
        reset_btn.clicked.connect(on_reset)
        cancel_btn.clicked.connect(dlg.reject)

        btn_row.addWidget(reset_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        dlg_layout.addWidget(btn_row_w)

        dlg.exec()

        if result[0]:
            reset_all_data()
            QApplication.quit()

    # ── Helper ────────────────────────────────────────────────────────────────

    def _add_divider(self) -> None:
        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        wrapper.setStyleSheet("background: transparent; border: none;")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 8, 0, 8)
        wl.addWidget(make_divider())
        self._layout.addWidget(wrapper)
