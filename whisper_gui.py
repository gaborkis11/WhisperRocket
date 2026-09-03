#!/usr/bin/env python3
import os
import sys
import json
import shutil
import tempfile
import time
import threading
import traceback
from queue import Queue

import system_check

# Check for --uninstall flag BEFORE Qt imports
if "--uninstall" in sys.argv:
    from appimage_uninstall import run_uninstall
    run_uninstall()
    sys.exit(0)

import sounddevice as sd
import soundfile as sf
import pyperclip
from pynput import keyboard
from platform_support.keyboard_listener import create_keyboard_listener, get_session_type
import numpy as np
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QTimer, Slot, Signal, QObject, Qt, QThread
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QAction

# Platform absztrakció
from platform_support import get_platform_handler
platform_handler = get_platform_handler()

# CUDA LD_LIBRARY_PATH setup (must be BEFORE WhisperModel import for AppImage support)
try:
    from cuda_manager import is_cuda_installed, setup_ld_library_path
    if is_cuda_installed():
        setup_ld_library_path()
except ImportError:
    pass  # cuda_manager not available (normal installation)

# Whisper backend (MLX vagy faster-whisper)
whisper_backend = None  # "mlx" vagy "faster-whisper"
WhisperModel = None

def init_whisper_backend():
    """Whisper backend inicializálása a platform alapján"""
    global whisper_backend, WhisperModel

    gpu_type = platform_handler.get_gpu_type()

    if gpu_type == "mlx":
        try:
            import mlx_whisper
            whisper_backend = "mlx"
            print("[INFO] MLX Whisper backend (Apple Silicon)")
            return
        except ImportError:
            print("[INFO] MLX not available, using faster-whisper")

    # Fallback: faster-whisper
    from faster_whisper import WhisperModel as FasterWhisperModel
    WhisperModel = FasterWhisperModel
    whisper_backend = "faster-whisper"
    print(f"[INFO] Faster-Whisper backend ({gpu_type})")

# Backend inicializálás
init_whisper_backend()
print("[INFO] Starting application, please wait...")
sys.stdout.flush()


class TrayIconUpdater(QObject):
    """Helper osztály thread-safe tray ikon frissítéshez"""
    update_requested = Signal(str, str)  # color, title
    notify_requested = Signal(str, str, str)  # title, message, level (info|warning)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_requested.connect(self._do_update)
        self.notify_requested.connect(self._do_notify)

    @Slot(str, str)
    def _do_update(self, color, title):
        global tray_icon
        if tray_icon:
            tray_icon.setIcon(create_icon(color))
            tray_icon.setToolTip(title)

    @Slot(str, str, str)
    def _do_notify(self, title, message, level):
        global tray_icon
        if tray_icon:
            icon = (QSystemTrayIcon.MessageIcon.Information if level == "info"
                    else QSystemTrayIcon.MessageIcon.Warning)
            tray_icon.showMessage(title, message, icon, 5000)


class UpdateProbe(QThread):
    """Runs the update check off the main thread (a filtered network can
    hang for seconds - same reason as settings_window._PhoneProbe)."""
    finished_with = Signal(object)  # UpdateInfo

    def __init__(self, current_version, lang, parent=None):
        super().__init__(parent)
        self._version = current_version
        self._lang = lang

    def run(self):
        import update_checker
        self.finished_with.emit(
            update_checker.check_for_update(self._version, self._lang))


class UpdateDownloader(QThread):
    """Streams the new AppImage and swaps it in place (update_checker does
    the atomic replace; this class only carries it off the main thread)."""
    progress = Signal(int, int)          # done, total bytes
    finished_with = Signal(object)       # error string or None

    def __init__(self, info, target_path, parent=None):
        super().__init__(parent)
        self._info = info
        self._target = target_path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import update_checker
        error = update_checker.download_and_replace(
            self._info.asset_url, self._info.asset_size, self._target,
            lambda done, total: self.progress.emit(done, total),
            lambda: self._cancelled)
        self.finished_with.emit(error)


from translations import t, TRANSLATIONS
import history_manager
import dictionary_manager
import transcript_filter
from functools import partial

# Konfiguráció (bundled app-ban user könyvtárba mentjük)
def get_config_path():
    """Config fájl útvonala - bundled app-ban user könyvtárba menti"""
    import platform as py_platform
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

