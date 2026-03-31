#!/usr/bin/env python3
"""
WhisperRocket - Download Manager
Handles Whisper model downloads with real-time byte-level progress tracking
using HTTP streaming instead of huggingface_hub's snapshot_download
"""
import os
import json
import time
import threading
import requests
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict

from platform_support import get_platform_handler

# Platform handler
platform_handler = get_platform_handler()

# State file path
STATE_FILE = os.path.join(os.path.dirname(__file__), '.download_state.json')

# Local models directory (simpler than HuggingFace cache structure)
MODELS_DIR = os.path.join(str(platform_handler.get_cache_dir()), 'whisperrocket_models')

# Model sizes (fallback estimates if metadata fails)
MODEL_SIZES = {
    "tiny": 150 * 1024 * 1024,       # ~150 MB cache
    "base": 290 * 1024 * 1024,       # ~290 MB cache
    "small": 490 * 1024 * 1024,      # ~490 MB cache
    "medium": 1550 * 1024 * 1024,    # ~1.5 GB cache
    "large-v3-turbo": 1600 * 1024 * 1024,  # ~1.6 GB cache
    "large-v3": 6200 * 1024 * 1024,  # ~6 GB cache
    "large-v3-hu": 3100 * 1024 * 1024,  # ~3 GB (CT2 float16 after conversion)
}


@dataclass
class DownloadState:
    """Download state"""
    model_name: str = ""
    device: str = ""  # "mlx", "cuda", "cpu"
    is_downloading: bool = False
    progress: float = 0.0  # 0.0 - 1.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # bytes/sec
    error: str = ""
    cancelled: bool = False
    completed: bool = False
    status_message: str = ""  # Optional override for UI progress text (translation key)


def _needs_conversion(model_name: str) -> bool:
    """Check if a model needs conversion from Transformers to CT2 format"""
    from model_manager import MODEL_INFO
    return MODEL_INFO.get(model_name, {}).get("needs_conversion", False)


def get_repo_id(model_name: str, device: str) -> str:
    """Returns the HuggingFace repo ID based on device"""
    if device == "mlx":
        return f"mlx-community/whisper-{model_name}-mlx"
    # Check for custom source repo (e.g. non-Systran models that need conversion)
    from model_manager import MODEL_INFO
    source_repo = MODEL_INFO.get(model_name, {}).get("source_repo")
    if source_repo:
        return source_repo
    return f"Systran/faster-whisper-{model_name}"


def get_local_model_dir(model_name: str, device: str) -> str:
    """Returns the local directory path for a model"""
    if device == "mlx":
        return os.path.join(MODELS_DIR, f"whisper-{model_name}-mlx")
    else:
        return os.path.join(MODELS_DIR, f"faster-whisper-{model_name}")


def get_file_list_with_sizes(repo_id: str) -> List[Dict]:
    """Get list of files with their sizes from HuggingFace repo"""
    from huggingface_hub import list_repo_files, get_hf_file_metadata, hf_hub_url

    files = list_repo_files(repo_id)
    file_info = []

    for filename in files:
        url = hf_hub_url(repo_id, filename)
        meta = get_hf_file_metadata(url)
        file_info.append({
            'name': filename,
            'url': url,
            'size': meta.size
        })

    return file_info


def is_model_downloaded_local(model_name: str, device: str) -> bool:
    """Check if model is downloaded in local directory"""
    model_dir = get_local_model_dir(model_name, device)
    if not os.path.exists(model_dir):
        return False

    # Check for essential files
    required_files = ['model.bin', 'config.json']
    for f in required_files:
        if not os.path.exists(os.path.join(model_dir, f)):
            return False

    return True


# Legacy function for backwards compatibility
def get_cache_subdir(model_name: str, device: str) -> str:
    """Returns the cache subdirectory name (legacy HF cache)"""
    if device == "mlx":
        return f"models--mlx-community--whisper-{model_name}-mlx"
    else:
        return f"models--Systran--faster-whisper-{model_name}"


