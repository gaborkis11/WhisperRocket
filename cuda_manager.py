#!/usr/bin/env python3
"""
WhisperRocket - CUDA Manager
Handles CUDA libraries download and installation for AppImage support
"""

import os
import json
import requests
import zipfile
import io
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass


@dataclass
class CudaDownloadState:
    """CUDA download state"""
    is_downloading: bool = False
    progress: float = 0.0  # 0.0 - 1.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # bytes/sec
    error: str = ""
    completed: bool = False
    current_package: str = ""


# CUDA packages to download
CUDA_PACKAGES = [
    "nvidia-cudnn-cu12",
    "nvidia-cublas-cu12",
]


def get_cuda_dir() -> Path:
    """Returns CUDA libraries directory: ~/.local/share/whisperrocket/cuda_libs/"""
    return Path.home() / ".local" / "share" / "whisperrocket" / "cuda_libs"


def get_cuda_state_file() -> Path:
    """Returns CUDA state file: ~/.config/whisperrocket/cuda_state.json"""
    config_dir = Path.home() / ".config" / "whisperrocket"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "cuda_state.json"


def is_cuda_installed() -> bool:
    """
    Check if CUDA libraries are installed.
    First checks Python imports (venv/pip install), then cuda_libs directory (AppImage).
    """
    # Method 1: Check if CUDA is available via Python import (source installation)
    # This handles the case where CUDA was installed via pip in a venv
    try:
        import nvidia.cudnn
        import nvidia.cublas
        # If imports succeed, CUDA is available via Python
        return True
    except ImportError:
        pass

    # Method 2: Check cuda_libs directory (AppImage installation)
    state_file = get_cuda_state_file()
    cuda_dir = get_cuda_dir()

    # Check state file
    try:
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                if not state.get("installed", False):
                    return False
        else:
            return False
    except:
        return False

    # Verify directories exist
    if not cuda_dir.exists():
        return False

    # Check if at least one package directory exists with lib folder
    has_libs = False
    for package_name in CUDA_PACKAGES:
        package_dir = cuda_dir / package_name
        # Check nested structure (nvidia-cudnn-cu12/cudnn/lib/)
        for subdir in package_dir.iterdir() if package_dir.exists() else []:
            if subdir.is_dir():
                lib_dir = subdir / "lib"
                if lib_dir.exists() and any(lib_dir.iterdir()):
                    has_libs = True
                    break
        if has_libs:
            break

    return has_libs


def setup_ld_library_path():
    """
    Setup LD_LIBRARY_PATH environment variable for CUDA libraries.
    Must be called BEFORE importing faster_whisper or WhisperModel.
    Handles both venv (source install) and cuda_libs (AppImage) cases.
    """
    lib_paths = []

    # Method 1: Try to get paths from Python packages (venv/source install)
    try:
        import nvidia.cudnn
        import nvidia.cublas
        cudnn_lib = Path(nvidia.cudnn.__path__[0]) / "lib"
        cublas_lib = Path(nvidia.cublas.__path__[0]) / "lib"
        if cudnn_lib.exists():
            lib_paths.append(str(cudnn_lib))
        if cublas_lib.exists():
            lib_paths.append(str(cublas_lib))
    except ImportError:
        pass

    # Method 2: Check cuda_libs directory (AppImage)
    if not lib_paths:
        cuda_dir = get_cuda_dir()
        if cuda_dir.exists():
            # Find all lib directories recursively (structure: package/subdir/lib/)
            # e.g., nvidia-cudnn-cu12/cudnn/lib/, nvidia-cublas-cu12/cublas/lib/
            for package_dir in cuda_dir.iterdir():
                if package_dir.is_dir():
                    # Search for lib directories recursively (up to 2 levels deep)
                    for subdir in package_dir.iterdir():
                        if subdir.is_dir():
                            lib_dir = subdir / "lib"
                            if lib_dir.exists():
                                lib_paths.append(str(lib_dir))
                    # Also check direct lib directory (fallback)
                    direct_lib = package_dir / "lib"
                    if direct_lib.exists():
                        lib_paths.append(str(direct_lib))

    if lib_paths:
        current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        new_paths = ":".join(lib_paths)
        if current_ld_path:
            os.environ["LD_LIBRARY_PATH"] = f"{new_paths}:{current_ld_path}"
        else:
            os.environ["LD_LIBRARY_PATH"] = new_paths
        print(f"[INFO] CUDA LD_LIBRARY_PATH set: {new_paths}")