# Hangfájlok (ezek a bundled app-ban is sys._MEIPASS-ben vannak)
def get_resource_path(relative_path):
    """Erőforrás fájl útvonala - bundled és dev módban is működik"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

ASSETS_DIR = get_resource_path('assets')
SOUND_START = os.path.join(ASSETS_DIR, 'start_soft_click_smooth.wav')
SOUND_STOP = os.path.join(ASSETS_DIR, 'stop_soft_click_smooth.wav')


def detect_device():
    """GPU elérhetőség automatikus detektálása (platform-független)"""
    gpu_type = platform_handler.get_gpu_type()
    if gpu_type == "cuda":
        return "cuda", "float16"
    elif gpu_type == "mlx":
        return "mlx", "float16"
    return "cpu", "int8"


def load_config():
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
            "language": "en",
            "sample_rate": 16000,
            "input_device": None,
            "output_device": None,
            # AI enhancement - off by default, so a fresh install behaves
            # exactly as it did before the feature existed
            "ai_enhance_enabled": False,
            "ai_model": "sonnet",
            "ai_effort": "low",
            "ai_trigger_phrases": ["fogalmazzuk meg hogy", "fogalmazd meg hogy",
                                   "segíts megfogalmazni", "jarvis segíts megfogalmazni"],
            "ai_timeout_seconds": 120,
            "ai_dictionary_enabled": True,
            # The dictionary can also go to the recogniser as hotwords. Off by
            # default: the AI layer already resolves misheard terms from the
            # same list, and the hint costs decoder budget and can echo hint
            # words on near-silence. Config-only switch for measuring it.
            "hotwords_enabled": False,
            # Phone endpoint - off by default. It opens a network port, so it
            # has to be something the user switches on deliberately.
            "phone_endpoint_enabled": False,
            "phone_endpoint_port": 8771,
            "phone_endpoint_budget_seconds": 20
        }

_update_probe = None  # keep the QThread referenced while it runs


def start_update_probe(manual=False):
    """Version check off the main thread. manual=True comes from the tray
    menu item: every outcome gets visible feedback, not just a new version."""
    global _update_probe
    if _update_probe and _update_probe.isRunning():
        return
    from about_window import APP_VERSION
    _update_probe = UpdateProbe(APP_VERSION, ui_lang)
    _update_probe.finished_with.connect(
        lambda info: on_update_check_result(info, manual=manual))
    _update_probe.start()


def check_updates_manual():
    """Tray menu: Check for updates"""
    start_update_probe(manual=True)


def on_update_check_result(info, manual=False):
    """Main-thread handler: notify, show localized notes, act on the choice."""
    if info.error:
        print(f"[UPDATE] check failed: {info.error}")
        if manual and tray_icon_updater:
            tray_icon_updater.notify_requested.emit(
                "WhisperRocket", t("update_failed", ui_lang), "warning")
        return
    if not info.is_newer:
        print(f"[UPDATE] up to date (latest: {info.latest})")
        if manual and tray_icon_updater:
            tray_icon_updater.notify_requested.emit(
                "WhisperRocket", t("update_uptodate", ui_lang), "info")
        return
    if not manual and tray_icon_updater:
        # Manual checks open the dialog right away - no balloon needed
        tray_icon_updater.notify_requested.emit(
            t("update_available_title", ui_lang, version=info.latest),
            t("update_balloon_msg", ui_lang), "info")
    from qt_helpers import show_update_dialog
    choice, disable_auto = show_update_dialog(info, ui_lang)
    if disable_auto:
        save_config_value("update_check_enabled", False)
    if choice == "update":
        perform_update(info)


def perform_update(info):
    """AppImage: self-update in place. Source install: hand over git pull."""
    if "APPIMAGE" in os.environ and info.asset_url:
        run_appimage_self_update(info)
    else:
        from qt_helpers import show_source_update_hint
        show_source_update_hint(info, ui_lang)


def run_appimage_self_update(info):
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QProgressBar, QPushButton)

    appimage_path = os.environ.get("APPIMAGE", "")
    if not appimage_path or not os.access(os.path.dirname(appimage_path), os.W_OK):
        _show_update_error(t("update_dl_failed", ui_lang,
                             error="target not writable"), info)
        return

    dlg = QDialog()
    dlg.setWindowTitle("WhisperRocket")
    dlg.setMinimumWidth(420)
    layout = QVBoxLayout(dlg)
    label = QLabel(t("update_downloading", ui_lang, percent=0))
    label.setWordWrap(True)
    layout.addWidget(label)
    bar = QProgressBar()
    bar.setRange(0, 100)
    layout.addWidget(bar)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    cancel_btn = QPushButton(t("update_cancel_btn", ui_lang))
    btn_row.addWidget(cancel_btn)
    layout.addLayout(btn_row)

    downloader = UpdateDownloader(info, appimage_path)
    dlg._downloader = downloader  # keep referenced for the dialog's lifetime
    cancel_btn.clicked.connect(downloader.cancel)

    def on_progress(done, total):
        if total:
            percent = int(done * 100 / total)
            bar.setValue(percent)
            label.setText(t("update_downloading", ui_lang, percent=percent))

    def on_finished(error):
        if error is None:
            bar.setValue(100)
            label.setText(t("update_restarting", ui_lang))
            cancel_btn.setEnabled(False)
            # The mounted squashfs keeps the old inode alive; exec'ing the
            # replaced file starts the new version in place.
            QTimer.singleShot(1200,
                              lambda: os.execv(appimage_path, [appimage_path]))
        else:
            dlg.accept()
            _show_update_error(t("update_dl_failed", ui_lang, error=error), info)

    downloader.progress.connect(on_progress)
    downloader.finished_with.connect(on_finished)
    downloader.start()
    dlg.exec()


def _show_update_error(message, info):
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                   QPushButton)
    import webbrowser
    dlg = QDialog()
    dlg.setWindowTitle("WhisperRocket")
    dlg.setMinimumWidth(420)
    layout = QVBoxLayout(dlg)
    label = QLabel(message)
    label.setWordWrap(True)
    layout.addWidget(label)
    btn_row = QHBoxLayout()
    release_btn = QPushButton(t("update_view_release", ui_lang))
    release_btn.clicked.connect(lambda: webbrowser.open(info.release_url))
    btn_row.addWidget(release_btn)
    btn_row.addStretch()
    ok_btn = QPushButton("OK")
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)
    dlg.exec()


def save_config_value(key, value):
    """Persist a single config key without touching the rest of the file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            current = json.load(f)
    except Exception:
        current = dict(config)
    current[key] = value
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Could not save config: {e}")
    config[key] = value


# Globális változók
config = load_config()
ui_lang = config.get("ui_language", "en")
model = None
hotwords_provider = None  # dictionary_manager.HotwordsProvider, set in load_model()
recording = False
audio_data = []
stream = None
tray_icon = None
hotkey_pressed = {}
actual_sample_rate = config.get("sample_rate", 16000)  # Tényleges sample rate
keyboard_listener = None  # pynput keyboard listener

# Popup ablak változók
amplitude_queue = Queue(maxsize=100)  # Thread-safe queue a waveform adatokhoz
popup_window = None
tray_icon_updater = None  # Thread-safe tray ikon frissítő
qt_app = None
history_detail_window = None  # History részlet ablak
history_menu = None  # History almenü referencia
settings_window_instance = None  # Settings ablak (közvetlen megnyitáshoz)
file_transcription_window_instance = None  # File transcription ablak
history_viewers = []  # Aktív history viewer ablakok
model_lock = threading.Lock()  # Lock for concurrent model access

# True while the local hotkey path is transcribing. The phone endpoint reads it
# to decide whether it may touch the tray icon: a dictation arriving from the
# phone must never overwrite the state of the one you are doing at the desk.
local_busy = False

phone_endpoint_instance = None  # phone_endpoint.PhoneEndpoint while it is running

# Hang lejátszás (platform-független)
def play_sound(sound_file):
    """Hangfájl lejátszása háttérszálban (platform-specifikus implementáció)"""
    platform_handler.play_sound(sound_file)

# System tray ikon létrehozása (Qt verzió)
def create_icon(color='blue'):
    """Mikrofon ikon lekerekített színes háttérrel - QIcon"""
    # Szín map
    color_map = {
        'blue': QColor(59, 130, 246),
        'red': QColor(239, 68, 68),
        'yellow': QColor(234, 179, 8),
        'orange': QColor(249, 115, 22),
        'green': QColor(34, 197, 94),
        'gray': QColor(107, 114, 128),
        # Phone dictation. Its own colour rather than the yellow the local path
        # uses, so a glance at the tray tells you whether the machine is working
        # on your own dictation or on one that arrived from the phone.
        'purple': QColor(168, 85, 247),
    }
    bg_color = color_map.get(color, QColor(59, 130, 246))

    # 64x64 pixmap
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))  # Átlátszó háttér

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Lekerekített színes háttér
    painter.setBrush(QBrush(bg_color))
    painter.setPen(QPen(QColor(0, 0, 0, 0)))
    painter.drawRoundedRect(0, 0, 64, 64, 12, 12)

    # Mikrofon (fehér)
    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.setPen(QPen(QColor(0, 0, 0, 0)))

    # Mikrofon fej
    painter.drawRoundedRect(24, 8, 16, 24, 8, 8)

    # Mikrofon állvány ív
    painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
    painter.setPen(QPen(QColor(255, 255, 255), 4))
    painter.drawArc(16, 20, 32, 28, 0, 180 * 16)

    # Függőleges rúd
    painter.setBrush(QBrush(QColor(255, 255, 255)))
    painter.setPen(QPen(QColor(0, 0, 0, 0)))
    painter.drawRect(30, 44, 4, 8)

    # Talp
    painter.drawRect(22, 52, 20, 4)

    painter.end()

    return QIcon(pixmap)

