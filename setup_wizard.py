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
    QRadioButton, QButtonGroup, QProgressBar, QFrame, QApplication
)
from PySide6.QtGui import QFont, QCursor

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
]

# Default model
DEFAULT_MODEL = "small"


def get_config_path():
    """Get user config file path"""
    config_dir = os.path.join(os.path.expanduser("~"), ".config", "whisperrocket")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")


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

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Create the UI"""
        self.setWindowTitle(t("wizard_title", self.lang))
        self.setFixedSize(450, 440)
        self.setModal(True)

        # Remove close button - user must complete setup
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowTitleHint |
            Qt.CustomizeWindowHint
        )

        layout = QVBoxLayout(self)
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

            if model_id == DEFAULT_MODEL:
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

    def setup_connections(self):
        """Connect signals"""
        self.download_btn.clicked.connect(self.start_download)
        self.button_group.buttonClicked.connect(self.on_model_selected)
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

    def start_download(self):
        """Start download (CUDA first if needed, then model)"""
        if self.is_downloading:
            return

        self.is_downloading = True
        self.download_success = False
        self.download_error = None

        # Update UI
        self.download_btn.setEnabled(False)
        self.download_btn.setText(t("wizard_downloading", self.lang))

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
            # CUDA download failed - continue with CPU mode
            self.progress_label.setText(t("cuda_download_failed", self.lang))
            self.device = "cpu"  # Fallback to CPU
            QTimer.singleShot(2000, self.start_model_download)

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
            self.progress_label.setText(f"Error: {state.error[:50]}")
            self.progress_label.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            self.progress_bar.setValue(0)

            # Re-enable for retry
            self.is_downloading = False
            self.download_manager.clear_error()
            self.download_btn.setEnabled(True)
            self.download_btn.setText(t("wizard_download_start", self.lang))
            for radio in self.model_radios.values():
                radio.setEnabled(True)
            return

        if state.is_downloading:
            # Update progress bar
            progress_percent = int(state.progress * 100)
            self.progress_bar.setValue(progress_percent)

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
        # Use user config directory (writable) instead of app directory (read-only in AppImage)
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "whisperrocket")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.json")

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
        config.setdefault("hotkey", "alt+s")
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
