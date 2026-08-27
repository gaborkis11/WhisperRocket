#!/usr/bin/env python3
"""
WhisperRocket Beállítások ablak v2
PyQt6 alapú modern UI tab-okkal
"""
import os
import json
import pathlib
import re
import sys
import shutil
import platform as py_platform
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QTabWidget,
    QProgressBar, QListWidget, QListWidgetItem, QFrame, QSpinBox,
    QScrollArea, QPlainTextEdit, QTextEdit, QDialog, QFileDialog,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QKeySequence, QDesktopServices, QIntValidator

from model_manager import (
    get_downloaded_models, get_active_model, delete_model,
    delete_all_unused, get_total_cache_size, get_freeable_size,
    format_size, is_model_downloaded
)
from download_manager import get_download_manager
from translations import t
from platform_support import get_platform_handler
from qt_helpers import block_wheel_changes

import ai_enhancer
import claude_cli
import dictionary_manager

# Platform handler
platform_handler = get_platform_handler()

# Konfiguráció útvonal (bundled app-ban user könyvtárba mentjük)
def get_config_path():
    """Config fájl útvonala - bundled app-ban user könyvtárba menti"""
    if getattr(sys, 'frozen', False):
        # Bundled app - user könyvtárba mentjük
        if py_platform.system() == "Darwin":
            config_dir = os.path.expanduser("~/Library/Application Support/WhisperRocket")
        else:
            config_dir = os.path.expanduser("~/.config/whisperrocket")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, 'config.json')
    else:
        # Fejlesztői mód - projekt könyvtárban
        return os.path.join(os.path.dirname(__file__), 'config.json')

CONFIG_FILE = get_config_path()
DESKTOP_FILE = os.path.join(os.path.dirname(__file__), 'whisperrocket.desktop')

