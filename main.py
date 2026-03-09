import calendar
import os
import customtkinter as ctk
import darkdetect
from datetime import date
from PIL import Image

from database.db import init_db, get_setting, get_snapshot, get_latest_snapshots
from utils import is_scroll_locked
from views.dashboard import DashboardView
from views.snapshot_entry import SnapshotEntryView
from views.expenses import ExpensesView
from views.portfolio import PortfolioView
from views.charts import ChartsView
from views.notes import NotesView
from views.settings import SettingsView
from views.help import HelpView

# ── Premium dark theme palette ─────────────────────────────────────────────────
_BG_SIDEBAR = "#161b22"
_BG_MAIN    = "#0d1117"
_BG_CARD    = "#1a2332"
_ACCENT     = "#00b4d8"
_TEXT_PRI   = "#e6edf3"
_TEXT_SEC   = "#8b949e"
_BORDER     = "#3d4d63"
_F          = "Helvetica Neue"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Money Tracker")
        self.geometry("1100x700")
        self.minsize(900, 600)

        init_db()

        # Apply saved appearance mode (fallback: follow system)
        saved_mode = get_setting("appearance_mode") or "System"
        if saved_mode == "System":
            ctk.set_appearance_mode("dark" if darkdetect.isDark() else "light")
        else:
            ctk.set_appearance_mode(saved_mode.lower())

        ctk.set_default_color_theme("blue")

        self._active_nav_key: str | None = None
        self._build_layout()
        self._bind_global_scroll()
        self._check_startup_banner()
        self.show_view("dashboard")

    def _build_layout(self):
        # ── Sidebar ──────────────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=_BG_SIDEBAR)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # App icon image — top of sidebar
        _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Money Tracker.png")
        try:
            _img = Image.open(_icon_path)
            _ctk_img = ctk.CTkImage(light_image=_img, dark_image=_img, size=(102, 102))
            ctk.CTkLabel(
                self.sidebar, image=_ctk_img, text="",
            ).pack(pady=(16, 16))
        except Exception:
            pass

        # ── Top group: primary tabs ───────────────────────────────────────────
        nav_top = [
            ("Dashboard",        "dashboard"),
            ("Monthly Snapshot", "snapshot"),
            ("Budget",           "expenses"),
            ("Portfolio",        "portfolio"),
            ("Analytics",        "charts"),
        ]
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for label, key in nav_top:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent",
                text_color=_TEXT_SEC,
                hover_color=_BG_CARD,
                font=ctk.CTkFont(family=_F, size=13),
                corner_radius=8,
                command=lambda k=key: self.show_view(k),
            )
            btn.pack(padx=12, pady=3, fill="x")
            self._nav_buttons[key] = btn
            self._bind_nav_hover(btn, key)

        # ── Divider 1 ─────────────────────────────────────────────────────────
        ctk.CTkFrame(self.sidebar, height=1, fg_color=_BORDER).pack(
            fill="x", padx=12, pady=(10, 8)
        )

        # ── Middle group: content tabs ────────────────────────────────────────
        nav_mid = [
            ("Notes", "notes"),
            ("Help",  "help"),
        ]
        for label, key in nav_mid:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent",
                text_color=_TEXT_SEC,
                hover_color=_BG_CARD,
                font=ctk.CTkFont(family=_F, size=13),
                corner_radius=8,
                command=lambda k=key: self.show_view(k),
            )
            btn.pack(padx=12, pady=3, fill="x")
            self._nav_buttons[key] = btn
            self._bind_nav_hover(btn, key)

        # ── Divider 2 ─────────────────────────────────────────────────────────
        ctk.CTkFrame(self.sidebar, height=1, fg_color=_BORDER).pack(
            fill="x", padx=12, pady=(10, 8)
        )

        # ── Bottom group: Settings ────────────────────────────────────────────
        for label, key in [("Settings", "settings")]:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent",
                text_color=_TEXT_SEC,
                hover_color=_BG_CARD,
                font=ctk.CTkFont(family=_F, size=13),
                corner_radius=8,
                command=lambda k=key: self.show_view(k),
            )
            btn.pack(padx=12, pady=3, fill="x")
            self._nav_buttons[key] = btn
            self._bind_nav_hover(btn, key)

        # Flexible spacer — pushes Exit to the very bottom
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Exit App button — always anchored to the bottom
        ctk.CTkButton(
            self.sidebar, text="Exit", anchor="w",
            fg_color="transparent",
            text_color="#FF4444",
            hover_color=("#ffcccc", "#5a1a1a"),
            font=ctk.CTkFont(family=_F, size=13),
            corner_radius=8,
            command=lambda: (self.quit(), self.destroy()),
        ).pack(padx=12, pady=(0, 16), fill="x")

        # ── Content area ─────────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG_MAIN)
        self.content.pack(side="right", fill="both", expand=True)

        # Banner frame — packed at top when a reminder is active; hidden otherwise
        self._banner_frame: ctk.CTkFrame | None = None

        # View container — sits below the banner and holds all tab views
        self._view_container = ctk.CTkFrame(self.content, corner_radius=0, fg_color=_BG_MAIN)
        self._view_container.pack(fill="both", expand=True)

        self._views: dict[str, ctk.CTkFrame] = {}
        self._view_classes = {
            "dashboard": lambda parent: DashboardView(parent, navigate=self.show_view),
            "snapshot":  SnapshotEntryView,
            "expenses":  ExpensesView,
            "portfolio": PortfolioView,
            "charts":    ChartsView,
            "notes":     NotesView,
            "settings":  SettingsView,
            "help":      HelpView,
        }

    def _bind_nav_hover(self, btn: ctk.CTkButton, key: str):
        def on_enter(e):
            if self._active_nav_key != key:
                btn.configure(text_color=_TEXT_PRI)

        def on_leave(e):
            if self._active_nav_key != key:
                btn.configure(text_color=_TEXT_SEC)

        btn.bind("<Enter>", on_enter, add="+")
        btn.bind("<Leave>", on_leave, add="+")

    def _bind_global_scroll(self):
        def on_scroll(event):
            if is_scroll_locked():
                return
            w = event.widget
            while w is not None:
                if isinstance(w, ctk.CTkScrollableFrame):
                    if event.widget is getattr(w, "_parent_canvas", None):
                        return
                    try:
                        canvas    = w._parent_canvas
                        scroll_up = (hasattr(event, "delta") and event.delta > 0) or (getattr(event, "num", 0) == 4)
                        # Block upward scroll when already at the top
                        if scroll_up and canvas.yview()[0] <= 0:
                            return
                        if hasattr(event, "delta") and event.delta:
                            canvas.yview_scroll(-3 if event.delta > 0 else 3, "units")
                        elif event.num == 4:
                            canvas.yview_scroll(-3, "units")
                        elif event.num == 5:
                            canvas.yview_scroll(3, "units")
                        # Clamp: prevent over-scrolling above the top boundary
                        if canvas.yview()[0] < 0:
                            canvas.yview_moveto(0)
                    except Exception:
                        pass
                    return
                w = getattr(w, "master", None)
        self.bind_all("<MouseWheel>", on_scroll)
        self.bind_all("<Button-4>", on_scroll)
        self.bind_all("<Button-5>", on_scroll)

    def _check_startup_banner(self):
        if get_setting("notif_enabled") != "1":
            return
        today = date.today()
        try:
            banner_days = int(get_setting("banner_days") or "7")
        except ValueError:
            banner_days = 7
        last_day  = calendar.monthrange(today.year, today.month)[1]
        days_left = last_day - today.day
        if days_left > banner_days:
            return
        if get_snapshot(today.year, today.month) is not None:
            return

        month_name = today.strftime("%B")
        snaps = get_latest_snapshots(1)
        if snaps:
            s = snaps[0]
            from calendar import month_name as _mnames
            prev_label = f"{_mnames[s['month']]} {s['year']}"
        else:
            prev_label = "none"

        self._show_startup_banner(month_name, days_left, prev_label)

    def _show_startup_banner(self, month_name: str, days_left: int, prev_label: str):
        if self._banner_frame is not None:
            return
        self._banner_frame = ctk.CTkFrame(
            self.content, fg_color="#3d3000", corner_radius=0,
        )
        self._banner_frame.pack(fill="x", before=self._view_container)

        inner = ctk.CTkFrame(self._banner_frame, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=8)

        text = (
            f"⚠  {month_name} ending in {days_left} day{'s' if days_left != 1 else ''} — "
            f"last snapshot was {prev_label}.  Click here to go to Monthly Snapshot →"
        )
        lbl = ctk.CTkLabel(
            inner, text=text,
            font=ctk.CTkFont(family=_F, size=13),
            text_color="#f0c040", cursor="hand2",
        )
        lbl.pack(side="left")
        lbl.bind("<Button-1>", lambda _e: self.show_view("snapshot"))

        def dismiss():
            if self._banner_frame:
                self._banner_frame.pack_forget()
                self._banner_frame.destroy()
                self._banner_frame = None

        ctk.CTkButton(
            inner, text="×", width=28, height=28,
            fg_color="transparent", hover_color="#5a4500",
            text_color="#f0c040", corner_radius=6,
            font=ctk.CTkFont(family=_F, size=16),
            command=dismiss,
        ).pack(side="right")

    def show_view(self, name: str):
        if name not in self._views:
            self._views[name] = self._view_classes[name](self._view_container)

        for v in self._views.values():
            v.pack_forget()

        view = self._views[name]
        view.pack(fill="both", expand=True)
        view.update_idletasks()  # Force immediate render (prevents blank tab on click)
        if hasattr(view, "refresh"):
            view.refresh()

        # Highlight the active nav button
        self._active_nav_key = name
        for key, btn in self._nav_buttons.items():
            is_active = key == name
            btn.configure(
                fg_color=_ACCENT if is_active else "transparent",
                hover_color=_ACCENT if is_active else _BG_CARD,
                text_color="white" if is_active else _TEXT_SEC,
            )

        # Subtle fade-in on content frame background
        self._fade_step(0)

    def _fade_step(self, step: int):
        _colors = ["#050a12", "#080f1a", "#0b131e", "#0d1117", "#0d1117"]
        if step < len(_colors):
            try:
                self.content.configure(fg_color=_colors[step])
            except Exception:
                pass
            self.after(20, lambda s=step: self._fade_step(s + 1))
        else:
            try:
                self.content.configure(fg_color=_BG_MAIN)
            except Exception:
                pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
