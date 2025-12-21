#!/usr/bin/env python3
import os
import sys
import json
import tempfile
import time
import threading
from queue import Queue
import sounddevice as sd
import soundfile as sf
import pyperclip
from pynput import keyboard
from faster_whisper import WhisperModel
import numpy as np
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from translations import t

# Konfiguráció
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

# Hangfájlok
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
SOUND_START = os.path.join(ASSETS_DIR, 'start_soft_click_smooth.wav')
SOUND_STOP = os.path.join(ASSETS_DIR, 'stop_soft_click_smooth.wav')


def detect_device():
    """CUDA elérhetőség automatikus detektálása"""
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
        if result.returncode == 0:
            return "cuda", "float16"
    except:
        pass
    return "cpu", "int8"


def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        device, compute_type = detect_device()
        return {
            "hotkey": "alt+s",
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

# Popup ablak változók
amplitude_queue = Queue(maxsize=100)  # Thread-safe queue a waveform adatokhoz
popup_window = None
qt_app = None

# Hang lejátszás háttérszálban (paplay használata - megbízhatóbb)
def play_sound(sound_file):
    """Hangfájl lejátszása háttérszálban"""
    def _play():
        try:
            if os.path.exists(sound_file):
                import subprocess
                # HDMI audio "felébresztése" - csendes ping + várakozás
                subprocess.run(['paplay', '--volume=1', sound_file], capture_output=True, timeout=2)
                time.sleep(0.15)  # Várunk, hogy az HDMI felébredjen
                # Tényleges lejátszás
                subprocess.run(['paplay', '--volume=65536', sound_file], capture_output=True, timeout=2)
        except Exception as e:
            print(f"[FIGYELEM] Hang lejátszás sikertelen: {e}")
    threading.Thread(target=_play, daemon=True).start()

# System tray ikon létrehozása
def create_icon(color='blue'):
    """Mikrofon ikon lekerekített színes háttérrel"""
    # 64x64 átlátszó háttér
    image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    dc = ImageDraw.Draw(image)

    # Lekerekített színes háttér
    dc.rounded_rectangle([0, 0, 63, 63], radius=12, fill=color)

    # Egyszerű mikrofon silhouette (fehér)
    # Mikrofon fej (lekerekített téglalap)
    dc.rounded_rectangle([24, 8, 40, 32], radius=8, fill='white')
    # Mikrofon állvány ív
    dc.arc([16, 20, 48, 48], start=0, end=180, fill='white', width=4)
    # Függőleges rúd
    dc.rectangle([30, 44, 34, 52], fill='white')
    # Talp
    dc.rectangle([22, 52, 42, 56], fill='white')

    return image

def update_icon(color, title):
    """Ikon és cím frissítése"""
    global tray_icon
    if tray_icon:
        tray_icon.icon = create_icon(color)
        tray_icon.title = title

def quit_app(icon, item):
    """Alkalmazás leállítása"""
    global stream, qt_app
    print("[INFO] Kilépés...")
    if stream:
        stream.stop()
        stream.close()
    icon.stop()
    # Qt alkalmazás leállítása
    if qt_app:
        qt_app.quit()

def open_settings(icon, item):
    """Beállítások ablak megnyitása"""
    print("[INFO] Beállítások megnyitása...")
    import subprocess
    import sys
    # Beállítások ablak indítása külön folyamatban
    subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), 'settings_window.py')])