def get_cuda_wheel_info() -> List[Dict]:
    """
    Get CUDA wheel URLs and sizes from PyPI.
    Returns list of dicts with: name, url, size
    """
    wheels = []

    for package_name in CUDA_PACKAGES:
        try:
            # Get package metadata from PyPI JSON API
            response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=10)
            response.raise_for_status()
            data = response.json()

            # Get latest version
            version = data["info"]["version"]
            releases = data["releases"][version]

            # Find manylinux x86_64 wheel
            for release in releases:
                filename = release["filename"]
                if "manylinux" in filename and "x86_64" in filename and filename.endswith(".whl"):
                    wheels.append({
                        "name": package_name,
                        "url": release["url"],
                        "size": release["size"],
                        "filename": filename,
                    })
                    break
        except Exception as e:
            print(f"[ERROR] Failed to get wheel info for {package_name}: {e}")

    return wheels


def download_cuda_wheels(progress_callback: Optional[Callable] = None) -> bool:
    """
    Download and extract CUDA wheels.

    Args:
        progress_callback: Optional callback(CudaDownloadState) for progress updates

    Returns:
        True if successful, False otherwise
    """
    state = CudaDownloadState()
    cuda_dir = get_cuda_dir()

    try:
        # Create CUDA directory
        cuda_dir.mkdir(parents=True, exist_ok=True)

        # Get wheel info
        wheels = get_cuda_wheel_info()
        if not wheels:
            state.error = "No wheels found"
            if progress_callback:
                progress_callback(state)
            return False

        # Calculate total size
        state.total_bytes = sum(w["size"] for w in wheels)
        state.is_downloading = True

        if progress_callback:
            progress_callback(state)

        # Download and extract each wheel
        downloaded_bytes = 0
        import time
        last_update_time = time.time()
        last_bytes = 0

        for wheel_info in wheels:
            package_name = wheel_info["name"]
            url = wheel_info["url"]
            size = wheel_info["size"]

            state.current_package = package_name

            # Download with streaming
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # Read wheel content into memory
            wheel_data = io.BytesIO()
            chunk_size = 64 * 1024  # 64KB chunks

            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    wheel_data.write(chunk)
                    downloaded_bytes += len(chunk)

                    # Update progress
                    current_time = time.time()
                    time_diff = current_time - last_update_time

                    if time_diff > 0.1:  # Update every 100ms
                        bytes_diff = downloaded_bytes - last_bytes
                        state.speed = bytes_diff / time_diff
                        last_bytes = downloaded_bytes
                        last_update_time = current_time

                    state.downloaded_bytes = downloaded_bytes
                    state.progress = min(downloaded_bytes / state.total_bytes, 0.99)

                    if progress_callback:
                        progress_callback(state)

            # Extract wheel (only nvidia package directories)
            wheel_data.seek(0)
            package_dir = cuda_dir / package_name
            package_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(wheel_data) as zf:
                for member in zf.namelist():
                    # Extract only nvidia/* files (lib, bin, include)
                    if member.startswith("nvidia/"):
                        # Remove "nvidia/" prefix
                        target_path = package_dir / member.replace("nvidia/", "", 1)
                        target_path.parent.mkdir(parents=True, exist_ok=True)

                        if not member.endswith("/"):
                            with zf.open(member) as source:
                                with open(target_path, 'wb') as target:
                                    target.write(source.read())

        # Mark as complete
        state.progress = 1.0
        state.completed = True
        state.is_downloading = False

        # Save state
        state_file = get_cuda_state_file()
        with open(state_file, 'w') as f:
            json.dump({
                "installed": True,
                "packages": CUDA_PACKAGES,
            }, f)

        if progress_callback:
            progress_callback(state)

        return True

    except Exception as e:
        state.error = str(e)
        state.is_downloading = False
        if progress_callback:
            progress_callback(state)
        return False


def format_size(bytes_val: int) -> str:
    """Format byte size to human readable string"""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def format_speed(speed: float) -> str:
    """Format speed to human readable string"""
    if speed < 1024:
        return f"{speed:.0f} B/s"
    elif speed < 1024 * 1024:
        return f"{speed / 1024:.1f} KB/s"
    else:
        return f"{speed / (1024 * 1024):.1f} MB/s"


def format_eta(downloaded: int, total: int, speed: float) -> str:
    """Format ETA to human readable string"""
    if speed <= 0 or total <= 0:
        return "calculating..."

    remaining_bytes = total - downloaded
    eta_seconds = remaining_bytes / speed

    if eta_seconds < 60:
        return f"~{int(eta_seconds)}s"
    elif eta_seconds < 3600:
        return f"~{int(eta_seconds / 60)}m"
    else:
        return f"~{eta_seconds / 3600:.1f}h"


# Testing
if __name__ == "__main__":
    print("=== CUDA Manager Test ===\n")

    print(f"CUDA directory: {get_cuda_dir()}")
    print(f"State file: {get_cuda_state_file()}")
    print(f"Is CUDA installed: {is_cuda_installed()}")

    print("\nGetting wheel info...")
    wheels = get_cuda_wheel_info()
    for w in wheels:
        print(f"  {w['name']}: {format_size(w['size'])}")
        print(f"    {w['url']}")

    print("\nTest complete!")