def update_icon(color, title):
    """Ikon és cím frissítése (thread-safe Signal-alapú)"""
    global tray_icon_updater
    if tray_icon_updater:
        tray_icon_updater.update_requested.emit(color, title)

@Slot()
def quit_app():
    """Alkalmazás leállítása"""
    global stream, qt_app, keyboard_listener
    print("[INFO] Exiting...")

    # Close the network port before anything else, so quitting never leaves a
    # dictation endpoint listening behind a dead app.
    try:
        stop_phone_endpoint()
    except Exception:
        pass

    # Stop keyboard listener
    try:
        if keyboard_listener:
            keyboard_listener.stop()
    except:
        pass

    # Stop audio stream
    if stream:
        try:
            stream.stop()
            stream.close()
        except:
            pass

    # Quit Qt app
    if qt_app:
        qt_app.quit()

    # Force exit if qt_app.quit() doesn't work
    import sys
    sys.exit(0)

@Slot()
def open_settings():
    """Beállítások ablak megnyitása"""
    print("[INFO] Opening settings...")
    global settings_window_instance
    from settings_window import SettingsWindow
    if settings_window_instance is None or not settings_window_instance.isVisible():
        # Handed in rather than imported the other way round: settings_window
        # importing this module would load a second copy of it (this one runs as
        # __main__), and the app would end up with two of every global.
        settings_window_instance = SettingsWindow(
            apply_phone_endpoint=apply_phone_endpoint_settings,
            request_quit=quit_app,
        )
        settings_window_instance.show()
    else:
        settings_window_instance.raise_()
        settings_window_instance.activateWindow()

@Slot()
def open_file_transcription():
    """Fájl átírás ablak megnyitása"""
    print("[INFO] Opening file transcription...")
    global file_transcription_window_instance
    from file_transcription_window import FileTranscriptionWindow
    if file_transcription_window_instance is None or not file_transcription_window_instance.isVisible():
        file_transcription_window_instance = FileTranscriptionWindow(
            model=model,
            whisper_backend=whisper_backend,
            config=config,
            ui_lang=ui_lang,
            model_lock=model_lock,
            hotwords=current_hotwords,
        )
        file_transcription_window_instance.show()
    else:
        file_transcription_window_instance.raise_()
        file_transcription_window_instance.activateWindow()

def show_history_entry(entry_id: str, checked: bool = False):
    """History bejegyzés megjelenítése"""
    global history_viewers
    try:
        entry = history_manager.get_entry_by_id(entry_id)
        if entry:
            from history_viewer import HistoryViewer
            import json
            entry_json = json.dumps(entry)
            viewer = HistoryViewer(entry_json)
            viewer.show()
            # Megtartjuk a referenciát, hogy ne törlődjön
            history_viewers.append(viewer)
            # Bezárt ablakok eltávolítása a listából
            history_viewers = [v for v in history_viewers if v.isVisible()]
    except Exception as e:
        print(f"[ERROR] show_history_entry failed: {e}")
        import traceback
        traceback.print_exc()

def clear_history_action():
    """History törlése megerősítés után"""
    from PySide6.QtWidgets import QMessageBox
    msg = QMessageBox()
    msg.setWindowTitle(t("dlg_confirm", ui_lang))
    msg.setText(t("history_confirm_clear", ui_lang))
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    if msg.exec() == QMessageBox.StandardButton.Yes:
        history_manager.clear_history()
        refresh_history_menu()
        print("[INFO] History cleared")

def refresh_history_menu():
    """History menü frissítése a legújabb adatokkal"""
    global history_menu
    if not history_menu:
        return

    try:
        history_menu.clear()

        # Legutóbbi bejegyzések lekérése (max 15)
        entries = history_manager.get_recent(15)

        if entries:
            for entry in entries:
                # Előnézet: idő + szöveg első 40 karaktere
                time_str = history_manager.format_timestamp(entry.get("timestamp", ""))
                preview = history_manager.format_preview(entry.get("text", ""), 35)
                label = f"{time_str} - \"{preview}\""

                action = QAction(label, qt_app)
                entry_id = entry.get("id")
                # Qt.QueuedConnection megoldja a crash-t QSystemTrayIcon menüből
                action.triggered.connect(partial(show_history_entry, entry_id), Qt.QueuedConnection)
                history_menu.addAction(action)

            history_menu.addSeparator()

            # Statisztika
            stats = history_manager.get_stats()
            stats_label = t("history_entries", ui_lang, count=stats["count"], size=stats["size_formatted"])
            stats_action = QAction(f"📊 {stats_label}", qt_app)
            stats_action.setEnabled(False)
            history_menu.addAction(stats_action)

            # Törlés gomb
            clear_action = QAction(f"🗑️ {t('history_clear', ui_lang)}", qt_app)
            clear_action.triggered.connect(clear_history_action, Qt.QueuedConnection)
            history_menu.addAction(clear_action)
        else:
            # Üres history
            empty_action = QAction(t("history_empty", ui_lang), qt_app)
            empty_action.setEnabled(False)
            history_menu.addAction(empty_action)
    except Exception as e:
        print(f"[ERROR] refresh_history_menu() failed: {e}")
        import traceback
        traceback.print_exc()

# Modell betöltés
def load_model():
    global model, hotwords_provider
    print("[INFO] Whisper modell betoltese...")
    sys.stdout.flush()
    update_icon('orange', t("tray_loading", ui_lang))

    try:
        if whisper_backend == "mlx":
            # MLX backend - a modell lazy-load-olódik transcribe-nál
            model = {"type": "mlx", "model_name": config["model"]}
            print(f"[INFO] MLX modell: {config['model']}")
            sys.stdout.flush()
        else:
            # Faster-whisper backend - use local path if available
            from model_manager import get_model_path_for_loading
            model_path = get_model_path_for_loading(config["model"], config["device"])
            print(f"[INFO] Loading model from: {model_path}")

            model = WhisperModel(
                model_path,
                device=config["device"],
                compute_type=config["compute_type"]
            )
            # The dictionary as a hint to the recogniser. Counted with the
            # model's own tokenizer, because faster-whisper cuts hotwords at
            # 223 tokens without saying so - see dictionary_manager.
            hf_tokenizer = model.hf_tokenizer
            hotwords_provider = dictionary_manager.HotwordsProvider(
                lambda text: len(hf_tokenizer.encode(text, add_special_tokens=False).ids))
        print("[INFO] Modell betoltve!")
        sys.stdout.flush()
        update_icon('blue', t("tray_ready", ui_lang))
    except Exception as e:
        print(f"[HIBA] Modell betoltes: {e}")
        sys.stdout.flush()
        update_icon('red', t("tray_error", ui_lang))

