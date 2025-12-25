"""
WhisperRocket - macOS Platform Handler
macOS-specifikus műveletek implementációja (Apple Silicon fókusz)
"""

import os
import subprocess
import time
import threading
import plistlib
from pathlib import Path
from typing import Optional

from .base import PlatformHandler


class MacOSHandler(PlatformHandler):
    """macOS platform handler (Apple Silicon optimalizálva)"""

    # Terminál alkalmazások listája
    TERMINAL_APPS = [
        'terminal', 'iterm', 'iterm2', 'alacritty', 'kitty', 'warp',
        'hyper', 'cursor', 'code', 'vscode', 'vscodium'
    ]

    def get_config_dir(self) -> Path:
        """Config mappa: ~/Library/Application Support/WhisperRocket/"""
        return Path.home() / "Library" / "Application Support" / "WhisperRocket"

    def get_cache_dir(self) -> Path:
        """Cache mappa: ~/.cache/huggingface/hub/ (HuggingFace standard)"""
        # macOS-en is a ~/.cache-t használjuk a HuggingFace kompatibilitás miatt
        return Path.home() / ".cache" / "huggingface" / "hub"

    def paste_text(self, is_terminal: bool = False) -> None:
        """Szöveg beillesztése osascript-tel (Command+V)

        Args:
            is_terminal: macOS-en nem számít, mindig Command+V
        """
        try:
            subprocess.run([
                'osascript', '-e',
                'tell application "System Events" to keystroke "v" using command down'
            ], check=True)
        except Exception as e:
            print(f"[FIGYELEM] Beillesztés sikertelen: {e}")

    def play_sound(self, path: str) -> None:
        """Hang lejátszása afplay-jel (háttérszálban)

        Args:
            path: Hangfájl útvonala
        """
        def _play():
            try:
                if os.path.exists(path):
                    subprocess.run(['afplay', path], capture_output=True, timeout=5)
            except Exception as e:
                print(f"[FIGYELEM] Hang lejátszás sikertelen: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def get_active_window_class(self) -> str:
        """Aktív alkalmazás nevének lekérdezése AppleScript-tel"""
        try:
            result = subprocess.run([
                'osascript', '-e',
                'tell application "System Events" to get name of first process whose frontmost is true'
            ], capture_output=True, text=True)
            return result.stdout.strip().lower()
        except Exception as e:
            print(f"[DEBUG] Ablak detektálás sikertelen: {e}")
            return ""

    def is_terminal_window(self, window_class: str) -> bool:
        """Ellenőrzi, hogy az ablak terminál vagy IDE-e

        Args:
            window_class: get_active_window_class() visszatérési értéke

        Returns:
            True ha terminál/IDE ablak
        """
        window_info = window_class.lower()
        for app in self.TERMINAL_APPS:
            if app in window_info:
                return True
        return False

    def setup_autostart(self, enable: bool, app_path: Optional[str] = None) -> bool:
        """Autostart be/kikapcsolása LaunchAgent-tel

        Args:
            enable: True = bekapcsolás, False = kikapcsolás
            app_path: Nem használt macOS-en (a plist tartalmazza)

        Returns:
            True ha sikeres
        """
        launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        plist_path = launch_agents_dir / "com.whisperrocket.app.plist"

        try:
            if enable:
                launch_agents_dir.mkdir(parents=True, exist_ok=True)

                # plist tartalom létrehozása
                plist_content = {
                    'Label': 'com.whisperrocket.app',
                    'ProgramArguments': [
                        '/Applications/WhisperRocket.app/Contents/MacOS/WhisperRocket'
                    ],
                    'RunAtLoad': True,
                    'KeepAlive': False
                }

                with open(plist_path, 'wb') as f:
                    plistlib.dump(plist_content, f)

                return True
            else:
                if plist_path.exists():
                    plist_path.unlink()
                return True
        except Exception as e:
            print(f"[HIBA] Autostart beállítás sikertelen: {e}")
            return False

    def is_autostart_enabled(self) -> bool:
        """Ellenőrzi, hogy az autostart be van-e kapcsolva"""
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.whisperrocket.app.plist"
        return plist_path.exists()

    def check_permissions(self) -> dict:
        """macOS engedélyek ellenőrzése (Input Monitoring, Accessibility, Microphone)"""
        permissions = {
            "microphone": True,  # Feltételezzük, hogy megvan
            "accessibility": False,
            "input_monitoring": False  # pynput keyboard listener-hez
        }

        # Input Monitoring ellenőrzés (IOHIDCheckAccess)
        # Ez a fontos a hotkey működéséhez!
        try:
            import ctypes
            iokit = ctypes.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
            iokit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]
            iokit.IOHIDCheckAccess.restype = ctypes.c_int
            # 1 = kIOHIDRequestTypeListenEvent (Input Monitoring)
            result = iokit.IOHIDCheckAccess(1)
            permissions["input_monitoring"] = (result == 1)  # 1 = engedélyezve
        except Exception:
            # Ha nem sikerül, feltételezzük, hogy nincs
            permissions["input_monitoring"] = False

        # Accessibility ellenőrzés
        try:
            from ApplicationServices import AXIsProcessTrusted
            permissions["accessibility"] = AXIsProcessTrusted()
        except ImportError:
            # Ha nincs PyObjC, próbáljuk meg másképp
            try:
                # Tesztelünk egy egyszerű AppleScript parancsot
                result = subprocess.run([
                    'osascript', '-e',
                    'tell application "System Events" to get name of first process'
                ], capture_output=True, timeout=2)
                permissions["accessibility"] = result.returncode == 0
            except:
                permissions["accessibility"] = False

        # Microphone ellenőrzés (macOS kéri automatikusan)
        try:
            import AVFoundation
            status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                AVFoundation.AVMediaTypeAudio
            )
            permissions["microphone"] = status == 3  # AVAuthorizationStatusAuthorized
        except ImportError:
            # Ha nincs PyObjC, feltételezzük, hogy meg fogja kérni
            permissions["microphone"] = True

        return permissions

    def request_permissions(self) -> None:
        """Engedély kérés - System Preferences megnyitása"""
        permissions = self.check_permissions()

        if not permissions["input_monitoring"]:
            # Input Monitoring beállítások megnyitása (pynput keyboard listener-hez)
            # PyObjC-vel nyitjuk meg, ami megbízhatóbb bundled app-ból
            try:
                from AppKit import NSWorkspace
                from Foundation import NSURL
                url = NSURL.URLWithString_('x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent')
                NSWorkspace.sharedWorkspace().openURL_(url)
            except ImportError:
                # Fallback: subprocess
                subprocess.run([
                    'open',
                    'x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent'
                ])

        if not permissions["microphone"]:
            # Microphone engedély kérése (macOS automatikusan kérdez)
            try:
                import AVFoundation
                AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                    AVFoundation.AVMediaTypeAudio,
                    lambda granted: None
                )
            except ImportError:
                # Ha nincs PyObjC, megnyitjuk a beállításokat
                subprocess.run([
                    'open',
                    'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone'
                ])

    def has_gpu_support(self) -> bool:
        """Apple Silicon GPU (MLX) támogatás ellenőrzése"""
        return self.get_gpu_type() == "mlx"

    def get_gpu_type(self) -> str:
        """GPU típus detektálása (MLX ha Apple Silicon, különben CPU)"""
        try:
            import platform as py_platform
            if py_platform.machine() == 'arm64':
                # Apple Silicon - próbáljuk meg importálni az mlx-et
                try:
                    import mlx
                    return "mlx"
                except ImportError:
                    pass
        except:
            pass
        return "cpu"

    def kill_app(self, process_name: str) -> None:
        """Alkalmazás leállítása pkill-lel

        Args:
            process_name: Process neve (pl. "whisper_gui.py")
        """
        try:
            subprocess.run(['pkill', '-f', process_name], capture_output=True)
        except Exception as e:
            print(f"[HIBA] Process leállítás sikertelen: {e}")

    def restart_app(self, start_script: str) -> None:
        """Alkalmazás újraindítása

        Args:
            start_script: Indító script útvonala
        """
        try:
            # macOS-en is a bash scriptet használjuk (ha létezik)
            if os.path.exists(start_script):
                subprocess.Popen(['bash', start_script],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            else:
                # Ha nincs script, közvetlenül indítjuk
                script_dir = os.path.dirname(start_script)
                gui_script = os.path.join(script_dir, 'whisper_gui.py')
                if os.path.exists(gui_script):
                    subprocess.Popen(['python3', gui_script],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[HIBA] Újraindítás sikertelen: {e}")
