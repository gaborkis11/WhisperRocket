#!/usr/bin/env python3
"""
WhisperRocket - File Transcription Window
Dedicated window for transcribing audio/video files with progress,
speaker diarization, and export support.
"""
import os
import threading
import subprocess

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QProgressBar, QTextEdit,
    QFileDialog, QFrame, QComboBox, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QAction

from translations import t
from transcription_engine import (
    TranscriptionEngine, TranscriptionResult, TranscriptionSegment,
    format_timestamp, export_srt, export_vtt, export_txt, export_json,
)
import diarization_manager


# Supported audio/video extensions
SUPPORTED_EXTENSIONS = {
    '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus',
    '.mp4', '.mkv', '.webm', '.avi', '.mov', '.wma', '.aac',
}


def get_audio_duration(file_path: str) -> float:
    """Get audio duration in seconds using soundfile or ffprobe"""
    try:
        import soundfile as sf
        info = sf.info(file_path)
        return info.duration
    except Exception:
        pass
    # Fallback: ffprobe
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def format_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS"""
    if seconds <= 0:
        return "?"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class DropZone(QFrame):
    """Drag & drop zone for audio/video files"""
    file_dropped = Signal(str)

    def __init__(self, ui_lang: str, parent=None):
        super().__init__(parent)
        self.ui_lang = ui_lang
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self._set_normal_style()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint_label = QLabel(t("ft_drop_hint", ui_lang))
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setFont(QFont("", 11))
        self.hint_label.setStyleSheet("color: #aaa; border: none;")
        layout.addWidget(self.hint_label)

        self.browse_btn = QPushButton(t("ft_browse", ui_lang))
        self.browse_btn.setMaximumWidth(150)
        self.browse_btn.setStyleSheet("border: 1px solid #666; padding: 5px 15px;")
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        fmt_label = QLabel(t("ft_supported", ui_lang))
        fmt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fmt_label.setStyleSheet("color: #777; font-size: 10px; border: none;")
        layout.addWidget(fmt_label)

    def _set_normal_style(self):
        self.setStyleSheet("DropZone { border: 2px dashed #555; border-radius: 8px; background: #2a2a2a; }")

    def _set_hover_style(self):
        self.setStyleSheet("DropZone { border: 2px solid #4CAF50; border-radius: 8px; background: #2d3a2d; }")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    event.acceptProposedAction()
                    self._set_hover_style()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_normal_style()

    def dropEvent(self, event: QDropEvent):
        self._set_normal_style()
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                self.file_dropped.emit(file_path)
                return


class FileTranscriptionWindow(QMainWindow):
    """Dedicated window for file transcription"""

    # Signals for thread-safe UI updates
    progress_updated = Signal(float, str)
    segment_ready = Signal(object)
    transcription_complete = Signal(object)
    transcription_error = Signal(str)

    def __init__(self, model, whisper_backend, config, ui_lang, model_lock):
        super().__init__()
        self.model = model
        self.whisper_backend = whisper_backend
        self.config = config
        self.ui_lang = ui_lang
        self.model_lock = model_lock

        self.engine = None
        self.result = None
        self.selected_file = None
        self.file_duration = 0.0
        self._transcribing = False

        self.setWindowTitle(t("ft_title", ui_lang))
        self.setMinimumSize(600, 650)
        self.resize(700, 750)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title = QLabel(t("ft_title", self.ui_lang))
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Drop zone
        self.drop_zone = DropZone(self.ui_lang)
        self.drop_zone.file_dropped.connect(self._load_file)
        self.drop_zone.browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(self.drop_zone)

        # File info
        self.file_info = QLabel("")
        self.file_info.setStyleSheet("color: #ccc; font-size: 12px;")
        layout.addWidget(self.file_info)

        # Options row
        opts = QHBoxLayout()

        # Language selector
        opts.addWidget(QLabel(t("ft_language", self.ui_lang)))
        self.lang_combo = QComboBox()
        from settings_window import LANGUAGES
        for code, name in LANGUAGES:
            self.lang_combo.addItem(name, code)
        # Set current language
        current_lang = self.config.get("language", "hu")
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == current_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        opts.addWidget(self.lang_combo)
        opts.addStretch()

        layout.addLayout(opts)

        # Checkboxes row
        checks = QHBoxLayout()
        self.vad_check = QCheckBox(t("ft_vad", self.ui_lang))
        self.vad_check.setChecked(True)
        checks.addWidget(self.vad_check)

        self.diarize_check = QCheckBox(t("ft_diarization", self.ui_lang))
        self.diarize_check.setChecked(False)
        self._update_diarize_state()
        self.diarize_check.stateChanged.connect(self._on_diarize_toggled)
        checks.addWidget(self.diarize_check)

        self.diarize_setup_btn = QPushButton(t("ft_diarization_setup_btn", self.ui_lang))
        self.diarize_setup_btn.setMaximumWidth(120)
        self.diarize_setup_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.diarize_setup_btn.clicked.connect(self._show_diarization_setup_dialog)
        checks.addWidget(self.diarize_setup_btn)
        checks.addStretch()

        layout.addLayout(checks)

        # Progress section
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_row.addWidget(self.progress_bar)
        self.cancel_btn = QPushButton(t("ft_cancel", self.ui_lang))
        self.cancel_btn.setMaximumWidth(80)
        self.cancel_btn.clicked.connect(self._cancel_transcription)
        progress_row.addWidget(self.cancel_btn)
        progress_layout.addLayout(progress_row)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #aaa; font-size: 11px;")
        progress_layout.addWidget(self.progress_label)

        layout.addWidget(self.progress_frame)

        # Results text area
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("monospace", 10))
        self.results_text.setPlaceholderText("")
        self.results_text.setMinimumHeight(200)
        layout.addWidget(self.results_text, stretch=1)

        # Button bar
        btn_bar = QHBoxLayout()

        self.start_btn = QPushButton(t("ft_start", self.ui_lang))
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        self.start_btn.clicked.connect(self._start_transcription)
        btn_bar.addWidget(self.start_btn)

        self.copy_btn = QPushButton(t("ft_copy_all", self.ui_lang))
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_all)
        btn_bar.addWidget(self.copy_btn)

        self.export_btn = QPushButton(t("ft_export", self.ui_lang))
        self.export_btn.setEnabled(False)
        export_menu = QMenu(self)
        export_menu.addAction(t("ft_export_srt", self.ui_lang), self._export_srt)
        export_menu.addAction(t("ft_export_vtt", self.ui_lang), self._export_vtt)
        export_menu.addAction(t("ft_export_txt", self.ui_lang), self._export_txt)
        export_menu.addAction(t("ft_export_json", self.ui_lang), self._export_json)
        self.export_btn.setMenu(export_menu)
        btn_bar.addWidget(self.export_btn)

        btn_bar.addStretch()

        close_btn = QPushButton(t("ft_close", self.ui_lang))
        close_btn.clicked.connect(self.close)
        btn_bar.addWidget(close_btn)

        layout.addLayout(btn_bar)

    def _connect_signals(self):
        self.progress_updated.connect(self._on_progress)
        self.segment_ready.connect(self._on_segment)
        self.transcription_complete.connect(self._on_complete)
        self.transcription_error.connect(self._on_error)

    # --- File Loading ---

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("ft_browse_title", self.ui_lang), "",
            "Audio/Video (*.wav *.mp3 *.m4a *.flac *.ogg *.mp4 *.mkv *.webm *.avi *.mov *.aac *.wma);;All (*)"
        )
        if file_path:
            self._load_file(file_path)

    @Slot(str)
    def _load_file(self, file_path: str):
        self.selected_file = file_path
        self.file_duration = get_audio_duration(file_path)

        name = os.path.basename(file_path)
        dur = format_duration(self.file_duration)
        self.file_info.setText(f"{t('ft_file_label', self.ui_lang)} {name}     {t('ft_duration_label', self.ui_lang)} {dur}")

        # Update drop zone to show loaded file
        self.drop_zone.hint_label.setText(f"✓ {name}  ({dur})")
        self.drop_zone.hint_label.setStyleSheet("color: #4CAF50; border: none; font-size: 12px;")

        self.start_btn.setEnabled(True)
        self.results_text.clear()
        self.result = None
        self.copy_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_frame.setVisible(False)

    # --- Transcription ---

    def _start_transcription(self):
        if not self.selected_file or self._transcribing:
            return

        if self.model is None:
            self.progress_label.setText(t("ft_model_busy", self.ui_lang))
            return

        self._transcribing = True
        self.results_text.clear()
        self.result = None
        self.start_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress_frame.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)
        self.progress_label.setText("")

        self.engine = TranscriptionEngine(self.model, self.whisper_backend, self.model_lock)

        thread = threading.Thread(target=self._transcription_worker, daemon=True)
        thread.start()

    def _transcription_worker(self):
        """Background worker for transcription + optional diarization"""
        try:
            language = self.lang_combo.currentData()
            vad = self.vad_check.isChecked()
            do_diarize = self.diarize_check.isChecked() and self.diarize_check.isEnabled()

            # Phase 1: Transcription
            result = self.engine.transcribe_file(
                file_path=self.selected_file,
                language=language,
                vad_enabled=vad,
                word_timestamps=False,
                beam_size=5,
                progress_callback=lambda p, s: self.progress_updated.emit(
                    p * (0.80 if do_diarize else 1.0), s
                ),
                segment_callback=lambda seg: self.segment_ready.emit(seg),
            )

            if self.engine.is_cancelled:
                self.transcription_error.emit(t("ft_cancelled", self.ui_lang))
                return

            # Phase 2: Speaker diarization (optional)
            if do_diarize and diarization_manager.is_available():
                self.progress_updated.emit(0.80, t("ft_progress_diarization", self.ui_lang))

                dm = diarization_manager.DiarizationManager(
                    device=self.config.get("device", "cpu")
                )
                diar_result = dm.diarize(self.selected_file)
                result.segments = diarization_manager.merge_speakers(result.segments, diar_result)
                result.has_diarization = True

            self.transcription_complete.emit(result)

        except Exception as e:
            self.transcription_error.emit(str(e))

    def _update_diarize_state(self):
        """Update diarization checkbox based on current state"""
        available = diarization_manager.is_available()
        has_tok = diarization_manager.has_token()
        ready = available and has_tok
        self.diarize_check.setEnabled(ready)
        self.diarize_check.setChecked(ready)

    def _on_diarize_toggled(self, state):
        """Handle diarization checkbox toggle — show setup if not ready"""
        if state and (not diarization_manager.is_available() or not diarization_manager.has_token()):
            self.diarize_check.setChecked(False)
            self._show_diarization_setup_dialog()

    def _show_diarization_setup_dialog(self):
        """Show dialog to set up speaker diarization (install + token)"""
        import webbrowser
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout

        pyannote_installed = diarization_manager.is_available()

        dlg = QDialog(self)
        dlg.setWindowTitle(t("ft_diarization_setup_title", self.ui_lang))
        dlg.setMinimumWidth(500)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        # Intro
        intro = QLabel(t("ft_diarization_setup_intro", self.ui_lang))
        intro.setWordWrap(True)
        intro.setFont(QFont("", 11))
        layout.addWidget(intro)

        # Step 0: Install pyannote (if not installed)
        step0_label = QLabel(t("ft_diarization_step0", self.ui_lang))
        step0_label.setWordWrap(True)
        layout.addWidget(step0_label)

        venv_pip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "pip")
        pip_cmd = f"{venv_pip} install pyannote-audio"
        cmd_field = QLineEdit(pip_cmd)
        cmd_field.setReadOnly(True)
        cmd_field.setStyleSheet("font-family: monospace; font-size: 12px; padding: 5px; background: #2b2b2b; color: #e0e0e0; border: 1px solid #555;")
        layout.addWidget(cmd_field)

        copy_cmd_btn = QPushButton(t("download_copy_cmd", self.ui_lang))
        copy_cmd_btn.setMaximumWidth(160)
        copy_cmd_btn.clicked.connect(lambda: (QApplication.clipboard().setText(pip_cmd), copy_cmd_btn.setText("✓")))
        layout.addWidget(copy_cmd_btn)

        if pyannote_installed:
            step0_label.setStyleSheet("color: #4CAF50;")
            step0_label.setText("✓ " + t("ft_diarization_step0_done", self.ui_lang))
            cmd_field.setVisible(False)
            copy_cmd_btn.setVisible(False)

        # Separator
        sep = QLabel("─" * 50)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        # Step 1: Create token
        step1 = QLabel(t("ft_diarization_step1", self.ui_lang))
        step1.setWordWrap(True)
        layout.addWidget(step1)
        hint1 = QLabel(t("ft_diarization_step1_hint", self.ui_lang))
        hint1.setWordWrap(True)
        hint1.setStyleSheet("color: #888; font-size: 11px; margin-left: 10px;")
        layout.addWidget(hint1)
        btn1 = QPushButton(t("ft_diarization_step1_btn", self.ui_lang))
        btn1.setStyleSheet("padding: 6px 12px; color: #4CAF50;")
        btn1.clicked.connect(lambda: webbrowser.open("https://huggingface.co/settings/tokens"))
        layout.addWidget(btn1)

        # Step 2: Accept license
        step2 = QLabel(t("ft_diarization_step2", self.ui_lang))
        step2.setWordWrap(True)
        layout.addWidget(step2)
        hint2 = QLabel(t("ft_diarization_step2_hint", self.ui_lang))
        hint2.setWordWrap(True)
        hint2.setStyleSheet("color: #888; font-size: 11px; margin-left: 10px;")
        layout.addWidget(hint2)
        btn2 = QPushButton(t("ft_diarization_step2_btn", self.ui_lang))
        btn2.setStyleSheet("padding: 6px 12px; color: #4CAF50;")
        btn2.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/speaker-diarization-3.1"))
        layout.addWidget(btn2)
        btn2b = QPushButton(t("ft_diarization_step2b_btn", self.ui_lang))
        btn2b.setStyleSheet("padding: 6px 12px; color: #4CAF50;")
        btn2b.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/segmentation-3.0"))
        layout.addWidget(btn2b)
        btn2c = QPushButton(t("ft_diarization_step2c_btn", self.ui_lang))
        btn2c.setStyleSheet("padding: 6px 12px; color: #4CAF50;")
        btn2c.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/speaker-diarization-community-1"))
        layout.addWidget(btn2c)

        # Step 3: Token input
        step3 = QLabel(t("ft_diarization_step3", self.ui_lang))
        layout.addWidget(step3)
        token_field = QLineEdit()
        token_field.setPlaceholderText("hf_...")
        token_field.setEchoMode(QLineEdit.EchoMode.Password)
        token_field.setStyleSheet("font-family: monospace; font-size: 13px; padding: 6px; background: #2b2b2b; color: #e0e0e0; border: 1px solid #555;")
        # Pre-fill if token already exists
        existing = diarization_manager.get_token()
        if existing:
            token_field.setText(existing)
        layout.addWidget(token_field)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton(t("ft_diarization_save", self.ui_lang))
        save_btn.setStyleSheet("padding: 6px 20px; font-weight: bold;")

        def on_save():
            tok = token_field.text().strip()
            if tok:
                diarization_manager.save_token(tok)
                self._update_diarize_state()
                if diarization_manager.is_available() and diarization_manager.has_token():
                    self.diarize_check.setChecked(True)
                self.progress_label.setText(t("ft_diarization_token_saved", self.ui_lang))
                dlg.accept()

        save_btn.clicked.connect(on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton(t("ft_cancel", self.ui_lang))
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _cancel_transcription(self):
        if self.engine:
            self.engine.cancel()

    # --- Signal Handlers ---

    @Slot(float, str)
    def _on_progress(self, progress: float, status: str):
        self.progress_bar.setValue(int(progress * 100))
        self.progress_label.setText(
            t("ft_progress", self.ui_lang, current=status.split("/")[0] if "/" in status else "?",
              total=status.split("/")[1] if "/" in status else "?")
            if "/" in status else status
        )

    @Slot(object)
    def _on_segment(self, seg: TranscriptionSegment):
        ts = format_timestamp(seg.start)
        speaker = f" {seg.speaker}:" if seg.speaker else ""
        self.results_text.append(f"[{ts}]{speaker} {seg.text}")

    @Slot(object)
    def _on_complete(self, result: TranscriptionResult):
        self.result = result
        self._transcribing = False
        self.progress_bar.setValue(100)
        dur = format_duration(result.duration)
        self.progress_label.setText(
            t("ft_complete", self.ui_lang, segments=len(result.segments), duration=dur)
        )
        self.start_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # If diarization was done, refresh the text with speaker labels
        if result.has_diarization:
            self.results_text.clear()
            for seg in result.segments:
                ts = format_timestamp(seg.start)
                speaker = f" {seg.speaker}:" if seg.speaker else ""
                self.results_text.append(f"[{ts}]{speaker} {seg.text}")

    @Slot(str)
    def _on_error(self, error: str):
        self._transcribing = False
        self.progress_label.setText(error)
        self.progress_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
        self.start_btn.setEnabled(True)
        QTimer.singleShot(3000, lambda: self.progress_label.setStyleSheet("color: #aaa; font-size: 11px;"))

    # --- Copy & Export ---

    def _copy_all(self):
        if self.result:
            lines = []
            for seg in self.result.segments:
                ts = format_timestamp(seg.start)
                speaker = f" {seg.speaker}:" if seg.speaker else ""
                lines.append(f"[{ts}]{speaker} {seg.text}")
            QApplication.clipboard().setText("\n".join(lines))
            self.progress_label.setText(t("ft_copied", self.ui_lang))

    def _export_file(self, export_fn, default_ext, filter_str):
        if not self.result:
            return
        base = os.path.splitext(self.selected_file)[0] if self.selected_file else "transcription"
        default_path = f"{base}.{default_ext}"
        path, _ = QFileDialog.getSaveFileName(self, t("ft_export", self.ui_lang), default_path, filter_str)
        if path:
            export_fn(self.result, path)
            self.progress_label.setText(t("ft_export_success", self.ui_lang, path=os.path.basename(path)))

    def _export_srt(self):
        self._export_file(export_srt, "srt", "SRT (*.srt)")

    def _export_vtt(self):
        self._export_file(export_vtt, "vtt", "VTT (*.vtt)")

    def _export_txt(self):
        self._export_file(export_txt, "txt", "Text (*.txt)")

    def _export_json(self):
        self._export_file(export_json, "json", "JSON (*.json)")
