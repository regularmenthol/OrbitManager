"""
SD Card Export Dialog

Shows what samples exist in the current project and lets the user
select which ones to write to an SD card folder.

Structure written:
  <sd_root>/COLOR/COLOR_SLOTn_Lm.wav  (and Rm)

Conflicts (file already on SD card) are asked one by one.
"""

import os
import shutil

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QScrollArea, QWidget, QCheckBox, QFrame,
    QMessageBox, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from core.project import COLORS, SLOTS, SIDES, INDICES

# Shared color constants
COLOR_ACCENT = {
    "BLUE":   "#4488ff",
    "CYAN":   "#22ccee",
    "GREEN":  "#44dd66",
    "ORANGE": "#ffaa33",
    "PINK":   "#ff66bb",
    "RED":    "#ff4444",
    "YELLOW": "#ffdd22",
}

COLOR_DIM = {
    "BLUE":   "#1a3a6a",
    "CYAN":   "#0a5a6a",
    "GREEN":  "#1a4a2a",
    "ORANGE": "#5a3a0a",
    "PINK":   "#5a1a4a",
    "RED":    "#5a1a1a",
    "YELLOW": "#4a420a",
}

UNCHECKED = Qt.CheckState.Unchecked
PARTIAL   = Qt.CheckState.PartiallyChecked
CHECKED   = Qt.CheckState.Checked


def _tri(checked_count, total):
    if checked_count == 0:     return UNCHECKED
    if checked_count == total: return CHECKED
    return PARTIAL


# ── Export worker ──────────────────────────────────────────────────────────────

class ExportWorker(QThread):
    progress  = pyqtSignal(int, int)           # done, total
    conflict  = pyqtSignal(str, int, str, str) # color, slot, key, dest_path
    finished_ok  = pyqtSignal(int)
    finished_err = pyqtSignal(str)

    def __init__(self, project, sd_root, selections, parent=None):
        super().__init__(parent)
        self.project    = project
        self.sd_root    = sd_root
        # selections: list of (color, slot, key)
        self.selections = selections
        self._resolution = None

    def resolve(self, overwrite: bool):
        self._resolution = overwrite

    def run(self):
        exported = 0
        total = len(self.selections)

        for i, (color, slot, key) in enumerate(self.selections):
            self.progress.emit(i, total)

            sample = self.project.get_sample(color, slot, key)
            if not sample:
                continue

            src_filename = sample.get("project_filename", "")
            src_path = os.path.join(self.project.project_path, color, src_filename)
            if not os.path.isfile(src_path):
                continue

            dest_dir  = os.path.join(self.sd_root, color)
            dest_filename = f"{color}_SLOT{slot}_{key}.wav"
            dest_path = os.path.join(dest_dir, dest_filename)

            # Check for conflict on SD card
            if os.path.isfile(dest_path):
                self._resolution = None
                self.conflict.emit(color, slot, key, dest_path)
                while self._resolution is None:
                    self.msleep(50)
                if not self._resolution:
                    continue   # skip

            try:
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                exported += 1
            except Exception as e:
                self.finished_err.emit(str(e))
                return

        self.progress.emit(total, total)
        self.finished_ok.emit(exported)


# ── Main dialog ────────────────────────────────────────────────────────────────

