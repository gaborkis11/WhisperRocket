#!/usr/bin/env python3
import os
import json
import tempfile
import time
import threading
import sounddevice as sd
import soundfile as sf
import pyperclip
from pynput import keyboard
from faster_whisper import WhisperModel
import numpy as np
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

# Konfiguráció
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

# Hangfájlok
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
SOUND_START = os.path.join(ASSETS_DIR, 'start_soft_click_smooth.wav')
SOUND_STOP = os.path.join(ASSETS_DIR, 'stop_soft_click_smooth.wav')

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "hotkey": "alt+s",
            "model": "large-v3",
            "device": "cuda",
            "compute_type": "float16",
            "language": "hu",
            "sample_rate": 16000,
            "input_device": None,
            "output_device": None
        }

# Globális változók
config = load_config()
model = None
recording = False
audio_data = []
stream = None
tray_icon = None
hotkey_pressed = {}
actual_sample_rate = config.get("sample_rate", 16000)  # Tényleges sample rate

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

# Színes ikon létrehozása
def create_icon(color='blue'):
    """Színes kör ikon - kék/piros/sárga/zöld"""
    image = Image.new('RGB', (64, 64), color=color)
    dc = ImageDraw.Draw(image)
    dc.ellipse([8, 8, 56, 56], fill='white')
    return image

def update_icon(color, title):
    """Ikon és cím frissítése"""
    global tray_icon
    if tray_icon:
        tray_icon.icon = create_icon(color)
        tray_icon.title = title

def quit_app(icon, item):
    """Alkalmazás leállítása"""
    global stream
    print("[INFO] Kilépés...")
    if stream:
        stream.stop()
        stream.close()
    icon.stop()

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
    update_icon('orange', 'Whisper - Modell betoltes...')
    
    try:
        model = WhisperModel(
            config["model"],
            device=config["device"],
            compute_type=config["compute_type"]
        )
        print("[INFO] Modell betoltve!")
        update_icon('blue', 'Whisper - Keszen all')
    except Exception as e:
        print(f"[HIBA] Modell betoltes: {e}")
        update_icon('red', 'Whisper - Modell HIBA!')

# Audio callback
def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_data.append(indata.copy())

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
        update_icon('green', 'Whisper - Kesz! Ctrl+V')
        time.sleep(2)
        update_icon('blue', 'Whisper - Keszen all')
        
    except Exception as e:
        print("\n" + "="*60)
        print(f"[HIBA] {e}")
        print("="*60 + "\n")
        
        update_icon('red', 'Whisper - HIBA!')
        time.sleep(2)
        update_icon('blue', 'Whisper - Keszen all')

# Rögzítés
def start_recording():
    global recording, audio_data
    if not recording:
        recording = True
        audio_data = []
        play_sound(SOUND_START)
        print("\n[ROGZITES] Indul...")
        update_icon('red', 'Whisper - ROGZITES')

def stop_recording():
    global recording, audio_data
    if recording:
        recording = False
        play_sound(SOUND_STOP)
        print("[ROGZITES] Megall")
        update_icon('yellow', 'Whisper - Feldolgozas...')
        
        if len(audio_data) > 0:
            audio_copy = audio_data.copy()
            audio_data = []
            threading.Thread(target=process_audio, args=(audio_copy,), daemon=True).start()
        else:
            print("[FIGYELEM] Nincs rogzitett hang!")
            update_icon('blue', 'Whisper - Keszen all')

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
    global stream, tray_icon
    
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
        MenuItem("Beállítások", open_settings),
        Menu.SEPARATOR,
        MenuItem("Kilépés", quit_app)
    )
    tray_icon = Icon("WhisperTalk", create_icon('gray'), "WhisperTalk", menu)
    
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
    
    # Tray ikon futtatása (ez blokkoló hívás)
    tray_icon.run()

if __name__ == "__main__":
    main()
