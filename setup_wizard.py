#!/usr/bin/env python3
"""
WhisperRocket - Setup Wizard
First-run blocking dialog for model selection and download
"""

import json
import os
import sys
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QProgressBar, QFrame, QApplication,
    QStackedLayout, QWidget, QComboBox
)
from PySide6.QtGui import QFont, QCursor

import config_paths
import system_check
from qt_helpers import STATUS_ICONS, make_copy_row
from translations import t
from download_manager import get_download_manager
from platform_support import get_platform_handler

# CUDA manager (optional - only for NVIDIA GPU)
try:
    from cuda_manager import is_cuda_installed, download_cuda_wheels, CudaDownloadState
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False


# Available models for selection
MODELS = [
    ("tiny", "wizard_model_tiny"),
    ("base", "wizard_model_base"),
    ("small", "wizard_model_small"),
    ("medium", "wizard_model_medium"),
    ("large-v3-turbo", "wizard_model_turbo"),
    ("large-v3", "wizard_model_large"),
    ("large-v3-hu", "wizard_model_hu"),
]

# Default model
DEFAULT_MODEL = "small"


def get_config_path():
    """Get the config file path the running app reads (see config_paths)"""
    return config_paths.get_config_path()


def get_ui_language():
    """Get UI language from config"""
    config_path = get_config_path()
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("ui_language", "en")
    except:
        return "en"


def get_device():
    """Get device - platform detection first, then config"""
    platform_handler = get_platform_handler()

    # Platform detection - macOS Apple Silicon = MLX, NVIDIA = CUDA
    gpu_type = platform_handler.get_gpu_type()
    if gpu_type == "mlx":
        return "mlx"
    elif gpu_type == "cuda":
        return "cuda"

    # Fallback: config-ból vagy CPU
    config_path = get_config_path()
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("device", "cpu")
    except:
        return "cpu"


