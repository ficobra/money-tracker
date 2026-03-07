import customtkinter as ctk
from datetime import datetime

from database.db import (
    get_all_notes,
    add_note,
    update_note,
    delete_note,
    get_setting,
    set_setting,
)
from utils import fmt_eur

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

# Maps the user-facing label to the DB string and its display colour
_DIRECTIONS: dict[str, tuple[str, str]] = {
    "They owe me": ("they_owe", _GREEN),
    "I owe them":  ("i_owe",   _RED),
}
_DB_TO_LABEL = {v[0]: k for k, v in _DIRECTIONS.items()}

_W_DESC = 300
_W_AMT  = 120
_W_DATE = 120


class NotesView(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self._editing_id: int | None = None
        self._edit_status_label: ctk.CTkLabel | None = None
        self._build()

    # ── Static skeleton ───────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Notes",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(24, 2))
        ctk.CTkLabel(
            self,
            text="Personal notes and debt/credit tracking.",
            text_color=_TEXT_SEC,
        ).pack(anchor="w", padx=24, pady=(0, 20))

        # ══ My Notes section ══════════════════════════════════════════════════
        ctk.CTkLabel(
            self, text="My Notes",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(0, 8))

        my_notes_card = ctk.CTkFrame(
            self, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        my_notes_card.pack(fill="x", padx=24, pady=(0, 6))
        my_notes_inner = ctk.CTkFrame(my_notes_card, fg_color="transparent")
        my_notes_inner.pack(fill="x", padx=16, pady=14)

        self._my_notes_box = ctk.CTkTextbox(
            my_notes_inner, height=140, wrap="word",
            fg_color=_BG_ELEM, border_color=_BORDER,
            text_color=_TEXT_PRI, border_width=1,
        )
        self._my_notes_box.pack(fill="x")

        save_row = ctk.CTkFrame(my_notes_inner, fg_color="transparent")
        save_row.pack(anchor="e", pady=(8, 0))
        ctk.CTkButton(
            save_row, text="Save Notes", width=110,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            command=self._save_my_notes,
        ).pack(side="left", padx=(0, 10))
        self._my_notes_status = ctk.CTkLabel(
            save_row, text="", font=ctk.CTkFont(family=_F, size=12),
        )
        self._my_notes_status.pack(side="left")

        # ── Divider ───────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=_BORDER).pack(
            fill="x", padx=24, pady=(16, 20)
        )

        # ══ Debt / Credit Notes section ═══════════════════════════════════════
        ctk.CTkLabel(
            self, text="Debt / Credit Notes",
            font=ctk.CTkFont(family=_F, size=15, weight="bold"),
            text_color=_TEXT_PRI,
        ).pack(anchor="w", padx=24, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text="Purely informational — not included in any calculations.",
            text_color=_TEXT_SEC,
        ).pack(anchor="w", padx=24, pady=(0, 16))

        # ── Summary cards ─────────────────────────────────────────────────────
        summary_row = ctk.CTkFrame(self, fg_color="transparent")
        summary_row.pack(fill="x", padx=24, pady=(0, 20))
        summary_row.columnconfigure([0, 1], weight=1)

        they_card = ctk.CTkFrame(
            summary_row, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        they_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        they_inner = ctk.CTkFrame(they_card, fg_color="transparent")
        they_inner.pack(padx=16, pady=14)
        ctk.CTkLabel(
            they_inner, text="OTHERS OWE ME", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=11),
        ).pack(anchor="w")
        self._they_total = ctk.CTkLabel(
            they_inner, text="€0.00",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_GREEN,
        )
        self._they_total.pack(anchor="w", pady=(6, 0))

        i_card = ctk.CTkFrame(
            summary_row, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        i_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        i_inner = ctk.CTkFrame(i_card, fg_color="transparent")
        i_inner.pack(padx=16, pady=14)
        ctk.CTkLabel(
            i_inner, text="I OWE OTHERS", text_color=_TEXT_SEC,
            font=ctk.CTkFont(family=_F, size=11),
        ).pack(anchor="w")
        self._i_total = ctk.CTkLabel(
            i_inner, text="€0.00",
            font=ctk.CTkFont(family=_F, size=22, weight="bold"),
            text_color=_RED,
        )
        self._i_total.pack(anchor="w", pady=(6, 0))

        # ── Add note form ─────────────────────────────────────────────────────
        add_card = ctk.CTkFrame(
            self, fg_color=_BG_CARD, corner_radius=14,
            border_width=1, border_color=_BORDER,
        )
        add_card.pack(fill="x", padx=24, pady=(0, 20))

        form = ctk.CTkFrame(add_card, fg_color="transparent")
        form.pack(anchor="w", padx=16, pady=14)

        self._add_dir = ctk.CTkSegmentedButton(
            form, values=list(_DIRECTIONS.keys()), width=260,
        )
        self._add_dir.set("They owe me")
        self._add_dir.pack(side="left", padx=(0, 14))

        self._add_desc = ctk.CTkEntry(
            form, placeholder_text="Description", width=260,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
        )
        self._add_desc.pack(side="left", padx=(0, 14))
        self._add_desc.bind("<Return>", lambda _: self._add_amount_entry.focus())

        ctk.CTkLabel(
            form, text="EUR", anchor="w", text_color=_TEXT_SEC,
        ).pack(side="left", padx=(0, 4))
        self._add_amount_entry = ctk.CTkEntry(
            form, placeholder_text="0.00", width=100,
            fg_color=_BG_ELEM, border_color=_BORDER, text_color=_TEXT_PRI,
        )
        self._add_amount_entry.pack(side="left", padx=(0, 14))
        self._add_amount_entry.bind("<Return>", lambda _: self._add_note())

        ctk.CTkButton(
            form, text="Add", width=80,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            command=self._add_note,
        ).pack(side="left", padx=(0, 12))
        self._add_status = ctk.CTkLabel(form, text="")
        self._add_status.pack(side="left")

        # ── Notes list (rebuilt on refresh) ──────────────────────────────────
        self._list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._list_frame.pack(anchor="w", padx=24, fill="x", pady=(0, 32))

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        # Reload My Notes text
        saved = get_setting("my_notes") or ""
        self._my_notes_box.delete("1.0", "end")
        if saved:
            self._my_notes_box.insert("1.0", saved)

        # Reload debt/credit notes list
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._edit_status_label = None

        notes     = [dict(n) for n in get_all_notes()]
        they_owe  = [n for n in notes if n["direction"] == "they_owe"]
        i_owe     = [n for n in notes if n["direction"] == "i_owe"]

        they_sum = sum(n["amount"] for n in they_owe)
        i_sum    = sum(n["amount"] for n in i_owe)

        self._they_total.configure(text=fmt_eur(they_sum))
        self._i_total.configure(text=fmt_eur(i_sum))

        self._render_section("They owe me", they_owe, _GREEN)
        self._render_section("I owe them",  i_owe,    _RED)

    # ── My Notes save ─────────────────────────────────────────────────────────

    def _save_my_notes(self):
        content = self._my_notes_box.get("1.0", "end-1c")
        set_setting("my_notes", content)
        self._my_notes_status.configure(text="Saved.", text_color=_GREEN)
        self.after(2500, lambda: self._my_notes_status.configure(text=""))

    # ── Section rendering ─────────────────────────────────────────────────────

    def _render_section(self, title: str, notes: list[dict], colour: str):
        hdr = ctk.CTkFrame(self._list_frame, fg_color="transparent")
        hdr.pack(fill="x", pady=(12, 4))

        ctk.CTkLabel(
            hdr, text=title,
            font=ctk.CTkFont(family=_F, size=14, weight="bold"), text_color=colour,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text=f"({len(notes)})",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=13),
        ).pack(side="left", padx=(6, 0))

        ctk.CTkFrame(self._list_frame, height=1, fg_color=_BORDER).pack(
            fill="x", pady=(0, 6)
        )

        if not notes:
            ctk.CTkLabel(
                self._list_frame, text="Nothing here yet.",
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            ).pack(anchor="w", pady=(2, 8))
            return

        col_hdr = ctk.CTkFrame(self._list_frame, fg_color="transparent")
        col_hdr.pack(anchor="w", fill="x", pady=(0, 2))
        for text, width, anchor in [
            ("Description", _W_DESC, "w"),
            ("Amount",      _W_AMT,  "e"),
            ("Added",       _W_DATE, "e"),
        ]:
            ctk.CTkLabel(
                col_hdr, text=text, width=width, anchor=anchor,
                text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
            ).pack(side="left")

        for note in notes:
            if note["id"] == self._editing_id:
                self._render_edit_row(note)
            else:
                self._render_display_row(note, colour)

    def _render_display_row(self, note: dict, colour: str):
        row = ctk.CTkFrame(self._list_frame, fg_color="transparent")
        row.pack(anchor="w", fill="x", pady=2)

        date_str = _fmt_date(note["created_at"])

        ctk.CTkLabel(
            row, text=note["content"], width=_W_DESC, anchor="w",
            text_color=_TEXT_PRI,
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=fmt_eur(note["amount"]), width=_W_AMT, anchor="e",
            text_color=colour,
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=date_str, width=_W_DATE, anchor="e",
            text_color=_TEXT_SEC, font=ctk.CTkFont(family=_F, size=12),
        ).pack(side="left", padx=(0, 16))

        ctk.CTkButton(
            row, text="Edit", width=64,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=lambda nid=note["id"]: self._start_edit(nid),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            row, text="Delete", width=72,
            fg_color=_BG_ELEM, hover_color="#3d1a1a",
            text_color=_RED, corner_radius=8,
            command=lambda nid=note["id"]: self._delete(nid),
        ).pack(side="left")

    def _render_edit_row(self, note: dict):
        row = ctk.CTkFrame(
            self._list_frame,
            fg_color=_BG_ELEM, corner_radius=8,
        )
        row.pack(anchor="w", fill="x", pady=2)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(anchor="w", padx=8, pady=8)

        dir_var    = ctk.StringVar(value=_DB_TO_LABEL.get(note["direction"], "They owe me"))
        desc_var   = ctk.StringVar(value=note["content"])
        amount_var = ctk.StringVar(value=f"{note['amount']:.2f}")

        dir_btn = ctk.CTkSegmentedButton(
            inner, values=list(_DIRECTIONS.keys()),
            variable=dir_var, width=260,
        )
        dir_btn.pack(side="left", padx=(0, 10))

        ctk.CTkEntry(
            inner, textvariable=desc_var, width=260,
            fg_color="#161b22", border_color=_BORDER, text_color=_TEXT_PRI,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(inner, text="EUR", text_color=_TEXT_SEC).pack(side="left", padx=(0, 4))
        ctk.CTkEntry(
            inner, textvariable=amount_var, width=100,
            fg_color="#161b22", border_color=_BORDER, text_color=_TEXT_PRI,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            inner, text="Save", width=64,
            fg_color=_ACCENT, hover_color="#0096b4",
            text_color="white", corner_radius=8,
            command=lambda: self._save_edit(note["id"], dir_var, desc_var, amount_var),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            inner, text="Cancel", width=72,
            fg_color=_BG_ELEM, hover_color="#3d4d63",
            text_color=_TEXT_PRI, corner_radius=8,
            command=self._cancel_edit,
        ).pack(side="left", padx=(0, 8))

        self._edit_status_label = ctk.CTkLabel(inner, text="")
        self._edit_status_label.pack(side="left")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_note(self):
        label      = self._add_dir.get()
        desc       = self._add_desc.get().strip()
        amount_str = self._add_amount_entry.get().strip()

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
        self._add_desc.delete(0, "end")
        self._add_amount_entry.delete(0, "end")
        self._set_add_status(f'"{desc}" added.', error=False)
        self.refresh()

    def _start_edit(self, note_id: int):
        self._editing_id = note_id
        self.refresh()

    def _save_edit(
        self,
        note_id: int,
        dir_var: ctk.StringVar,
        desc_var: ctk.StringVar,
        amount_var: ctk.StringVar,
    ):
        desc = desc_var.get().strip()
        if not desc:
            self._set_edit_status("Description is required.", error=True)
            return
        try:
            amount = float(amount_var.get().strip())
            if amount < 0:
                raise ValueError
        except ValueError:
            self._set_edit_status("Enter a positive amount.", error=True)
            return

        direction = _DIRECTIONS.get(dir_var.get(), ("they_owe", ""))[0]
        update_note(note_id, desc, amount, direction)
        self._editing_id = None
        self.refresh()

    def _cancel_edit(self):
        self._editing_id = None
        self.refresh()

    def _delete(self, note_id: int):
        delete_note(note_id)
        if self._editing_id == note_id:
            self._editing_id = None
        self.refresh()

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_add_status(self, text: str, *, error: bool):
        color = _RED if error else _GREEN
        self._add_status.configure(text=text, text_color=color)
        if not error:
            self.after(3000, lambda: self._add_status.configure(text=""))

    def _set_edit_status(self, text: str, *, error: bool):
        if self._edit_status_label is None:
            return
        self._edit_status_label.configure(
            text=text, text_color=_RED if error else _GREEN
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at)
        return dt.strftime("%-d %b %Y")
    except Exception:
        return created_at