# Audio callback
def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_data.append(indata.copy())
        # Amplitude számítás a waveform vizualizációhoz
        amplitude = np.abs(indata).mean()
        try:
            amplitude_queue.put_nowait(amplitude)
        except:
            pass  # Queue tele - nem gond, csak vizualizáció

# AI failure reasons -> translation keys, so the tray tooltip says something a
# person understands instead of an internal token.
AI_REASON_KEYS = {
    "not_installed": "ai_reason_not_installed",
    "not_logged_in": "ai_reason_not_logged_in",
    "usage_limit": "ai_reason_usage_limit",
    "billing": "ai_reason_billing",
    "timeout": "ai_reason_timeout",
    "network": "ai_reason_network",
    "disabled": "ai_reason_disabled",
}


def run_whisper(file_path):
    """
    Transcribe one audio file with the loaded model.

    Shared by the hotkey path and the phone endpoint. It was inline in
    process_audio first; pulling it out means the two paths cannot drift apart -
    a beam size or a language fixed in one of them would otherwise silently not
    apply to the other.

    Takes model_lock, so callers must not already hold it.
    """
    with model_lock:
        if whisper_backend == "mlx":
            # mlx_whisper has no hotwords parameter; the dictionary still
            # reaches the AI layer as before
            import mlx_whisper
            result = mlx_whisper.transcribe(
                file_path,
                path_or_hf_repo=f"mlx-community/whisper-{model['model_name']}-mlx",
                language=config["language"],
            )
            return result.get("text", "").strip()

        segments, _info = model.transcribe(
            file_path,
            language=config["language"],
            beam_size=5,
            **dictionary_manager.hotwords_options(current_hotwords()),
        )
        text = " ".join(segment.text.strip() for segment in segments)
        # What Whisper writes on silence ("Feliratot készítette Amara.org
        # közössége") goes before anything downstream can paste it
        filtered = transcript_filter.filter_transcript(text)
        if filtered != text:
            print(f"[FILTER] dropped: {text[len(filtered):].strip()[:80]!r}")
        return filtered


def current_hotwords():
    """
    The dictionary packed for the recogniser, or None.

    None when switched off in config, when the model is not loaded, or when the
    dictionary is empty. Never raises: this sits in the dictation path, and a
    broken dictionary file must cost the hint, not the transcription.
    """
    if not config.get("hotwords_enabled", True) or hotwords_provider is None:
        return None
    try:
        return hotwords_provider.current()
    except Exception as e:
        print(f"[HOTWORDS] skipped: {e}")
        return None


def ai_reason_label(reason: str) -> str:
    """Human-readable label for why the AI cleanup did not deliver"""
    if reason.startswith("guard:"):
        return t("ai_reason_guard", ui_lang)
    return t(AI_REASON_KEYS.get(reason, "ai_reason_other"), ui_lang)


# Settings that take effect on the next dictation rather than the next restart.
# Everything else - model, device, hotkey - genuinely needs a restart and keeps
# coming from the `config` loaded at startup.
LIVE_CONFIG_PREFIXES = ("ai_", "phone_endpoint_")


def current_ai_config():
    """
    Config with the live keys re-read from disk.

    The module-level `config` is loaded once at startup, so without this a user
    who ticks "Clean up dictation with AI" in Settings and saves would see no
    change until the app restarted - and there is no reason to restart for a
    prompt, a trigger phrase or the phone endpoint's response budget.
    """
    settings = dict(config)
    try:
        with open(CONFIG_FILE, 'r') as f:
            stored = json.load(f)
    except Exception:
        return settings

    for key, value in stored.items():
        if key.startswith(LIVE_CONFIG_PREFIXES):
            settings[key] = value
    return settings


def apply_ai_enhancement(raw_text, timeout_override=None):
    """
    Custom-dictionary fix plus AI cleanup, or None when neither is switched on.

    Imported lazily and wrapped in a catch-all on purpose: plain dictation is
    this app's original feature and predates the AI path, so a missing or broken
    ai_enhancer must cost the tidying and never the transcript.

    timeout_override shortens the wait for this one call. The phone endpoint uses
    it to keep the whole request inside the window the iPhone is willing to wait:
    whatever is left of the budget after Whisper becomes the AI's timeout, and if
    the model does not make it, enhance() falls back to the raw transcript
    exactly as it does on the desktop - and the stuck Claude process is killed
    rather than left running against the account's limit.
    """
    ai_config = current_ai_config()
    if not (ai_config.get("ai_enhance_enabled")
            or ai_config.get("ai_dictionary_enabled", True)):
        return None

    if timeout_override is not None:
        ai_config["ai_timeout_seconds"] = timeout_override

    try:
        from ai_enhancer import enhance
        result = enhance(raw_text, ai_config)
    except Exception as e:
        print(f"[WARN] AI enhancement unavailable: {e}")
        return None

    if result.enhanced:
        print(f"[AI] {result.mode} mode, {result.elapsed:.2f}s, "
              f"{result.dictionary_hits} dictionary fix(es)")
    elif result.failed:
        print(f"[AI] plain transcript used ({result.reason})")
    elif result.dictionary_hits:
        print(f"[AI] {result.dictionary_hits} dictionary fix(es), cleanup off")

    return result