# Modell betöltés
def load_model():
    global model
    print("[INFO] Whisper modell betoltese...")
    update_icon('orange', t("tray_loading", ui_lang))

    try:
        model = WhisperModel(
            config["model"],
            device=config["device"],
            compute_type=config["compute_type"]
        )
        print("[INFO] Modell betoltve!")
        update_icon('blue', t("tray_ready", ui_lang))
    except Exception as e:
        print(f"[HIBA] Modell betoltes: {e}")
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
    print("[FELDOLGOZAS] Indul...")
    
    try:
        # Audio összefűzés
        audio_array = np.concatenate(audio_copy, axis=0)
        print(f"[INFO] Audio hossz: {len(audio_array)/actual_sample_rate:.2f}s")

        # Temp fájl (Whisper automatikusan resample-öl)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        sf.write(temp_file.name, audio_array, actual_sample_rate)
        
        # Whisper transcribe
        print("[INFO] Whisper feldolgozas...")
        start_time = time.time()
        
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
        # Automatikus beillesztes xdotool-lal
        try:
            print("[INFO] Automatikus beillesztes...")
            time.sleep(0.3)
            import subprocess

            # Aktív ablak detektálás
            paste_key = "ctrl+v"  # Alapértelmezett
            try:
                # Ablak neve és osztálya lekérése
                window_name = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowname'],
                    capture_output=True, text=True
                ).stdout.strip().lower()

                window_class = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowclassname'],
                    capture_output=True, text=True
                ).stdout.strip().lower()

                print(f"[DEBUG] Ablak: {window_name} ({window_class})")

                # Terminálok és Cursor detektálása - ezek Ctrl+Shift+V-t használnak
                ctrl_shift_v_apps = [
                    'terminal', 'terminator', 'konsole', 'xterm', 'urxvt', 'alacritty',
                    'kitty', 'tilix', 'guake', 'yakuake', 'gnome-terminal', 'xfce4-terminal',
                    'cursor', 'code', 'vscode', 'vscodium'  # Cursor és VS Code
                ]

                for app in ctrl_shift_v_apps:
                    if app in window_name or app in window_class:
                        paste_key = "ctrl+shift+v"
                        print(f"[INFO] Detektalva: {app} -> Ctrl+Shift+V")
                        break

            except Exception as detect_err:
                print(f"[DEBUG] Ablak detektalas sikertelen: {detect_err}")

            subprocess.run(['xdotool', 'key', paste_key], check=True)
            print(f"[INFO] Beillesztve ({paste_key})!")
        except Exception as e:
            print(f"[FIGYELEM] Beillesztes sikertelen: {e}")
        print("="*60)
        print(f"EREDMENY: '{text}'")
        print(f"IDO: {elapsed:.2f}s")
        print("="*60)
        print(">>> VAGOLAP: Nyomd meg Ctrl+V! <<<")
        print("="*60 + "\n")
        
        # Temp fájl törlés
        os.unlink(temp_file.name)

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

# Popup kezelés
def show_popup():
    """Popup ablak megjelenítése (thread-safe)"""
    global popup_window
    if popup_window:
        # Qt-nek főszálból kell hívni - QTimer.singleShot használata
        QTimer.singleShot(0, popup_window.show_popup)

def show_text_popup(text: str):
    """Szöveg megjelenítése a popup-ban (thread-safe)"""
    global popup_window
    print(f"[DEBUG] show_text_popup() hívva, text='{text[:30]}...'")
    if popup_window:
        # Szöveg tárolása a popup objektumon és metódus hívás
        popup_window.pending_text = text
        QTimer.singleShot(0, popup_window.show_pending_text)

def show_processing_popup():
    """Processing állapot megjelenítése (thread-safe)"""
    global popup_window
    if popup_window:
        QTimer.singleShot(0, popup_window.show_processing)

def hide_popup():
    """Popup ablak elrejtése (thread-safe)"""
    global popup_window
    if popup_window:
        QTimer.singleShot(0, popup_window.hide_popup)

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
        print("\n[ROGZITES] Indul...")
        update_icon('red', t("tray_recording", ui_lang))

def stop_recording():
    global recording, audio_data
    if recording:
        recording = False
        play_sound(SOUND_STOP)
        print("[ROGZITES] Megall")
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
        print("[ROGZITES] Megszakítva (Cancel)")
        update_icon('blue', t("tray_ready", ui_lang))

# Hotkey
def parse_hotkey(hotkey_str):
    parts = hotkey_str.lower().split('+')
    return {
        'modifiers': [p for p in parts if p in ['ctrl', 'alt', 'shift']],
        'key': parts[-1]
    }

