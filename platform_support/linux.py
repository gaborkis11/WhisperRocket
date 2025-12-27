"""
WhisperRocket - Linux Platform Handler
Linux-specifikus műveletek implementációja
"""

import os
import shutil
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional

from .base import PlatformHandler


class LinuxHandler(PlatformHandler):
    """Linux platform handler"""

    # Terminál alkalmazások listája (Ctrl+Shift+V használnak)
    TERMINAL_APPS = [
        'terminal', 'terminator', 'konsole', 'xterm', 'urxvt', 'alacritty',
        'kitty', 'tilix', 'guake', 'yakuake', 'gnome-terminal', 'xfce4-terminal',
        'cursor', 'code', 'vscode', 'vscodium'
    ]

    def get_config_dir(self) -> Path:
        """Config mappa: ~/.config/whisperrocket/"""
        return Path.home() / ".config" / "whisperrocket"

    def get_cache_dir(self) -> Path:
        """Cache mappa: ~/.cache/huggingface/hub/"""
        return Path.home() / ".cache" / "huggingface" / "hub"

    def paste_text(self, is_terminal: bool = False) -> None:
        """Szöveg beillesztése xdotool-lal

        Args:
            is_terminal: True ha terminál/IDE ablakba kell beilleszteni (Ctrl+Shift+V)
        """
        paste_key = "ctrl+shift+v" if is_terminal else "ctrl+v"
        try:
            subprocess.run(['xdotool', 'key', paste_key], check=True)
        except Exception as e:
            print(f"[FIGYELEM] Beillesztés sikertelen: {e}")

    def play_sound(self, path: str) -> None:
        """Hang lejátszása paplay-jel (háttérszálban)

        Args:
            path: Hangfájl útvonala
        """
        def _play():
            try:
                if os.path.exists(path):
                    # HDMI audio "felébresztése" - csendes ping + várakozás
                    subprocess.run(['paplay', '--volume=1', path],
                                   capture_output=True, timeout=2)
                    time.sleep(0.15)
                    # Tényleges lejátszás
                    subprocess.run(['paplay', '--volume=65536', path],
                                   capture_output=True, timeout=2)
            except Exception as e:
                print(f"[FIGYELEM] Hang lejátszás sikertelen: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def get_active_window_class(self) -> str:
        """Aktív ablak class nevének lekérdezése xdotool-lal"""
        try:
            # Ablak neve
            window_name = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True
            ).stdout.strip().lower()

            # Ablak class
            window_class = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowclassname'],
                capture_output=True, text=True
            ).stdout.strip().lower()

            return f"{window_name}|{window_class}"
        except Exception as e:
            print(f"[DEBUG] Ablak detektálás sikertelen: {e}")
            return ""

    def is_terminal_window(self, window_class: str) -> bool:
        """Ellenőrzi, hogy az ablak terminál vagy IDE-e (Ctrl+Shift+V használók)

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
        """Autostart be/kikapcsolása .desktop fájllal

        Args:
            enable: True = bekapcsolás, False = kikapcsolás
            app_path: Nem használt (kompatibilitás miatt marad)

        Returns:
            True ha sikeres
        """
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_file = autostart_dir / "whisperrocket.desktop"

        try:
            if enable:
                autostart_dir.mkdir(parents=True, exist_ok=True)

                # Dinamikusan generáljuk a .desktop fájlt a megfelelő útvonalakkal
                # A projekt mappa meghatározása (ez a fájl a platform_support/ mappában van)
                project_dir = Path(__file__).parent.parent.resolve()
                start_script = project_dir / "start.sh"
                icon_path = project_dir / "assets" / "icons" / "whisperrocket_ico.png"

                desktop_content = f"""[Desktop Entry]
Type=Application
Name=WhisperRocket
Comment=Local Speech-to-Text with Whisper AI
Exec={start_script}
Icon={icon_path}
Terminal=false
Categories=AudioVideo;Audio;Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
                autostart_file.write_text(desktop_content)
                return True
            else:
                if autostart_file.exists():
                    autostart_file.unlink()
                return True
        except Exception as e:
            print(f"[HIBA] Autostart beállítás sikertelen: {e}")
            return False

    def is_autostart_enabled(self) -> bool:
        """Ellenőrzi, hogy az autostart be van-e kapcsolva"""
        autostart_file = Path.home() / ".config" / "autostart" / "whisperrocket.desktop"
        return autostart_file.exists()

    def check_permissions(self) -> dict:
        """Linux-on nincsenek speciális engedélyek szükségesek"""
        return {
            "microphone": True,
            "accessibility": True
        }

    def request_permissions(self) -> None:
        """Linux-on nem szükséges engedélykérés"""
        pass

    def has_gpu_support(self) -> bool:
        """NVIDIA GPU elérhetőség ellenőrzése"""
        return self.get_gpu_type() == "cuda"

    def get_gpu_type(self) -> str:
        """GPU típus detektálása (CUDA vagy CPU)"""
        try:
            result = subprocess.run(['nvidia-smi'],
                                    capture_output=True, timeout=5)
            if result.returncode == 0:
                return "cuda"
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
            start_script: Indító script útvonala (pl. "start.sh")
        """
        try:
            subprocess.Popen(['bash', start_script],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[HIBA] Újraindítás sikertelen: {e}")

    def warmup_audio(self, sound_file: str) -> None:
        """Audio rendszer "felébresztése" (HDMI/USB audio késleltetés elkerülése)

        Args:
            sound_file: Hangfájl útvonala a warmup-hoz
        """
        try:
            subprocess.run(['paplay', '--volume=1', sound_file],
                           capture_output=True, timeout=2)
        except:
            pass
