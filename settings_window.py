#!/usr/bin/env python3
"""
WhisperRocket Beállítások ablak v2
PyQt6 alapú modern UI tab-okkal
"""
import os
import json
import sys
import shutil
import platform as py_platform
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QTabWidget,
    QProgressBar, QListWidget, QListWidgetItem, QFrame, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence

from model_manager import (
    get_downloaded_models, get_active_model, delete_model,
    delete_all_unused, get_total_cache_size, get_freeable_size,
    format_size, is_model_downloaded
)
from download_manager import get_download_manager
from translations import t
from platform_support import get_platform_handler

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
            "output_device": None
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
        self.setFixedSize(500, 620)

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
        layout.addWidget(self.tabs)

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

    def save_settings(self):
        """Beállítások mentése"""
        self.config["language"] = self.language_combo.currentData()
        self.config["ui_language"] = self.ui_lang_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()
        self.config["popup_display_duration"] = self.popup_duration_spin.value()

        if self.config["device"] in ("cuda", "mlx"):
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        save_config(self.config)
        set_autostart(self.autostart_check.isChecked())

        QMessageBox.information(
            self,
            t("dlg_saved", self.ui_lang),
            t("dlg_settings_saved", self.ui_lang)
        )
        self.close()

    def save_and_restart(self):
        """Beállítások mentése és alkalmazás újraindítása"""
        self.config["language"] = self.language_combo.currentData()
        self.config["ui_language"] = self.ui_lang_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()
        self.config["popup_display_duration"] = self.popup_duration_spin.value()

        if self.config["device"] in ("cuda", "mlx"):
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        save_config(self.config)
        set_autostart(self.autostart_check.isChecked())

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
