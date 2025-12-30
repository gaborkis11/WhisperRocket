"""
WhisperRocket - Cross-platform Keyboard Listener
Supports both X11 (pynput) and Wayland (evdev)
"""

import os
import threading
from typing import Callable, Optional, Set
from abc import ABC, abstractmethod


def get_session_type() -> str:
    """Detect display server type (x11, wayland, or unknown)"""
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    if session_type in ['x11', 'wayland']:
        return session_type

    # Fallback detection
    if os.environ.get('WAYLAND_DISPLAY'):
        return 'wayland'
    if os.environ.get('DISPLAY'):
        return 'x11'

    return 'unknown'


def is_user_in_input_group() -> bool:
    """Check if current user is in the 'input' group (required for evdev)"""
    try:
        import grp
        input_group = grp.getgrnam('input')
        username = os.environ.get('USER', '')
        return username in input_group.gr_mem or os.getgid() == input_group.gr_gid
    except (KeyError, ImportError):
        return False


def get_input_devices() -> list:
    """Get list of keyboard input devices"""
    devices = []
    try:
        import evdev
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                caps = device.capabilities()
                # Check if device has keyboard capabilities (EV_KEY = 1)
                if evdev.ecodes.EV_KEY in caps:
                    keys = caps[evdev.ecodes.EV_KEY]
                    # Check if it has typical keyboard keys (KEY_A = 30)
                    if evdev.ecodes.KEY_A in keys:
                        devices.append(device)
                    else:
                        device.close()
                else:
                    device.close()
            except (PermissionError, OSError):
                continue
    except ImportError:
        pass
    return devices


class KeyboardListenerBase(ABC):
    """Abstract base class for keyboard listeners"""

    def __init__(self, on_press: Callable, on_release: Callable):
        self.on_press = on_press
        self.on_release = on_release
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @abstractmethod
    def start(self) -> bool:
        """Start listening. Returns True if successful."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop listening."""
        pass

    def is_running(self) -> bool:
        return self._running


class PynputListener(KeyboardListenerBase):
    """Keyboard listener using pynput (works on X11)"""

    def __init__(self, on_press: Callable, on_release: Callable):
        super().__init__(on_press, on_release)
        self._listener = None

    def start(self) -> bool:
        try:
            from pynput import keyboard
            self._listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            )
            self._listener.start()
            self._running = True
            return True
        except Exception as e:
            print(f"[WARNING] Pynput listener failed to start: {e}")
            return False

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._running = False


class EvdevListener(KeyboardListenerBase):
    """Keyboard listener using evdev (works on Wayland)

    Requires:
    - evdev Python package
    - User must be in 'input' group OR have appropriate permissions
    """

    # Key code mappings (evdev to key names)
    EVDEV_KEY_MAP = {
        # Letters
        30: 'a', 48: 'b', 46: 'c', 32: 'd', 18: 'e', 33: 'f', 34: 'g',
        35: 'h', 23: 'i', 36: 'j', 37: 'k', 38: 'l', 50: 'm', 49: 'n',
        24: 'o', 25: 'p', 16: 'q', 19: 'r', 31: 's', 20: 't', 22: 'u',
        47: 'v', 17: 'w', 45: 'x', 21: 'y', 44: 'z',
        # Numbers
        2: '1', 3: '2', 4: '3', 5: '4', 6: '5', 7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
        # Function keys
        59: 'f1', 60: 'f2', 61: 'f3', 62: 'f4', 63: 'f5', 64: 'f6',
        65: 'f7', 66: 'f8', 67: 'f9', 68: 'f10', 87: 'f11', 88: 'f12',
        # Special keys
        1: 'esc', 14: 'backspace', 15: 'tab', 28: 'enter', 57: 'space',
    }

    # Modifier key codes
    MODIFIER_KEYS = {
        29: 'ctrl',   # KEY_LEFTCTRL
        97: 'ctrl',   # KEY_RIGHTCTRL
        56: 'alt',    # KEY_LEFTALT
        100: 'alt',   # KEY_RIGHTALT
        42: 'shift',  # KEY_LEFTSHIFT
        54: 'shift',  # KEY_RIGHTSHIFT
        125: 'cmd',   # KEY_LEFTMETA (Super/Win key)
        126: 'cmd',   # KEY_RIGHTMETA
    }

    def __init__(self, on_press: Callable, on_release: Callable):
        super().__init__(on_press, on_release)
        self._devices = []
        self._stop_event = threading.Event()

    def start(self) -> bool:
        try:
            import evdev
            import select
        except ImportError:
            print("[WARNING] evdev package not installed. Install with: pip install evdev")
            return False

        self._devices = get_input_devices()
        if not self._devices:
            print("[WARNING] No keyboard devices found or no permission to access them.")
            print("[INFO] Wayland requires user to be in 'input' group.")
            print("[INFO] Run: sudo usermod -a -G input $USER")
            print("[INFO] Then log out and log back in.")
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        self._running = True
        return True

    def _listen_loop(self) -> None:
        import evdev
        import select

        try:
            while not self._stop_event.is_set():
                # Use select to wait for events with timeout
                r, w, x = select.select(self._devices, [], [], 0.1)
                for device in r:
                    try:
                        for event in device.read():
                            if event.type == evdev.ecodes.EV_KEY:
                                key_event = evdev.categorize(event)
                                self._handle_key_event(key_event)
                    except (OSError, IOError):
                        # Device disconnected
                        continue
        except Exception as e:
            print(f"[WARNING] Evdev listener error: {e}")
        finally:
            self._running = False

    def _handle_key_event(self, key_event) -> None:
        """Convert evdev key event to pynput-compatible format and call handlers"""
        import evdev

        keycode = key_event.scancode
        key_state = key_event.keystate

        # Create a simple key object that mimics pynput
        key = EvdevKey(keycode, self.EVDEV_KEY_MAP, self.MODIFIER_KEYS)

        try:
            if key_state == evdev.KeyEvent.key_down:
                self.on_press(key)
            elif key_state == evdev.KeyEvent.key_up:
                self.on_release(key)
        except Exception:
            pass

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        for device in self._devices:
            try:
                device.close()
            except:
                pass
        self._devices = []
        self._running = False