class SetupWizard(QDialog):
    """Blocking first-run setup dialog"""

    download_complete = Signal()
    cuda_progress_signal = Signal(object)  # CudaDownloadState

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = get_ui_language()
        self.device = get_device()
        self.download_manager = get_download_manager()
        self.selected_model = DEFAULT_MODEL
        self.is_downloading = False
        self.cuda_download_complete = False
        self.needs_cuda = self.device == "cuda" and CUDA_AVAILABLE and not is_cuda_installed()

        # System check page: always shown on Wayland (the install needs to be
        # visually followable there), and on X11 only when something critical
        # is broken. Non-Linux platforms skip straight to model selection.
        self.health_results = []
        self.show_check_page = False
        if sys.platform == "linux":
            self.health_results = system_check.run_all()
            self.show_check_page = (
                system_check.get_session_type() == "wayland"
                or any(r.critical and r.status in ("warn", "fail")
                       for r in self.health_results))

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Create the UI"""
        self.setWindowTitle(t("wizard_title", self.lang))
        self.setFixedWidth(450)
        self.setMinimumHeight(440)
        self.setModal(True)

        # Remove close button - user must complete setup
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowTitleHint |
            Qt.CustomizeWindowHint
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(0)

        # Language selector - lives outside the pages so it survives rebuilds;
        # switching it re-renders the wizard in the chosen language and saves
        # the choice to the config (Settings can change it again later)
        lang_row = QHBoxLayout()
        lang_row.setContentsMargins(0, 0, 16, 0)
        lang_row.addStretch()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Magyar", "hu")
        self.lang_combo.setCurrentIndex(1 if self.lang == "hu" else 0)
        self.lang_combo.setFixedWidth(110)
        lang_row.addWidget(self.lang_combo)
        outer.addLayout(lang_row)

        # Two pages: system check first (when relevant), then model selection
        self.stack = QStackedLayout()
        outer.addLayout(self.stack)
        self._build_pages()
        self.stack.setCurrentWidget(
            self.page_check if self.show_check_page else self.page_model)

    def _build_pages(self):
        """(Re)build both pages in the current language."""
        while self.stack.count():
            widget = self.stack.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.page_check = QWidget()
        self._build_check_page(self.page_check)
        self.page_model = QWidget()
        self._build_model_page(self.page_model)
        self.stack.addWidget(self.page_check)
        self.stack.addWidget(self.page_model)
        self._connect_widgets()

    def change_language(self, index):
        """Re-render the wizard in the selected language and persist it"""
        lang = self.lang_combo.itemData(index)
        if lang == self.lang:
            return
        self.lang = lang
        self._persist_language(lang)
        self.setWindowTitle(t("wizard_title", self.lang))
        current = self.stack.currentIndex()
        self._build_pages()
        self.stack.setCurrentIndex(current)

    def _persist_language(self, lang):
        """Save the explicit first-run language choice: UI language and the
        dictation language both follow it (Settings can split them later)."""
        config_path = get_config_path()
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception:
            config = {}
        config["ui_language"] = lang
        config["language"] = lang
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Could not save language choice: {e}")

    def _build_check_page(self, page):
        """System-check page: one row per check, copyable fix commands,
        re-check button. Makes the Wayland onboarding visually followable."""
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(30, 25, 30, 25)

        title = QLabel(t("wizard_syscheck_title", self.lang))
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(t("wizard_syscheck_subtitle", self.lang))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #888; margin-bottom: 5px;")
        layout.addWidget(subtitle)

        rows_frame = QFrame()
        rows_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
            }
        """)
        self.check_rows_layout = QVBoxLayout(rows_frame)
        self.check_rows_layout.setSpacing(6)
        self.check_rows_layout.setContentsMargins(15, 12, 15, 12)
        layout.addWidget(rows_frame)
        self._populate_check_rows()

        self.check_note = QLabel("")
        self.check_note.setWordWrap(True)
        self.check_note.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.check_note)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self.recheck_btn = QPushButton(t("wizard_syscheck_recheck", self.lang))
        self.recheck_btn.setFixedHeight(42)
        self.recheck_btn.setCursor(Qt.PointingHandCursor)
        self.recheck_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #6a6a6a; }
        """)
        btn_row.addWidget(self.recheck_btn)

        self.continue_btn = QPushButton("")
        self.continue_btn.setFixedHeight(42)
        self.continue_btn.setCursor(Qt.PointingHandCursor)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A84FF;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0071E3; }
        """)
        btn_row.addWidget(self.continue_btn)
        layout.addLayout(btn_row)

        self._update_check_footer()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # setParent(None) removes it from painting immediately;
                # deleteLater alone leaves it visible until the event loop runs
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                SetupWizard._clear_layout(item.layout())
                item.layout().deleteLater()

    def _populate_check_rows(self):
        self._clear_layout(self.check_rows_layout)
        for r in self.health_results:
            icon, color = STATUS_ICONS.get(r.status, STATUS_ICONS["warn"])
            row = QLabel(
                f'<span style="color: {color}; font-weight: bold;">{icon}</span>  '
                f'{t(r.label_key, self.lang)}'
                + (f'  <span style="color: #888; font-size: 11px;">— {r.detail}</span>'
                   if r.detail else ""))
            row.setWordWrap(True)
            row.setStyleSheet("font-size: 13px; background: transparent;")
            self.check_rows_layout.addWidget(row)
            if r.fix_cmd and r.status in ("warn", "fail"):
                self.check_rows_layout.addLayout(make_copy_row(r.fix_cmd))

    def _update_check_footer(self):
        criticals_bad = any(r.critical and r.status in ("warn", "fail")
                            for r in self.health_results)
        if criticals_bad:
            self.continue_btn.setText(t("wizard_syscheck_continue_anyway", self.lang))
            self.check_note.setText(t("wizard_syscheck_warn_note", self.lang))
            self.check_note.setStyleSheet("color: #FF9800; font-size: 12px;")
        else:
            self.continue_btn.setText(t("wizard_syscheck_continue", self.lang))
            self.check_note.setText(t("wizard_syscheck_all_ok", self.lang))
            self.check_note.setStyleSheet("color: #4CAF50; font-size: 12px;")

    def recheck_system(self):
        """Re-run the checks (e.g. after installing a missing tool)"""
        self.health_results = system_check.run_all()
        self._populate_check_rows()
        self._update_check_footer()

    def continue_to_model_page(self):
        self.stack.setCurrentWidget(self.page_model)

    def _build_model_page(self, page):
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 25, 30, 25)

        # Welcome title
        title = QLabel(t("wizard_welcome", self.lang))
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel(t("wizard_select_model", self.lang))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #888; margin-bottom: 5px;")
        layout.addWidget(subtitle)

        # Model selection frame
        model_frame = QFrame()
        model_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
            }
        """)
        model_layout = QVBoxLayout(model_frame)
        model_layout.setSpacing(4)
        model_layout.setContentsMargins(15, 12, 15, 12)

        # Radio buttons for models
        self.button_group = QButtonGroup(self)
        self.model_radios = {}

        for model_id, label_key in MODELS:
            radio = QRadioButton(t(label_key, self.lang))
            radio.setStyleSheet("""
                QRadioButton {
                    padding: 8px 5px;
                    font-size: 13px;
                }
                QRadioButton::indicator {
                    width: 16px;
                    height: 16px;
                }
            """)
            self.button_group.addButton(radio)
            self.model_radios[model_id] = radio
            model_layout.addWidget(radio)

            # selected_model (not DEFAULT_MODEL): a language-switch rebuild
            # must keep whatever the user already picked
            if model_id == self.selected_model:
                radio.setChecked(True)

        layout.addWidget(model_frame)

        # Progress section (hidden initially)
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
            }
        """)
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setSpacing(8)
        progress_layout.setContentsMargins(15, 12, 15, 12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("color: #aaa; font-size: 12px;")
        progress_layout.addWidget(self.progress_label)

        layout.addWidget(self.progress_frame)

        layout.addStretch()

        # Download button
        self.download_btn = QPushButton(t("wizard_download_start", self.lang))
        self.download_btn.setFixedHeight(48)
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #0A84FF;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0071E3;
            }
            QPushButton:pressed {
                background-color: #0062CC;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        layout.addWidget(self.download_btn)

        # Secondary action after a failed CUDA download (hidden by default)
        self.cpu_fallback_btn = QPushButton(t("cuda_continue_cpu", self.lang))
        self.cpu_fallback_btn.setFixedHeight(36)
        self.cpu_fallback_btn.setCursor(Qt.PointingHandCursor)
        self.cpu_fallback_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #FF9800;
                border: 1px solid #FF9800;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 152, 0, 0.1);
            }
        """)
        self.cpu_fallback_btn.setVisible(False)
        layout.addWidget(self.cpu_fallback_btn)

    def _connect_widgets(self):
        """Connect widget signals - called after every page (re)build, the
        widgets are new objects each time"""
        self.download_btn.clicked.connect(self.start_download)
        self.cpu_fallback_btn.clicked.connect(self.continue_with_cpu)
        self.recheck_btn.clicked.connect(self.recheck_system)
        self.continue_btn.clicked.connect(self.continue_to_model_page)
        self.button_group.buttonClicked.connect(self.on_model_selected)

    def setup_connections(self):
        """Connect signals that live for the whole dialog (once only)"""
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        self.cuda_progress_signal.connect(self.on_cuda_progress)

        # Progress update timer
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)

    def on_model_selected(self, button):
        """Handle model selection"""
        for model_id, radio in self.model_radios.items():
            if radio == button:
                self.selected_model = model_id
                break

    def _show_conversion_deps_dialog(self):
        """Show dialog for missing conversion dependencies with copyable command"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
        venv_pip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "pip")
        cmd = f"{venv_pip} install torch transformers"

        dlg = QDialog(self)
        dlg.setWindowTitle("WhisperRocket")
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        msg = QLabel(t("download_install_deps_msg", self.lang))
        msg.setWordWrap(True)
        layout.addWidget(msg)

        cmd_field = QLineEdit(cmd)
        cmd_field.setReadOnly(True)
        cmd_field.setStyleSheet("font-family: monospace; font-size: 13px; padding: 6px; background: #2b2b2b; color: #e0e0e0; border: 1px solid #555;")
        layout.addWidget(cmd_field)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton(t("download_copy_cmd", self.lang))
        copy_btn.clicked.connect(lambda: (QApplication.clipboard().setText(cmd), copy_btn.setText("✓")))
        btn_row.addWidget(copy_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def start_download(self):
        """Start download (CUDA first if needed, then model)"""
        if self.is_downloading:
            return

        # Check conversion dependencies before starting
        from download_manager import _needs_conversion
        if _needs_conversion(self.selected_model):
            try:
                import torch
                import transformers
            except ImportError:
                self._show_conversion_deps_dialog()
                return

        self.is_downloading = True
        self.download_success = False
        self.download_error = None

        # Update UI
        self.download_btn.setEnabled(False)
        self.download_btn.setText(t("wizard_downloading", self.lang))
        self.cpu_fallback_btn.setVisible(False)
        self.progress_label.setStyleSheet("color: #aaa; font-size: 12px;")
        # Language switch rebuilds the pages - not safe while a download is
        # updating the progress widgets
        self.lang_combo.setEnabled(False)

        # Disable model selection
        for radio in self.model_radios.values():
            radio.setEnabled(False)

        # Show progress
        self.progress_frame.setVisible(True)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # If CUDA is needed, download it first
        if self.needs_cuda and not self.cuda_download_complete:
            self.progress_label.setText(t("cuda_downloading", self.lang))
            self.start_cuda_download()
        else:
            # Start model download directly
            self.progress_label.setText(t("wizard_downloading", self.lang) + " - 0%")
            self.download_manager.start_download(self.selected_model, self.device)
            self.progress_timer.start(250)

    def start_cuda_download(self):
        """Start CUDA libraries download in background thread"""
        def cuda_progress_callback(state: CudaDownloadState):
            # Emit signal to update UI on main thread
            self.cuda_progress_signal.emit(state)

        # Start CUDA download in thread
        threading.Thread(
            target=download_cuda_wheels,
            args=(cuda_progress_callback,),
            daemon=True
        ).start()

    def on_cuda_progress(self, state: CudaDownloadState):
        """Handle CUDA progress update from background thread (runs on main thread)"""
        self.progress_bar.setValue(int(state.progress * 100))
        if state.current_package:
            self.progress_label.setText(
                t("cuda_download_progress", self.lang, name=state.current_package)
            )

        if state.completed:
            self.cuda_download_complete = True
            # Now start model download
            QTimer.singleShot(500, self.start_model_download)
        elif state.error:
            # CUDA download failed - offer retry; only an explicit user choice
            # may persist CPU mode (a transient network error must not
            # permanently slow down a GPU machine)
            self.progress_label.setText(t("cuda_download_failed_retry", self.lang))
            self.progress_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.is_downloading = False
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("cuda_retry", self.lang))
            self.cpu_fallback_btn.setVisible(True)
            self.lang_combo.setEnabled(True)

    def continue_with_cpu(self):
        """User explicitly chose CPU mode after a failed CUDA download"""
        self.cpu_fallback_btn.setVisible(False)
        self.device = "cpu"
        self.needs_cuda = False
        self.is_downloading = True
        self.download_btn.setEnabled(False)
        self.download_btn.setText(t("wizard_downloading", self.lang))
        self.progress_label.setStyleSheet("color: #aaa; font-size: 12px;")
        self.start_model_download()

    def start_model_download(self):
        """Start model download after CUDA is ready"""
        self.progress_bar.setValue(0)
        self.progress_label.setText(t("wizard_downloading", self.lang) + " - 0%")
        self.download_manager.start_download(self.selected_model, self.device)
        self.progress_timer.start(250)

    def update_progress(self):
        """Update progress display from DownloadManager (called by timer)"""
        state = self.download_manager.get_state()

        if state.completed:
            self.progress_timer.stop()
            self.on_download_complete()
            return

        if state.error:
            self.progress_timer.stop()
            error_text = t(state.error, self.lang)
            self.progress_label.setText(f"Error: {error_text[:80]}")
            self.progress_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.progress_bar.setValue(0)

            # Re-enable for retry
            self.is_downloading = False
            self.download_manager.clear_error()
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("wizard_download_start", self.lang))
            self.lang_combo.setEnabled(True)
            for radio in self.model_radios.values():
                radio.setEnabled(True)
            return

        if state.is_downloading:
            # Update progress bar
            progress_percent = int(state.progress * 100)
            self.progress_bar.setValue(progress_percent)

            # If there's a status message (e.g. conversion phase), show it
            if state.status_message:
                self.progress_bar.setMaximum(0)  # Pulsating mode
                progress_text = f"{t(state.status_message, self.lang)}"
            else:
                if self.progress_bar.maximum() == 0:
                    self.progress_bar.setMaximum(100)
                # Format progress text with details
                downloaded = self.download_manager.format_size(state.downloaded_bytes)
                total = self.download_manager.format_size(state.total_bytes)
                speed = self.download_manager.format_speed()
                eta = self.download_manager.format_eta()
                progress_text = f"{t('wizard_downloading', self.lang)} - {progress_percent}%  ({downloaded} / {total})  {speed}  ETA: {eta}"

            self.progress_label.setText(progress_text)

    def on_download_complete(self):
        """Handle download completion"""
        self.progress_timer.stop()
        self.progress_bar.setMaximum(100)  # Back to determinate
        self.progress_bar.setValue(100)

        # Save config first
        self.save_config()

        # If CUDA was downloaded and we're in AppImage, need to restart
        # so AppRun can set LD_LIBRARY_PATH correctly
        if self.needs_cuda and os.environ.get("APPIMAGE"):
            self.progress_label.setText("✓ " + t("download_complete", self.lang) + " - Restarting...")
            self.progress_label.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
            self.download_btn.setText("✓ Complete!")
            QTimer.singleShot(1500, self.restart_app)
        else:
            self.progress_label.setText("✓ " + t("download_complete", self.lang))
            self.progress_label.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
            self.download_btn.setText("✓ Complete!")
            QTimer.singleShot(1500, self.accept)

    def restart_app(self):
        """Restart the app (for AppImage after CUDA download)"""
        appimage_path = os.environ.get("APPIMAGE")
        if appimage_path:
            # Re-execute the AppImage - this replaces the current process
            os.execv(appimage_path, [appimage_path] + sys.argv[1:])
        else:
            # Fallback - just close wizard
            self.accept()

    def save_config(self):
        """Save selected model and device to config"""
        # config_paths keeps this writable: project dir in dev mode, user config
        # dir when bundled (the AppImage's own directory is read-only)
        config_path = get_config_path()

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except:
            config = {}

        # Set values from wizard
        config["model"] = self.selected_model
        config["device"] = self.device
        config["setup_complete"] = True

        # Set compute_type based on device
        if self.device in ("cuda", "mlx"):
            config["compute_type"] = "float16"
        else:
            config["compute_type"] = "int8"

        # Set defaults for missing keys (required for first run)
        # Same default as install.sh writes - the two must not diverge
        config.setdefault("hotkey", "ctrl+shift+s")
        config.setdefault("language", "en")
        config.setdefault("ui_language", "en")
        config.setdefault("sample_rate", 16000)
        config.setdefault("input_device", None)
        config.setdefault("output_device", None)
        config.setdefault("popup_display_duration", 5)

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

    def closeEvent(self, event):
        """Prevent closing during download"""
        if self.is_downloading:
            event.ignore()
        else:
            # If user somehow closes without completing, exit app
            event.accept()
            sys.exit(0)


def run_setup_wizard() -> bool:
    """
    Run the setup wizard if needed.
    Returns True if app should continue, False to exit.
    """
    config_path = get_config_path()

    # Check if setup is complete
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            if config.get("setup_complete", False):
                return True
    except:
        pass

    # Show wizard
    wizard = SetupWizard()
    result = wizard.exec()

    return result == QDialog.Accepted


# Test
if __name__ == "__main__":
    app = QApplication(sys.argv)

    wizard = SetupWizard()
    result = wizard.exec()

    print(f"Result: {result}")
    print(f"Selected model: {wizard.selected_model}")
