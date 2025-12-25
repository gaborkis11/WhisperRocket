#!/usr/bin/env python3
"""
WhisperRocket - Setup Wizard
First-run blocking dialog for model selection and download
"""

import json
import os
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QProgressBar, QFrame, QApplication
)
from PySide6.QtGui import QFont, QCursor

from translations import t
from download_manager import get_download_manager
from platform_support import get_platform_handler


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


def get_ui_language():
    """Get UI language from config"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("ui_language", "en")
    except:
        return "en"


def get_device():
    """Get device - platform detection first, then config"""
    platform_handler = get_platform_handler()

    # Platform detekció - macOS Apple Silicon = MLX, NVIDIA = CUDA
    gpu_type = platform_handler.get_gpu_type()
    if gpu_type == "mlx":
        return "mlx"
    elif gpu_type == "cuda":
        return "cuda"

    # Fallback: config-ból vagy CPU
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("device", "cpu")
    except:
        return "cpu"


class SetupWizard(QDialog):
    """Blocking first-run setup dialog"""

    download_complete = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = get_ui_language()
        self.device = get_device()
        self.download_manager = get_download_manager()
        self.selected_model = DEFAULT_MODEL
        self.is_downloading = False

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
        """Start model download"""
        if self.is_downloading:
            return

        self.is_downloading = True

        # Update UI
        self.download_btn.setEnabled(False)
        self.download_btn.setText(t("wizard_downloading", self.lang))

        # Disable model selection
        for radio in self.model_radios.values():
            radio.setEnabled(False)

        # Show progress - indeterminate mode (pörgő animáció)
        self.progress_frame.setVisible(True)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_label.setText(t("wizard_downloading", self.lang) + " - please wait...")

        # Start download in background thread
        import threading
        self.download_thread = threading.Thread(
            target=self._do_download,
            daemon=True
        )
        self.download_thread.start()

        # Check completion timer
        self.progress_timer.start(1000)

    def _do_download(self):
        """Download worker - runs in background thread"""
        from huggingface_hub import snapshot_download
        try:
            if self.device == "mlx":
                repo_id = f"mlx-community/whisper-{self.selected_model}-mlx"
            else:
                repo_id = f"Systran/faster-whisper-{self.selected_model}"

            snapshot_download(repo_id=repo_id, local_files_only=False)
            self.download_success = True
        except Exception as e:
            self.download_error = str(e)
            self.download_success = False

    def update_progress(self):
        """Check if download completed (called by timer)"""
        # Check if download thread finished
        if hasattr(self, 'download_thread') and not self.download_thread.is_alive():
            self.progress_timer.stop()

            if hasattr(self, 'download_success') and self.download_success:
                self.on_download_complete()
            elif hasattr(self, 'download_error'):
                self.progress_label.setText(f"Hiba: {self.download_error[:50]}")
                self.progress_label.setStyleSheet("color: #ff6b6b;")
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(0)

                # Re-enable for retry
                self.is_downloading = False
                self.download_btn.setEnabled(True)
                self.download_btn.setText(t("wizard_download_start", self.lang))
                for radio in self.model_radios.values():
                    radio.setEnabled(True)

    def on_download_complete(self):
        """Handle download completion"""
        self.progress_timer.stop()
        self.progress_bar.setMaximum(100)  # Back to determinate
        self.progress_bar.setValue(100)
        self.progress_label.setText("✓ " + t("download_complete", self.lang) + " - Restarting...")
        self.progress_label.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
        self.download_btn.setText("✓ Complete!")

        # Save config and complete
        self.save_config()
        QTimer.singleShot(1500, self.accept)  # Longer delay so user can see the message

    def save_config(self):
        """Save selected model and device to config"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except:
            config = {}

        config["model"] = self.selected_model
        config["device"] = self.device
        config["setup_complete"] = True

        # compute_type beállítása device alapján
        if self.device in ("cuda", "mlx"):
            config["compute_type"] = "float16"
        else:
            config["compute_type"] = "int8"

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
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')

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
