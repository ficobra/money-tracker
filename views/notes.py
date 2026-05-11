"""Notes tab — My Notes (free text) + Debt/Credit tracking (PyQt6)."""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QLineEdit, QTextEdit,
    QDialog, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from database.db import (
    get_setting, set_setting,
    get_all_notes, add_note, update_note, delete_note,
)
from styles.theme import (
    BG_CARD, BG_ELEM, BG_MAIN, ACCENT, TEXT_PRI, TEXT_SEC,
    BORDER, GREEN, RED, FONT
)
from utils import fmt_eur, fmt_eur_signed, open_dialog, bind_numeric_entry

# Direction mapping: display label → (db_string, colour)
_DIRECTIONS: dict[str, tuple[str, str]] = {
    "They owe me": ("they_owe", GREEN),
    "I owe them":  ("i_owe",   RED),
}
_DB_TO_LABEL = {v[0]: k for k, v in _DIRECTIONS.items()}


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


def _fmt_date(created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at)
        return dt.strftime("%-d %b %Y")
    except Exception:
        return created_at


# ── View ──────────────────────────────────────────────────────────────────────

class NotesView(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("background: #0d1117; border: none;")

        self._editing_id: int | None = None

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        content.setStyleSheet("background: #0d1117;")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(8)
        self.setWidget(content)

        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self) -> None:
        # Title
        title = make_label("Notes", 22, bold=True)
        self._layout.addWidget(title)

        sub = make_label("Personal notes and debt/credit tracking.", 13, color=TEXT_SEC)
        sub.setContentsMargins(0, 0, 0, 12)
        self._layout.addWidget(sub)

        # ── My Notes section ──────────────────────────────────────────────────
        self._layout.addWidget(make_label("My Notes", 15, bold=True))

        notes_card = make_card()
        notes_card_layout = QVBoxLayout(notes_card)
        notes_card_layout.setContentsMargins(16, 14, 16, 14)
        notes_card_layout.setSpacing(8)

        self._my_notes_box = QTextEdit()
        self._my_notes_box.setFixedHeight(140)
        self._my_notes_box.setFont(QFont(FONT, 13))
        self._my_notes_box.setStyleSheet(
            f"QTextEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 8px; color: {TEXT_PRI}; padding: 6px; }}"
        )
        notes_card_layout.addWidget(self._my_notes_box)

        save_row_w = QWidget()
        save_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        save_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        save_row_w.setStyleSheet("background: transparent; border: none;")
        save_row = QHBoxLayout(save_row_w)
        save_row.setContentsMargins(0, 0, 0, 0)
        save_row.setSpacing(10)
        save_row.addStretch()

        save_btn = QPushButton("Save Notes")
        save_btn.setFixedHeight(32)
        save_btn.setFont(QFont(FONT, 13))
        save_btn.setProperty("class", "accent")
        save_btn.clicked.connect(self._save_my_notes)
        save_row.addWidget(save_btn)

        self._my_notes_status = make_label("", 12, color=GREEN)
        save_row.addWidget(self._my_notes_status)

        notes_card_layout.addWidget(save_row_w)
        self._layout.addWidget(notes_card)

        # ── Divider ───────────────────────────────────────────────────────────
        divider = make_divider()
        divider.setContentsMargins(0, 8, 0, 8)
        div_wrapper = QWidget()
        div_wrapper.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        div_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        div_wrapper.setStyleSheet("background: transparent; border: none;")
        div_wl = QVBoxLayout(div_wrapper)
        div_wl.setContentsMargins(0, 12, 0, 12)
        div_wl.addWidget(divider)
        self._layout.addWidget(div_wrapper)

        # ── Debt / Credit Notes section ───────────────────────────────────────
        self._layout.addWidget(make_label("Debt / Credit Notes", 15, bold=True))

        dc_sub = make_label("Purely informational — not included in any calculations.", 13, color=TEXT_SEC)
        dc_sub.setContentsMargins(0, 0, 0, 8)
        self._layout.addWidget(dc_sub)

        # Summary cards row
        summary_row_w = QWidget()
        summary_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        summary_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        summary_row_w.setStyleSheet("background: transparent; border: none;")
        summary_row = QHBoxLayout(summary_row_w)
        summary_row.setContentsMargins(0, 0, 0, 16)
        summary_row.setSpacing(12)

        they_card = make_card()
        they_inner_layout = QVBoxLayout(they_card)
        they_inner_layout.setContentsMargins(16, 14, 16, 14)
        they_inner_layout.setSpacing(4)
        they_inner_layout.addWidget(make_label("OTHERS OWE ME", 11, color=TEXT_SEC))
        self._they_total = make_label("€0,00", 22, bold=True, color=GREEN)
        they_inner_layout.addWidget(self._they_total)
        summary_row.addWidget(they_card, 1)

        i_card = make_card()
        i_inner_layout = QVBoxLayout(i_card)
        i_inner_layout.setContentsMargins(16, 14, 16, 14)
        i_inner_layout.setSpacing(4)
        i_inner_layout.addWidget(make_label("I OWE OTHERS", 11, color=TEXT_SEC))
        self._i_total = make_label("€0,00", 22, bold=True, color=RED)
        i_inner_layout.addWidget(self._i_total)
        summary_row.addWidget(i_card, 1)

        self._layout.addWidget(summary_row_w)

        # ── Add note form ─────────────────────────────────────────────────────
        add_card = make_card()
        add_card_layout = QVBoxLayout(add_card)
        add_card_layout.setContentsMargins(16, 14, 16, 14)
        add_card_layout.setSpacing(0)

        form_row_w = QWidget()
        form_row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        form_row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        form_row_w.setStyleSheet("background: transparent; border: none;")
        form_row = QHBoxLayout(form_row_w)
        form_row.setContentsMargins(0, 0, 0, 0)
        form_row.setSpacing(12)

        self._add_dir_combo = QComboBox()
        self._add_dir_combo.addItems(list(_DIRECTIONS.keys()))
        self._add_dir_combo.setFont(QFont(FONT, 13))
        self._add_dir_combo.setFixedHeight(32)
        self._add_dir_combo.setStyleSheet(
            f"QComboBox {{ background-color: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{ background-color: #1c2333; color: {TEXT_PRI};"
            f" selection-background-color: {ACCENT}; border: 1px solid {BORDER}; }}"
        )
        form_row.addWidget(self._add_dir_combo)

        self._add_desc = QLineEdit()
        self._add_desc.setPlaceholderText("Description")
        self._add_desc.setFont(QFont(FONT, 13))
        self._add_desc.setFixedHeight(32)
        self._add_desc.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        self._add_desc.returnPressed.connect(lambda: self._add_amount_entry.setFocus())
        form_row.addWidget(self._add_desc, 2)

        eur_lbl = make_label("EUR", 13, color=TEXT_SEC)
        form_row.addWidget(eur_lbl)

        self._add_amount_entry = QLineEdit()
        self._add_amount_entry.setPlaceholderText("0.00")
        self._add_amount_entry.setFont(QFont(FONT, 13))
        self._add_amount_entry.setFixedWidth(100)
        self._add_amount_entry.setFixedHeight(32)
        self._add_amount_entry.setStyleSheet(
            f"QLineEdit {{ background: {BG_ELEM}; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        bind_numeric_entry(self._add_amount_entry)
        self._add_amount_entry.returnPressed.connect(self._add_note)
        form_row.addWidget(self._add_amount_entry)

        add_btn = QPushButton("Add")
        add_btn.setFixedHeight(32)
        add_btn.setFixedWidth(80)
        add_btn.setFont(QFont(FONT, 13))
        add_btn.setProperty("class", "accent")
        add_btn.clicked.connect(self._add_note)
        form_row.addWidget(add_btn)

        self._add_status = make_label("", 12)
        form_row.addWidget(self._add_status)
        form_row.addStretch()

        add_card_layout.addWidget(form_row_w)
        self._layout.addWidget(add_card)

        # ── Notes list (dynamic) ──────────────────────────────────────────────
        self._list_widget = QWidget()
        self._list_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._list_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._list_widget.setStyleSheet("background: transparent; border: none;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._layout.addWidget(self._list_widget)

        self._layout.addStretch()

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        # Reload My Notes text
        saved = get_setting("my_notes") or ""
        self._my_notes_box.setPlainText(saved)

        # Reload debt/credit notes list
        _clear_layout(self._list_layout)

        notes = [dict(n) for n in get_all_notes()]
        they_owe = [n for n in notes if n["direction"] == "they_owe"]
        i_owe    = [n for n in notes if n["direction"] == "i_owe"]

        they_sum = sum(n["amount"] for n in they_owe)
        i_sum    = sum(n["amount"] for n in i_owe)

        self._they_total.setText(fmt_eur(they_sum))
        self._i_total.setText(fmt_eur(i_sum))

        self._render_section("They owe me", they_owe, GREEN)
        self._render_section("I owe them",  i_owe,    RED)

    # ── My Notes save ─────────────────────────────────────────────────────────

    def _save_my_notes(self) -> None:
        content = self._my_notes_box.toPlainText()
        set_setting("my_notes", content)
        self._my_notes_status.setText("Saved.")
        self._my_notes_status.setStyleSheet(f"color: {GREEN}; background: transparent; border: none;")
        QTimer.singleShot(2500, lambda: self._my_notes_status.setText(""))

    # ── Section rendering ─────────────────────────────────────────────────────

    def _render_section(self, title: str, notes: list[dict], colour: str) -> None:
        # Section header row
        hdr_w = QWidget()
        hdr_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        hdr_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        hdr_w.setStyleSheet("background: transparent; border: none;")
        hdr_row = QHBoxLayout(hdr_w)
        hdr_row.setContentsMargins(0, 8, 0, 2)
        hdr_row.setSpacing(6)
        hdr_row.addWidget(make_label(title, 14, bold=True, color=colour))
        hdr_row.addWidget(make_label(f"({len(notes)})", 13, color=TEXT_SEC))
        hdr_row.addStretch()
        self._list_layout.addWidget(hdr_w)

        self._list_layout.addWidget(make_divider())

        if not notes:
            empty = make_label("Nothing here yet.", 12, color=TEXT_SEC)
            empty.setContentsMargins(0, 2, 0, 8)
            self._list_layout.addWidget(empty)
            return

        # Column headers
        col_hdr_w = QWidget()
        col_hdr_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        col_hdr_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        col_hdr_w.setStyleSheet("background: transparent; border: none;")
        col_hdr_row = QHBoxLayout(col_hdr_w)
        col_hdr_row.setContentsMargins(0, 2, 0, 2)
        col_hdr_row.setSpacing(0)

        desc_hdr = make_label("Description", 12, color=TEXT_SEC)
        desc_hdr.setFixedWidth(300)
        col_hdr_row.addWidget(desc_hdr)

        amt_hdr = make_label("Amount", 12, color=TEXT_SEC)
        amt_hdr.setFixedWidth(120)
        amt_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        col_hdr_row.addWidget(amt_hdr)

        date_hdr = make_label("Added", 12, color=TEXT_SEC)
        date_hdr.setFixedWidth(120)
        date_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        col_hdr_row.addWidget(date_hdr)

        col_hdr_row.addStretch()
        self._list_layout.addWidget(col_hdr_w)

        for note in notes:
            if note["id"] == self._editing_id:
                self._render_edit_row(note)
            else:
                self._render_display_row(note, colour)

    def _render_display_row(self, note: dict, colour: str) -> None:
        row_w = QWidget()
        row_w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        row_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        row_w.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(0)

        date_str = _fmt_date(note["created_at"])

        desc_lbl = make_label(note["content"], 13)
        desc_lbl.setFixedWidth(300)
        row.addWidget(desc_lbl)

        amt_lbl = make_label(fmt_eur(note["amount"]), 13, color=colour)
        amt_lbl.setFixedWidth(120)
        amt_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(amt_lbl)

        date_lbl = make_label(date_str, 12, color=TEXT_SEC)
        date_lbl.setFixedWidth(120)
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(date_lbl)

        row.addWidget(_make_spacer(16, 1))

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(64, 28)
        edit_btn.setFont(QFont(FONT, 11))
        edit_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
            f" border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #3d4d63; }}"
        )
        edit_btn.clicked.connect(lambda _=False, nid=note["id"]: self._start_edit(nid))
        row.addWidget(edit_btn)

        row.addWidget(_make_spacer(6, 1))

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(72, 28)
        del_btn.setFont(QFont(FONT, 11))
        del_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {RED}; border: none;"
            f" border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #3d1a1a; }}"
        )
        del_btn.clicked.connect(lambda _=False, nid=note["id"]: self._delete(nid))
        row.addWidget(del_btn)

        row.addStretch()
        self._list_layout.addWidget(row_w)

    def _render_edit_row(self, note: dict) -> None:
        row_card = QFrame()
        row_card.setFrameShape(QFrame.Shape.NoFrame)
        row_card.setFrameShadow(QFrame.Shadow.Plain)
        row_card.setLineWidth(0)
        row_card.setStyleSheet(
            f"QFrame {{ background: {BG_ELEM}; border-radius: 8px; border: none; }}"
            f"QFrame QWidget {{ background: transparent; border: none; }}"
        )

        row_layout = QHBoxLayout(row_card)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(10)

        # Direction combo
        dir_combo = QComboBox()
        dir_combo.addItems(list(_DIRECTIONS.keys()))
        dir_combo.setFont(QFont(FONT, 13))
        dir_combo.setFixedHeight(30)
        current_label = _DB_TO_LABEL.get(note["direction"], "They owe me")
        idx = dir_combo.findText(current_label)
        if idx >= 0:
            dir_combo.setCurrentIndex(idx)
        dir_combo.setStyleSheet(
            f"QComboBox {{ background-color: #161b22; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{ background-color: #1c2333; color: {TEXT_PRI};"
            f" selection-background-color: {ACCENT}; border: 1px solid {BORDER}; }}"
        )
        row_layout.addWidget(dir_combo)

        # Description entry
        desc_entry = QLineEdit(note["content"])
        desc_entry.setFont(QFont(FONT, 13))
        desc_entry.setFixedHeight(30)
        desc_entry.setFixedWidth(260)
        desc_entry.setStyleSheet(
            f"QLineEdit {{ background: #161b22; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        row_layout.addWidget(desc_entry)

        row_layout.addWidget(make_label("EUR", 13, color=TEXT_SEC))

        # Amount entry
        amount_entry = QLineEdit(f"{note['amount']:.2f}")
        amount_entry.setFont(QFont(FONT, 13))
        amount_entry.setFixedHeight(30)
        amount_entry.setFixedWidth(100)
        amount_entry.setStyleSheet(
            f"QLineEdit {{ background: #161b22; border: 1px solid {BORDER};"
            f" border-radius: 6px; color: {TEXT_PRI}; padding: 4px 8px; }}"
        )
        bind_numeric_entry(amount_entry)
        row_layout.addWidget(amount_entry)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(64, 28)
        save_btn.setFont(QFont(FONT, 13))
        save_btn.setProperty("class", "accent")
        save_btn.clicked.connect(
            lambda _=False, nid=note["id"]: self._save_edit(nid, dir_combo, desc_entry, amount_entry)
        )
        row_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(72, 28)
        cancel_btn.setFont(QFont(FONT, 13))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_ELEM}; color: {TEXT_PRI}; border: none;"
            f" border-radius: 6px; }}"
            f"QPushButton:hover {{ background: #3d4d63; }}"
        )
        cancel_btn.clicked.connect(self._cancel_edit)
        row_layout.addWidget(cancel_btn)

        self._edit_status = make_label("", 12)
        row_layout.addWidget(self._edit_status)
        row_layout.addStretch()

        self._list_layout.addWidget(row_card)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_note(self) -> None:
        label = self._add_dir_combo.currentText()
        desc = self._add_desc.text().strip()
        amount_str = self._add_amount_entry.text().strip()

        if not desc:
            self._set_add_status("Description is required.", error=True)
            return
        try:
            amount = float(amount_str)
            if amount < 0:
                raise ValueError
        except ValueError:
            self._set_add_status("Enter a positive amount.", error=True)
            return

        direction = _DIRECTIONS[label][0]
        add_note(desc, amount, direction)
        self._add_desc.clear()
        self._add_amount_entry.clear()
        self._set_add_status(f'"{desc}" added.', error=False)
        self.refresh()

    def _start_edit(self, note_id: int) -> None:
        self._editing_id = note_id
        self.refresh()

    def _save_edit(
        self,
        note_id: int,
        dir_combo: QComboBox,
        desc_entry: QLineEdit,
        amount_entry: QLineEdit,
    ) -> None:
        desc = desc_entry.text().strip()
        if not desc:
            self._set_edit_status("Description is required.", error=True)
            return
        try:
            amount = float(amount_entry.text().strip())
            if amount < 0:
                raise ValueError
        except ValueError:
            self._set_edit_status("Enter a positive amount.", error=True)
            return

        label = dir_combo.currentText()
        direction = _DIRECTIONS.get(label, ("they_owe", ""))[0]
        update_note(note_id, desc, amount, direction)
        self._editing_id = None
        self.refresh()

    def _cancel_edit(self) -> None:
        self._editing_id = None
        self.refresh()

    def _delete(self, note_id: int) -> None:
        delete_note(note_id)
        if self._editing_id == note_id:
            self._editing_id = None
        self.refresh()

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_add_status(self, text: str, *, error: bool) -> None:
        color = RED if error else GREEN
        self._add_status.setText(text)
        self._add_status.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        if not error:
            QTimer.singleShot(3000, lambda: self._add_status.setText(""))

    def _set_edit_status(self, text: str, *, error: bool) -> None:
        if hasattr(self, "_edit_status"):
            color = RED if error else GREEN
            self._edit_status.setText(text)
            self._edit_status.setStyleSheet(
                f"color: {color}; background: transparent; border: none;"
            )


# ── Widget helpers ────────────────────────────────────────────────────────────

def _make_spacer(width: int, height: int) -> QWidget:
    w = QWidget()
    w.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    w.setFixedSize(width, height)
    w.setStyleSheet("background: transparent; border: none;")
    return w
