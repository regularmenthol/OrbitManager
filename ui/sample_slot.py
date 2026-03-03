import os
import platform
import subprocess
from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout,
                              QPushButton, QSizePolicy, QFrame,
                              QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QDrag, QColor, QPainter, QPen, QFont, QPixmap

from core.validator import validate_wav
from core.audio_player import get_player
from ui.convert_dialog import ConvertDialog

AUDIO_EXTENSIONS = {'.wav'}
SLOT_MIME_TYPE = "application/x-orbit-slot"


def _get_main_window(widget):
    """Walk up the parent chain to find the MainWindow."""
    p = widget.parent()
    while p is not None:
        if hasattr(p, 'get_last_import_dir'):
            return p
        p = p.parent()
    return None


def _format_duration(seconds) -> str:
    """Format seconds as MM:SS.cs (e.g. 00:02.34, 01:14.07)."""
    if seconds is None:
        return ""
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return ""
    total_cs = round(s * 100)          # centiseconds
    cs = total_cs % 100
    total_s = total_cs // 100
    secs = total_s % 60
    mins = total_s // 60
    return f"{mins:02d}:{secs:02d}.{cs:02d}"


def _reveal_in_os(path: str):
    """Open the OS file manager and highlight the file."""
    system = platform.system()
    if not os.path.exists(path):
        # Fall back to parent directory
        path = os.path.dirname(path)
    try:
        if system == "Darwin":
            subprocess.run(["open", "-R", path])
        elif system == "Windows":
            subprocess.run(["explorer", "/select,", os.path.normpath(path)])
        else:
            # Linux — open parent folder
            subprocess.run(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass


class SampleSlotWidget(QFrame):
    """A single droppable/draggable sample slot."""

    sample_changed = pyqtSignal()
    # Emitted after a move so the source slot can be told to refresh
    # args: src_color, src_slot_num, src_key
    slot_moved = pyqtSignal(str, int, str)

    def __init__(self, color, slot_num, key, project_ref, parent=None):
        super().__init__(parent)
        self.color = color
        self.slot_num = slot_num
        self.key = key
        self.project_ref = project_ref
        self._drag_start_pos = None
        self._is_playing = False
        self._is_dragging = False

        self.setAcceptDrops(True)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self._set_style(False)

        player = get_player()
        player.playback_started.connect(self._on_playback_started)
        player.playback_stopped.connect(self._on_playback_stopped)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 6, 4)
        layout.setSpacing(6)

        # Key label (L0, R3 etc.)
        self.key_label = QLabel(self.key)
        self.key_label.setFixedWidth(26)
        self.key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_font = QFont("Monospace", 9)
        key_font.setBold(True)
        self.key_label.setFont(key_font)
        self.key_label.setStyleSheet("color: #666; background: transparent;")

        # ── Info column ──────────────────────────────────────────────────
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        # Top row: project filename + duration
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        top_row.setContentsMargins(0, 0, 0, 0)

        self.project_name_label = QLabel("— click or drop a file —")
        self.project_name_label.setStyleSheet("color: #333; font-size: 10px; background: transparent;")

        self.duration_label = QLabel("")
        self.duration_label.setStyleSheet("color: #557755; font-size: 9px; background: transparent; font-family: 'Monospace';")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.duration_label.setMinimumWidth(56)
        self.duration_label.setFixedWidth(56)

        top_row.addWidget(self.project_name_label, 1)
        top_row.addWidget(self.duration_label)

        # Bottom row: original filename
        self.original_name_label = QLabel("")
        self.original_name_label.setStyleSheet("color: #555; font-size: 9px; background: transparent;")

        info_layout.addLayout(top_row)
        info_layout.addWidget(self.original_name_label)

        # ── Buttons ──────────────────────────────────────────────────────
        # Play/stop
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(24, 24)
        self.play_btn.setToolTip("Preview sample")
        self.play_btn.setStyleSheet(self._play_btn_style(False))
        self.play_btn.clicked.connect(self._on_play)
        self.play_btn.hide()

        # Reveal in Finder/Explorer
        self.reveal_btn = QPushButton("⌖")
        self.reveal_btn.setFixedSize(24, 24)
        self.reveal_btn.setToolTip("Reveal original file in Finder / Explorer")
        self.reveal_btn.setStyleSheet("""
            QPushButton {
                background: #1e1e1e;
                color: #666;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #222;
                color: #aaaaff;
                border-color: #4444aa;
            }
        """)
        self.reveal_btn.clicked.connect(self._on_reveal)
        self.reveal_btn.hide()

        # Delete
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(22, 22)
        self.delete_btn.setToolTip("Remove sample from slot")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #444;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { color: #ff5555; }
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.hide()

        layout.addWidget(self.key_label)
        layout.addLayout(info_layout, 1)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.reveal_btn)
        layout.addWidget(self.delete_btn)

    # ── Style helpers ──────────────────────────────────────────────────────

    def _play_btn_style(self, playing: bool) -> str:
        if playing:
            return """
                QPushButton {
                    background: #3a6a3a;
                    color: #aaffaa;
                    border: 1px solid #55aa55;
                    border-radius: 12px;
                    font-size: 10px;
                }
                QPushButton:hover { background: #2a5a2a; }
            """
        return """
            QPushButton {
                background: #1e1e1e;
                color: #666;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                font-size: 10px;
            }
            QPushButton:hover {
                background: #1e2e1e;
                color: #aaffaa;
                border-color: #3a6a3a;
            }
        """

    def _set_style(self, highlight):
        if highlight:
            self.setStyleSheet("""
                SampleSlotWidget {
                    background: #1e2e1e;
                    border: 1px dashed #55aa55;
                    border-radius: 5px;
                }
            """)
        elif self._get_sample():
            self.setStyleSheet("""
                SampleSlotWidget {
                    background: #161e16;
                    border: 1px solid #2a422a;
                    border-radius: 5px;
                }
                SampleSlotWidget:hover {
                    background: #1a221a;
                    border: 1px solid #3a5a3a;
                }
            """)
        else:
            self.setStyleSheet("""
                SampleSlotWidget {
                    background: #111111;
                    border: 1px dashed #222222;
                    border-radius: 5px;
                }
                SampleSlotWidget:hover {
                    background: #141414;
                    border: 1px dashed #333333;
                }
            """)

    # ── Data helpers ───────────────────────────────────────────────────────

    def _get_sample(self):
        if self.project_ref[0]:
            return self.project_ref[0].get_sample(self.color, self.slot_num, self.key)
        return None

    def _get_project_file_path(self, sample):
        if not sample or not self.project_ref[0]:
            return None
        pf = sample.get("project_filename", "")
        if pf:
            return os.path.join(self.project_ref[0].project_path, self.color, pf)
        return None

    def _uid(self):
        return f"{self.color}_{self.slot_num}_{self.key}"

    # ── Refresh ────────────────────────────────────────────────────────────

    def refresh(self):
        # Always reset drag state on refresh — covers cases where this slot
        # was the source of a drag-to-another-slot move
        self._is_dragging = False
        self._drag_start_pos = None

        sample = self._get_sample()
        if sample:
            self.project_name_label.setText(sample.get("project_filename", ""))
            self.project_name_label.setStyleSheet("color: #cccccc; font-size: 10px; background: transparent;")

            # Use stored duration, or read it live from the project file as fallback
            duration_sec = sample.get("duration_sec")
            if duration_sec is None:
                proj_path = self._get_project_file_path(sample)
                if proj_path and os.path.exists(proj_path):
                    try:
                        import wave
                        with wave.open(proj_path, 'rb') as wf:
                            duration_sec = wf.getnframes() / wf.getframerate()
                    except Exception:
                        pass

            self.duration_label.setText(_format_duration(duration_sec))

            orig = sample.get("original_name", "")
            self.original_name_label.setText(f"← {orig}")

            self.play_btn.show()
            self.reveal_btn.show()
            self.delete_btn.show()
        else:
            self.project_name_label.setText("— click or drop a file —")
            self.project_name_label.setStyleSheet("color: #333; font-size: 10px; background: transparent;")
            self.duration_label.setText("")
            self.original_name_label.setText("")
            self.play_btn.hide()
            self.reveal_btn.hide()
            self.delete_btn.hide()
        self._set_style(False)

    # ── Button handlers ────────────────────────────────────────────────────

    def _on_delete(self):
        proj = self.project_ref[0]
        if proj:
            if get_player().is_playing(self._uid()):
                get_player().stop()
            proj.remove_sample(self.color, self.slot_num, self.key)
            self.refresh()
            self.sample_changed.emit()

    def _on_play(self):
        sample = self._get_sample()
        if not sample:
            return
        path = self._get_project_file_path(sample)
        if path and os.path.exists(path):
            get_player().play(path, self._uid())

    def _on_reveal(self):
        sample = self._get_sample()
        if not sample:
            return
        original_path = sample.get("original_path", "")
        if original_path:
            _reveal_in_os(original_path)

    def _on_playback_started(self, key):
        self._is_playing = (key == self._uid())
        self.play_btn.setText("■" if self._is_playing else "▶")
        self.play_btn.setStyleSheet(self._play_btn_style(self._is_playing))

    def _on_playback_stopped(self):
        self._is_playing = False
        self.play_btn.setText("▶")
        self.play_btn.setStyleSheet(self._play_btn_style(False))

    # ── Click to open file dialog ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._is_dragging = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._is_dragging
            self._is_dragging = False
            if not was_dragging and self.project_ref[0]:
                self._open_file_dialog()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self._drag_start_pos:
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                sample = self._get_sample()
                if sample:
                    self._is_dragging = True
                    copy_mode = bool(event.modifiers() & (
                        Qt.KeyboardModifier.ControlModifier |
                        Qt.KeyboardModifier.MetaModifier
                    ))
                    self._start_drag(sample, copy=copy_mode)
        super().mouseMoveEvent(event)

    def _open_file_dialog(self):
        proj = self.project_ref[0]
        if not proj:
            return
        mw = _get_main_window(self)
        start_dir = mw.get_last_import_dir() if mw else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import sample → {self.color} · SLOT {self.slot_num} · {self.key}",
            start_dir,
            "WAV Files (*.wav)"
        )
        if path:
            self._handle_file_import(path, proj)

    # ── Import logic ───────────────────────────────────────────────────────

    def _handle_file_import(self, path: str, proj):
        """Validate, optionally convert, then import a file into this slot."""
        result = validate_wav(path)

        if result["error"]:
            QMessageBox.warning(self, "Cannot Import File", result["error"])
            return

        # Save the directory for next time
        mw = _get_main_window(self)
        if mw:
            mw.set_last_import_dir(os.path.dirname(path))

        duration_sec = result["info"].get("duration_sec")

        if result["needs_conversion"]:
            dialog = ConvertDialog(path, result["info"], parent=self)
            converted_path = [None]

            def on_ready(tmp_path):
                converted_path[0] = tmp_path

            dialog.import_ready.connect(on_ready)
            dialog.exec()

            if converted_path[0]:
                original_name = os.path.basename(path)
                proj.set_sample(self.color, self.slot_num, self.key,
                                original_name, path, converted_path[0],
                                duration_sec=duration_sec)
                self.refresh()
                self.sample_changed.emit()
        else:
            original_name = os.path.basename(path)
            proj.set_sample(self.color, self.slot_num, self.key,
                            original_name, path, path,
                            duration_sec=duration_sec)
            self.refresh()
            self.sample_changed.emit()

    # ── Drag ───────────────────────────────────────────────────────────────

    def _start_drag(self, sample, copy=False):
        mime = QMimeData()
        # Encode copy flag in payload: COLOR|SLOT|KEY|copy
        payload = f"{self.color}|{self.slot_num}|{self.key}|{'copy' if copy else 'move'}"
        mime.setData(SLOT_MIME_TYPE, payload.encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = QPixmap(240, 36)
        pix.fill(QColor("#1e2e3e" if copy else "#1e2e1e"))
        p = QPainter(pix)
        p.setPen(QPen(QColor("#88aaff" if copy else "#88cc88")))
        prefix = "⊕ " if copy else ""
        p.drawText(pix.rect().adjusted(8, 0, -8, 0),
                   Qt.AlignmentFlag.AlignVCenter,
                   f"{prefix}{self.key}  {sample.get('original_name', '')}")
        p.end()
        drag.setPixmap(pix)
        drag.setHotSpot(pix.rect().center())
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)
        self._is_dragging = False
        self._drag_start_pos = None

    # ── Drop ───────────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(SLOT_MIME_TYPE):
            self._set_style(True)
            event.acceptProposedAction()
        elif event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(os.path.splitext(u.toLocalFile())[1].lower() in AUDIO_EXTENSIONS
                   for u in urls):
                self._set_style(True)
                event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_style(False)

    def dropEvent(self, event):
        self._set_style(False)
        proj = self.project_ref[0]
        if not proj:
            return

        if event.mimeData().hasFormat(SLOT_MIME_TYPE):
            payload = bytes(event.mimeData().data(SLOT_MIME_TYPE)).decode()
            parts = payload.split("|")
            src_color, src_slot, src_key = parts[0], parts[1], parts[2]
            copy_mode = (len(parts) > 3 and parts[3] == "copy")
            src_slot = int(src_slot)
            if (src_color, src_slot, src_key) != (self.color, self.slot_num, self.key):
                if copy_mode:
                    proj.copy_sample(src_color, src_slot, src_key,
                                     self.color, self.slot_num, self.key)
                    self.refresh()
                    self.sample_changed.emit()
                else:
                    proj.move_sample(src_color, src_slot, src_key,
                                     self.color, self.slot_num, self.key)
                    self.refresh()
                    self.slot_moved.emit(src_color, src_slot, src_key)
                    self.sample_changed.emit()
            event.acceptProposedAction()

        elif event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
                    self._is_dragging = True   # suppress mouseRelease dialog for this drop
                    self._handle_file_import(path, proj)
                    self._is_dragging = False  # reset immediately after
                    break
            event.acceptProposedAction()
