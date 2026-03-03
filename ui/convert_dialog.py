from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from core.converter import get_wav_info, convert_to_orbit_wav, check_libraries_available
import os
import tempfile


class ConvertWorker(QThread):
    """Runs conversion off the main thread so the UI doesn't freeze."""
    finished = pyqtSignal(bool, str)  # success, error_or_output_path

    def __init__(self, src_path: str, dst_path: str):
        super().__init__()
        self.src_path = src_path
        self.dst_path = dst_path

    def run(self):
        success, err = convert_to_orbit_wav(self.src_path, self.dst_path)
        if success:
            self.finished.emit(True, self.dst_path)
        else:
            self.finished.emit(False, err)


class ConvertDialog(QDialog):
    """
    Shown when a dropped WAV doesn't meet Orbit specs.
    Offers: Convert & Import | Skip | Cancel
    """

    # Emitted with the path to use for import (either original or converted temp file)
    import_ready = pyqtSignal(str)

    def __init__(self, src_path: str, info: dict, parent=None):
        super().__init__(parent)
        self.src_path = src_path
        self.info = info
        self._tmp_path = None
        self._worker = None

        self.setWindowTitle("Convert Audio File")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog {
                background: #141414;
                color: #dddddd;
            }
            QWidget {
                background: #141414;
                color: #dddddd;
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
            }
            QLabel { background: transparent; }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("⚠  File needs conversion")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #ffaa44; background: transparent;")
        layout.addWidget(title)

        filename = QLabel(os.path.basename(self.src_path))
        filename.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        layout.addWidget(filename)

        # Info panel
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
            }
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(8)

        def row(label, current, target, ok):
            r = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #666; font-size: 10px; background: transparent;")
            lbl.setFixedWidth(100)

            icon = "✓" if ok else "✗"
            icon_color = "#55aa55" if ok else "#ff5555"
            curr = QLabel(f"{icon}  {current}")
            curr.setStyleSheet(f"color: {icon_color}; font-size: 11px; font-weight: bold; background: transparent;")
            curr.setFixedWidth(160)

            if ok:
                arrow = QLabel("no change")
                arrow.setStyleSheet("color: #444; font-size: 10px; font-style: italic; background: transparent;")
            else:
                arrow = QLabel(f"→  {target}")
                arrow.setStyleSheet("color: #55aa55; font-size: 11px; font-weight: bold; background: transparent;")

            r.addWidget(lbl)
            r.addWidget(curr)
            r.addWidget(arrow)
            r.addStretch()
            return r

        sr = self.info.get("sample_rate", "?")
        bd = self.info.get("bit_depth", "?")
        ch = self.info.get("channels", "?")
        dur = self.info.get("duration_sec", 0)

        sr_ok = (sr == 44100)
        bd_ok = (bd == 16)
        ch_ok = (ch == 1)

        panel_layout.addLayout(row("Sample Rate",
                                   f"{sr:,} Hz" if isinstance(sr, int) else str(sr),
                                   "44,100 Hz", sr_ok))
        panel_layout.addLayout(row("Bit Depth",
                                   f"{bd}-bit" if isinstance(bd, int) else str(bd),
                                   "16-bit", bd_ok))
        ch_label = f"{ch} ({'mono' if ch == 1 else 'stereo' if ch == 2 else f'{ch}-channel'})"
        panel_layout.addLayout(row("Channels", ch_label, "mono (left channel kept)", ch_ok))

        # Duration
        dur_str = f"{dur:.2f}s" if dur < 60 else f"{int(dur//60)}m {dur%60:.1f}s"
        dur_row = QHBoxLayout()
        dur_lbl = QLabel("Duration")
        dur_lbl.setStyleSheet("color: #666; font-size: 10px; background: transparent;")
        dur_lbl.setFixedWidth(100)
        dur_val = QLabel(dur_str)
        dur_val.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent;")
        dur_row.addWidget(dur_lbl)
        dur_row.addWidget(dur_val)
        dur_row.addStretch()
        panel_layout.addLayout(dur_row)

        layout.addWidget(panel)

        # Note about quality
        note = QLabel("Converting will not alter your original file. A converted copy will be used for import.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-size: 10px; background: transparent;")
        layout.addWidget(note)

        # Progress bar (hidden until converting)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: #1a1a1a;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #55aa55;
                border-radius: 2px;
            }
        """)
        self.progress.hide()
        layout.addWidget(self.progress)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-size: 10px; background: transparent;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #1e1e1e;
                color: #888;
                border: 1px solid #2a2a2a;
                border-radius: 5px;
                padding: 0 16px;
                font-size: 11px;
            }
            QPushButton:hover { color: #cccccc; border-color: #3a3a3a; }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.convert_btn = QPushButton("Convert && Import")
        self.convert_btn.setFixedHeight(32)
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background: #1e3a1e;
                color: #55dd55;
                border: 1px solid #2a5a2a;
                border-radius: 5px;
                padding: 0 18px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: #254825; border-color: #3a6a3a; }
            QPushButton:disabled { background: #1a1a1a; color: #444; border-color: #222; }
        """)
        self.convert_btn.clicked.connect(self._on_convert)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.convert_btn)
        layout.addLayout(btn_layout)

    def _on_convert(self):
        # Check libraries first
        ok, err = check_libraries_available()
        if not ok:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Missing Libraries", err)
            return

        self.convert_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.convert_btn.setText("Converting…")
        self.progress.show()
        self.status_label.setText("Converting audio…")
        self.status_label.show()

        # Write to a temp file
        suffix = ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        self._tmp_path = tmp.name
        tmp.close()

        self._worker = ConvertWorker(self.src_path, self._tmp_path)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, success: bool, result: str):
        self.progress.hide()
        if success:
            self.status_label.setText("✓  Conversion complete")
            self.status_label.setStyleSheet("color: #55aa55; font-size: 10px; background: transparent;")
            self.import_ready.emit(self._tmp_path)
            self.accept()
        else:
            self.status_label.setText(f"✗  {result}")
            self.status_label.setStyleSheet("color: #ff5555; font-size: 10px; background: transparent;")
            self.convert_btn.setEnabled(True)
            self.convert_btn.setText("Retry")
            self.cancel_btn.setEnabled(True)

    def get_tmp_path(self):
        return self._tmp_path