class SdExportDialog(QDialog):
    export_complete = pyqtSignal()

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Export to SD Card")
        self.setMinimumSize(660, 680)
        self.resize(740, 760)
        self._sd_root = None

        self._color_checks  = {}
        self._slot_checks   = {}
        self._sample_checks = {}

        self._setup_ui()
        self._apply_style()
        self._build_tree()   # tree reflects project, built immediately

    # ── Styles ────────────────────────────────────────────────────────────────

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog, QWidget { background: #111111; color: #dddddd; }
            QScrollArea { border: none; background: #111111; }
            QLabel { background: transparent; }
            QPushButton {
                background: #1e1e1e; color: #aaaaaa;
                border: 1px solid #333; border-radius: 4px;
                padding: 5px 14px; font-size: 11px;
            }
            QPushButton:hover  { background: #2a2a2a; color: #ffffff; border-color: #555; }
            QPushButton:pressed { background: #333; }
            QPushButton:disabled { color: #444; border-color: #222; }
            QFrame#separator   { background: #222; }
            QFrame#side_divider { background: #2a2a2a; }
            QProgressBar {
                background: #1a1a1a; border: 1px solid #333; border-radius: 4px;
                height: 8px; text-align: center; color: transparent;
            }
            QProgressBar::chunk { background: #ffaa33; border-radius: 3px; }
        """)

    def _checkbox_style(self, color: str, enabled: bool) -> str:
        accent = COLOR_ACCENT.get(color, "#ffaa33")
        dim    = COLOR_DIM.get(color, "#5a3a0a")
        if not enabled:
            return ("QCheckBox { color: #2a2a2a; background: transparent; spacing: 5px; }"
                    " QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px;"
                    " border: 1px solid #252525; background: #141414; }")
        return f"""
            QCheckBox {{
                color: {accent}; background: transparent;
                spacing: 5px; font-size: 11px;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px; border-radius: 3px;
                border: 1px solid {accent}55; background: {dim}44;
            }}
            QCheckBox::indicator:checked      {{ background: {accent}; border-color: {accent}; }}
            QCheckBox::indicator:indeterminate {{ background: {dim};    border-color: {accent}; }}
            QCheckBox::indicator:hover         {{ border-color: {accent}; }}
        """

    def _color_header_style(self, color: str) -> str:
        accent = COLOR_ACCENT.get(color, "#aaaaaa")
        dim    = COLOR_DIM.get(color, "#1a1a1a")
        return f"""
            QCheckBox {{
                color: {accent}; background: transparent;
                spacing: 6px; font-size: 11px; font-weight: bold;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px; border-radius: 3px;
                border: 1px solid {accent}88; background: {dim};
            }}
            QCheckBox::indicator:checked      {{ background: {accent}; border-color: {accent}; }}
            QCheckBox::indicator:indeterminate {{ background: {dim};    border-color: {accent}; }}
        """

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # Header
        title = QLabel("Export to SD Card")
        f = QFont(); f.setPointSize(13); f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color: #ffffff;")
        root.addWidget(title)

        subtitle = QLabel("Choose which samples to write to your SD card.")
        subtitle.setStyleSheet("color: #555; font-size: 11px;")
        root.addWidget(subtitle)

        # Folder picker
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)

        self._folder_label = QLabel("No folder selected")
        self._folder_label.setStyleSheet("""
            color: #444; font-size: 11px;
            background: #1a1a1a; border: 1px solid #2a2a2a;
            border-radius: 4px; padding: 5px 10px;
        """)
        self._folder_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._on_browse)

        folder_row.addWidget(self._folder_label)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        # Select all / none
        sel_row = QHBoxLayout()

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setFixedWidth(100)
        self._select_all_btn.clicked.connect(self._on_select_all)

        self._select_none_btn = QPushButton("Select None")
        self._select_none_btn.setFixedWidth(100)
        self._select_none_btn.clicked.connect(self._on_select_none)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #555; font-size: 11px;")

        sel_row.addWidget(self._select_all_btn)
        sel_row.addWidget(self._select_none_btn)
        sel_row.addStretch()
        sel_row.addWidget(self._count_label)
        root.addLayout(sel_row)

        sep = QFrame(); sep.setObjectName("separator")
        sep.setFixedHeight(1)
        sep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(sep)

        # Scrollable tree
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tree_container = QWidget()
        self._tree_layout = QVBoxLayout(self._tree_container)
        self._tree_layout.setContentsMargins(4, 8, 4, 8)
        self._tree_layout.setSpacing(6)
        self._tree_layout.addStretch()
        self._scroll.setWidget(self._tree_container)
        root.addWidget(self._scroll, 1)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._export_btn = QPushButton("Export to SD Card")
        self._export_btn.setEnabled(False)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #3a2a0a; color: #ffaa33;
                border: 1px solid #ffaa33; border-radius: 4px;
                padding: 6px 20px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover   { background: #4a3a1a; color: #ffcc66; }
            QPushButton:pressed { background: #2a1a00; }
            QPushButton:disabled { background: #1a1a1a; color: #333;
                                   border-color: #222; font-weight: normal; }
        """)
        self._export_btn.clicked.connect(self._on_export)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._export_btn)
        root.addLayout(btn_row)

    # ── Tree (built from project, not SD card) ────────────────────────────────

    def _build_tree(self):
        total = 0

        for color in COLORS:
            # Collect which slots have any samples for this color
            color_has_samples = False
            for slot in SLOTS:
                for side in SIDES:
                    for idx in INDICES:
                        if self.project.get_sample(color, slot, f"{side}{idx}"):
                            color_has_samples = True
                            break

            if not color_has_samples:
                continue

            color_block = self._build_color_block(color)
            self._tree_layout.insertWidget(self._tree_layout.count() - 1, color_block)

            for slot in SLOTS:
                for side in SIDES:
                    for idx in INDICES:
                        key = f"{side}{idx}"
                        if self.project.get_sample(color, slot, key):
                            total += 1

        color = "#55aa55" if total > 0 else "#555"
        self._count_label.setText(f"{total} sample{'s' if total != 1 else ''} in project")
        self._count_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._update_export_btn()

    def _build_color_block(self, color):
        block = QWidget()
        block.setStyleSheet(f"""
            QWidget {{
                background: {COLOR_DIM.get(color, '#1a1a1a')}33;
                border: 1px solid {COLOR_ACCENT.get(color, '#444')}22;
                border-radius: 6px;
            }}
        """)
        bl = QVBoxLayout(block)
        bl.setContentsMargins(14, 12, 14, 12)
        bl.setSpacing(8)

        color_cb = QCheckBox(color)
        f = QFont(); f.setBold(True); f.setPointSize(11)
        color_cb.setFont(f)
        color_cb.setCheckState(CHECKED)
        color_cb.setTristate(True)
        color_cb.setStyleSheet(self._color_header_style(color))
        self._color_checks[color] = color_cb
        bl.addWidget(color_cb)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLOR_ACCENT.get(color, '#333')}33; border: none;")
        bl.addWidget(sep)

        for slot in SLOTS:
            # Only show slots that have at least one sample
            has_any = any(
                self.project.get_sample(color, slot, f"{side}{idx}")
                for side in SIDES for idx in INDICES
            )
            if not has_any:
                continue
            bl.addWidget(self._build_slot_block(color, slot))

        color_cb.stateChanged.connect(
            lambda state, c=color: self._on_color_toggled(c, state)
        )
        self._update_color_state(color)
        return block

    def _build_slot_block(self, color, slot):
        block = QWidget()
        block.setStyleSheet("QWidget { background: transparent; border: none; }")
        bl = QHBoxLayout(block)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(14)

        slot_cb = QCheckBox(f"SLOT {slot}")
        slot_cb.setCheckState(CHECKED)
        slot_cb.setTristate(True)
        slot_cb.setFixedWidth(76)
        slot_cb.setStyleSheet(f"""
            QCheckBox {{
                color: #888; background: transparent;
                spacing: 6px; font-size: 11px;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px; border-radius: 3px;
                border: 1px solid #3a3a3a; background: #1a1a1a;
            }}
            QCheckBox::indicator:checked {{
                background: {COLOR_ACCENT.get(color, '#ffaa33')}88;
                border-color: {COLOR_ACCENT.get(color, '#ffaa33')};
            }}
            QCheckBox::indicator:indeterminate {{
                background: {COLOR_DIM.get(color, '#5a3a0a')};
                border-color: {COLOR_ACCENT.get(color, '#ffaa33')};
            }}
        """)
        self._slot_checks[(color, slot)] = slot_cb
        bl.addWidget(slot_cb)

        div = QFrame(); div.setObjectName("side_divider")
        div.setFixedWidth(1)
        div.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        bl.addWidget(div)

        for side in SIDES:
            for idx in INDICES:
                key = f"{side}{idx}"
                present = bool(self.project.get_sample(color, slot, key))
                cb = QCheckBox(key)
                cb.setEnabled(present)
                cb.setCheckState(CHECKED if present else UNCHECKED)
                cb.setStyleSheet(self._checkbox_style(color, present))
                self._sample_checks[(color, slot, key)] = cb
                cb.stateChanged.connect(
                    lambda state, c=color, s=slot: self._on_sample_toggled(c, s)
                )
                bl.addWidget(cb)

            if side == "L":
                bl.addSpacing(6)
                mid_div = QFrame(); mid_div.setObjectName("side_divider")
                mid_div.setFixedWidth(1)
                mid_div.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
                bl.addWidget(mid_div)
                bl.addSpacing(6)

        bl.addStretch()

        slot_cb.stateChanged.connect(
            lambda state, c=color, s=slot: self._on_slot_toggled(c, s, state)
        )
        self._update_slot_state(color, slot)
        return block

    # ── Tri-state propagation (identical logic to import) ─────────────────────

    def _on_color_toggled(self, color, state):
        if state == PARTIAL:
            return
        target = CHECKED if (state == CHECKED or state == 2) else UNCHECKED
        for slot in SLOTS:
            slot_cb = self._slot_checks.get((color, slot))
            if not slot_cb:
                continue
            slot_cb.blockSignals(True)
            slot_cb.setCheckState(target)
            slot_cb.blockSignals(False)
            for side in SIDES:
                for idx in INDICES:
                    cb = self._sample_checks.get((color, slot, f"{side}{idx}"))
                    if cb and cb.isEnabled():
                        cb.blockSignals(True)
                        cb.setCheckState(target)
                        cb.blockSignals(False)
        self._update_export_btn()

    def _on_slot_toggled(self, color, slot, state):
        if state == PARTIAL:
            return
        target = CHECKED if (state == CHECKED or state == 2) else UNCHECKED
        for side in SIDES:
            for idx in INDICES:
                cb = self._sample_checks.get((color, slot, f"{side}{idx}"))
                if cb and cb.isEnabled():
                    cb.blockSignals(True)
                    cb.setCheckState(target)
                    cb.blockSignals(False)
        self._update_color_state(color)
        self._update_export_btn()

    def _on_sample_toggled(self, color, slot):
        self._update_slot_state(color, slot)
        self._update_color_state(color)
        self._update_export_btn()

    def _update_slot_state(self, color, slot):
        cb = self._slot_checks.get((color, slot))
        if not cb:
            return
        enabled = [self._sample_checks[(color, slot, f"{side}{idx}")]
                   for side in SIDES for idx in INDICES
                   if self._sample_checks.get((color, slot, f"{side}{idx}")) and
                   self._sample_checks[(color, slot, f"{side}{idx}")].isEnabled()]
        if not enabled:
            return
        checked = sum(1 for c in enabled if c.checkState() == CHECKED)
        cb.blockSignals(True)
        cb.setCheckState(_tri(checked, len(enabled)))
        cb.blockSignals(False)

    def _update_color_state(self, color):
        cb = self._color_checks.get(color)
        if not cb:
            return
        slots = [self._slot_checks[(color, s)]
                 for s in SLOTS if (color, s) in self._slot_checks]
        if not slots:
            return
        checked = sum(1 for s in slots if s.checkState() == CHECKED)
        partial = sum(1 for s in slots if s.checkState() == PARTIAL)
        total   = len(slots)
        if checked == total:        state = CHECKED
        elif checked == 0 and partial == 0: state = UNCHECKED
        else:                       state = PARTIAL
        cb.blockSignals(True)
        cb.setCheckState(state)
        cb.blockSignals(False)

    def _update_export_btn(self):
        has_folder = bool(self._sd_root)
        any_checked = any(
            cb.checkState() == CHECKED and cb.isEnabled()
            for cb in self._sample_checks.values()
        )
        self._export_btn.setEnabled(has_folder and any_checked)

    def _set_all(self, state):
        for cb in self._color_checks.values():
            cb.blockSignals(True); cb.setCheckState(state); cb.blockSignals(False)
        for cb in self._slot_checks.values():
            cb.blockSignals(True); cb.setCheckState(state); cb.blockSignals(False)
        for cb in self._sample_checks.values():
            if cb.isEnabled():
                cb.blockSignals(True); cb.setCheckState(state); cb.blockSignals(False)
        self._update_export_btn()

    def _on_select_all(self):  self._set_all(CHECKED)
    def _on_select_none(self): self._set_all(UNCHECKED)

    # ── Folder picker ─────────────────────────────────────────────────────────

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select SD Card Root Folder", "",
            QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return
        self._sd_root = folder
        self._folder_label.setText(folder)
        self._folder_label.setStyleSheet(
            self._folder_label.styleSheet().replace("color: #444", "color: #aaaaaa")
        )
        self._update_export_btn()

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export(self):
        selections = []
        for color in COLORS:
            for slot in SLOTS:
                for side in SIDES:
                    for idx in INDICES:
                        key = f"{side}{idx}"
                        cb = self._sample_checks.get((color, slot, key))
                        if cb and cb.isEnabled() and cb.checkState() == CHECKED:
                            selections.append((color, slot, key))

        if not selections:
            return

        self._set_controls_enabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(selections))
        self._progress.setValue(0)

        self._worker = ExportWorker(self.project, self._sd_root, selections, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.conflict.connect(self._on_conflict)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.finished_err.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, done, total):
        self._progress.setValue(done)

    def _on_conflict(self, color, slot: int, key, dest_path):
        msg = QMessageBox(self)
        msg.setWindowTitle("File Already on SD Card")
        msg.setText(
            f"<b>{color} / SLOT {slot} / {key}</b> already exists on the SD card.<br><br>"
            f"<span style='color:#888'>{os.path.basename(dest_path)}</span><br><br>"
            f"Overwrite it?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.button(QMessageBox.StandardButton.Yes).setText("Overwrite")
        msg.button(QMessageBox.StandardButton.No).setText("Skip")
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        result = msg.exec()
        self._worker.resolve(result == QMessageBox.StandardButton.Yes)

    def _on_finished(self, count):
        self._progress.setValue(self._progress.maximum())
        self._set_controls_enabled(True)
        if count > 0:
            self.export_complete.emit()
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {count} sample{'s' if count != 1 else ''} to SD card."
        )
        self.accept()

    def _on_error(self, msg):
        self._set_controls_enabled(True)
        QMessageBox.critical(self, "Export Error", msg)

    def _set_controls_enabled(self, enabled):
        self._export_btn.setEnabled(enabled and bool(self._sd_root))
        self._select_all_btn.setEnabled(enabled)
        self._select_none_btn.setEnabled(enabled)
