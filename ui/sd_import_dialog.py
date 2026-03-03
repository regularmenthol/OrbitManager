"""
SD Card Import Dialog

Scans a user-selected folder for the Orbit file structure:
  <root>/COLOR/COLOR_SLOTn_Lm.wav  (and Rm)

Presents a tree of checkboxes (Color → Slot → Sample) so the user
can pick exactly what to import.  Skipped / conflicting slots prompt
the user one by one before any files are copied.
"""

import os
import wave

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QScrollArea, QWidget, QCheckBox, QFrame,
    QMessageBox, QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from core.project import COLORS, SLOTS, SIDES, INDICES

# Color accent values matching the sidebar
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


# ── Tri-state checkbox helper ──────────────────────────────────────────────────

UNCHECKED   = Qt.CheckState.Unchecked
PARTIAL     = Qt.CheckState.PartiallyChecked
CHECKED     = Qt.CheckState.Checked


def _tri(checked_count, total):
    if checked_count == 0:       return UNCHECKED
    if checked_count == total:   return CHECKED
    return PARTIAL


# ── Scan SD root ───────────────────────────────────────────────────────────────

def scan_sd_root(root: str) -> dict:
    """
    Walk root looking for Orbit WAV files.
    Returns nested dict:
      { COLOR: { slot_num: { key: abs_path | None } } }
    Only includes files that actually exist on the SD card.
    """
    found = {color: {s: {} for s in SLOTS} for color in COLORS}

    for color in COLORS:
        color_dir = os.path.join(root, color)
        if not os.path.isdir(color_dir):
            continue
        for slot in SLOTS:
            for side in SIDES:
                for idx in INDICES:
                    key = f"{side}{idx}"
                    filename = f"{color}_SLOT{slot}_{key}.wav"
                    path = os.path.join(color_dir, filename)
                    if os.path.isfile(path):
                        found[color][slot][key] = path
    return found


# ── Import worker thread ───────────────────────────────────────────────────────

class ImportWorker(QThread):
    progress     = pyqtSignal(int, int)          # done, total
    conflict     = pyqtSignal(str, int, str, str) # color, slot, key, sd_path
    conflict_resolved = pyqtSignal(bool)          # True=overwrite, False=skip
    finished_ok  = pyqtSignal(int)               # count imported
    finished_err = pyqtSignal(str)

    def __init__(self, project, selections, parent=None):
        super().__init__(parent)
        self.project = project
        self.selections = selections   # list of (color, slot, key, sd_path)
        self._resolution = None        # set by main thread via resolve()

    def resolve(self, overwrite: bool):
        self._resolution = overwrite

    def run(self):
        imported = 0
        total = len(self.selections)

        for i, (color, slot, key, sd_path) in enumerate(self.selections):
            self.progress.emit(i, total)

            existing = self.project.get_sample(color, slot, key)
            if existing:
                # Pause and ask main thread
                self._resolution = None
                self.conflict.emit(color, slot, key, sd_path)
                # Spin-wait for resolution (main thread calls resolve())
                while self._resolution is None:
                    self.msleep(50)
                if not self._resolution:
                    continue   # skip

            # Read duration from SD file
            duration_sec = None
            try:
                with wave.open(sd_path, 'rb') as wf:
                    duration_sec = wf.getnframes() / wf.getframerate()
            except Exception:
                pass

            try:
                original_name = os.path.basename(sd_path)
                self.project.set_sample(
                    color, slot, key,
                    original_name, sd_path, sd_path,
                    duration_sec=duration_sec
                )
                imported += 1
            except Exception as e:
                self.finished_err.emit(str(e))
                return

        self.progress.emit(total, total)
        self.finished_ok.emit(imported)


# ── Main dialog ────────────────────────────────────────────────────────────────

