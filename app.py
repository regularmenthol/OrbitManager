import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                              QStackedWidget, QLabel, QFileDialog,
                              QMessageBox, QInputDialog, QStatusBar,
                              QToolBar, QSizePolicy)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap, QPainter, QColor, QPen, QBrush

from core.project import Project, COLORS
from ui.color_sidebar import ColorSidebarWidget
from ui.slot_tabs import SlotTabsWidget

SETTINGS_LAST_PROJECT = "last_project_path"
SETTINGS_LAST_IMPORT_DIR = "last_import_dir"


def _make_icon(symbol: str, color: str = "#aaaaaa", size: int = 28) -> QIcon:
    """Draw a simple text/symbol icon onto a pixmap."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(color))
    font = QFont()
    font.setPointSize(14)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    p.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_ref = [None]
        self.tab_widgets = {}
        self.settings = QSettings("VenusInstruments", "OrbitManager")

        self.setWindowTitle("Orbit Sample Manager")
        self.resize(1024, 768)
        self._apply_dark_theme()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

        # Auto-load last project
        self._load_last_project()

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #0f0f0f;
            }
            QWidget {
                background: #0f0f0f;
                color: #dddddd;
                font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif;
            }
            QMenuBar {
                background: #141414;
                color: #888888;
                border-bottom: 1px solid #222;
                padding: 2px;
                font-size: 12px;
            }
            QMenuBar::item:selected {
                background: #2a2a2a;
                color: #eeeeee;
            }
            QMenu {
                background: #1a1a1a;
                border: 1px solid #333;
                color: #dddddd;
            }
            QMenu::item:selected {
                background: #2a2a2a;
            }
            QToolBar {
                background: #141414;
                border-bottom: 1px solid #222;
                spacing: 4px;
                padding: 4px 8px;
            }
            QToolBar QToolButton {
                background: #1e1e1e;
                color: #aaaaaa;
                border: 1px solid #2a2a2a;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
                min-width: 80px;
            }
            QToolBar QToolButton:hover {
                background: #282828;
                color: #eeeeee;
                border-color: #3a3a3a;
            }
            QToolBar QToolButton:pressed {
                background: #333333;
            }
            QToolBar::separator {
                background: #2a2a2a;
                width: 1px;
                margin: 4px 6px;
            }
            QStatusBar {
                background: #141414;
                color: #555;
                border-top: 1px solid #1a1a1a;
                font-size: 10px;
            }
        """)

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        new_action = QAction("New Project", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Open Project…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Save Project", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        import_action = QAction("Import from SD Card…", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._import_from_sd)
        file_menu.addAction(import_action)

        export_action = QAction("Export to SD Card…", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_to_sd)
        file_menu.addAction(export_action)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        new_action = QAction(_make_icon("✦", "#6699ff"), "  New", self)
        new_action.setToolTip("New Project  (Ctrl+N)")
        new_action.triggered.connect(self._new_project)
        toolbar.addAction(new_action)

        toolbar.addSeparator()

        open_action = QAction(_make_icon("⏏", "#66bbff"), "  Open", self)
        open_action.setToolTip("Open Project  (Ctrl+O)")
        open_action.triggered.connect(self._open_project)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        save_action = QAction(_make_icon("⬡", "#66ffaa"), "  Save", self)
        save_action.setToolTip("Save Project  (Ctrl+S)")
        save_action.triggered.connect(self._save_project)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        self._import_sd_action = QAction(_make_icon("⇩", "#ffaa44"), "  Import SD", self)
        self._import_sd_action.setToolTip("Import from SD Card  (Ctrl+I)")
        self._import_sd_action.triggered.connect(self._import_from_sd)
        self._import_sd_action.setEnabled(False)
        toolbar.addAction(self._import_sd_action)

        toolbar.addSeparator()

        self._export_sd_action = QAction(_make_icon("⇧", "#ff8844"), "  Export SD", self)
        self._export_sd_action.setToolTip("Export to SD Card  (Ctrl+E)")
        self._export_sd_action.triggered.connect(self._export_to_sd)
        self._export_sd_action.setEnabled(False)
        toolbar.addAction(self._export_sd_action)

        # Push project name label to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)

        self.project_label = QLabel("No project open")
        self.project_label.setStyleSheet("""
            color: #444;
            font-size: 11px;
            background: transparent;
            padding-right: 8px;
        """)
        toolbar.addWidget(self.project_label)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        self.sidebar = ColorSidebarWidget()
        self.sidebar.color_selected.connect(self._on_color_selected)
        root_layout.addWidget(self.sidebar)

        # Divider
        divider = QWidget()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background: #1e1e1e;")
        root_layout.addWidget(divider)

        # Main area
        self.main_area = QWidget()
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Stacked widget
        self.stack = QStackedWidget()

        # Empty state
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label = QLabel(
            "Open or create a project to get started\n\n"
            "Use the toolbar buttons above  ·  or  File → New / Open"
        )
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        empty_layout.addWidget(empty_label)
        self.stack.addWidget(empty)  # index 0

        self.color_stack = QStackedWidget()
        self.stack.addWidget(self.color_stack)  # index 1

        main_layout.addWidget(self.stack)
        root_layout.addWidget(self.main_area, 1)

    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def _build_color_tabs(self):
        self.tab_widgets = {}
        while self.color_stack.count():
            w = self.color_stack.widget(0)
            self.color_stack.removeWidget(w)
            w.deleteLater()

        for color in COLORS:
            tabs = SlotTabsWidget(color, self.project_ref)
            tabs.sample_changed.connect(self._on_sample_changed)
            tabs.slot_moved.connect(self._on_slot_moved)
            self.tab_widgets[color] = tabs
            self.color_stack.addWidget(tabs)

        self._import_sd_action.setEnabled(True)
        self._export_sd_action.setEnabled(True)

    def _import_from_sd(self):
        if not self.project_ref[0]:
            QMessageBox.warning(self, "No Project", "Please open or create a project first.")
            return
        from ui.sd_import_dialog import SdImportDialog
        dlg = SdImportDialog(self.project_ref[0], self)
        dlg.import_complete.connect(self._on_import_complete)
        dlg.exec()

    def _on_import_complete(self):
        for tabs in self.tab_widgets.values():
            tabs.refresh()
        self.status.showMessage("SD import complete  ✓", 4000)

    def _export_to_sd(self):
        if not self.project_ref[0]:
            QMessageBox.warning(self, "No Project", "Please open or create a project first.")
            return
        from ui.sd_export_dialog import SdExportDialog
        dlg = SdExportDialog(self.project_ref[0], self)
        dlg.export_complete.connect(lambda: self.status.showMessage("SD export complete  ✓", 4000))
        dlg.exec()

    def _on_color_selected(self, color):
        if not self.project_ref[0]:
            return
        idx = COLORS.index(color)
        self.color_stack.setCurrentIndex(idx)

    def _on_sample_changed(self):
        self.status.showMessage("Saved  ✓", 3000)

    def _on_slot_moved(self, src_color, src_slot, src_key):
        """Refresh the source slot in whichever color tab it belongs to."""
        tabs = self.tab_widgets.get(src_color)
        if tabs:
            grid = tabs.grids.get(src_slot)
            if grid:
                slot_widget = grid.slots.get(src_key)
                if slot_widget:
                    slot_widget.refresh()
            tabs._tab_bar.update()

    def _load_last_project(self):
        last = self.settings.value(SETTINGS_LAST_PROJECT, "")
        if last and os.path.isdir(last):
            proj = Project.load(last)
            if proj:
                self.project_ref[0] = proj
                self._build_color_tabs()
                self.stack.setCurrentIndex(1)
                self._update_project_label(proj)
                self.sidebar.select(COLORS[0])
                for tabs in self.tab_widgets.values():
                    tabs.refresh()
                self.status.showMessage(f"Restored: {last}")

    def get_last_import_dir(self) -> str:
        return self.settings.value(SETTINGS_LAST_IMPORT_DIR, "")

    def set_last_import_dir(self, path: str):
        self.settings.setValue(SETTINGS_LAST_IMPORT_DIR, path)

    def _update_project_label(self, proj):
        name = proj.project_name
        path = proj.project_path
        self.project_label.setText(f"{name}  ·  {path}")
        self.project_label.setStyleSheet("""
            color: #666;
            font-size: 11px;
            background: transparent;
            padding-right: 8px;
        """)

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose project folder")
        if not folder:
            return

        proj_folder = os.path.join(folder, name.strip().replace(" ", "_"))
        proj = Project()
        proj.project_name = name.strip()
        proj.project_path = proj_folder
        proj.save()

        self.project_ref[0] = proj
        self._build_color_tabs()
        self.stack.setCurrentIndex(1)
        self._update_project_label(proj)
        self.sidebar.select(COLORS[0])
        self.settings.setValue(SETTINGS_LAST_PROJECT, proj_folder)
        self.status.showMessage(f"Project created: {proj_folder}")

    def _open_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Open project folder")
        if not folder:
            return
        proj = Project.load(folder)
        if not proj:
            QMessageBox.warning(self, "Error", "No valid project.json found in that folder.")
            return

        self.project_ref[0] = proj
        self._build_color_tabs()
        self.stack.setCurrentIndex(1)
        self._update_project_label(proj)
        self.sidebar.select(COLORS[0])
        self.settings.setValue(SETTINGS_LAST_PROJECT, folder)

        for tabs in self.tab_widgets.values():
            tabs.refresh()

        self.status.showMessage(f"Opened: {folder}")

    def _save_project(self):
        if self.project_ref[0]:
            self.project_ref[0].save()
            self.status.showMessage("Saved  ✓", 3000)
        else:
            self.status.showMessage("No project open", 2000)