class EvdevKey:
    """Wrapper class to make evdev keys compatible with pynput-style handling"""

    def __init__(self, keycode: int, key_map: dict, modifier_map: dict):
        self.keycode = keycode
        self._key_map = key_map
        self._modifier_map = modifier_map

        # Determine key properties
        self.char = key_map.get(keycode)
        self.name = self.char
        self.vk = keycode

        # Check if it's a special pynput-style key
        self._is_modifier = keycode in modifier_map
        self._modifier_name = modifier_map.get(keycode)

    def __eq__(self, other):
        """Allow comparison with pynput Key enum values"""
        try:
            from pynput import keyboard

            if self._is_modifier:
                modifier = self._modifier_name
                if modifier == 'ctrl':
                    return other in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]
                elif modifier == 'alt':
                    return other in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]
                elif modifier == 'shift':
                    return other in [keyboard.Key.shift, keyboard.Key.shift_r]
                elif modifier == 'cmd':
                    return other in [keyboard.Key.cmd, keyboard.Key.cmd_r]

            if self.keycode == 1:  # ESC
                return other == keyboard.Key.esc

            return False
        except ImportError:
            return False


def create_keyboard_listener(on_press: Callable, on_release: Callable) -> Optional[KeyboardListenerBase]:
    """
    Factory function to create the appropriate keyboard listener.

    - On X11: Uses pynput (reliable, no special permissions needed)
    - On Wayland: Uses evdev (requires user in 'input' group)

    Returns None if no listener could be created.
    """
    session_type = get_session_type()
    print(f"[INFO] Display server: {session_type}")

    if session_type == 'wayland':
        # Try evdev first for Wayland
        print("[INFO] Wayland detected, using evdev for hotkey support...")
        listener = EvdevListener(on_press, on_release)
        if listener.start():
            print("[INFO] Evdev keyboard listener started successfully")
            return listener
        else:
            # Fallback to pynput (might work through XWayland)
            print("[INFO] Falling back to pynput (may not work on pure Wayland)...")
            listener = PynputListener(on_press, on_release)
            if listener.start():
                return listener
    else:
        # X11 or unknown - use pynput
        listener = PynputListener(on_press, on_release)
        if listener.start():
            print("[INFO] Pynput keyboard listener started successfully")
            return listener

        # Fallback to evdev if pynput fails
        print("[INFO] Pynput failed, trying evdev...")
        listener = EvdevListener(on_press, on_release)
        if listener.start():
            return listener

    print("[ERROR] No keyboard listener could be started!")
    print("[ERROR] Hotkeys will not work.")
    return None
