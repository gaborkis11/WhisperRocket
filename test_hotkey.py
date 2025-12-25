#!/usr/bin/env python3
from pynput import keyboard
import time

print('KEYBOARD TESZT - nyomj billentyűket 5 mp-ig...')

events = []

def on_press(key):
    events.append(str(key))
    print(f'  -> {key}')

listener = keyboard.Listener(on_press=on_press)
listener.start()
time.sleep(5)
listener.stop()

print(f'Összesen: {len(events)} esemény')
if events:
    print('MŰKÖDIK!')
else:
    print('NEM MŰKÖDIK')