class SdImportDialog(QDialog):
    import_complete = pyqtSignal()   # emitted when at least one sample was imported

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Import from SD Card")
        self.setMinimumSize(660, 680)
        self.resize(740, 760)
        self._sd_root = None
        self._sd_data = {}

        # Checkbox references
        self._color_checks  = {}   # color -> QCheckBox
        self._slot_checks   = {}   # (color, slot) -> QCheckBox
        self._sample_checks = {}   # (color, slot, key) -> QCheckBox

        self._setup_ui()
        self._apply_style()

    # ── UI setup ──────────────────────────────────────────────────────────────

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
            QFrame#separator { background: #222; }
            QFrame#side_divider { background: #2a2a2a; }
            QProgressBar {
                background: #1a1a1a; border: 1px solid #333; border-radius: 4px;
                height: 8px; text-align: center; color: transparent;
            }
            QProgressBar::chunk { background: #4488ff; border-radius: 3px; }
        """)

    def _checkbox_style(self, color: str, enabled: bool) -> str:
        accent = COLOR_ACCENT.get(color, "#4488ff")
        dim    = COLOR_DIM.get(color, "#1a3a6a")
        if not enabled:
            return "QCheckBox { color: #2a2a2a; background: transparent; spacing: 5px; } QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #252525; background: #141414; }"
        return f"""
            QCheckBox {{
                color: {accent};
                background: transparent;
                spacing: 5px;
                font-size: 11px;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border-radius: 3px;
                border: 1px solid {accent}55;
                background: {dim}44;
            }}
            QCheckBox::indicator:checked {{
                background: {accent};
                border-color: {accent};
            }}
            QCheckBox::indicator:indeterminate {{
                background: {dim};
                border-color: {accent};
            }}
            QCheckBox::indicator:hover {{
                border-color: {accent};
            }}
        """

    def _color_header_style(self, color: str) -> str:
        accent = COLOR_ACCENT.get(color, "#aaaaaa")
        dim    = COLOR_DIM.get(color, "#1a1a1a")
        return f"""
            QCheckBox {{
                color: {accent};
                background: transparent;
                spacing: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border-radius: 3px;
                border: 1px solid {accent}88;
                background: {dim};
            }}
            QCheckBox::indicator:checked {{
                background: {accent};
                border-color: {accent};
            }}
            QCheckBox::indicator:indeterminate {{
                background: {dim};
                border-color: {accent};
            }}
        """

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # ── Header ────────────────────────────────────────────────────────────
        title = QLabel("Import from SD Card")
        f = QFont(); f.setPointSize(13); f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color: #ffffff;")
        root.addWidget(title)

        subtitle = QLabel("Select an SD card folder, then choose which samples to import.")
        subtitle.setStyleSheet("color: #555; font-size: 11px;")
        root.addWidget(subtitle)

        # ── Folder picker ─────────────────────────────────────────────────────
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

        # ── Select all / none row ─────────────────────────────────────────────
        sel_row = QHBoxLayout()
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setFixedWidth(100)
        self._select_all_btn.setEnabled(False)
        self._select_all_btn.clicked.connect(self._on_select_all)

        self._select_none_btn = QPushButton("Select None")
        self._select_none_btn.setFixedWidth(100)
        self._select_none_btn.setEnabled(False)
        self._select_none_btn.clicked.connect(self._on_select_none)

        self._found_label = QLabel("")
        self._found_label.setStyleSheet("color: #555; font-size: 11px;")

        sel_row.addWidget(self._select_all_btn)
        sel_row.addWidget(self._select_none_btn)
        sel_row.addStretch()
        sel_row.addWidget(self._found_label)
        root.addLayout(sel_row)

        sep = QFrame(); sep.setObjectName("separator")
        sep.setFixedHeight(1); sep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(sep)

        # ── Scrollable tree ───────────────────────────────────────────────────
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

        # ── Progress bar (hidden until import starts) ─────────────────────────
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._import_btn = QPushButton("Import Selected")
        self._import_btn.setEnabled(False)
        self._import_btn.setStyleSheet("""
            QPushButton {
                background: #1a3a6a; color: #88bbff;
                border: 1px solid #4488ff; border-radius: 4px;
                padding: 6px 20px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover  { background: #1e4a8a; color: #aaccff; }
            QPushButton:pressed { background: #152e58; }
            QPushButton:disabled { background: #1a1a1a; color: #333;
                                   border-color: #222; font-weight: normal; }
        """)
        self._import_btn.clicked.connect(self._on_import)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._import_btn)
        root.addLayout(btn_row)

    # ── Folder browsing & scan ────────────────────────────────────────────────

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select SD Card Root Folder", "",
            QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return
        self._sd_root = folder
        self._folder_label.setText(folder)
        self._folder_label.setStyleSheet(self._folder_label.styleSheet().replace("color: #444", "color: #aaaaaa"))
        self._scan_and_build(folder)

    def _scan_and_build(self, root):
        self._sd_data = scan_sd_root(root)
        self._color_checks.clear()
        self._slot_checks.clear()
        self._sample_checks.clear()

        # Clear tree
        while self._tree_layout.count() > 1:   # keep the trailing stretch
            item = self._tree_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total_found = 0

        for color in COLORS:
            slot_data = self._sd_data[color]
            color_samples = sum(len(v) for v in slot_data.values())
            if color_samples == 0:
                continue
            total_found += color_samples

            color_block = self._build_color_block(color, slot_data)
            self._tree_layout.insertWidget(self._tree_layout.count() - 1, color_block)

        has_any = total_found > 0
        self._select_all_btn.setEnabled(has_any)
        self._select_none_btn.setEnabled(has_any)
        self._import_btn.setEnabled(has_any)
        self._found_label.setText(f"{total_found} sample{'s' if total_found != 1 else ''} found" if has_any else "No samples found")
        self._found_label.setStyleSheet(f"color: {'#55aa55' if has_any else '#aa5555'}; font-size: 11px;")

    # ── Tree builders ─────────────────────────────────────────────────────────

    def _build_color_block(self, color, slot_data):
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

        # Color header checkbox
        color_cb = QCheckBox(color)
        f = QFont(); f.setBold(True); f.setPointSize(11)
        color_cb.setFont(f)
        color_cb.setCheckState(CHECKED)
        color_cb.setTristate(True)
        color_cb.setStyleSheet(self._color_header_style(color))
        self._color_checks[color] = color_cb
        bl.addWidget(color_cb)

        # Thin separator under color header
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLOR_ACCENT.get(color, '#333')}33; border: none;")
        bl.addWidget(sep)

        # Slots under this color
        for slot in SLOTS:
            keys = slot_data[slot]
            if not keys:
                continue
            slot_block = self._build_slot_block(color, slot, keys)
            bl.addWidget(slot_block)

        # Wire color checkbox — must happen after children exist
        color_cb.stateChanged.connect(
            lambda state, c=color: self._on_color_toggled(c, state)
        )
        self._update_color_state(color)
        return block

    def _build_slot_block(self, color, slot, keys):
        block = QWidget()
        block.setStyleSheet("QWidget { background: transparent; border: none; }")
        bl = QHBoxLayout(block)
        bl.setContentsMargins(8, 4, 8, 4)
        bl.setSpacing(14)

        # Slot checkbox on the left
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
                background: {COLOR_ACCENT.get(color, '#4488ff')}88;
                border-color: {COLOR_ACCENT.get(color, '#4488ff')};
            }}
            QCheckBox::indicator:indeterminate {{
                background: {COLOR_DIM.get(color, '#1a3a6a')};
                border-color: {COLOR_ACCENT.get(color, '#4488ff')};
            }}
        """)
        self._slot_checks[(color, slot)] = slot_cb
        bl.addWidget(slot_cb)

        # Thin vertical divider
        div = QFrame(); div.setObjectName("side_divider")
        div.setFixedWidth(1)
        div.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        bl.addWidget(div)

        # L0 L1 L2 L3  |  R0 R1 R2 R3
        for side in SIDES:
            for idx in INDICES:
                key = f"{side}{idx}"
                cb = QCheckBox(key)
                present = key in keys
                cb.setEnabled(present)
                cb.setCheckState(CHECKED if present else UNCHECKED)
                cb.setStyleSheet(self._checkbox_style(color, present))
                self._sample_checks[(color, slot, key)] = cb
                cb.stateChanged.connect(
                    lambda state, c=color, s=slot: self._on_sample_toggled(c, s)
                )
                bl.addWidget(cb)

            # Gap + divider between L and R groups
            if side == "L":
                bl.addSpacing(6)
                mid_div = QFrame(); mid_div.setObjectName("side_divider")
                mid_div.setFixedWidth(1)
                mid_div.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
                bl.addWidget(mid_div)
                bl.addSpacing(6)

        bl.addStretch()

        # Wire slot checkbox after children exist
        slot_cb.stateChanged.connect(
            lambda state, c=color, s=slot: self._on_slot_toggled(c, s, state)
        )
        self._update_slot_state(color, slot)
        return block
        self._update_slot_state(color, slot)
        return block

    # ── Tri-state propagation ─────────────────────────────────────────────────

    def _on_color_toggled(self, color, state):
        if state == PARTIAL:
            return   # programmatic partial — don't cascade
        target = CHECKED if state == CHECKED.value or state == CHECKED else UNCHECKED
        # Also handle int comparison from Qt
        if isinstance(state, int):
            target = CHECKED if state == 2 else UNCHECKED

        for slot in SLOTS:
            slot_cb = self._slot_checks.get((color, slot))
            if slot_cb is None:
                continue
            slot_cb.blockSignals(True)
            slot_cb.setCheckState(target)
            slot_cb.blockSignals(False)
            for side in SIDES:
                for idx in INDICES:
                    key = f"{side}{idx}"
                    cb = self._sample_checks.get((color, slot, key))
                    if cb and cb.isEnabled():
                        cb.blockSignals(True)
                        cb.setCheckState(target)
                        cb.blockSignals(False)

        self._update_import_btn()

    def _on_slot_toggled(self, color, slot, state):
        if state == PARTIAL:
            return
        if isinstance(state, int):
            target = CHECKED if state == 2 else UNCHECKED
        else:
            target = state

        for side in SIDES:
            for idx in INDICES:
                key = f"{side}{idx}"
                cb = self._sample_checks.get((color, slot, key))
                if cb and cb.isEnabled():
                    cb.blockSignals(True)
                    cb.setCheckState(target)
                    cb.blockSignals(False)

        self._update_color_state(color)
        self._update_import_btn()

    def _on_sample_toggled(self, color, slot):
        self._update_slot_state(color, slot)
        self._update_color_state(color)
        self._update_import_btn()

    def _update_slot_state(self, color, slot):
        cb = self._slot_checks.get((color, slot))
        if not cb:
            return
        enabled = [self._sample_checks[(color, slot, f"{side}{idx}")]
                   for side in SIDES for idx in INDICES
                   if (color, slot, f"{side}{idx}") in self._sample_checks
                   and self._sample_checks[(color, slot, f"{side}{idx}")].isEnabled()]
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
        # Count slots that are fully or partially checked
        checked = sum(1 for s in slots if s.checkState() == CHECKED)
        partial = sum(1 for s in slots if s.checkState() == PARTIAL)
        total = len(slots)
        if checked == total:
            state = CHECKED
        elif checked == 0 and partial == 0:
            state = UNCHECKED
        else:
            state = PARTIAL
        cb.blockSignals(True)
        cb.setCheckState(state)
        cb.blockSignals(False)

    def _update_import_btn(self):
        any_checked = any(
            cb.checkState() == CHECKED and cb.isEnabled()
            for cb in self._sample_checks.values()
        )
        self._import_btn.setEnabled(any_checked)

    # ── Select all / none ─────────────────────────────────────────────────────

    def _set_all(self, state):
        for color, cb in self._color_checks.items():
            cb.blockSignals(True)
            cb.setCheckState(state)
            cb.blockSignals(False)
        for (color, slot), cb in self._slot_checks.items():
            cb.blockSignals(True)
            cb.setCheckState(state)
            cb.blockSignals(False)
        for (color, slot, key), cb in self._sample_checks.items():
            if cb.isEnabled():
                cb.blockSignals(True)
                cb.setCheckState(state)
                cb.blockSignals(False)
        self._update_import_btn()

    def _on_select_all(self):
        self._set_all(CHECKED)

    def _on_select_none(self):
        self._set_all(UNCHECKED)

    # ── Import ────────────────────────────────────────────────────────────────

    def _on_import(self):
        selections = []
        for color in COLORS:
            for slot in SLOTS:
                for side in SIDES:
                    for idx in INDICES:
                        key = f"{side}{idx}"
                        cb = self._sample_checks.get((color, slot, key))
                        if cb and cb.isEnabled() and cb.checkState() == CHECKED:
                            sd_path = self._sd_data[color][slot].get(key)
                            if sd_path:
                                selections.append((color, slot, key, sd_path))

        if not selections:
            return

        self._set_controls_enabled(False)
        self._progress.setVisible(True)
        self._progress.setMaximum(len(selections))
        self._progress.setValue(0)

        self._worker = ImportWorker(self.project, selections, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.conflict.connect(self._on_conflict)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.finished_err.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, done, total):
        self._progress.setValue(done)

    def _on_conflict(self, color, slot: int, key, sd_path):
        existing = self.project.get_sample(color, slot, key)
        existing_name = existing.get("original_name", key) if existing else key

        msg = QMessageBox(self)
        msg.setWindowTitle("Slot Already Occupied")
        msg.setText(
            f"<b>{color} / SLOT {slot} / {key}</b> already contains:<br>"
            f"<span style='color:#888'>{existing_name}</span><br><br>"
            f"Replace it with:<br>"
            f"<span style='color:#aaaaff'>{os.path.basename(sd_path)}</span>?"
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
        msg = f"Imported {count} sample{'s' if count != 1 else ''} successfully."
        if count > 0:
            self.import_complete.emit()
        QMessageBox.information(self, "Import Complete", msg)
        self.accept()

    def _on_error(self, msg):
        self._set_controls_enabled(True)
        QMessageBox.critical(self, "Import Error", msg)

    def _set_controls_enabled(self, enabled):
        self._import_btn.setEnabled(enabled)
        self._select_all_btn.setEnabled(enabled)
        self._select_none_btn.setEnabled(enabled)