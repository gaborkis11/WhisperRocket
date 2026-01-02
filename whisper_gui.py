#!/usr/bin/env python3
import os
import sys
import json
import tempfile
import time
import threading
from queue import Queue

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
from PySide6.QtCore import QTimer, Slot, Signal, QObject, Qt
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_requested.connect(self._do_update)

    @Slot(str, str)
    def _do_update(self, color, title):
        global tray_icon
        if tray_icon:
            tray_icon.setIcon(create_icon(color))
            tray_icon.setToolTip(title)


from translations import t, TRANSLATIONS
import history_manager
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
            "language": "hu",
            "sample_rate": 16000,
            "input_device": None,
            "output_device": None
        }

# Globális változók
config = load_config()
ui_lang = config.get("ui_language", "en")
model = None
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
history_viewers = []  # Aktív history viewer ablakok

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
        settings_window_instance = SettingsWindow()
        settings_window_instance.show()
    else:
        settings_window_instance.raise_()
        settings_window_instance.activateWindow()

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
    global model
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

# Feldolgozás
def process_audio(audio_copy):
    print("\n" + "="*60)
    print("[PROCESSING] Starting...")

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

        if whisper_backend == "mlx":
            # MLX backend
            import mlx_whisper
            result = mlx_whisper.transcribe(
                temp_file.name,
                path_or_hf_repo=f"mlx-community/whisper-{model['model_name']}-mlx",
                language=config["language"]
            )
            text = result.get("text", "").strip()
        else:
            # Faster-whisper backend
            segments, info = model.transcribe(
                temp_file.name,
                language=config["language"],
                beam_size=5
            )
            # Szöveg összegyűjtés
            text = " ".join([segment.text.strip() for segment in segments])
        
        elapsed = time.time() - start_time
        
        # Vágólapra másolás
        pyperclip.copy(text)
        # Auto-paste (platform-independent)
        try:
            print("[INFO] Auto-pasting...")
            time.sleep(0.3)

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
        
        # Temp fájl törlés
        os.unlink(temp_file.name)

        # History mentés
        if text.strip():
            history_manager.add_entry(text, elapsed, config["language"])
            # Menü frissítése a főszálban (QTimer.singleShot thread-safe)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, refresh_history_menu)

        # Ikon frissítés
        update_icon('green', t("tray_done", ui_lang))

        # Szöveg megjelenítése a popup-ban (3mp-ig látszik, kattintásra expand)
        show_text_popup(text)

        # Ikon visszaállítás késleltetéssel
        time.sleep(3)
        update_icon('blue', t("tray_ready", ui_lang))

    except Exception as e:
        print("\n" + "="*60)
        print(f"[HIBA] {e}")
        print("="*60 + "\n")

        update_icon('red', t("tray_error", ui_lang))
        time.sleep(2)
        hide_popup()
        update_icon('blue', t("tray_ready", ui_lang))

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
    tray_menu.addSeparator()

    # History almenü
    history_menu = QMenu(t("tray_history", ui_lang))
    tray_menu.addMenu(history_menu)

    # Fő menü aboutToShow frissíti a history-t (submenu aboutToShow nem megbízható)
    tray_menu.aboutToShow.connect(refresh_history_menu)

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

    # Modell betöltés háttérben
    threading.Thread(target=load_model, daemon=True).start()

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
