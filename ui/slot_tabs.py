from PyQt6.QtWidgets import QTabWidget, QTabBar
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont

from core.project import SIDES, INDICES
from ui.sample_grid import SampleGridWidget
from ui.sample_slot import SLOT_MIME_TYPE

COLOR_TAB = {
    "BLUE":   ("#1a3a6a", "#4488ff"),
    "CYAN":   ("#0a5a6a", "#22ccee"),
    "GREEN":  ("#1a4a2a", "#44dd66"),
    "ORANGE": ("#5a3a0a", "#ffaa33"),
    "PINK":   ("#5a1a4a", "#ff66bb"),
    "RED":    ("#5a1a1a", "#ff4444"),
    "YELLOW": ("#4a420a", "#ffdd22"),
}


class ColoredTabBar(QTabBar):
    """Custom tab bar — paints populated slots with the bank's color."""

    def __init__(self, color, project_ref, parent=None):
        super().__init__(parent)
        self.color = color
        self.project_ref = project_ref
        dim, bright = COLOR_TAB.get(color, ("#1a1a1a", "#aaaaaa"))
        self._dim = QColor(dim)
        self._bright = QColor(bright)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setAcceptDrops(True)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(1000)
        self._hover_tab_index = -1
        self._hover_timer.timeout.connect(self._on_hover_timeout)

    def _is_populated(self, slot_num: int) -> bool:
        proj = self.project_ref[0]
        if not proj:
            return False
        for side in SIDES:
            for idx in INDICES:
                if proj.get_sample(self.color, slot_num, f"{side}{idx}"):
                    return True
        return False

    def tabSizeHint(self, index):
        s = super().tabSizeHint(index)
        s.setWidth(max(s.width(), 72))
        s.setHeight(28)
        return s

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        current = self.currentIndex()

        for i in range(self.count()):
            rect = self.tabRect(i)
            populated = self._is_populated(i)
            is_current = (i == current)
            is_hover_target = (i == self._hover_tab_index)

            if populated:
                bg = self._dim.lighter(160) if is_current else self._dim
                fg = QColor("#ffffff") if is_current else self._bright
                border_color = self._bright
            else:
                bg = QColor("#2e2e2e") if is_current else QColor("#1a1a1a")
                fg = QColor("#ffffff") if is_current else QColor("#555555")
                border_color = QColor("#555555") if is_current else QColor("#252525")

            # Highlight tab being hovered during a drag
            if is_hover_target and not is_current:
                bg = bg.lighter(140)
                border_color = QColor("#888888")

            draw_rect = rect.adjusted(1, 1, -1, 0)

            painter.setPen(QPen(border_color, 1))
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(draw_rect, 4, 4)

            painter.setPen(fg)
            font = QFont()
            font.setPointSize(9)
            font.setBold(is_current or populated)
            painter.setFont(font)
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, self.tabText(i))

        painter.end()

    def _tab_at(self, pos):
        for i in range(self.count()):
            if self.tabRect(i).contains(pos):
                return i
        return -1

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(SLOT_MIME_TYPE):
            event.acceptProposedAction()
            idx = self._tab_at(event.position().toPoint())
            self._start_hover(idx)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(SLOT_MIME_TYPE):
            event.acceptProposedAction()
            idx = self._tab_at(event.position().toPoint())
            if idx != self._hover_tab_index:
                self._start_hover(idx)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._stop_hover()

    def dropEvent(self, event):
        # Drops handled by SampleSlotWidget
        self._stop_hover()
        event.ignore()

    def _start_hover(self, idx):
        self._hover_timer.stop()
        self._hover_tab_index = idx
        self.update()
        if idx >= 0:
            self._hover_timer.start()

    def _stop_hover(self):
        self._hover_timer.stop()
        self._hover_tab_index = -1
        self.update()

    def _on_hover_timeout(self):
        idx = self._hover_tab_index
        self._hover_tab_index = -1
        self.update()
        if idx >= 0:
            parent = self.parent()
            if parent and hasattr(parent, 'setCurrentIndex'):
                parent.setCurrentIndex(idx)

    def _switch_to(self, idx):
        self._hover_tab_index = -1
        self.update()
        parent = self.parent()
        if parent and hasattr(parent, 'setCurrentIndex'):
            parent.setCurrentIndex(idx)


class SlotTabsWidget(QTabWidget):
    sample_changed = pyqtSignal()
    slot_moved = pyqtSignal(str, int, str)  # bubble up to app level

    def __init__(self, color, project_ref, parent=None):
        super().__init__(parent)
        self.color = color
        self.project_ref = project_ref
        self.grids = {}

        # IMPORTANT: set custom tab bar BEFORE adding any tabs
        self._tab_bar = ColoredTabBar(color, project_ref, self)
        self.setTabBar(self._tab_bar)

        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2a2a2a;
                background: #111111;
                border-radius: 0 4px 4px 4px;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
        """)

        for slot_num in range(8):
            grid = SampleGridWidget(color, slot_num, project_ref)
            grid.sample_changed.connect(self._on_grid_changed)
            grid.slot_moved.connect(self._on_slot_moved)
            self.grids[slot_num] = grid
            self.addTab(grid, f"SLOT {slot_num}")

    def _on_slot_moved(self, src_color, src_slot, src_key):
        """Refresh the source slot widget if it lives in this color's tabs."""
        if src_color == self.color:
            grid = self.grids.get(src_slot)
            if grid:
                slot_widget = grid.slots.get(src_key)
                if slot_widget:
                    slot_widget.refresh()
        # Always bubble up so app.py can handle cross-color moves
        self.slot_moved.emit(src_color, src_slot, src_key)
        self._tab_bar.update()

    def _on_grid_changed(self):
        self._tab_bar.update()
        self.sample_changed.emit()

    def refresh(self):
        for grid in self.grids.values():
            grid.refresh()
        self._tab_bar.update()