class DownloadManager:
    """Download manager singleton"""

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

        # Load state (if there's a download in progress)
        self._load_state()

    def _load_state(self):
        """Load state from file"""
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

                    # If crashed during download, reset
                    if self.state.is_downloading and not self._download_thread:
                        self.state.is_downloading = False
                        self._clear_state()
                    # If old error remains, clear it
                    elif self.state.error and not self.state.is_downloading:
                        self._clear_state()
        except:
            pass

    def _save_state(self):
        """Save state to file"""
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
        """Clear state"""
        self.state = DownloadState()
        if os.path.exists(STATE_FILE):
            try:
                os.remove(STATE_FILE)
            except:
                pass

    def set_progress_callback(self, callback: Optional[Callable]):
        """Set progress callback (for UI updates)"""
        self._progress_callback = callback

    def _update_progress(self, downloaded: int, total: int):
        """Update progress"""
        current_time = time.time()

        # Speed calculation
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

    def _get_cache_size(self, model_name: str, device: str = None) -> int:
        """Get cache directory size (including .incomplete files)"""
        import os
        cache_dir = str(platform_handler.get_cache_dir())
        subdir = get_cache_subdir(model_name, device or self.state.device)
        cache_path = os.path.join(cache_dir, subdir)
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

    def _download_and_convert_worker(self, model_name: str, device: str = "cpu"):
        """Download a Transformers model and convert it to CTranslate2 format"""
        import shutil
        import tempfile

        try:
            self.state.model_name = model_name
            self.state.device = device
            self.state.is_downloading = True
            self.state.progress = 0.0
            self.state.error = ""
            self.state.cancelled = False
            self.state.completed = False
            self.state.downloaded_bytes = 0
            self._last_update_time = time.time()
            self._last_bytes = 0
            self._save_state()

            # Step 1: Check conversion dependencies
            try:
                import torch
                import transformers
            except ImportError:
                self.state.error = "download_install_deps"
                self.state.is_downloading = False
                self._save_state()
                if self._progress_callback:
                    self._progress_callback(self.state)
                return

            if self._cancel_flag:
                self.state.cancelled = True
                self.state.is_downloading = False
                self._save_state()
                return

            repo_id = get_repo_id(model_name, device)
            model_dir = get_local_model_dir(model_name, device)
            os.makedirs(model_dir, exist_ok=True)

            # Step 2: Download the Transformers model with HTTP streaming (0-80%)
            tmp_dir = tempfile.mkdtemp(prefix="whisperrocket_convert_")

            try:
                print(f"[INFO] Downloading {repo_id} for conversion...")

                # Get file list with sizes (same as _download_worker)
                try:
                    file_list = get_file_list_with_sizes(repo_id)
                    self.state.total_bytes = sum(f['size'] for f in file_list)
                except Exception as e:
                    # Fallback to estimated size and snapshot_download
                    print(f"[WARNING] File list failed ({e}), using snapshot_download fallback")
                    self.state.total_bytes = MODEL_SIZES.get(model_name, 3000 * 1024 * 1024)
                    self.state.status_message = "download_starting"
                    self._save_state()
                    if self._progress_callback:
                        self._progress_callback(self.state)
                    from huggingface_hub import snapshot_download
                    snapshot_download(repo_id=repo_id, local_dir=tmp_dir)
                    file_list = None  # Skip streaming loop

                self.state.status_message = ""
                self._save_state()

                # Download each file with streaming progress
                if file_list is not None:
                    total_downloaded = 0
                    chunk_size = 64 * 1024  # 64KB

                    for file_info in file_list:
                        if self._cancel_flag:
                            self.state.cancelled = True
                            self.state.is_downloading = False
                            self._save_state()
                            return

                        filename = file_info['name']
                        url = file_info['url']
                        file_size = file_info['size']

                        # Create subdirectories if needed
                        target_path = os.path.join(tmp_dir, filename)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)

                        # Skip if already exists with correct size
                        if os.path.exists(target_path):
                            existing_size = os.path.getsize(target_path)
                            if existing_size == file_size:
                                total_downloaded += file_size
                                self.state.downloaded_bytes = total_downloaded
                                self.state.progress = min(total_downloaded / self.state.total_bytes * 0.80, 0.80)
                                self._save_state()
                                continue

                        try:
                            response = requests.get(url, stream=True, timeout=30)
                            response.raise_for_status()

                            with open(target_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=chunk_size):
                                    if self._cancel_flag:
                                        response.close()
                                        self.state.cancelled = True
                                        self.state.is_downloading = False
                                        self._save_state()
                                        return

                                    if chunk:
                                        f.write(chunk)
                                        total_downloaded += len(chunk)

                                        current_time = time.time()
                                        time_diff = current_time - self._last_update_time
                                        if time_diff > 0.1:
                                            bytes_diff = total_downloaded - self._last_bytes
                                            self.state.speed = bytes_diff / time_diff
                                            self._last_bytes = total_downloaded
                                            self._last_update_time = current_time

                                        self.state.downloaded_bytes = total_downloaded
                                        self.state.progress = min(
                                            total_downloaded / self.state.total_bytes * 0.80,
                                            0.80
                                        )
                                        self._save_state()

                        except requests.RequestException as e:
                            self.state.error = f"Download error: {str(e)[:100]}"
                            self.state.is_downloading = False
                            self._save_state()
                            return

                if self._cancel_flag:
                    self.state.cancelled = True
                    self.state.is_downloading = False
                    self._save_state()
                    return

                # Step 3: Convert to CTranslate2 format (80-95% progress)
                print(f"[INFO] Converting {model_name} to CTranslate2 format...")
                self.state.progress = 0.80
                self.state.status_message = "download_converting"
                self.state.speed = 0
                self._save_state()
                if self._progress_callback:
                    self._progress_callback(self.state)

                from ctranslate2.converters import TransformersConverter

                converter = TransformersConverter(
                    tmp_dir,
                    copy_files=["tokenizer.json", "preprocessor_config.json"],
                )

                converter.convert(
                    model_dir,
                    quantization="float16",
                    force=True,
                )

                # Update progress to 95%
                self.state.progress = 0.95
                self.state.status_message = "download_conversion_done"
                self._save_state()
                if self._progress_callback:
                    self._progress_callback(self.state)

                print(f"[INFO] Conversion complete: {model_dir}")

            finally:
                # Step 4: Clean up temporary source model (95-100%)
                if os.path.exists(tmp_dir):
                    try:
                        shutil.rmtree(tmp_dir)
                        print(f"[INFO] Cleaned up temporary files: {tmp_dir}")
                    except Exception as e:
                        print(f"[WARNING] Failed to clean up {tmp_dir}: {e}")

            # Done
            self.state.progress = 1.0
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

    def _download_worker(self, model_name: str, device: str = "cpu"):
        """Download worker thread - uses HTTP streaming for real-time byte-level progress"""
        try:
            self.state.model_name = model_name
            self.state.device = device
            self.state.is_downloading = True
            self.state.progress = 0.0
            self.state.error = ""
            self.state.cancelled = False
            self.state.completed = False
            self.state.downloaded_bytes = 0
            self._last_update_time = time.time()
            self._last_bytes = 0

            self._save_state()

            repo_id = get_repo_id(model_name, device)
            model_dir = get_local_model_dir(model_name, device)

            # Create model directory
            os.makedirs(model_dir, exist_ok=True)

            # Get file list with sizes from HuggingFace
            try:
                file_list = get_file_list_with_sizes(repo_id)
                self.state.total_bytes = sum(f['size'] for f in file_list)
            except Exception as e:
                # Fallback to estimated size
                self.state.total_bytes = MODEL_SIZES.get(model_name, 500 * 1024 * 1024)
                self.state.error = f"Warning: Using estimated size ({e})"
                # Try with snapshot_download as fallback
                self._download_fallback(model_name, device)
                return

            self._save_state()

            # Download each file with streaming
            total_downloaded = 0
            chunk_size = 64 * 1024  # 64KB chunks

            for file_info in file_list:
                if self._cancel_flag:
                    self.state.cancelled = True
                    self.state.error = "Download cancelled"
                    self._save_state()
                    return

                filename = file_info['name']
                url = file_info['url']
                file_size = file_info['size']

                target_path = os.path.join(model_dir, filename)

                # Skip if file already exists with correct size
                if os.path.exists(target_path):
                    existing_size = os.path.getsize(target_path)
                    if existing_size == file_size:
                        total_downloaded += file_size
                        self.state.downloaded_bytes = total_downloaded
                        self.state.progress = total_downloaded / self.state.total_bytes
                        self._save_state()
                        continue

                # Download with streaming
                try:
                    response = requests.get(url, stream=True, timeout=30)
                    response.raise_for_status()

                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if self._cancel_flag:
                                response.close()
                                self.state.cancelled = True
                                self.state.error = "Download cancelled"
                                self._save_state()
                                return

                            if chunk:
                                f.write(chunk)
                                total_downloaded += len(chunk)

                                # Update progress
                                current_time = time.time()
                                time_diff = current_time - self._last_update_time

                                if time_diff > 0.1:  # Update every 100ms
                                    bytes_diff = total_downloaded - self._last_bytes
                                    self.state.speed = bytes_diff / time_diff
                                    self._last_bytes = total_downloaded
                                    self._last_update_time = current_time

                                self.state.downloaded_bytes = total_downloaded
                                self.state.progress = min(
                                    total_downloaded / self.state.total_bytes,
                                    0.99
                                )
                                self._save_state()

                except requests.RequestException as e:
                    self.state.error = f"Download error: {str(e)[:100]}"
                    self.state.is_downloading = False
                    self._save_state()
                    return

            # Download complete
            if not self._cancel_flag:
                self.state.progress = 1.0
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

    def _download_fallback(self, model_name: str, device: str):
        """Fallback download using huggingface_hub (less accurate progress)"""
        from huggingface_hub import snapshot_download

        try:
            repo_id = get_repo_id(model_name, device)
            model_dir = get_local_model_dir(model_name, device)

            # Download using snapshot_download with local_dir
            snapshot_download(
                repo_id=repo_id,
                local_dir=model_dir,
                local_files_only=False
            )

            self.state.progress = 1.0
            self.state.completed = True
            self.state.is_downloading = False
            self._save_state()

            if self._progress_callback:
                self._progress_callback(self.state)

        except Exception as e:
            self.state.error = f"Fallback download failed: {str(e)[:100]}"
            self.state.is_downloading = False
            self._save_state()

    def start_download(self, model_name: str, device: str = "cpu") -> bool:
        """
        Start download
        Args:
            model_name: Model name (e.g. "large-v3")
            device: "mlx", "cuda", "cpu"
        Returns: True if successfully started
        """
        if self.state.is_downloading:
            return False

        self._cancel_flag = False
        self._last_update_time = 0
        self._last_downloaded_bytes = 0

        # Use conversion worker for models that need it
        if _needs_conversion(model_name):
            worker = self._download_and_convert_worker
        else:
            worker = self._download_worker

        self._download_thread = threading.Thread(
            target=worker,
            args=(model_name, device),
            daemon=True
        )
        self._download_thread.start()
        return True

    def cancel_download(self):
        """Cancel download"""
        self._cancel_flag = True
        self.state.cancelled = True
        self.state.is_downloading = False
        self._save_state()

    def is_downloading(self) -> bool:
        """Check if download is in progress"""
        return self.state.is_downloading

    def get_state(self) -> DownloadState:
        """Get current state"""
        return self.state

    def clear_completed(self):
        """Clear completed download state"""
        if not self.state.is_downloading:
            self._clear_state()

    def clear_error(self):
        """Clear error state"""
        if self.state.error or self.state.cancelled:
            self._clear_state()

    def format_speed(self) -> str:
        """Format speed"""
        speed = self.state.speed
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        else:
            return f"{speed / (1024 * 1024):.1f} MB/s"

    def format_eta(self) -> str:
        """Format estimated time"""
        if self.state.speed <= 0:
            return "calculating..."

        remaining_bytes = self.state.total_bytes - self.state.downloaded_bytes
        eta_seconds = remaining_bytes / self.state.speed

        if eta_seconds < 60:
            return f"~{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            return f"~{int(eta_seconds / 60)}m"
        else:
            return f"~{eta_seconds / 3600:.1f}h"

    def format_size(self, bytes_val: int) -> str:
        """Format size"""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


# Global instance
_download_manager: Optional[DownloadManager] = None


def get_download_manager() -> DownloadManager:
    """Get download manager singleton"""
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager()
    return _download_manager


# Testing
if __name__ == "__main__":
    print("=== Download Manager Test ===\n")

    dm = get_download_manager()
    print(f"Is downloading: {dm.is_downloading()}")
    print(f"State: {dm.get_state()}")