# Feldolgozás
def process_audio(audio_copy):
    global local_busy

    print("\n" + "="*60)
    print("[PROCESSING] Starting...")

    # Claimed for the whole run so a phone dictation arriving mid-way cannot
    # repaint the tray out from under the one happening at the desk.
    local_busy = True
    temp_file = None

    try:
        # Audio concatenation
        audio_array = np.concatenate(audio_copy, axis=0)
        print(f"[INFO] Audio length: {len(audio_array)/actual_sample_rate:.2f}s")

        # Temp file (Whisper auto-resamples)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        sf.write(temp_file.name, audio_array, actual_sample_rate)

        # Whisper transcribe
        print("[INFO] Whisper processing...")
        start_time = time.time()

        text = run_whisper(temp_file.name)

        elapsed = time.time() - start_time

        # AI enhancement. The processing popup started in stop_recording() is
        # still up, so it covers this step too - no new popup state needed.
        ai_result = apply_ai_enhancement(text)
        if ai_result is not None:
            text = ai_result.text

        # Vágólapra másolás
        pyperclip.copy(text)
        # Auto-paste (platform-independent)
        try:
            print("[INFO] Auto-pasting...")
            time.sleep(0.3)

            # The paste tool can be missing (fresh Wayland install): tell the
            # user via a tray balloon - the text is on the clipboard either way.
            paste_tool = ("wtype" if system_check.get_session_type() == "wayland"
                          else "xdotool")
            if sys.platform == "linux" and not shutil.which(paste_tool):
                if tray_icon_updater:
                    tray_icon_updater.notify_requested.emit(
                        t("notify_paste_missing_title", ui_lang),
                        t("notify_paste_missing_msg", ui_lang, tool=paste_tool),
                        "warning")
                print(f"[WARNING] {paste_tool} not installed - auto-paste skipped")
            else:
                # Active window detection
                window_class = platform_handler.get_active_window_class()
                is_terminal = platform_handler.is_terminal_window(window_class)

                # Paste (different key combo for terminals)
                platform_handler.paste_text(is_terminal=is_terminal)
                print(f"[INFO] Pasted!")
        except Exception as e:
            print(f"[WARNING] Paste failed: {e}")
        print("="*60)
        print(f"RESULT: '{text}'")
        print(f"TIME: {elapsed:.2f}s")
        print("="*60)
        print(">>> CLIPBOARD: Press Ctrl+V to paste! <<<")
        print("="*60 + "\n")

        # History mentés
        if text.strip():
            history_manager.add_entry(
                text, elapsed, config["language"],
                enhanced=(ai_result.enhanced if ai_result else None),
                raw_text=(ai_result.raw_text if ai_result else None),
            )
            # Menü frissítése a főszálban (QTimer.singleShot thread-safe)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, refresh_history_menu)

        # Ikon frissítés - orange amikor az AI tisztítás nem tudott lefutni és a
        # nyers átirat került a vágólapra, hogy egy pillantásból látszódjon
        if ai_result is not None and ai_result.failed:
            update_icon('orange', f'{t("tray_done", ui_lang)} - '
                                  f'{t("popup_plain", ui_lang)}: {ai_reason_label(ai_result.reason)}')
        else:
            update_icon('green', t("tray_done", ui_lang))

        # Szöveg megjelenítése a popup-ban (3mp-ig látszik, kattintásra expand)
        show_text_popup(text)

        # Ikon visszaállítás késleltetéssel
        time.sleep(3)
        update_icon('blue', t("tray_ready", ui_lang))

    except Exception as e:
        print("\n" + "="*60)
        print(f"[HIBA] {e}")
        traceback.print_exc()
        print("="*60 + "\n")

        update_icon('red', t("tray_error", ui_lang))
        time.sleep(2)
        hide_popup()
        update_icon('blue', t("tray_ready", ui_lang))

    finally:
        local_busy = False
        # The recording must not outlive this run either way - a failed
        # transcription used to leave the WAV behind in /tmp
        if temp_file is not None:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass


# --- Phone endpoint -------------------------------------------------------
#
# The HTTP server itself lives in phone_endpoint.py and deliberately imports
# nothing from this app. Everything it needs to reach - the warm model, the AI
# cleanup, the history, the tray - is handed to it as the callbacks below, which
# is what keeps the network-facing code unable to touch anything else.


def phone_model_ready() -> bool:
    """Whether a recording could be transcribed right now"""
    return model is not None


def phone_tray(color, title_key, suffix=""):
    """
    Tray feedback for a phone dictation, skipped while the desk is busy.

    A light touch on purpose: enough to see at a glance that a request came in,
    never enough to hide what the local path is doing.
    """
    if local_busy or recording:
        return
    title = t(title_key, ui_lang)
    update_icon(color, f"{title}{suffix}")


def dictate_from_phone(audio_bytes):
    """
    One recording from the phone, all the way to finished text.

    Runs on the endpoint's worker thread. Returns a DictationOutcome; it does not
    raise, because the endpoint turns any failure into a spoken error and this
    path should decide for itself which failure the user hears.
    """
    from phone_endpoint import DictationOutcome

    if not phone_model_ready():
        return DictationOutcome(error="not_ready")

    settings = current_ai_config()
    budget = float(settings.get("phone_endpoint_budget_seconds", 20))

    started = time.time()
    temp_path = None

    try:
        # The filename never comes from the request - the endpoint hands over
        # bytes and nothing else, so there is no name to be tricked by.
        handle, temp_path = tempfile.mkstemp(suffix=".m4a", prefix="whisperrocket-phone-")
        with os.fdopen(handle, "wb") as audio_file:
            audio_file.write(audio_bytes)

        phone_tray('purple', "tray_phone_working")

        text = run_whisper(temp_path)
        whisper_elapsed = time.time() - started
        print(f"[PHONE] Whisper {whisper_elapsed:.2f}s, {len(audio_bytes)} bytes")

        if not text.strip():
            phone_tray('blue', "tray_ready")
            return DictationOutcome(error="no_speech")

        # Whatever is left of the budget is what the AI gets. Below five seconds
        # there is no point spawning the call at all - it could not finish, and
        # the raw transcript is the same answer either way, minus the wait.
        remaining = budget - whisper_elapsed
        ai_result = apply_ai_enhancement(text, timeout_override=int(remaining)) \
            if remaining >= 5 else None

        if ai_result is None and remaining < 5:
            print(f"[PHONE] {remaining:.1f}s left of the budget - sending the plain transcript")

        if ai_result is not None:
            text = ai_result.text

        mode = ai_result.mode if (ai_result and ai_result.enhanced) else "transcript"
        enhanced = bool(ai_result and ai_result.enhanced)

        if text.strip():
            history_manager.add_entry(
                text, time.time() - started, config["language"],
                enhanced=(ai_result.enhanced if ai_result else None),
                raw_text=(ai_result.raw_text if ai_result else None),
                source="phone",
            )
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, refresh_history_menu)

        total = time.time() - started
        print(f"[PHONE] {mode} mode, {total:.2f}s total, enhanced={enhanced}")

        phone_tray('green' if enhanced else 'orange', "tray_phone_done")
        threading.Timer(3.0, lambda: phone_tray('blue', "tray_ready")).start()

        return DictationOutcome(text=text, mode=mode, enhanced=enhanced)

    except Exception as error:
        print(f"[PHONE] failed: {error}")
        phone_tray('blue', "tray_ready")
        return DictationOutcome(error="failed")

    finally:
        # The recording is deleted whatever happened - the briefing asks for the
        # audio to leave no trace once it has been processed.
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def phone_endpoint_messages():
    """The user-visible strings, translated, keyed as phone_endpoint expects"""
    return {
        "bad_request": t("phone_err_bad_request", ui_lang),
        "bad_token": t("phone_err_bad_token", ui_lang),
        "not_found": t("phone_err_not_found", ui_lang),
        "too_large": t("phone_err_too_large", ui_lang),
        "no_speech": t("phone_err_no_speech", ui_lang),
        "busy": t("phone_err_busy", ui_lang),
        "not_ready": t("phone_err_not_ready", ui_lang),
        "failed": t("phone_err_failed", ui_lang),
        "health_ok": t("phone_health_ok", ui_lang),
    }


