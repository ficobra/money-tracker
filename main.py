import customtkinter as ctk
import darkdetect

from database.db import init_db, get_setting
from views.dashboard import DashboardView
from views.snapshot_entry import SnapshotEntryView
from views.expenses import ExpensesView
from views.charts import ChartsView
from views.notes import NotesView
from views.settings import SettingsView
from views.help import HelpView


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

        self._build_layout()
        self._bind_global_scroll()
        self.show_view("dashboard")

    def _build_layout(self):
        # ── Sidebar ──────────────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="Money Tracker",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(pady=(28, 20), padx=16)

        # Main navigation tabs (top section)
        nav_top = [
            ("Dashboard",        "dashboard"),
            ("Monthly Snapshot", "snapshot"),
            ("Budget",           "expenses"),
            ("Charts",           "charts"),
            ("Notes",            "notes"),
        ]
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for label, key in nav_top:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                command=lambda k=key: self.show_view(k),
            )
            btn.pack(padx=12, pady=3, fill="x")
            self._nav_buttons[key] = btn

        # Divider between main tabs and utility tabs
        ctk.CTkFrame(self.sidebar, height=1, fg_color=("gray75", "gray35")).pack(
            fill="x", padx=12, pady=(12, 8)
        )

        # Utility tabs (bottom section)
        nav_bottom = [
            ("Settings", "settings"),
            ("Help",     "help"),
        ]
        for label, key in nav_bottom:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                command=lambda k=key: self.show_view(k),
            )
            btn.pack(padx=12, pady=3, fill="x")
            self._nav_buttons[key] = btn

        # ── Content area ─────────────────────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0)
        self.content.pack(side="right", fill="both", expand=True)

        self._views: dict[str, ctk.CTkFrame] = {}
        self._view_classes = {
            "dashboard": lambda parent: DashboardView(parent, navigate=self.show_view),
            "snapshot":  SnapshotEntryView,
            "expenses":  ExpensesView,
            "charts":    ChartsView,
            "notes":     NotesView,
            "settings":  SettingsView,
            "help":      HelpView,
        }

    def _bind_global_scroll(self):
        def on_scroll(event):
            w = event.widget
            while w is not None:
                if isinstance(w, ctk.CTkScrollableFrame):
                    if event.widget is getattr(w, "_parent_canvas", None):
                        return
                    try:
                        if hasattr(event, "delta") and event.delta:
                            w._parent_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                        elif event.num == 4:
                            w._parent_canvas.yview_scroll(-1, "units")
                        elif event.num == 5:
                            w._parent_canvas.yview_scroll(1, "units")
                    except Exception:
                        pass
                    return
                w = getattr(w, "master", None)
        self.bind_all("<MouseWheel>", on_scroll)
        self.bind_all("<Button-4>", on_scroll)
        self.bind_all("<Button-5>", on_scroll)

    def show_view(self, name: str):
        if name not in self._views:
            self._views[name] = self._view_classes[name](self.content)

        for v in self._views.values():
            v.pack_forget()

        view = self._views[name]
        view.pack(fill="both", expand=True)
        view.update_idletasks()  # Force immediate render (prevents blank tab on click)
        if hasattr(view, "refresh"):
            view.refresh()

        # Highlight the active nav button
        active_color = ("gray75", "gray30")
        for key, btn in self._nav_buttons.items():
            btn.configure(fg_color=active_color if key == name else "transparent")


if __name__ == "__main__":
    app = App()
    app.mainloop()
