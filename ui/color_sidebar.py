from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

from ui.sample_slot import SLOT_MIME_TYPE

COLORS = ["BLUE", "CYAN", "GREEN", "ORANGE", "PINK", "RED", "YELLOW"]

COLOR_MAP = {
    "BLUE":   "#1a4a8a",
    "CYAN":   "#0a7a8a",
    "GREEN":  "#1a6a2a",
    "ORANGE": "#8a4a0a",
    "PINK":   "#8a1a5a",
    "RED":    "#8a1a1a",
    "YELLOW": "#7a6a0a",
}

COLOR_TEXT = {
    "BLUE":   "#6aaaff",
    "CYAN":   "#4addf0",
    "GREEN":  "#4aee6a",
    "ORANGE": "#ffaa44",
    "PINK":   "#ff6ab0",
    "RED":    "#ff5555",
    "YELLOW": "#ffe044",
}


class ColorButton(QPushButton):
    drag_hovered = pyqtSignal(str)  # emitted after 1s hover during a drag

    def __init__(self, color_name, parent=None):
        super().__init__(parent)
        self.color_name = color_name
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAcceptDrops(True)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(1000)
        self._hover_timer.timeout.connect(lambda: self.drag_hovered.emit(self.color_name))

        bg = COLOR_MAP[color_name]
        text = COLOR_TEXT[color_name]

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {text};
                border: 1px solid {text}44;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
            }}
            QPushButton:hover {{
                background: {bg}cc;
                border: 1px solid {text}88;
            }}
            QPushButton:checked {{
                background: {bg}ff;
                border: 2px solid {text};
                color: {text};
            }}
        """)
        self.setText(color_name)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(SLOT_MIME_TYPE):
            self._hover_timer.start()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._hover_timer.stop()

    def dropEvent(self, event):
        # Drops are handled by SampleSlotWidget — just accept so dragLeave fires cleanly
        self._hover_timer.stop()
        event.ignore()


class ColorSidebarWidget(QWidget):
    color_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(110)
        self.buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(6)

        title = QLabel("BANKS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        title.setFont(font)
        title.setStyleSheet("color: #444; margin-bottom: 8px;")
        layout.addWidget(title)

        for color in COLORS:
            btn = ColorButton(color)
            btn.clicked.connect(lambda checked, c=color: self._on_click(c))
            btn.drag_hovered.connect(self._on_drag_hover)
            self.buttons[color] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Select first by default
        first = COLORS[0]
        self.buttons[first].setChecked(True)

    def _on_click(self, color):
        for name, btn in self.buttons.items():
            btn.setChecked(name == color)
        self.color_selected.emit(color)

    def _on_drag_hover(self, color):
        self._on_click(color)

    def select(self, color):
        self._on_click(color)