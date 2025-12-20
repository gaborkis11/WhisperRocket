#!/usr/bin/env python3
"""
WhisperTalk - Download Manager
Whisper modellek letöltésének kezelése progress követéssel
"""
import os
import json
import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable

# Állapot fájl útvonal
STATE_FILE = os.path.join(os.path.dirname(__file__), '.download_state.json')

# Modell méretek (valós cache méretek, bájtokban)
MODEL_SIZES = {
    "tiny": 150 * 1024 * 1024,       # ~150 MB cache
    "base": 290 * 1024 * 1024,       # ~290 MB cache
    "small": 490 * 1024 * 1024,      # ~490 MB cache
    "medium": 1550 * 1024 * 1024,    # ~1.5 GB cache
    "large-v3-turbo": 1600 * 1024 * 1024,  # ~1.6 GB cache
    "large-v3": 6200 * 1024 * 1024,  # ~6 GB cache
}


@dataclass
class DownloadState:
    """Letöltés állapot"""
    model_name: str = ""
    is_downloading: bool = False
    progress: float = 0.0  # 0.0 - 1.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # bytes/sec
    error: str = ""
    cancelled: bool = False
    completed: bool = False


class DownloadManager:
    """Letöltés kezelő singleton"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.state = DownloadState()
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_flag = False
        self._progress_callback: Optional[Callable] = None
        self._last_update_time = 0
        self._last_downloaded_bytes = 0

        # Állapot betöltése (ha van folyamatban lévő letöltés)
        self._load_state()

    def _load_state(self):
        """Állapot betöltése fájlból"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.state.model_name = data.get("model_name", "")
                    self.state.is_downloading = data.get("is_downloading", False)
                    self.state.progress = data.get("progress", 0.0)
                    self.state.downloaded_bytes = data.get("downloaded_bytes", 0)
                    self.state.total_bytes = data.get("total_bytes", 0)
                    self.state.error = data.get("error", "")
                    self.state.completed = data.get("completed", False)

                    # Ha letöltés közben crashelt, reseteljük
                    if self.state.is_downloading and not self._download_thread:
                        self.state.is_downloading = False
                        self._clear_state()
                    # Ha régi hiba maradt, töröljük
                    elif self.state.error and not self.state.is_downloading:
                        self._clear_state()
        except:
            pass

    def _save_state(self):
        """Állapot mentése fájlba"""
        try:
            data = {
                "model_name": self.state.model_name,
                "is_downloading": self.state.is_downloading,
                "progress": self.state.progress,
                "downloaded_bytes": self.state.downloaded_bytes,
                "total_bytes": self.state.total_bytes,
                "error": self.state.error,
                "completed": self.state.completed,
            }
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f)
        except:
            pass

    def _clear_state(self):
        """Állapot törlése"""
        self.state = DownloadState()
        if os.path.exists(STATE_FILE):
            try:
                os.remove(STATE_FILE)
            except:
                pass

    def set_progress_callback(self, callback: Optional[Callable]):
        """Progress callback beállítása (UI frissítéshez)"""
        self._progress_callback = callback

    def _update_progress(self, downloaded: int, total: int):
        """Progress frissítése"""
        current_time = time.time()

        # Sebesség számítás
        if self._last_update_time > 0:
            time_diff = current_time - self._last_update_time
            if time_diff > 0:
                bytes_diff = downloaded - self._last_downloaded_bytes
                self.state.speed = bytes_diff / time_diff

        self._last_update_time = current_time
        self._last_downloaded_bytes = downloaded

        self.state.downloaded_bytes = downloaded
        self.state.total_bytes = total
        self.state.progress = downloaded / total if total > 0 else 0

        self._save_state()

        # Callback hívása
        if self._progress_callback:
            try:
                self._progress_callback(self.state)
            except:
                pass

    def _get_cache_size(self, model_name: str) -> int:
        """Cache mappa méretének lekérdezése (beleértve .incomplete fájlokat)"""
        import os
        cache_path = os.path.expanduser(f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{model_name}")
        if not os.path.exists(cache_path):
            return 0
        total = 0
        for dirpath, dirnames, filenames in os.walk(cache_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except:
                    pass
        return total

    def _download_worker(self, model_name: str):
        """Letöltés worker thread"""
        try:
            from huggingface_hub import snapshot_download

            self.state.model_name = model_name
            self.state.is_downloading = True
            self.state.progress = 0.0
            self.state.error = ""
            self.state.cancelled = False
            self.state.completed = False
            self.state.total_bytes = MODEL_SIZES.get(model_name, 1000 * 1024 * 1024)

            self._save_state()

            repo_id = f"Systran/faster-whisper-{model_name}"

            # Letöltés külön thread-ben
            download_error = None
            download_done = False

            def do_download():
                nonlocal download_error, download_done
                try:
                    snapshot_download(
                        repo_id=repo_id,
                        local_files_only=False,
                    )
                    download_done = True
                except Exception as e:
                    download_error = e

            # Indítsuk a letöltést háttérben
            download_thread = threading.Thread(target=do_download, daemon=True)
            download_thread.start()

            # Progress figyelés a cache méret alapján (beleértve .incomplete fájlokat)
            while download_thread.is_alive():
                if self._cancel_flag:
                    self.state.cancelled = True
                    self.state.error = "Letöltés megszakítva"
                    self._save_state()
                    return

                current_size = self._get_cache_size(model_name)
                self._update_progress(current_size, self.state.total_bytes)

                time.sleep(0.5)

            # Várjuk meg a thread befejezését
            download_thread.join(timeout=5)

            # Letöltés befejeződött
            if download_error:
                error_msg = str(download_error)
                if "CAS service error" in error_msg or "No such file" in error_msg:
                    self.state.error = "Letöltési hiba - próbáld újra"
                elif "Connection" in error_msg or "Timeout" in error_msg:
                    self.state.error = "Hálózati hiba - ellenőrizd az internetkapcsolatot"
                else:
                    self.state.error = f"Hiba: {error_msg[:100]}"
                self.state.is_downloading = False
                self._save_state()
                return

            if download_done and not self._cancel_flag:
                # Végső méret
                final_size = self._get_cache_size(model_name)
                self._update_progress(final_size, final_size)

                self.state.completed = True
                self.state.is_downloading = False
                self._save_state()

                if self._progress_callback:
                    self._progress_callback(self.state)

        except Exception as e:
            self.state.error = str(e)
            self.state.is_downloading = False
            self._save_state()

            if self._progress_callback:
                self._progress_callback(self.state)

        finally:
            self.state.is_downloading = False
            self._save_state()

    def start_download(self, model_name: str) -> bool:
        """
        Letöltés indítása
        Returns: True ha sikerült elindítani
        """
        if self.state.is_downloading:
            return False

        self._cancel_flag = False
        self._last_update_time = 0
        self._last_downloaded_bytes = 0

        self._download_thread = threading.Thread(
            target=self._download_worker,
            args=(model_name,),
            daemon=True
        )
        self._download_thread.start()
        return True

    def cancel_download(self):
        """Letöltés megszakítása"""
        self._cancel_flag = True
        self.state.cancelled = True
        self.state.is_downloading = False
        self._save_state()

    def is_downloading(self) -> bool:
        """Folyamatban van-e letöltés"""
        return self.state.is_downloading

    def get_state(self) -> DownloadState:
        """Aktuális állapot lekérdezése"""
        return self.state

    def clear_completed(self):
        """Befejezett letöltés állapot törlése"""
        if not self.state.is_downloading:
            self._clear_state()

    def clear_error(self):
        """Hiba állapot törlése"""
        if self.state.error or self.state.cancelled:
            self._clear_state()

    def format_speed(self) -> str:
        """Sebesség formázása"""
        speed = self.state.speed
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        else:
            return f"{speed / (1024 * 1024):.1f} MB/s"

    def format_eta(self) -> str:
        """Becsült idő formázása"""
        if self.state.speed <= 0:
            return "számítás..."

        remaining_bytes = self.state.total_bytes - self.state.downloaded_bytes
        eta_seconds = remaining_bytes / self.state.speed

        if eta_seconds < 60:
            return f"~{int(eta_seconds)} mp"
        elif eta_seconds < 3600:
            return f"~{int(eta_seconds / 60)} perc"
        else:
            return f"~{eta_seconds / 3600:.1f} óra"

    def format_size(self, bytes_val: int) -> str:
        """Méret formázása"""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


# Globális instance
_download_manager: Optional[DownloadManager] = None


def get_download_manager() -> DownloadManager:
    """Download manager singleton lekérése"""
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager()
    return _download_manager


# Tesztelés
if __name__ == "__main__":
    print("=== Download Manager Test ===\n")

    dm = get_download_manager()
    print(f"Is downloading: {dm.is_downloading()}")
    print(f"State: {dm.get_state()}")
