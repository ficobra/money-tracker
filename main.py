import os
import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QSizePolicy,
)
from PyQt6.QtGui import QPixmap, QPalette, QColor, QFont
from PyQt6.QtCore import Qt
from typing import Callable

from database.db import init_db
from styles.theme import get_stylesheet, register_fonts, BG_MAIN, FONT
from views.dashboard import DashboardView
from views.charts import ChartsView
from views.snapshot_entry import SnapshotEntryView
from views.expenses import ExpensesView
from views.portfolio import PortfolioView
from views.notes import NotesView
from views.settings import SettingsView
from views.help import HelpView

register_fonts()


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Money Tracker")
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)

        init_db()

        self._active_nav_key: str | None = None
        self._nav_buttons: dict[str, QPushButton] = {}
        self._nav_labels: dict[str, str] = {
            "dashboard": "Dashboard",
            "snapshot":  "Monthly Snapshot",
            "expenses":  "Budget",
            "portfolio": "Portfolio",
            "charts":    "Analytics",
            "notes":     "Notes",
            "help":      "Help",
            "settings":  "Settings",
        }
        self._views: dict[str, QWidget] = {}
        self._view_classes: dict[str, Callable[[], QWidget]] = {
            "dashboard": lambda: DashboardView(self.show_view),
            "snapshot":  lambda: SnapshotEntryView(navigate_callback=self.show_view),
            "expenses":  ExpensesView,
            "portfolio": PortfolioView,
            "charts":    ChartsView,
            "notes":     NotesView,
            "settings":  SettingsView,
            "help":      HelpView,
        }

        self._build_layout()
        self.show_view("dashboard")

    def _build_layout(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("QWidget#sidebar { background: #060c15; border-right: 1px solid #0f1e30; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 16)
        sidebar_layout.setSpacing(0)

        # ── Logo area ─────────────────────────────────────────────────────────
        logo_area = QWidget()
        logo_area.setFixedHeight(80)
        logo_area.setStyleSheet("background: transparent;")
        logo_h = QHBoxLayout(logo_area)
        logo_h.setContentsMargins(16, 12, 16, 12)
        logo_h.setSpacing(10)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Money Tracker.png")
        logo_lbl = QLabel()
        logo_lbl.setStyleSheet(
            "border: none;"
            "background: #111d2e;"
            "border-radius: 10px;"
            "padding: 4px;"
        )
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_lbl.setPixmap(pix)
        logo_h.addWidget(logo_lbl)

        app_name_col = QWidget()
        app_name_col.setStyleSheet("background: transparent;")
        app_name_v = QVBoxLayout(app_name_col)
        app_name_v.setContentsMargins(0, 0, 0, 0)
        app_name_v.setSpacing(1)
        name_lbl = QLabel("Money Tracker")
        name_lbl.setFont(QFont(FONT, 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #e7eef7; background: transparent; border: none;")
        ver_lbl = QLabel("v1.6")
        ver_lbl.setFont(QFont(FONT, 10))
        ver_lbl.setStyleSheet("color: #6b7d94; background: transparent; border: none;")
        app_name_v.addWidget(name_lbl)
        app_name_v.addWidget(ver_lbl)
        logo_h.addWidget(app_name_col, stretch=1)
        sidebar_layout.addWidget(logo_area)

        # Separator below logo
        logo_sep = QFrame()
        logo_sep.setFixedHeight(1)
        logo_sep.setStyleSheet("background: #0f1e30; border: none;")
        sidebar_layout.addWidget(logo_sep)

        # ── Top nav group ─────────────────────────────────────────────────────
        for key in ("dashboard", "snapshot", "expenses", "portfolio", "charts"):
            sidebar_layout.addWidget(self._make_nav_btn(key))

        sidebar_layout.addWidget(self._make_divider())

        # ── Middle nav group ──────────────────────────────────────────────────
        for key in ("notes", "help"):
            sidebar_layout.addWidget(self._make_nav_btn(key))

        sidebar_layout.addWidget(self._make_divider())

        # ── Bottom nav group ──────────────────────────────────────────────────
        sidebar_layout.addWidget(self._make_nav_btn("settings"))

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sidebar_layout.addWidget(spacer)

        # Exit button
        exit_btn = QPushButton("Exit")
        exit_btn.setFixedHeight(36)
        exit_btn.setFont(QFont(FONT, 13))
        exit_btn.setStyleSheet(
            "QPushButton {"
            " background: transparent;"
            " border: 1px solid rgba(248,81,73,0.3);"
            " border-radius: 8px;"
            " color: #f85149;"
            " font-size: 13px;"
            " padding: 8px 16px;"
            " margin: 0px 12px;"
            " text-align: center;"
            "}"
            " QPushButton:hover {"
            " background: rgba(248,81,73,0.08);"
            " border-color: #f85149;"
            "}"
        )
        exit_btn.clicked.connect(QApplication.quit)
        sidebar_layout.addWidget(exit_btn)

        root_layout.addWidget(sidebar)

        # ── Content area ──────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BG_MAIN};")
        root_layout.addWidget(self._stack)

    _NAV_INACTIVE = (
        "QPushButton {"
        " background: transparent;"
        " border: none;"
        " color: #6b7d94;"
        " font-size: 13px; font-weight: 400;"
        " padding: 9px 16px;"
        " text-align: left;"
        " margin: 0px 8px;"
        "}"
        " QPushButton:hover {"
        " background: rgba(255,255,255,0.04);"
        " color: #9fb0c5;"
        "}"
    )
    _NAV_ACTIVE = (
        "QPushButton {"
        " background: #0d1f35;"
        " border: none;"
        " border-radius: 8px;"
        " color: #00b4d8;"
        " font-size: 13px; font-weight: 600;"
        " padding: 9px 16px;"
        " text-align: left;"
        " margin: 0px 8px;"
        "}"
        " QPushButton:hover {"
        " background: #112440;"
        " color: #00d4ff;"
        "}"
    )

    def _make_nav_btn(self, key: str) -> QPushButton:
        btn = QPushButton(self._nav_labels[key])
        btn.setFixedHeight(40)
        btn.setFont(QFont(FONT, 13))
        btn.setStyleSheet(self._NAV_INACTIVE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, k=key: self.show_view(k))
        self._nav_buttons[key] = btn
        return btn

    def _make_divider(self) -> QWidget:
        spacer = QWidget()
        spacer.setFixedHeight(16)
        spacer.setStyleSheet("background: transparent;")
        return spacer

    def show_view(self, name: str):
        if name not in self._view_classes:
            return

        if name not in self._views:
            view = self._view_classes[name]()
            self._views[name] = view
            self._stack.addWidget(view)

        self._stack.setCurrentWidget(self._views[name])

        view = self._views[name]
        refresh = getattr(view, "refresh", None)
        if callable(refresh):
            refresh()

        self._active_nav_key = name
        for k, btn in self._nav_buttons.items():
            is_active = k == name
            btn.setText(self._nav_labels[k])
            btn.setStyleSheet(self._NAV_ACTIVE if is_active else self._NAV_INACTIVE)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#00b4d8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseStyleSheetPropagationInWidgetStyles, True)

    app.setStyleSheet(get_stylesheet())

    window = App()
    window.show()
    sys.exit(app.exec())