def stop_phone_endpoint():
    """Shut the endpoint down if it is running"""
    global phone_endpoint_instance
    if phone_endpoint_instance is not None:
        phone_endpoint_instance.stop()
        phone_endpoint_instance = None


def apply_phone_endpoint_settings():
    """
    Start, stop or restart the endpoint to match the saved settings.

    Called at startup and again whenever the Settings window saves, so switching
    the feature on takes effect immediately - restarting the app to open a port
    would be a poor trade for a setting the user is likely to be experimenting
    with.

    Returns (running, reason) where reason names the obstacle when it is not.
    """
    global phone_endpoint_instance

    settings = current_ai_config()
    if not settings.get("phone_endpoint_enabled"):
        stop_phone_endpoint()
        return False, "disabled"

    import phone_endpoint
    import secrets_manager
    import tailscale_support

    state = tailscale_support.get_state()
    if not state.usable:
        # Refusing to start is the whole point: without Tailscale the only
        # addresses left are the LAN and the wildcard, and this endpoint is not
        # meant to be reachable on either.
        stop_phone_endpoint()
        print(f"[PHONE] not starting - Tailscale is {state.reason}")
        return False, state.reason

    token = secrets_manager.get_secret(phone_endpoint.TOKEN_ENV_NAME)
    if not token:
        token = phone_endpoint.generate_token()
        secrets_manager.set_secret(phone_endpoint.TOKEN_ENV_NAME, token)
        print("[PHONE] generated a new access key")

    port = int(settings.get("phone_endpoint_port", phone_endpoint.DEFAULT_PORT))

    # Restart when anything about the socket or the token changed; leave a
    # correctly running server alone.
    if phone_endpoint_instance is not None:
        unchanged = (phone_endpoint_instance.host == state.ipv4
                     and phone_endpoint_instance.port == port
                     and phone_endpoint_instance.token == token)
        if unchanged:
            return True, "ok"
        stop_phone_endpoint()

    endpoint = phone_endpoint.PhoneEndpoint(
        host=state.ipv4,
        port=port,
        token=token,
        dictate=dictate_from_phone,
        ready_check=phone_model_ready,
        messages=phone_endpoint_messages(),
    )

    try:
        endpoint.start()
    except OSError as error:
        print(f"[PHONE] could not open the port: {error}")
        return False, "port_busy"
    except Exception as error:
        print(f"[PHONE] could not start: {error}")
        return False, "unknown"

    phone_endpoint_instance = endpoint
    return True, "ok"


# Popup kezelés (Signal-alapú thread-safe kommunikáció)
def show_popup():
    """Popup ablak megjelenítése (thread-safe)"""
    global popup_window
    if popup_window:
        popup_window.request_show_popup.emit()

def show_text_popup(text: str):
    """Szöveg megjelenítése a popup-ban (thread-safe)"""
    global popup_window
    if popup_window:
        popup_window.request_show_text.emit(text)

def show_processing_popup():
    """Processing állapot megjelenítése (thread-safe)"""
    global popup_window
    if popup_window:
        popup_window.request_show_processing.emit()

def hide_popup():
    """Popup ablak elrejtése (thread-safe)"""
    global popup_window
    if popup_window:
        popup_window.request_hide_popup.emit()

# Rögzítés
def start_recording():
    global recording, audio_data
    if not recording:
        recording = True
        audio_data = []
        # Queue ürítése
        while not amplitude_queue.empty():
            try:
                amplitude_queue.get_nowait()
            except:
                break
        show_popup()
        play_sound(SOUND_START)
        print("\n[RECORDING] Starting...")
        update_icon('red', t("tray_recording", ui_lang))

def stop_recording():
    global recording, audio_data
    if recording:
        recording = False
        play_sound(SOUND_STOP)
        print("[RECORDING] Stopped")
        update_icon('yellow', t("tray_processing", ui_lang))

        if len(audio_data) > 0:
            show_processing_popup()  # Processing animáció indítása
            audio_copy = audio_data.copy()
            audio_data = []
            threading.Thread(target=process_audio, args=(audio_copy,), daemon=True).start()
        else:
            print("[FIGYELEM] Nincs rogzitett hang!")
            hide_popup()
            update_icon('blue', t("tray_ready", ui_lang))

def cancel_recording():
    """Felvétel megszakítása (Escape) - nem dolgozza fel"""
    global recording, audio_data
    if recording:
        recording = False
        audio_data = []
        hide_popup()
        print("[RECORDING] Cancelled")
        update_icon('blue', t("tray_ready", ui_lang))

# Hotkey
# macOS virtual key codes (fizikai billentyűk - nem függ a modifier-ektől!)
MACOS_VK_CODES = {
    'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7, 'c': 8, 'v': 9,
    'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15, 'y': 16, 't': 17,
    '1': 18, '2': 19, '3': 20, '4': 21, '6': 22, '5': 23, '9': 25, '7': 26,
    '8': 28, '0': 29, 'o': 31, 'u': 32, 'i': 34, 'p': 35, 'l': 37, 'j': 38,
    'k': 40, 'n': 45, 'm': 46,
}
# Fordított map: vk -> betű
VK_TO_KEY = {v: k for k, v in MACOS_VK_CODES.items()}

def parse_hotkey(hotkey_str):
    parts = hotkey_str.lower().split('+')
    return {
        'modifiers': [p for p in parts if p in ['ctrl', 'alt', 'shift', 'cmd']],
        'key': parts[-1]
    }

def get_key_from_vk(key):
    """Virtual key code alapján visszaadja a billentyű nevét (macOS Alt workaround)"""
    if hasattr(key, 'vk') and key.vk is not None:
        return VK_TO_KEY.get(key.vk, None)
    return None

def check_hotkey_match():
    hotkey_config = parse_hotkey(config["hotkey"])
    for mod in hotkey_config['modifiers']:
        if mod == 'ctrl' and not hotkey_pressed.get('ctrl', False):
            return False
        if mod == 'alt' and not hotkey_pressed.get('alt', False):
            return False
        if mod == 'shift' and not hotkey_pressed.get('shift', False):
            return False
        if mod == 'cmd' and not hotkey_pressed.get('cmd', False):
            return False
    if not hotkey_pressed.get(hotkey_config['key'], False):
        return False
    return True