def check_hotkey_match():
    hotkey_config = parse_hotkey(config["hotkey"])
    for mod in hotkey_config['modifiers']:
        if mod == 'ctrl' and not hotkey_pressed.get('ctrl', False):
            return False
        if mod == 'alt' and not hotkey_pressed.get('alt', False):
            return False
        if mod == 'shift' and not hotkey_pressed.get('shift', False):
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

    if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
        hotkey_pressed['ctrl'] = True
    elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
        hotkey_pressed['alt'] = True
    elif key in [keyboard.Key.shift, keyboard.Key.shift_r]:
        hotkey_pressed['shift'] = True
    elif hasattr(key, 'char') and key.char:
        hotkey_pressed[key.char.lower()] = True
    elif hasattr(key, 'name'):
        hotkey_pressed[key.name.lower()] = True

    if check_hotkey_match():
        if not recording:
            start_recording()
        else:
            stop_recording()

def on_release(key):
    global hotkey_pressed
    if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
        hotkey_pressed['ctrl'] = False
    elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]:
        hotkey_pressed['alt'] = False
    elif key in [keyboard.Key.shift, keyboard.Key.shift_r]:
        hotkey_pressed['shift'] = False
    elif hasattr(key, 'char') and key.char:
        hotkey_pressed[key.char.lower()] = False
    elif hasattr(key, 'name'):
        hotkey_pressed[key.name.lower()] = False

# Fő program
def main():
    global stream, tray_icon, qt_app, popup_window

    # PyQt6 inicializálás (először kell lennie)
    qt_app = QApplication(sys.argv)

    # Popup ablak létrehozása (hotkey és nyelv átadása)
    from popup_window import RecordingPopup
    popup_window = RecordingPopup(
        amplitude_queue,
        config["hotkey"],
        config.get("popup_display_duration", 5),
        ui_lang
    )

    # Audio stream (rendszer alapértelmezett mikrofon)
    global actual_sample_rate
    try:
        # Lekérdezzük az alapértelmezett input device sample rate-jét
        default_input = sd.query_devices(kind='input')
        actual_sample_rate = int(default_input['default_samplerate'])
        print(f"[INFO] Mikrofon sample rate: {actual_sample_rate} Hz")
    except:
        actual_sample_rate = 48000  # Biztonságos alapértelmezett

    stream = sd.InputStream(
        samplerate=actual_sample_rate,
        channels=1,
        callback=audio_callback,
        dtype=np.float32
    )
    stream.start()

    # Audio rendszer "felébresztése" - csendes warmup
    import subprocess
    subprocess.run(['paplay', '--volume=1', SOUND_START], capture_output=True, timeout=2)
    print("[INFO] Audio rendszer inicializálva")

    # Hotkey listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # System Tray ikon menüvel (klikk -> menü)
    menu = Menu(
        MenuItem(t("tray_settings", ui_lang), open_settings),
        Menu.SEPARATOR,
        MenuItem(t("tray_quit", ui_lang), quit_app)
    )
    tray_icon = Icon("WhisperWarp", create_icon('gray'), "WhisperWarp", menu)

    # Modell betöltés háttérben
    threading.Thread(target=load_model, daemon=True).start()

    print("="*60)
    print("  WHISPER SPEECH-TO-TEXT")
    print("="*60)
    print(f"  Hotkey: {config['hotkey']}")
    print(f"  Modell: {config['model']}")
    print(f"  Device: {config['device']}")
    print("")
    print("  SYSTEM TRAY SZINEK:")
    print("    KEK     = Keszen all")
    print("    PIROS   = Rogzites")
    print("    SARGA   = Feldolgozas")
    print("    ZOLD    = Kesz! (Ctrl+V beillesztes)")
    print("")
    print("  Leallit: Jobb klikk tray ikonra -> Kilépés")
    print("  Config:  nano config.json")
    print("="*60)
    print("")

    # Tray ikon futtatása háttérszálban
    tray_icon.run_detached()

    # Qt event loop futtatása (főszál)
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
