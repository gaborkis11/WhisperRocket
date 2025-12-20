#!/usr/bin/env python3
import os
import tempfile
import time
import sounddevice as sd
import soundfile as sf
import pyperclip
from pynput import keyboard
from faster_whisper import WhisperModel
import numpy as np

SAMPLE_RATE = 16000
MODEL_NAME = "large-v3"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
LANGUAGE = "hu"

print("Whisper modell betoltese...")
model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
print("Modell betoltve!")
print("")
print("Speech-to-Text AKTIV!")
print("Hasznalat:")
print("  Alt+S -> rogzites indul/leallit")
print("  Ctrl+Q -> kilepes")
print("")

recording = False
audio_data = []
alt_pressed = False

def start_recording():
    global recording, audio_data
    if not recording:
        recording = True
        audio_data = []
        print("Rogzites...")

def stop_recording():
    global recording, audio_data
    if recording:
        recording = False
        print("Feldolgozas...", end=" ", flush=True)
        
        if len(audio_data) > 0:
            audio_array = np.concatenate(audio_data, axis=0)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            sf.write(temp_file.name, audio_array, SAMPLE_RATE)
            
            start_time = time.time()
            segments, info = model.transcribe(temp_file.name, language=LANGUAGE, beam_size=5)
            
            text = " ".join([segment.text.strip() for segment in segments])
            pyperclip.copy(text)
            
            time.sleep(0.1)
            keyboard_controller = keyboard.Controller()
            keyboard_controller.press(keyboard.Key.ctrl)
            keyboard_controller.press('v')
            keyboard_controller.release('v')
            keyboard_controller.release(keyboard.Key.ctrl)
            
            elapsed = time.time() - start_time
            print(f"Kesz! '{text}' ({elapsed:.2f}s)")
            
            os.unlink(temp_file.name)
        else:
            print("Nincs rogzitett hang!")

def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_data.append(indata.copy())

stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback, dtype=np.float32)
stream.start()

def on_press(key):
    global alt_pressed
    
    if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r or key == keyboard.Key.alt_gr:
        alt_pressed = True
    elif hasattr(key, 'char') and key.char == 's':
        if alt_pressed:
            if not recording:
                start_recording()
            else:
                stop_recording()
    elif key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        pass
    
    if hasattr(key, 'char') and key.char == 'q':
        try:
            if keyboard.Controller()._current_modifiers and keyboard.Key.ctrl in keyboard.Controller()._current_modifiers:
                print("Kilepes...")
                return False
        except:
            pass

def on_release(key):
    global alt_pressed
    
    if key == keyboard.Key.alt_l or key == keyboard.Key.alt_r or key == keyboard.Key.alt_gr:
        alt_pressed = False

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

stream.stop()
stream.close()