def on_press(key):
    global hotkey_pressed

    # Escape = Cancel (felvétel megszakítása)
    if key == keyboard.Key.esc:
        if recording:
            cancel_recording()
        return

    # Check for evdev modifier keys (has _modifier_name attribute)
    if hasattr(key, '_modifier_name') and key._modifier_name:
        hotkey_pressed[key._modifier_name] = True
    # Modifier billentyűk (pynput)
    elif key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
        hotkey_pressed['ctrl'] = True
    elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
        hotkey_pressed['alt'] = True
    elif key in [keyboard.Key.shift, keyboard.Key.shift_r]:
        hotkey_pressed['shift'] = True
    elif key in [keyboard.Key.cmd, keyboard.Key.cmd_r]:
        hotkey_pressed['cmd'] = True
    else:
        # Normál billentyűk
        # Evdev keys: use char attribute directly (don't use macOS VK codes!)
        if hasattr(key, 'char') and key.char:
            hotkey_pressed[key.char.lower()] = True
        elif hasattr(key, 'name') and key.name:
            hotkey_pressed[key.name.lower()] = True
        else:
            # Fallback: macOS VK codes (pynput on macOS)
            vk_key = get_key_from_vk(key)
            if vk_key:
                hotkey_pressed[vk_key] = True
    if check_hotkey_match():
        if not recording:
            start_recording()
        else:
            stop_recording()

def on_release(key):
    global hotkey_pressed
    # Check for evdev modifier keys (has _modifier_name attribute)
    if hasattr(key, '_modifier_name') and key._modifier_name:
        hotkey_pressed[key._modifier_name] = False
    # Modifier billentyűk (pynput)
    elif key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
        hotkey_pressed['ctrl'] = False
    elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
        hotkey_pressed['alt'] = False
    elif key in [keyboard.Key.shift, keyboard.Key.shift_r]:
        hotkey_pressed['shift'] = False
    elif key in [keyboard.Key.cmd, keyboard.Key.cmd_r]:
        hotkey_pressed['cmd'] = False
    else:
        # Normál billentyűk
        # Evdev keys: use char attribute directly (don't use macOS VK codes!)
        if hasattr(key, 'char') and key.char:
            hotkey_pressed[key.char.lower()] = False
        elif hasattr(key, 'name') and key.name:
            hotkey_pressed[key.name.lower()] = False
        else:
            # Fallback: macOS VK codes (pynput on macOS)
            vk_key = get_key_from_vk(key)
            if vk_key:
                hotkey_pressed[vk_key] = False