# Támogatott nyelvek
LANGUAGES = [
    ("hu", "Magyar"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pl", "Polski"),
    ("nl", "Nederlands"),
    ("pt", "Português"),
    ("ru", "Русский"),
    ("ja", "日本語"),
    ("zh", "中文"),
    ("ko", "한국어"),
]

# Whisper modellek
MODELS = [
    ("tiny", "Tiny (~150 MB) - Leggyorsabb"),
    ("base", "Base (~290 MB) - Gyors"),
    ("small", "Small (~490 MB) - Közepes"),
    ("medium", "Medium (~1.5 GB) - Jó"),
    ("large-v3-turbo", "Large-v3-turbo (~1.6 GB) - Gyors és jó"),
    ("large-v3", "Large-v3 (~6 GB) - Legjobb"),
    ("large-v3-hu", "Large-v3-hu (~3 GB) - Magyar optimalizált"),
]

# Device opciók (platform-függő)
def get_available_devices():
    """Elérhető device-ok lekérdezése a platform alapján"""
    devices = []
    gpu_type = platform_handler.get_gpu_type()

    if gpu_type == "cuda":
        devices.append(("cuda", "GPU (CUDA)"))
    elif gpu_type == "mlx":
        devices.append(("mlx", "GPU (Apple Silicon)"))

    devices.append(("cpu", "CPU"))
    return devices

DEVICES = get_available_devices()

# UI nyelvek
UI_LANGUAGES = [
    ("en", "English"),
    ("hu", "Magyar"),
]


def detect_device():
    """GPU elérhetőség automatikus detektálása (platform-független)"""
    gpu_type = platform_handler.get_gpu_type()
    if gpu_type == "cuda":
        return "cuda", "float16"
    elif gpu_type == "mlx":
        return "mlx", "float16"
    return "cpu", "int8"


def load_config():
    """Konfiguráció betöltése"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        device, compute_type = detect_device()
        return {
            "hotkey": "ctrl+shift+s",
            "model": "large-v3",
            "device": device,
            "compute_type": compute_type,
            "language": "hu",
            "sample_rate": 16000,
            "input_device": None,
            "output_device": None,
            # Keep these in step with load_config() in whisper_gui.py - the two
            # default dicts are separate and silently drifting apart is how the
            # setup wizard once wrote to a file the app never read.
            "ai_enhance_enabled": False,
            "ai_model": "sonnet",
            "ai_trigger_phrases": ["fogalmazzuk meg hogy", "fogalmazd meg hogy",
                                   "segíts megfogalmazni", "jarvis segíts megfogalmazni"],
            "ai_timeout_seconds": 120,
            "ai_dictionary_enabled": True
        }


def save_config(config):
    """Konfiguráció mentése"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def is_autostart_enabled():
    """Ellenőrzi, hogy be van-e állítva autostart (platform-specifikus)"""
    return platform_handler.is_autostart_enabled()


def set_autostart(enabled):
    """Autostart be/kikapcsolása (platform-specifikus)"""
    platform_handler.setup_autostart(enabled, app_path=DESKTOP_FILE)



# Seeded into ~/.config/whisperrocket/style_profile.md when the user first opens
# it for editing. Deliberately a set of prompts to answer rather than an example
# profile: a filled-in example would get shipped back to the model as if it
# described the user.
STYLE_PROFILE_TEMPLATE = """# Style profile
<!-- UNFILLED-TEMPLATE: delete this line once you have written your profile.
     While it is here, WhisperRocket ignores this file. -->

Describe how you write, so the cleanup keeps your voice instead of flattening it.
Aggregate traits only - no real messages, no names, nothing you would not want in
a prompt. Delete the questions and leave your answers.

## Sentence length and rhythm
(Short and clipped, or long and flowing? Do you use dashes, ellipses?)

## Greetings and sign-offs
(Do you open with a greeting, or start straight into the message?)

## Language mixing
(Do you mix in English words? Which kinds - technical terms, slang?)

## Swearing
(Where and how do you swear? Which words? This is kept verbatim, never softened.)

## Formality
(How do you address people? Formal, informal, depends on who?)

## Anything else
"""

class _ClaudeInstallWorker(QThread):
    """Runs the official installer off the UI thread so the window stays alive"""
    output = Signal(str)
    done = Signal(bool, str)

    def run(self):
        ok, message = claude_cli.install(on_output=self.output.emit)
        self.done.emit(ok, message)


class ClaudeInstallDialog(QDialog):
    """
    Confirms and runs Anthropic's official Claude Code installer.

    The command is shown in full before anything runs. It downloads and executes
    a script from the network, which is not something to do behind the user's
    back - and it is the same command they would paste into a terminal, which is
    also why the binary stays exactly as Anthropic publishes it.
    """

    def __init__(self, ui_lang, parent=None):
        super().__init__(parent)
        self.ui_lang = ui_lang
        self.worker = None
        self.installed_path = None

        self.setWindowTitle(t("ai_install_title", ui_lang))
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(self._wrapped(t("ai_install_intro", ui_lang)))

        command = QLineEdit(claude_cli.INSTALL_COMMAND)
        command.setReadOnly(True)
        command.setStyleSheet("font-family: monospace;")
        layout.addWidget(command)

        note = self._wrapped(t("ai_install_note", ui_lang))
        note.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(note)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.log.setFixedHeight(160)
        self.log.setVisible(False)
        layout.addWidget(self.log)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.run_btn = QPushButton(t("ai_install_run", ui_lang))
        self.run_btn.clicked.connect(self.start_install)
        buttons.addWidget(self.run_btn)
        self.close_btn = QPushButton(t("ft_close", ui_lang))
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        missing = claude_cli.install_prerequisites_missing()
        if missing:
            self.run_btn.setEnabled(False)
            self.status.setText(
                t("ai_install_missing_tools", ui_lang, tools=", ".join(missing))
            )

    @staticmethod
    def _wrapped(text):
        label = QLabel(text)
        label.setWordWrap(True)
        return label

    def start_install(self):
        self.run_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.log.setVisible(True)
        self.status.setText(t("ai_install_running", self.ui_lang))
        self.adjustSize()

        self.worker = _ClaudeInstallWorker()
        self.worker.output.connect(self.log.appendPlainText)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def on_done(self, ok, message):
        self.close_btn.setEnabled(True)
        if ok:
            self.installed_path = message
            self.status.setText(t("ai_install_done", self.ui_lang, path=message))
            self.accept()
        else:
            self.run_btn.setEnabled(True)
            self.status.setText(t("ai_install_failed", self.ui_lang, error=message))


class ClaudeLoginDialog(QDialog):
    """
    Runs `claude auth login`, which performs Anthropic's own browser sign-in.

    WhisperRocket only starts the process and then watches `claude auth status`
    until it reports success. It never reads, transports or stores the resulting
    credential - Anthropic's policy requires that sign-in complete through their
    own flow, and this is how that requirement is met.

    If the CLI cannot open a browser itself, it prints a URL. That URL is picked
    out of its output and offered here, because a sign-in that silently waits
    forever is worse than one that asks for a click.
    """
    _URL_PATTERN = re.compile(r"https://\S+")
    POLL_MS = 2000
    TIMEOUT_MS = 180_000

    def __init__(self, ui_lang, parent=None):
        super().__init__(parent)
        self.ui_lang = ui_lang
        self.process = None
        self.elapsed_ms = 0
        self.found_url = None

        self.setWindowTitle(t("ai_login_btn", ui_lang).rstrip("."))
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        hint = QLabel(t("ai_login_hint", ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        self.status = QLabel(t("ai_login_waiting", ui_lang))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.url_row = QWidget()
        url_layout = QHBoxLayout(self.url_row)
        url_layout.setContentsMargins(0, 0, 0, 0)
        self.url_field = QLineEdit()
        self.url_field.setReadOnly(True)
        self.url_field.setStyleSheet("font-family: monospace; font-size: 11px;")
        url_layout.addWidget(self.url_field)
        open_btn = QPushButton("↗")
        open_btn.setFixedWidth(32)
        open_btn.clicked.connect(self.open_url)
        url_layout.addWidget(open_btn)
        self.url_row.setVisible(False)
        layout.addWidget(self.url_row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(t("ft_cancel", ui_lang))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.start()

    def start(self):
        self.process = claude_cli.start_login()
        if self.process is None:
            self.status.setText(t("ai_not_installed", self.ui_lang))
            return
        self.timer.start(self.POLL_MS)

    def poll(self):
        self.elapsed_ms += self.POLL_MS

        if claude_cli.auth_status(use_cache=False).logged_in:
            self.timer.stop()
            self.accept()
            return

        if self.found_url is None and self.process is not None:
            # The process already exited: whatever it printed is all we get, and
            # it may hold the URL the CLI could not open itself.
            if self.process.poll() is not None:
                try:
                    remaining = self.process.stdout.read() or ""
                except Exception:
                    remaining = ""
                match = self._URL_PATTERN.search(remaining)
                if match:
                    self.found_url = match.group(0).rstrip(".,)")
                    self.url_field.setText(self.found_url)
                    self.url_row.setVisible(True)
                    self.adjustSize()

        if self.elapsed_ms >= self.TIMEOUT_MS:
            self.timer.stop()
            self.status.setText(t("ai_login_failed", self.ui_lang))

    def open_url(self):
        if self.found_url:
            QDesktopServices.openUrl(QUrl(self.found_url))

    def reject(self):
        self.timer.stop()
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        super().reject()


class VocabularyDialog(QDialog):
    """
    Editor for the personal vocabulary.

    A plain text box rather than a table, because the file is now just a list of
    words - one per line - and a table for that is more furniture than help. The
    format is explained above the box instead of in a tooltip nobody hovers.
    """

    def __init__(self, ui_lang, parent=None):
        super().__init__(parent)
        self.ui_lang = ui_lang

        self.setWindowTitle(t("ai_dict_dialog_title", ui_lang))
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(t("ai_dict_dialog_intro", ui_lang))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # No separate example box: it showed one list while the editor showed
        # another, which read as a contradiction. The example lives in the
        # editor's own commented template, so there is exactly one of them.
        self.editor = QPlainTextEdit(
            dictionary_manager.read_text() or t("ai_dict_template", ui_lang)
        )
        self.editor.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.editor, 1)

        advanced = QLabel(t("ai_dict_dialog_advanced", ui_lang))
        advanced.setWordWrap(True)
        advanced.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(advanced)

        buttons = QHBoxLayout()
        self.count = QLabel("")
        self.count.setStyleSheet("color: #888; font-size: 11px;")
        buttons.addWidget(self.count)
        buttons.addStretch()

        load_btn = QPushButton(t("ai_dict_load", ui_lang))
        load_btn.clicked.connect(self.on_load_file)
        buttons.addWidget(load_btn)

        save_btn = QPushButton(t("btn_save", ui_lang))
        save_btn.clicked.connect(self.on_save)
        buttons.addWidget(save_btn)

        cancel_btn = QPushButton(t("btn_cancel", ui_lang))
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.editor.textChanged.connect(self.update_count)
        self.update_count()

    def update_count(self):
        stats = dictionary_manager.stats(
            dictionary_manager.parse(self.editor.toPlainText())
        )
        self.count.setText(t("ai_dict_count", self.ui_lang, **stats))

    def on_load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("ai_file_load_title", self.ui_lang), "",
            "Vocabulary (*.md *.txt *.json);;All files (*)"
        )
        if not path:
            return
        ok, message = dictionary_manager.import_from_file(path)
        if ok:
            self.editor.setPlainText(
                dictionary_manager.read_text() or t("ai_dict_template", self.ui_lang)
            )
        else:
            QMessageBox.warning(
                self, t("dlg_error", self.ui_lang),
                t("ai_dict_import_failed", self.ui_lang, error=message)
            )

    def on_save(self):
        if not dictionary_manager.write_text(self.editor.toPlainText()):
            QMessageBox.warning(self, t("dlg_error", self.ui_lang),
                                t("ai_dict_write_failed", self.ui_lang))
            return
        self.accept()


class SettingsWindow(QMainWindow):
    """Beállítások ablak tab-okkal"""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.ui_lang = self.config.get("ui_language", "en")
        self.download_manager = get_download_manager()
        self.init_ui()

        # Progress frissítő timer
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_download_progress)
        self.progress_timer.start(500)  # 500ms

        # Permission ellenőrzés timer (csak macOS-en)
        if py_platform.system() == "Darwin":
            self.permission_timer = QTimer()
            self.permission_timer.timeout.connect(self.update_permission_status)
            self.permission_timer.start(2000)  # 2s
            self.update_permission_status()  # Azonnal ellenőrzés

    def init_ui(self):
        """UI inicializálása"""
        self.setWindowTitle(t("settings_title", self.ui_lang))
        # Resizable rather than fixed: the AI tab is long, and being able to drag
        # the window taller beats scrolling a settings page.
        self.resize(560, 720)
        self.setMinimumSize(500, 460)

        # Központi widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Cím
        title = QLabel(t("settings_title", self.ui_lang))
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_settings_tab(), t("tab_settings", self.ui_lang))
        self.tabs.addTab(self.create_models_tab(), t("tab_models", self.ui_lang))
        self.tabs.addTab(self.create_ai_tab(), t("tab_ai", self.ui_lang))
        layout.addWidget(self.tabs)

        # A wheel over a dropdown or a number field must not change it - see
        # _NoWheelFilter. Applied after the tabs exist so it covers all of them,
        # including any control added later.
        block_wheel_changes(self)

        # Hotkey rögzítés állapota
        self.recording_hotkey = False

    def create_settings_tab(self):
        """Beállítások tab létrehozása"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Model warning banner (ha nincs letöltve)
        self.model_warning_frame = self.create_model_warning_section()
        layout.addWidget(self.model_warning_frame)
        self.update_model_warning()

        # Beállítások form
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # UI Nyelv (felület nyelve)
        self.ui_lang_combo = QComboBox()
        for code, name in UI_LANGUAGES:
            self.ui_lang_combo.addItem(name, code)
        self.set_combo_value(self.ui_lang_combo, self.ui_lang)
        form_layout.addRow(t("label_ui_language", self.ui_lang), self.ui_lang_combo)

        # Nyelv (Whisper nyelve)
        self.language_combo = QComboBox()
        for code, name in LANGUAGES:
            self.language_combo.addItem(f"{name} ({code})", code)
        self.set_combo_value(self.language_combo, self.config.get("language", "hu"))
        form_layout.addRow(t("label_language", self.ui_lang), self.language_combo)

        # Hotkey
        hotkey_layout = QHBoxLayout()
        self.hotkey_edit = QLineEdit(self.config.get("hotkey", "ctrl+shift+s"))
        self.hotkey_edit.setReadOnly(True)
        hotkey_layout.addWidget(self.hotkey_edit)

        self.record_btn = QPushButton(t("btn_record", self.ui_lang))
        self.record_btn.setFixedWidth(80)
        self.record_btn.clicked.connect(self.start_hotkey_recording)
        hotkey_layout.addWidget(self.record_btn)

        hotkey_widget = QWidget()
        hotkey_widget.setLayout(hotkey_layout)
        form_layout.addRow(t("label_hotkey", self.ui_lang), hotkey_widget)

        layout.addLayout(form_layout)

        # Permission section (csak macOS-en)
        if py_platform.system() == "Darwin":
            self.permission_frame = self.create_permission_section()
            layout.addWidget(self.permission_frame)

        # Modell form (külön form a permission után)
        form_layout_model = QFormLayout()
        form_layout_model.setSpacing(10)

        # Modell
        self.model_combo = QComboBox()
        for code, name in MODELS:
            downloaded = " ✓" if is_model_downloaded(code) else ""
            self.model_combo.addItem(f"{name}{downloaded}", code)
        self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        form_layout_model.addRow(t("label_model", self.ui_lang), self.model_combo)

        layout.addLayout(form_layout_model)

        # Letöltés progress panel - minimális dizájn
        self.progress_panel = QWidget()
        progress_layout = QVBoxLayout(self.progress_panel)
        progress_layout.setSpacing(4)
        progress_layout.setContentsMargins(0, 8, 0, 8)

        # Progress bar egy sorban a cancel gombbal
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setFixedHeight(18)
        progress_row.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.setStyleSheet("QPushButton { border-radius: 12px; }")
        self.cancel_btn.clicked.connect(self.cancel_download)
        progress_row.addWidget(self.cancel_btn)

        progress_layout.addLayout(progress_row)

        # Info sor (modell neve, méret, sebesség)
        self.progress_info = QLabel("")
        self.progress_info.setStyleSheet("color: #888; font-size: 11px;")
        progress_layout.addWidget(self.progress_info)

        self.progress_panel.setVisible(False)
        layout.addWidget(self.progress_panel)

        # További beállítások
        form_layout2 = QFormLayout()
        form_layout2.setSpacing(10)

        # Device (GPU/CPU)
        self.device_combo = QComboBox()
        for code, name in DEVICES:
            self.device_combo.addItem(name, code)
        default_device = "mlx" if platform_handler.get_gpu_type() == "mlx" else "cuda"
        self.set_combo_value(self.device_combo, self.config.get("device", default_device))
        form_layout2.addRow(t("label_device", self.ui_lang), self.device_combo)

        # Popup megjelenítési idő
        self.popup_duration_spin = QSpinBox()
        self.popup_duration_spin.setRange(1, 30)
        self.popup_duration_spin.setSuffix(t("suffix_seconds", self.ui_lang))
        self.popup_duration_spin.setValue(self.config.get("popup_display_duration", 5))
        form_layout2.addRow(t("label_popup_duration", self.ui_lang), self.popup_duration_spin)

        layout.addLayout(form_layout2)

        # Autostart checkbox
        self.autostart_check = QCheckBox(t("autostart", self.ui_lang))
        self.autostart_check.setChecked(is_autostart_enabled())
        layout.addWidget(self.autostart_check)

        # Info label
        info_label = QLabel(t("info_restart", self.ui_lang))
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Stretch
        layout.addStretch()

        # Gombok
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton(t("btn_save", self.ui_lang))
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

        restart_btn = QPushButton(t("btn_save_restart", self.ui_lang))
        restart_btn.setFixedWidth(160)
        restart_btn.clicked.connect(self.save_and_restart)
        button_layout.addWidget(restart_btn)

        close_btn = QPushButton(t("btn_cancel", self.ui_lang))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        return tab

    def create_models_tab(self):
        """Modellek tab létrehozása"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Cím
        title_label = QLabel(t("models_downloaded", self.ui_lang))
        font = title_label.font()
        font.setPointSize(11)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)

        # Modellek lista
        self.models_list = QListWidget()
        self.models_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """)
        layout.addWidget(self.models_list)

        # Összesítés
        self.storage_label = QLabel("-")
        self.storage_label.setStyleSheet("color: #666;")
        layout.addWidget(self.storage_label)

        # Info
        info_label = QLabel("ℹ " + t("info_active_model", self.ui_lang))
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info_label)

        # Gombok
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton(t("btn_refresh", self.ui_lang))
        refresh_btn.clicked.connect(self.refresh_models_list)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        delete_selected_btn = QPushButton(t("btn_delete_selected", self.ui_lang))
        delete_selected_btn.clicked.connect(self.delete_selected_model)
        button_layout.addWidget(delete_selected_btn)

        delete_all_btn = QPushButton(t("btn_delete_all", self.ui_lang))
        delete_all_btn.clicked.connect(self.delete_all_unused_models)
        button_layout.addWidget(delete_all_btn)

        layout.addLayout(button_layout)

        # Lista feltöltése
        self.refresh_models_list()

        return tab

    def refresh_models_list(self):
        """Modellek lista frissítése"""
        self.models_list.clear()
        active_model = get_active_model()
        models = get_downloaded_models()

        for model in models:
            is_active = model["name"] == active_model
            prefix = "● " if is_active else "   "
            text = f"{prefix}{model['display_name']:20} {model['size_formatted']:>10}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, model["name"])

            if is_active:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(Qt.GlobalColor.gray)

            self.models_list.addItem(item)

        # Összesítés frissítése
        total = format_size(get_total_cache_size())
        freeable = format_size(get_freeable_size())
        self.storage_label.setText(t("storage_info", self.ui_lang, total=total, free=freeable))

        # Modell combo frissítése is
        self.refresh_model_combo()

    def refresh_model_combo(self):
        """Modell dropdown frissítése letöltött jelölésekkel"""
        current_model = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        for code, name in MODELS:
            downloaded = " ✓" if is_model_downloaded(code) else ""
            self.model_combo.addItem(f"{name}{downloaded}", code)

        self.set_combo_value(self.model_combo, current_model)
        self.model_combo.blockSignals(False)

    def delete_selected_model(self):
        """Kijelölt modell törlése"""
        item = self.models_list.currentItem()
        if not item:
            QMessageBox.warning(self, t("dlg_warning", self.ui_lang), t("dlg_select_model", self.ui_lang))
            return

        model_name = item.data(Qt.ItemDataRole.UserRole)
        if model_name == get_active_model():
            QMessageBox.warning(self, t("dlg_warning", self.ui_lang), t("dlg_active_no_delete", self.ui_lang))
            return

        reply = QMessageBox.question(
            self,
            t("dlg_confirm", self.ui_lang),
            t("dlg_confirm_delete", self.ui_lang, model=model_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = delete_model(model_name)
            if success:
                QMessageBox.information(self, t("dlg_success", self.ui_lang), t("dlg_model_deleted", self.ui_lang, model=model_name))
                self.refresh_models_list()
            else:
                # Translate error messages
                if message == "active_model_cannot_delete":
                    msg = t("info_active_model", self.ui_lang)
                elif message == "model_not_found":
                    msg = t("dlg_model_not_found", self.ui_lang)
                elif message.startswith("delete_error:"):
                    msg = t("dlg_delete_error", self.ui_lang, error=message.split(":", 1)[1])
                else:
                    msg = message
                QMessageBox.warning(self, t("dlg_error", self.ui_lang), msg)

    def delete_all_unused_models(self):
        """Összes nem használt modell törlése"""
        freeable = get_freeable_size()
        if freeable == 0:
            QMessageBox.information(self, t("dlg_info", self.ui_lang), t("dlg_no_deletable", self.ui_lang))
            return

        reply = QMessageBox.question(
            self,
            t("dlg_confirm", self.ui_lang),
            t("dlg_confirm_delete_all", self.ui_lang, size=format_size(freeable)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted, freed, errors = delete_all_unused()
            if deleted > 0:
                QMessageBox.information(
                    self,
                    t("dlg_success", self.ui_lang),
                    t("dlg_deleted", self.ui_lang, count=deleted, size=format_size(freed))
                )
                self.refresh_models_list()
            elif errors:
                QMessageBox.warning(self, t("dlg_error", self.ui_lang), "\n".join(errors))

    def set_combo_value(self, combo, value):
        """ComboBox értékének beállítása"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def on_model_changed(self, index):
        """Modell váltás kezelése"""
        model_name = self.model_combo.currentData()

        # Ellenőrzés: folyamatban van-e letöltés
        if self.download_manager.is_downloading():
            reply = QMessageBox.question(
                self,
                t("dlg_warning", self.ui_lang),
                t("dlg_download_in_progress", self.ui_lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # Visszaállítás az előző értékre
                self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))
                return
            else:
                self.download_manager.cancel_download()

        # Ha a modell nincs letöltve, kérdés
        if not is_model_downloaded(model_name):
            reply = QMessageBox.question(
                self,
                t("dlg_download", self.ui_lang),
                t("dlg_download_ask", self.ui_lang, model=model_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_model_download(model_name)
            else:
                # Visszaállítás
                self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))

    def start_model_download(self, model_name):
        """Modell letöltés indítása"""
        # Check conversion dependencies before starting
        from download_manager import _needs_conversion
        if _needs_conversion(model_name):
            try:
                import torch
                import transformers
            except ImportError:
                self._show_conversion_deps_dialog()
                self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))
                return

        self.progress_panel.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_info.setText(f"⬇ {model_name} - {t('download_starting', self.ui_lang)}")

        # Platform-aware device a letöltéshez
        current_device = "mlx" if platform_handler.get_gpu_type() == "mlx" else self.config.get("device", "cpu")
        self.download_manager.start_download(model_name, current_device)

    def update_download_progress(self):
        """Letöltés progress frissítése (timer által hívva)"""
        state = self.download_manager.get_state()

        if state.is_downloading:
            self.progress_panel.setVisible(True)

            # Ha a progress nem változott, pulzáló módba váltunk
            current_progress = state.downloaded_bytes
            if not hasattr(self, '_last_progress_bytes'):
                self._last_progress_bytes = 0
                self._stall_count = 0

            if current_progress == self._last_progress_bytes:
                self._stall_count += 1
            else:
                self._stall_count = 0
                self._last_progress_bytes = current_progress

            # If there's a status message (e.g. conversion phase), show it
            if state.status_message:
                if self.progress_bar.maximum() != 0:
                    self.progress_bar.setRange(0, 0)  # Pulsating mode
                self.progress_info.setText(f"⬇ {state.model_name} - {t(state.status_message, self.ui_lang)}")
            # Ha 4+ tick (2+ sec) óta nem változott, pulzáló mód
            elif self._stall_count >= 4:
                if self.progress_bar.maximum() != 0:
                    self.progress_bar.setRange(0, 0)
                self.progress_info.setText(f"⬇ {state.model_name} - {t('download_stall', self.ui_lang)}")
            else:
                if self.progress_bar.maximum() == 0:
                    self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(int(state.progress * 100))

                downloaded = self.download_manager.format_size(state.downloaded_bytes)
                total = self.download_manager.format_size(state.total_bytes)
                speed = self.download_manager.format_speed()

                self.progress_info.setText(f"⬇ {state.model_name}: {downloaded}/{total} • {speed}")

        elif state.completed:
            self.progress_panel.setVisible(True)
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_info.setText(f"✓ {state.model_name} - {t('download_complete', self.ui_lang)}")
            self.cancel_btn.setVisible(False)
            self._last_progress_bytes = 0
            self._stall_count = 0

            # Offer to remove conversion deps if this was a converted model
            completed_model = state.model_name
            self.download_manager.clear_completed()
            self.refresh_model_combo()

            from download_manager import _needs_conversion
            if _needs_conversion(completed_model):
                QTimer.singleShot(500, self._offer_remove_conversion_deps)
            else:
                QTimer.singleShot(2000, self.hide_progress_panel)

        elif state.error:
            self.progress_panel.setVisible(True)
            error_text = t(state.error, self.ui_lang)
            self.progress_info.setText(f"✗ {state.model_name}: {error_text}")
            self.cancel_btn.setText("✕")
            try:
                self.cancel_btn.clicked.disconnect()
            except:
                pass
            self.cancel_btn.clicked.connect(self.close_error_panel)

        elif state.cancelled:
            self.progress_panel.setVisible(True)
            self.progress_info.setText(t("download_cancelled", self.ui_lang))
            QTimer.singleShot(1500, self.hide_progress_panel)
            self.download_manager.clear_completed()

        else:
            if not state.model_name:
                self.progress_panel.setVisible(False)
            else:
                if is_model_downloaded(state.model_name):
                    self.progress_panel.setVisible(True)
                    self.progress_bar.setValue(100)
                    self.progress_info.setText(f"✓ {state.model_name}")
                    self.cancel_btn.setVisible(False)
                    QTimer.singleShot(2000, self.hide_progress_panel)
                    self.download_manager.clear_completed()
                    self.refresh_model_combo()

    def _show_conversion_deps_dialog(self):
        """Show dialog for missing conversion dependencies with copyable command"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
        venv_pip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "pip")
        cmd = f"{venv_pip} install torch transformers"

        dlg = QDialog(self)
        dlg.setWindowTitle(t("dlg_warning", self.ui_lang))
        dlg.setMinimumWidth(420)
        layout = QVBoxLayout(dlg)

        msg = QLabel(t("download_install_deps_msg", self.ui_lang))
        msg.setWordWrap(True)
        layout.addWidget(msg)

        cmd_field = QLineEdit(cmd)
        cmd_field.setReadOnly(True)
        cmd_field.setStyleSheet("font-family: monospace; font-size: 13px; padding: 6px; background: #2b2b2b; color: #e0e0e0; border: 1px solid #555;")
        layout.addWidget(cmd_field)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton(t("download_copy_cmd", self.ui_lang))
        copy_btn.clicked.connect(lambda: (QApplication.clipboard().setText(cmd), copy_btn.setText("✓")))
        btn_row.addWidget(copy_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _offer_remove_conversion_deps(self):
        """Offer to uninstall torch/transformers after successful conversion"""
        self.hide_progress_panel()
        reply = QMessageBox.question(
            self,
            t("download_conversion_done", self.ui_lang),
            t("download_remove_deps", self.ui_lang),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            import subprocess
            venv_pip = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "pip")
            try:
                subprocess.Popen(
                    [venv_pip, "uninstall", "torch", "transformers", "-y"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"[WARNING] Failed to uninstall conversion deps: {e}")

    def hide_progress_panel(self):
        """Progress panel elrejtése"""
        self.progress_panel.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setText("✕")
        try:
            self.cancel_btn.clicked.disconnect()
        except:
            pass
        self.cancel_btn.clicked.connect(self.cancel_download)

    def close_error_panel(self):
        """Hiba panel bezárása és állapot törlése"""
        self.download_manager.clear_error()
        self.hide_progress_panel()

    def cancel_download(self):
        """Letöltés megszakítása"""
        self.download_manager.cancel_download()

    def start_hotkey_recording(self):
        """Hotkey rögzítés indítása"""
        self.recording_hotkey = True
        self.hotkey_edit.setText(t("hotkey_press", self.ui_lang))
        self.hotkey_edit.setFocus()
        self.record_btn.setText("...")

    def keyPressEvent(self, event):
        """Billentyű lenyomás kezelése"""
        if self.recording_hotkey:
            # Modifier-only billentyűk figyelmen kívül hagyása
            modifier_keys = [
                Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift,
                Qt.Key.Key_Meta, Qt.Key.Key_AltGr
            ]
            if event.key() in modifier_keys:
                # Csak modifier lett lenyomva, várunk a tényleges billentyűre
                return

            modifiers = event.modifiers()
            parts = []

            # macOS: MetaModifier = Control (^), ControlModifier = Command (⌘)
            # pynput macOS-en: ctrl = Control billentyű
            if modifiers & Qt.KeyboardModifier.MetaModifier:
                parts.append("ctrl")  # macOS Control (^) billentyű
            elif modifiers & Qt.KeyboardModifier.ControlModifier:
                # macOS-en ez Command, de pynput-ban "ctrl" a Control
                # Linux/Windows-on ez a Ctrl
                if py_platform.system() != "Darwin":
                    parts.append("ctrl")
                # macOS-en Command-ot nem támogatjuk hotkey-ként
            if modifiers & Qt.KeyboardModifier.AltModifier:
                parts.append("alt")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                parts.append("shift")

            # Tényleges billentyű neve - mindig event.key()-ből, mert event.text()
            # üres lehet Ctrl/Shift kombinációkkal
            key_name = QKeySequence(event.key()).toString().lower()

            if key_name:
                parts.append(key_name)

            if parts:
                hotkey = "+".join(parts)
                self.hotkey_edit.setText(hotkey)
                self.recording_hotkey = False
                self.record_btn.setText(t("btn_record", self.ui_lang))
        else:
            super().keyPressEvent(event)

    def collect_and_save(self):
        """
        Read every tab back into the config and write it out.

        One place, called by all three save paths. Previously each path repeated
        the same field list, so a tab whose Save button forgot one of them would
        silently drop the user's change.
        """
        self.config["language"] = self.language_combo.currentData()
        self.config["ui_language"] = self.ui_lang_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()
        self.config["popup_display_duration"] = self.popup_duration_spin.value()
        self.collect_ai_settings()

        if self.config["device"] in ("cuda", "mlx"):
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        save_config(self.config)
        set_autostart(self.autostart_check.isChecked())

    def save_ai_settings(self):
        """
        Save from the AI tab without closing the window.

        The AI tab had no Save button at all - the only one lived at the bottom
        of the first tab - so settings changed here were lost unless the user
        knew to switch tabs before saving. Staying open also matters because
        these settings are worth trying and adjusting, and they apply to the
        next dictation without a restart.
        """
        self.collect_and_save()
        self.ai_save_status.setText(t("ai_saved", self.ui_lang))
        QTimer.singleShot(4000, lambda: self.ai_save_status.setText(""))

    def save_settings(self):
        """Beállítások mentése"""
        self.collect_and_save()

        QMessageBox.information(
            self,
            t("dlg_saved", self.ui_lang),
            t("dlg_settings_saved", self.ui_lang)
        )
        self.close()

    def save_and_restart(self):
        """Beállítások mentése és alkalmazás újraindítása"""
        self.collect_and_save()

        # Restart flag írása - a fő app ezt fogja észlelni és újraindul
        RESTART_FLAG_FILE = '/tmp/whisperrocket_restart'
        with open(RESTART_FLAG_FILE, 'w') as f:
            f.write('restart')

        # Settings ablak bezárása
        self.close()

    def create_model_warning_section(self):
        """Model warning banner létrehozása"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#model_warning {
                background-color: #FFF3E0;
                border: 1px solid #FFB74D;
                border-radius: 6px;
            }
            QFrame#model_warning QLabel {
                background: transparent;
            }
        """)
        frame.setObjectName("model_warning")
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 10, 12, 10)

        # Cím
        self.model_warning_title = QLabel("⚠️ " + t("model_warning_title", self.ui_lang))
        font = self.model_warning_title.font()
        font.setBold(True)
        self.model_warning_title.setFont(font)
        self.model_warning_title.setStyleSheet("color: #E65100;")
        layout.addWidget(self.model_warning_title)

        # Leírás
        self.model_warning_text = QLabel("")
        self.model_warning_text.setWordWrap(True)
        self.model_warning_text.setStyleSheet("color: #BF360C;")
        layout.addWidget(self.model_warning_text)

        # Download gomb
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.model_warning_btn = QPushButton(t("model_warning_download", self.ui_lang))
        self.model_warning_btn.setFixedWidth(120)
        self.model_warning_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.model_warning_btn.clicked.connect(self.download_missing_model)
        btn_layout.addWidget(self.model_warning_btn)
        layout.addLayout(btn_layout)

        frame.setVisible(False)  # Alapból rejtett
        return frame

    def create_permission_section(self):
        """Permission section létrehozása (macOS)"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#perm_section {
                background-color: #E3F2FD;
                border: 1px solid #90CAF9;
                border-radius: 6px;
            }
            QFrame#perm_section QLabel {
                background: transparent;
            }
        """)
        frame.setObjectName("perm_section")
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 10)

        # Cím
        title = QLabel("🔒 " + t("perm_title", self.ui_lang))
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        title.setStyleSheet("color: #1565C0;")
        layout.addWidget(title)

        # Leírás
        desc = QLabel(t("perm_description", self.ui_lang))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #0D47A1;")
        layout.addWidget(desc)

        # Státusz
        self.perm_status_label = QLabel("")
        layout.addWidget(self.perm_status_label)

        # Gomb és megjegyzés
        btn_layout = QHBoxLayout()
        self.perm_btn = QPushButton(t("perm_open_settings", self.ui_lang))
        self.perm_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.perm_btn.clicked.connect(self.open_permission_settings)
        btn_layout.addWidget(self.perm_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Megjegyzés
        note = QLabel(t("perm_restart_note", self.ui_lang))
        note.setStyleSheet("color: #666;")
        layout.addWidget(note)

        return frame

    def update_model_warning(self):
        """Model warning frissítése"""
        current_model = self.config.get("model", "large-v3")
        # Platform-aware device detekció (nem config-ból!)
        current_device = "mlx" if platform_handler.get_gpu_type() == "mlx" else self.config.get("device", "cpu")

        # Ellenőrizzük a megfelelő device-hoz tartozó modellt
        if not is_model_downloaded(current_model, current_device):
            self.model_warning_text.setText(
                t("model_warning_text", self.ui_lang, model=current_model)
            )
            self.model_warning_frame.setVisible(True)
        else:
            self.model_warning_frame.setVisible(False)

    def update_permission_status(self):
        """Permission status frissítése (macOS)"""
        if not hasattr(self, 'permission_frame'):
            return

        permissions = platform_handler.check_permissions()
        is_granted = permissions.get("input_monitoring", False)

        # Ha megvan az engedély, elrejtjük az egész panelt
        if is_granted:
            self.permission_frame.setVisible(False)
        else:
            self.permission_frame.setVisible(True)
            self.perm_status_label.setText("❌ " + t("perm_status_not_granted", self.ui_lang))
            self.perm_status_label.setStyleSheet("color: #C62828; border: none;")

    def open_permission_settings(self):
        """System Settings megnyitása (macOS)"""
        platform_handler.request_permissions()

    def download_missing_model(self):
        """Hiányzó modell letöltése"""
        current_model = self.config.get("model", "large-v3")
        if not is_model_downloaded(current_model):
            self.start_model_download(current_model)

    def closeEvent(self, event):
        """Ablak bezárásakor timer leállítása"""
        self.progress_timer.stop()
        if hasattr(self, 'permission_timer'):
            self.permission_timer.stop()
        super().closeEvent(event)


    # ------------------------------------------------------------------
    # AI tab
    #
    # Three buttons in order - Install, Sign in, Enable - so the whole setup
    # happens here and never in a terminal. Everything is off by default: a user
    # who ignores this tab gets exactly the dictation the app always had.
    # ------------------------------------------------------------------

    def create_ai_tab(self):
        """AI cleanup tab: account, cleanup, compose mode, style, prompts, dictionary"""
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)
        layout.setContentsMargins(4, 4, 4, 4)

        intro = QLabel(t("ai_intro", self.ui_lang))
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(intro)

        layout.addWidget(self._build_ai_files_group())
        layout.addWidget(self._build_ai_account_group())
        layout.addWidget(self._build_ai_cleanup_group())
        layout.addWidget(self._build_ai_compose_group())
        layout.addWidget(self._build_ai_style_group())
        layout.addWidget(self._build_ai_prompts_group())
        layout.addWidget(self._build_ai_dictionary_group())
        layout.addStretch()
        layout.addLayout(self._build_ai_save_row())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)

        self.refresh_ai_status()
        return scroll

    def _build_ai_save_row(self):
        """Save button for this tab, so nothing here depends on the first tab"""
        row = QHBoxLayout()

        hint = QLabel(t("ai_save_hint", self.ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        row.addWidget(hint, 1)

        self.ai_save_status = QLabel("")
        self.ai_save_status.setStyleSheet("color: #4CAF50; font-size: 11px;")
        row.addWidget(self.ai_save_status)

        save_btn = QPushButton(t("btn_save", self.ui_lang))
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self.save_ai_settings)
        row.addWidget(save_btn)

        close_btn = QPushButton(t("btn_cancel", self.ui_lang))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)

        return row

    def _build_ai_files_group(self):
        """
        Where the personal files live, and a button to open it.

        Shown because the location is the whole privacy design: these files sit
        outside the repository, so git cannot see them even in principle. It also
        answers "how do I move my setup to another machine" - copy this folder.
        """
        group = QGroupBox(t("ai_group_files", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        row = QHBoxLayout()
        path_field = QLineEdit(str(ai_enhancer.user_dir()))
        path_field.setReadOnly(True)
        path_field.setStyleSheet("font-family: monospace; font-size: 11px;")
        row.addWidget(path_field)

        open_btn = QPushButton(t("ai_open_folder", self.ui_lang))
        open_btn.clicked.connect(self.on_ai_open_folder)
        row.addWidget(open_btn)
        layout.addLayout(row)

        hint = QLabel(t("ai_files_hint", self.ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        return group

    def _build_ai_account_group(self):
        group = QGroupBox(t("ai_group_account", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.ai_account_label = QLabel("")
        self.ai_account_label.setWordWrap(True)
        layout.addWidget(self.ai_account_label)

        row = QHBoxLayout()
        self.ai_install_btn = QPushButton(t("ai_install_btn", self.ui_lang))
        self.ai_install_btn.clicked.connect(self.on_ai_install)
        row.addWidget(self.ai_install_btn)

        self.ai_login_btn = QPushButton(t("ai_login_btn", self.ui_lang))
        self.ai_login_btn.clicked.connect(self.on_ai_login)
        row.addWidget(self.ai_login_btn)

        self.ai_logout_btn = QPushButton(t("ai_logout_btn", self.ui_lang))
        self.ai_logout_btn.clicked.connect(self.on_ai_logout)
        row.addWidget(self.ai_logout_btn)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _build_ai_cleanup_group(self):
        group = QGroupBox(t("ai_group_enhance", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.ai_enable_check = QCheckBox(t("ai_enable", self.ui_lang))
        self.ai_enable_check.setChecked(bool(self.config.get("ai_enhance_enabled")))
        layout.addWidget(self.ai_enable_check)

        hint = QLabel(t("ai_enable_hint", self.ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(8)

        self.ai_model_combo = QComboBox()
        for code, name in claude_cli.available_models():
            self.ai_model_combo.addItem(name, code)
        self.set_combo_value(
            self.ai_model_combo,
            self.config.get("ai_model", claude_cli.DEFAULT_MODEL),
        )
        form.addRow(t("ai_model", self.ui_lang), self.ai_model_combo)

        # A plain field, not a spin box: a spin box swallows the mouse wheel, so
        # scrolling this tab with the pointer over it silently changes the value.
        self.ai_timeout_edit = QLineEdit(
            str(int(self.config.get("ai_timeout_seconds", ai_enhancer.DEFAULT_TIMEOUT)))
        )
        self.ai_timeout_edit.setValidator(QIntValidator(5, 600, self))
        self.ai_timeout_edit.setFixedWidth(80)
        self.ai_timeout_edit.setToolTip(t("ai_timeout_tip", self.ui_lang))

        timeout_row = QHBoxLayout()
        timeout_row.setContentsMargins(0, 0, 0, 0)
        timeout_row.addWidget(self.ai_timeout_edit)
        timeout_note = QLabel(t("ai_timeout_note", self.ui_lang))
        timeout_note.setStyleSheet("color: #888; font-size: 11px;")
        timeout_note.setToolTip(t("ai_timeout_tip", self.ui_lang))
        timeout_row.addWidget(timeout_note, 1)
        timeout_widget = QWidget()
        timeout_widget.setLayout(timeout_row)
        form.addRow(t("ai_timeout", self.ui_lang), timeout_widget)

        layout.addLayout(form)
        return group

    def _build_ai_compose_group(self):
        group = QGroupBox(t("ai_group_mode", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        hint = QLabel(t("ai_trigger_hint", self.ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        phrases = self.config.get("ai_trigger_phrases") or ai_enhancer.DEFAULT_TRIGGER_PHRASES
        self.ai_trigger_edit = QPlainTextEdit("\n".join(phrases))
        self.ai_trigger_edit.setFixedHeight(64)
        layout.addWidget(self.ai_trigger_edit)

        return group

    def _build_ai_style_group(self):
        group = QGroupBox(t("ai_group_style", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.ai_style_label = QLabel("")
        self.ai_style_label.setWordWrap(True)
        layout.addWidget(self.ai_style_label)

        hint = QLabel(t("ai_style_hint", self.ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setToolTip(t("ai_style_tip", self.ui_lang))
        layout.addWidget(hint)
        self.ai_style_label.setToolTip(t("ai_style_tip", self.ui_lang))

        row = QHBoxLayout()
        load_btn = QPushButton(t("ai_style_load", self.ui_lang))
        load_btn.clicked.connect(self.on_ai_style_load)
        row.addWidget(load_btn)
        edit_btn = QPushButton(t("ai_style_edit", self.ui_lang))
        edit_btn.clicked.connect(self.on_ai_style_edit)
        row.addWidget(edit_btn)
        row.addStretch()
        layout.addLayout(row)

        self.update_ai_style_label()
        return group

    def _build_ai_prompts_group(self):
        group = QGroupBox(t("ai_group_prompts", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.ai_prompt_labels = {}
        for mode, key in (("transcript", "ai_prompt_transcript"),
                          ("compose", "ai_prompt_compose")):
            row = QHBoxLayout()

            label = QLabel("")
            label.setMinimumWidth(150)
            self.ai_prompt_labels[mode] = label
            row.addWidget(label)

            edit_btn = QPushButton(t("ai_prompt_edit", self.ui_lang))
            edit_btn.clicked.connect(partial(self.on_ai_prompt_edit, mode))
            row.addWidget(edit_btn)

            reset_btn = QPushButton(t("ai_prompt_reset", self.ui_lang))
            reset_btn.clicked.connect(partial(self.on_ai_prompt_reset, mode))
            row.addWidget(reset_btn)
            row.addStretch()

            container = QWidget()
            container.setLayout(row)
            form_label = QLabel(t(key, self.ui_lang))
            form_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(form_label)
            layout.addWidget(container)

        self.update_ai_prompt_labels()
        return group

    def _build_ai_dictionary_group(self):
        """
        Personal vocabulary: a checkbox, a count, and one button.

        The editor lives in its own dialog. An earlier version put the whole
        table here, which crowded an already long tab for something you set up
        once and rarely touch.
        """
        group = QGroupBox(t("ai_group_dict", self.ui_lang))
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.ai_dict_check = QCheckBox(t("ai_dict_enable", self.ui_lang))
        self.ai_dict_check.setChecked(bool(self.config.get("ai_dictionary_enabled", True)))
        self.ai_dict_check.setToolTip(t("ai_dict_tip", self.ui_lang))
        layout.addWidget(self.ai_dict_check)

        hint = QLabel(t("ai_dict_hint", self.ui_lang))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setToolTip(t("ai_dict_tip", self.ui_lang))
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.ai_dict_label = QLabel("")
        self.ai_dict_label.setWordWrap(True)
        row.addWidget(self.ai_dict_label, 1)

        edit_btn = QPushButton(t("ai_dict_edit_words", self.ui_lang))
        edit_btn.clicked.connect(self.on_ai_dict_edit_words)
        edit_btn.setToolTip(t("ai_dict_tip", self.ui_lang))
        row.addWidget(edit_btn)
        layout.addLayout(row)

        self.update_ai_dict_label()
        return group

    def update_ai_dict_label(self):
        """How many words are live, or a nudge to add some"""
        stats = dictionary_manager.stats()
        if stats["total"] == 0:
            self.ai_dict_label.setText(t("ai_dict_empty", self.ui_lang))
        else:
            self.ai_dict_label.setText(t("ai_dict_count", self.ui_lang, **stats))

    def on_ai_dict_edit_words(self):
        dialog = VocabularyDialog(self.ui_lang, self)
        dialog.exec()
        self.update_ai_dict_label()

    # --- dictionary table ---

    # --- AI tab state ---

    def refresh_ai_status(self):
        """
        Reflect the CLI and sign-in state, and gate the cleanup switch on it.

        The switch is disabled rather than hidden when the prerequisites are
        missing, so it is obvious that the feature exists and what is needed.
        """
        status = claude_cli.auth_status(use_cache=False)

        if not status.installed:
            self.ai_account_label.setText(t("ai_not_installed", self.ui_lang))
        elif status.logged_in:
            version = claude_cli.version() or ""
            account = t("ai_logged_in", self.ui_lang,
                        email=status.email or "-", plan=status.plan or "-")
            self.ai_account_label.setText(
                f"{account}\n{version}" if version else account
            )
        else:
            self.ai_account_label.setText(t("ai_not_logged_in", self.ui_lang))

        self.ai_install_btn.setVisible(not status.installed)
        self.ai_login_btn.setVisible(status.installed and not status.logged_in)
        self.ai_logout_btn.setVisible(status.installed and status.logged_in)

        # Grey the controls out when the prerequisites are missing, but never
        # change what the user chose. This probe spawns `claude auth status`, and
        # right after a reboot - before the network is up - it can report "not
        # ready" for a machine that is perfectly signed in. Unchecking the box on
        # that basis, then persisting it on the next save, would quietly wipe the
        # setting. The cleanup already falls back safely on its own, so leaving
        # the box ticked costs nothing.
        self.ai_enable_check.setEnabled(status.ready)
        self.ai_model_combo.setEnabled(status.ready)
        self.ai_timeout_edit.setEnabled(status.ready)

    def update_ai_style_label(self):
        path = ai_enhancer.style_profile_path()
        if ai_enhancer.has_style_profile():
            self.ai_style_label.setText(
                t("ai_style_present", self.ui_lang, size=format_size(path.stat().st_size))
            )
        elif ai_enhancer.style_profile_is_unfilled_template():
            self.ai_style_label.setText(t("ai_style_template", self.ui_lang))
        else:
            self.ai_style_label.setText(t("ai_style_missing", self.ui_lang))

    def update_ai_prompt_labels(self):
        for mode, label in self.ai_prompt_labels.items():
            customised = ai_enhancer.prompt_path(mode).is_file()
            label.setText(t("ai_prompt_custom" if customised else "ai_prompt_default",
                            self.ui_lang))

    def collect_ai_settings(self):
        """Read the AI tab back into the config, called from both save paths"""
        self.config["ai_enhance_enabled"] = self.ai_enable_check.isChecked()
        self.config["ai_model"] = self.ai_model_combo.currentData()
        # An empty or nonsense field must not become a 0-second timeout that
        # fails every call - fall back to the default instead.
        try:
            timeout = int(self.ai_timeout_edit.text().strip())
        except ValueError:
            timeout = ai_enhancer.DEFAULT_TIMEOUT
        timeout = max(5, min(600, timeout))
        self.config["ai_timeout_seconds"] = timeout
        self.ai_timeout_edit.setText(str(timeout))
        self.config["ai_dictionary_enabled"] = self.ai_dict_check.isChecked()

        phrases = [line.strip()
                   for line in self.ai_trigger_edit.toPlainText().splitlines()
                   if line.strip()]
        # An empty box would silently disable compose mode, so fall back to the
        # built-in phrase rather than saving nothing.
        self.config["ai_trigger_phrases"] = phrases or list(
            ai_enhancer.DEFAULT_TRIGGER_PHRASES
        )

    # --- AI tab actions ---

    def on_ai_install(self):
        dialog = ClaudeInstallDialog(self.ui_lang, self)
        dialog.exec()
        claude_cli.invalidate_status_cache()
        self.refresh_ai_status()

    def on_ai_login(self):
        dialog = ClaudeLoginDialog(self.ui_lang, self)
        dialog.exec()
        claude_cli.invalidate_status_cache()
        self.refresh_ai_status()

    def on_ai_logout(self):
        claude_cli.logout()
        self.refresh_ai_status()

    @staticmethod
    def _open_in_editor(path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def on_ai_open_folder(self):
        folder = ai_enhancer.user_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, t("dlg_error", self.ui_lang), str(e))
            return
        self._open_in_editor(folder)

    def on_ai_style_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("ai_file_load_title", self.ui_lang), "",
            "Markdown / text (*.md *.txt);;All files (*)"
        )
        if not path:
            return
        try:
            content = pathlib.Path(path).read_text(encoding="utf-8")
            target = ai_enhancer.style_profile_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, t("dlg_error", self.ui_lang), str(e))
            return
        self.update_ai_style_label()

    def on_ai_style_edit(self):
        path = ai_enhancer.style_profile_path()
        if not path.is_file():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(STYLE_PROFILE_TEMPLATE, encoding="utf-8")
            except Exception as e:
                QMessageBox.warning(self, t("dlg_error", self.ui_lang), str(e))
                return
        self._open_in_editor(path)
        self.update_ai_style_label()

    def on_ai_prompt_edit(self, mode, checked=False):
        """
        Open the prompt for editing, writing the built-in default first if the
        file does not exist yet - there has to be something in the editor.
        """
        path = ai_enhancer.prompt_path(mode)
        if not path.is_file():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(ai_enhancer.default_prompt(mode), encoding="utf-8")
            except Exception as e:
                QMessageBox.warning(self, t("dlg_error", self.ui_lang), str(e))
                return
        self._open_in_editor(path)
        self.update_ai_prompt_labels()

    def on_ai_prompt_reset(self, mode, checked=False):
        """
        Delete the customised prompt so the built-in default applies again.

        Deleting rather than rewriting matters: with no file present the app uses
        whatever the current build ships, so later improvements to the prompt
        reach this user instead of being frozen at install time.
        """
        path = ai_enhancer.prompt_path(mode)
        if not path.is_file():
            return

        confirm = QMessageBox(self)
        confirm.setWindowTitle(t("dlg_confirm", self.ui_lang))
        confirm.setText(t("ai_prompt_reset_confirm", self.ui_lang))
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            path.unlink()
        except Exception as e:
            QMessageBox.warning(self, t("dlg_error", self.ui_lang), str(e))
            return
        self.update_ai_prompt_labels()

def show_settings():
    """Beállítások ablak megjelenítése"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = SettingsWindow()
    window.show()

    if not app.property("running"):
        app.setProperty("running", True)
        app.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # macOS: Ne jelenjen meg a Dock-ban
    if py_platform.system() == "Darwin":
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except ImportError:
            pass  # PyObjC nem elérhető

    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())
