from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.sample_slot import SampleSlotWidget


class SampleGridWidget(QWidget):
    """Displays 4L + 4R slots for a given color + slot number."""

    sample_changed = pyqtSignal()
    slot_moved = pyqtSignal(str, int, str)  # src_color, src_slot, src_key

    def __init__(self, color, slot_num, project_ref, parent=None):
        super().__init__(parent)
        self.color = color
        self.slot_num = slot_num
        self.project_ref = project_ref
        self.slots = {}
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(5)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #1a1a1a;
            }
            QSplitter::handle:hover {
                background: #3a3a3a;
            }
            QSplitter::handle:pressed {
                background: #555;
            }
        """)

        for side in ["L", "R"]:
            side_widget = QFrame()
            side_widget.setStyleSheet("""
                QFrame {
                    background: #161616;
                    border: 1px solid #2a2a2a;
                    border-radius: 6px;
                }
            """)
            side_layout = QVBoxLayout(side_widget)
            side_layout.setContentsMargins(12, 12, 12, 12)
            side_layout.setSpacing(6)

            header = QLabel(f"{'LEFT' if side == 'L' else 'RIGHT'} PLAYHEAD")
            font = QFont()
            font.setPointSize(9)
            font.setBold(True)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
            header.setFont(font)
            header.setStyleSheet("color: #666; background: transparent; border: none;")
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            side_layout.addWidget(header)

            for i in range(4):
                key = f"{side}{i}"
                slot_widget = SampleSlotWidget(
                    self.color, self.slot_num, key, self.project_ref
                )
                slot_widget.sample_changed.connect(self.sample_changed)
                slot_widget.slot_moved.connect(self.slot_moved)
                self.slots[key] = slot_widget
                side_layout.addWidget(slot_widget)

            side_layout.addStretch()
            splitter.addWidget(side_widget)

        # Set after widgets are added so indices exist
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        main_layout.addWidget(splitter)

    def refresh(self):
        for slot in self.slots.values():
            slot.refresh()