# Fő program
def main():
    global stream, tray_icon, qt_app, popup_window, tray_icon_updater, history_menu, config, ui_lang

    # PyQt6 inicializálás (először kell lennie)
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)  # Ne lépjen ki amikor a Settings bezárul

    # Modell ellenőrzés - van-e letöltött modell az aktuális device-hoz?
    from model_manager import has_any_model_downloaded, is_model_downloaded
    current_device = config.get("device", "cpu")
    current_model = config.get("model", "large-v3")

    # Először nézzük, hogy a beállított modell le van-e töltve
    if not is_model_downloaded(current_model, current_device):
        # Ha nincs, nézzük, van-e BÁRMILYEN modell
        has_model, available_model = has_any_model_downloaded(current_device)

        if not has_model:
            # Nincs egyetlen modell sem - wizard megjelenítése
            from setup_wizard import SetupWizard
            from PySide6.QtWidgets import QDialog
            wizard = SetupWizard()
            if wizard.exec() != QDialog.Accepted:
                # Felhasználó bezárta a wizard-ot letöltés nélkül
                sys.exit(0)
            # Wizard után ÚJRAINDÍTÁS szükséges (Qt/Metal konfliktus elkerülése)
            # Az app újraindítja magát, most már letöltött modellel
            print("[INFO] Model downloaded, restarting app...")
            qt_app.quit()
            if getattr(sys, 'frozen', False):
                # Bundled app
                os.execv(sys.executable, [sys.executable])
            else:
                # Dev mód
                os.execv(sys.executable, [sys.executable] + sys.argv)
            sys.exit(0)  # Biztonsági exit (nem kellene ide jutni)

    # Popup ablak létrehozása (hotkey és nyelv átadása)
    # Wayland: GTK layer-shell (nem lop fókuszt)
    # X11: Qt PopupManager (eredeti működés)
    def _is_wayland_session():
        session = os.environ.get('XDG_SESSION_TYPE', '').lower()
        return session == 'wayland' or bool(os.environ.get('WAYLAND_DISPLAY'))

    if _is_wayland_session():
        try:
            from wayland_overlay import WaylandOverlay, init_gtk, pump_gtk_events
            # GTK inicializálása FŐSZÁLBAN
            init_gtk()
            popup_window = WaylandOverlay(
                amplitude_queue,
                config["hotkey"],
                config.get("popup_display_duration", 5),
                ui_lang
            )
            # Qt timer a GTK event-ek pumpálásához (10ms intervallum)
            gtk_pump_timer = QTimer()
            gtk_pump_timer.timeout.connect(pump_gtk_events)
            gtk_pump_timer.start(10)
            print("[INFO] Wayland detected - using GTK layer-shell overlay (no focus stealing)")
        except ImportError as e:
            print(f"[WARN] GTK layer-shell not available: {e}")
            print("[WARN] Falling back to Qt popup (may steal focus on Wayland)")
            from popup_window import PopupManager
            popup_window = PopupManager(
                amplitude_queue,
                config["hotkey"],
                config.get("popup_display_duration", 5),
                ui_lang
            )
    else:
        from popup_window import PopupManager
        popup_window = PopupManager(
            amplitude_queue,
            config["hotkey"],
            config.get("popup_display_duration", 5),
            ui_lang
        )
        print("[INFO] X11 detected - using Qt popup")

    # Audio stream (rendszer alapértelmezett mikrofon)
    global actual_sample_rate
    try:
        # Lekérdezzük az alapértelmezett input device sample rate-jét
        default_input = sd.query_devices(kind='input')
        actual_sample_rate = int(default_input['default_samplerate'])
        print(f"[INFO] Microphone sample rate: {actual_sample_rate} Hz")
    except:
        actual_sample_rate = 48000  # Biztonságos alapértelmezett

    stream = sd.InputStream(
        samplerate=actual_sample_rate,
        channels=1,
        callback=audio_callback,
        dtype=np.float32
    )
    stream.start()

    # Audio rendszer "felébresztése" - csendes warmup (platform-specifikus)
    if hasattr(platform_handler, 'warmup_audio'):
        platform_handler.warmup_audio(SOUND_START)
    print("[INFO] Audio system initialized")
    sys.stdout.flush()

    # Platform-specifikus figyelmeztetések
    import platform as py_platform
    if py_platform.system() == "Darwin":
        print("[INFO] macOS: If hotkey doesn't work, add the app to Input Monitoring:")
        print("[INFO]   System Settings → Privacy & Security → Input Monitoring")
        sys.stdout.flush()
    elif py_platform.system() == "Linux":
        session_type = get_session_type()
        if session_type == "wayland":
            print("[INFO] Wayland session detected")
            print("[INFO] If hotkey doesn't work, add user to input group:")
            print("[INFO]   sudo usermod -a -G input $USER")
            print("[INFO]   Then log out and back in.")
            sys.stdout.flush()

    # Hotkey listener (platform-aware: X11/Wayland/macOS)
    global keyboard_listener
    keyboard_listener = create_keyboard_listener(on_press=on_press, on_release=on_release)

    # Health check: on Wayland a broken piece (no input group, missing wtype,
    # ...) used to fail silently into /tmp/whisper_stdout.log. Show a dialog
    # with copyable fix commands instead. A completely dead hotkey listener is
    # always shown, even when the user suppressed routine warnings.
    if sys.platform == "linux":
        session = system_check.get_session_type()
        if session == "wayland" or keyboard_listener is None:
            health_results = system_check.run_all(session)
            critical_bad = [r for r in health_results
                            if r.critical and r.status in ("warn", "fail")]
            suppressed = config.get("suppress_system_warnings", False)
            must_show = keyboard_listener is None
            if must_show and not critical_bad:
                # Listener failed although checks pass - show every non-ok row
                critical_bad = [r for r in health_results if r.status != "ok"] \
                               or health_results
            if critical_bad and (must_show or not suppressed):
                from qt_helpers import show_health_dialog
                suppress = show_health_dialog(critical_bad, ui_lang,
                                              show_suppress=not must_show)
                if suppress:
                    save_config_value("suppress_system_warnings", True)

    # System Tray ikon menüvel (Qt QSystemTrayIcon)
    tray_icon = QSystemTrayIcon(create_icon('gray'), qt_app)
    tray_icon.setToolTip("WhisperRocket")

    # Tray ikon frissítő (thread-safe)
    tray_icon_updater = TrayIconUpdater(qt_app)

    # Menü létrehozása
    tray_menu = QMenu()
    settings_action = QAction(t("tray_settings", ui_lang), qt_app)
    settings_action.triggered.connect(open_settings, Qt.QueuedConnection)
    tray_menu.addAction(settings_action)

    file_transcription_action = QAction(t("tray_file_transcription", ui_lang), qt_app)
    file_transcription_action.triggered.connect(open_file_transcription, Qt.QueuedConnection)
    tray_menu.addAction(file_transcription_action)
    tray_menu.addSeparator()

    # History almenü
    history_menu = QMenu(t("tray_history", ui_lang))
    tray_menu.addMenu(history_menu)

    # Fő menü aboutToShow frissíti a history-t (submenu aboutToShow nem megbízható)
    tray_menu.aboutToShow.connect(refresh_history_menu)

    # Frissítés keresése menüpont - a About ablakba senki nem néz be, a tray
    # menü a látható helye
    update_action = QAction(t("update_check_btn", ui_lang), qt_app)
    update_action.triggered.connect(check_updates_manual, Qt.QueuedConnection)
    tray_menu.addAction(update_action)

    # About menüpont
    from about_window import show_about
    about_action = QAction(t("tray_about", ui_lang), qt_app)
    about_action.triggered.connect(show_about, Qt.QueuedConnection)
    tray_menu.addAction(about_action)

    tray_menu.addSeparator()
    quit_action = QAction(t("tray_quit", ui_lang), qt_app)
    # Qt.QueuedConnection needed for QSystemTrayIcon menu actions
    quit_action.triggered.connect(quit_app, Qt.QueuedConnection)
    tray_menu.addAction(quit_action)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Automatic update check: at most once per day, only while the setting is
    # on (Settings > "Check for updates at startup"). One version query to
    # GitHub, nothing about the user is sent. Result arrives via Signal on the
    # main thread; failures are logged, never shown - a startup check must not
    # nag about the network.
    import update_checker
    if update_checker.should_auto_check(config):
        save_config_value("update_last_check", int(time.time()))
        start_update_probe()

    # Modell betöltés háttérben
    threading.Thread(target=load_model, daemon=True).start()

    # Started without waiting for the model: the endpoint answers /health with
    # "still loading" until it is ready, which is a better answer for the phone
    # than a refused connection.
    apply_phone_endpoint_settings()

    print("="*60)
    print("  WHISPER SPEECH-TO-TEXT")
    print("="*60)
    print(f"  Hotkey: {config['hotkey']}")
    print(f"  Model: {config['model']}")
    actual_device = "mlx" if whisper_backend == "mlx" else config['device']
    print(f"  Device: {actual_device}")
    print("")
    print("  SYSTEM TRAY COLORS:")
    print("    BLUE    = Ready")
    print("    RED     = Recording")
    print("    YELLOW  = Processing")
    print("    GREEN   = Done! (Ctrl+V to paste)")
    print("")
    print("  Exit: Right-click tray icon -> Exit")
    print("  Config: ~/.config/whisperrocket/config.json")
    print("="*60)
    print("")
    sys.stdout.flush()

    # Restart flag figyelő (Settings-ből jövő restart kéréshez)
    RESTART_FLAG_FILE = '/tmp/whisperrocket_restart'

    def check_restart_flag():
        """Restart flag ellenőrzése - Settings-ből jövő kérés"""
        if os.path.exists(RESTART_FLAG_FILE):
            print("[INFO] Restart request detected, restarting...")
            os.remove(RESTART_FLAG_FILE)

            import platform
            if getattr(sys, 'frozen', False):
                # Bundled app - közvetlenül újraindítjuk a binárist
                os.execv(sys.executable, [sys.executable])
            else:
                # Fejlesztői mód - script használata
                script_dir = os.path.dirname(__file__)
                if platform.system() == "Darwin":
                    start_script = os.path.join(script_dir, 'start_macos.sh')
                else:
                    start_script = os.path.join(script_dir, 'start.sh')
                os.execv('/bin/bash', ['bash', start_script])

    restart_timer = QTimer()
    restart_timer.timeout.connect(check_restart_flag)
    restart_timer.start(1000)  # 1 másodpercenként ellenőriz

    # Qt event loop futtatása (főszál)
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
