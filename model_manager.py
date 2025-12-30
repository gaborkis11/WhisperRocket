#!/usr/bin/env python3
"""
WhisperRocket - Modell Manager
Whisper modellek cache kezelése (lista, méret, törlés)
Supports both local directory (new) and HuggingFace cache (legacy)
"""
import os
import shutil
import json

from platform_support import get_platform_handler

# Platform handler és cache útvonal
platform_handler = get_platform_handler()
HF_CACHE_DIR = str(platform_handler.get_cache_dir())

# Local models directory (new, simpler structure)
LOCAL_MODELS_DIR = os.path.join(HF_CACHE_DIR, 'whisperrocket_models')

# Modell prefixek backend-enként (legacy HF cache)
MODEL_PREFIX_FASTER_WHISPER = "models--Systran--faster-whisper-"
MODEL_PREFIX_MLX = "models--mlx-community--whisper-"
MODEL_SUFFIX_MLX = "-mlx"

# Legacy alias
MODEL_PREFIX = MODEL_PREFIX_FASTER_WHISPER

# Támogatott modellek és méreteik (becsült, letöltés előtti info)
MODEL_INFO = {
    "tiny": {"name": "Tiny", "size_estimate": "39 MB"},
    "base": {"name": "Base", "size_estimate": "74 MB"},
    "small": {"name": "Small", "size_estimate": "244 MB"},
    "medium": {"name": "Medium", "size_estimate": "769 MB"},
    "large-v3-turbo": {"name": "Large-v3-turbo", "size_estimate": "1.6 GB"},
    "large-v3": {"name": "Large-v3", "size_estimate": "3 GB"},
}


def get_local_model_path(model_name, device=None):
    """Returns the local model directory path (new structure)

    Args:
        model_name: Model name (e.g. "large-v3")
        device: "mlx", "cuda", "cpu" or None
    """
    if device == "mlx":
        return os.path.join(LOCAL_MODELS_DIR, f"whisper-{model_name}-mlx")
    else:
        return os.path.join(LOCAL_MODELS_DIR, f"faster-whisper-{model_name}")


def get_cache_path(model_name, device=None):
    """Visszaadja a modell cache útvonalát (legacy HF cache)

    Args:
        model_name: Modell neve (pl. "large-v3")
        device: "mlx", "cuda", "cpu" vagy None (faster-whisper default)
    """
    if device == "mlx":
        return os.path.join(HF_CACHE_DIR, f"{MODEL_PREFIX_MLX}{model_name}{MODEL_SUFFIX_MLX}")
    else:
        return os.path.join(HF_CACHE_DIR, f"{MODEL_PREFIX_FASTER_WHISPER}{model_name}")


def get_directory_size(path):
    """Könyvtár méretének kiszámítása bájtokban"""
    total_size = 0
    if os.path.exists(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    return total_size


def format_size(size_bytes):
    """Bájt méret formázása olvasható formátumra"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_downloaded_models(device=None):
    """
    Visszaadja a letöltött modellek listáját

    Args:
        device: "mlx", "cuda", "cpu" vagy None (aktuális device a configból)

    Returns: [{"name": "large-v3", "size": 3045678901, "size_formatted": "2.84 GB", "path": "/...", "backend": "mlx"}]
    """
    models = []
    found_models = set()  # Track already found models to avoid duplicates

    if not os.path.exists(HF_CACHE_DIR):
        return models

    # Ha nincs megadva device, használjuk a config-ból
    if device is None:
        device = get_current_device()

    # Backend és prefix beállítása
    if device == "mlx":
        local_prefix = "whisper-"
        local_suffix = "-mlx"
        legacy_prefix = MODEL_PREFIX_MLX
        legacy_suffix = MODEL_SUFFIX_MLX
        backend = "mlx"
    else:
        local_prefix = "faster-whisper-"
        local_suffix = ""
        legacy_prefix = MODEL_PREFIX_FASTER_WHISPER
        legacy_suffix = ""
        backend = "faster-whisper"

    # 1. Először ellenőrizzük a LOCAL_MODELS_DIR mappát (új struktúra)
    if os.path.exists(LOCAL_MODELS_DIR) and os.path.isdir(LOCAL_MODELS_DIR):
        for dirname in os.listdir(LOCAL_MODELS_DIR):
            if dirname.startswith(local_prefix):
                # Modell név kinyerése
                model_name = dirname.replace(local_prefix, "")
                if local_suffix and model_name.endswith(local_suffix):
                    model_name = model_name[:-len(local_suffix)]

                model_path = os.path.join(LOCAL_MODELS_DIR, dirname)

                if os.path.isdir(model_path) and is_model_downloaded_local(model_name, device):
                    size = get_directory_size(model_path)
                    models.append({
                        "name": model_name,
                        "display_name": MODEL_INFO.get(model_name, {}).get("name", model_name),
                        "size": size,
                        "size_formatted": format_size(size),
                        "path": model_path,
                        "backend": backend
                    })
                    found_models.add(model_name)

    # 2. Utána ellenőrizzük a legacy HF cache-t
    for dirname in os.listdir(HF_CACHE_DIR):
        if dirname.startswith(legacy_prefix):
            # Modell név kinyerése
            model_name = dirname.replace(legacy_prefix, "")
            if legacy_suffix and model_name.endswith(legacy_suffix):
                model_name = model_name[:-len(legacy_suffix)]

            # Skip if already found in local directory
            if model_name in found_models:
                continue

            model_path = os.path.join(HF_CACHE_DIR, dirname)

            if os.path.isdir(model_path):
                # Ellenőrizzük, hogy nincs-e .incomplete fájl (részleges letöltés)
                blobs_dir = os.path.join(model_path, "blobs")
                has_incomplete = False
                if os.path.exists(blobs_dir) and os.path.isdir(blobs_dir):
                    for f in os.listdir(blobs_dir):
                        if f.endswith('.incomplete'):
                            has_incomplete = True
                            break

                # Csak teljes letöltéseket listázzuk
                if has_incomplete:
                    continue

                size = get_directory_size(model_path)
                models.append({
                    "name": model_name,
                    "display_name": MODEL_INFO.get(model_name, {}).get("name", model_name),
                    "size": size,
                    "size_formatted": format_size(size),
                    "path": model_path,
                    "backend": backend
                })

    # Méret szerint rendezés (legnagyobb elöl)
    models.sort(key=lambda x: x["size"], reverse=True)
    return models


def get_active_model():
    """Visszaadja az aktív (konfigurált) modell nevét"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("model", "large-v3")
    except:
        return "large-v3"


def is_model_downloaded_local(model_name, device=None):
    """Check if model is downloaded in local directory (new structure)"""
    local_path = get_local_model_path(model_name, device)

    if not os.path.exists(local_path) or not os.path.isdir(local_path):
        return False

    # Check for essential files
    required_files = ['model.bin', 'config.json']
    for f in required_files:
        if not os.path.exists(os.path.join(local_path, f)):
            return False

    return True


def is_model_downloaded(model_name, device=None):
    """Ellenőrzi, hogy a modell TELJESEN le van-e töltve

    Args:
        model_name: Modell neve (pl. "large-v3")
        device: "mlx", "cuda", "cpu" vagy None (faster-whisper default)

    Checks both local directory (new) and HuggingFace cache (legacy)
    """
    # First check local directory (new download location)
    if is_model_downloaded_local(model_name, device):
        return True

    # Fall back to legacy HuggingFace cache
    model_path = get_cache_path(model_name, device)

    if not os.path.exists(model_path) or not os.path.isdir(model_path):
        return False

    # FONTOS: Ha van .incomplete fájl a blobs-ban, a letöltés nem teljes!
    blobs_dir = os.path.join(model_path, "blobs")
    if os.path.exists(blobs_dir) and os.path.isdir(blobs_dir):
        for f in os.listdir(blobs_dir):
            if f.endswith('.incomplete'):
                return False

    # A refs/main fájl létezése jelzi a sikeres letöltést
    refs_main = os.path.join(model_path, "refs", "main")
    if os.path.exists(refs_main):
        return True

    # Fallback: snapshots könyvtár létezik és nem üres
    snapshots_dir = os.path.join(model_path, "snapshots")
    if os.path.exists(snapshots_dir) and os.path.isdir(snapshots_dir):
        snapshots = os.listdir(snapshots_dir)
        if snapshots:
            # Ellenőrizzük, hogy van-e fájl a snapshot-ban (nem csak .incomplete)
            snapshot_path = os.path.join(snapshots_dir, snapshots[0])
            if os.path.isdir(snapshot_path):
                files = [f for f in os.listdir(snapshot_path) if not f.endswith('.incomplete')]
                return len(files) > 0

    return False


def get_model_path_for_loading(model_name, device=None):
    """Returns the path to use for loading the model

    Checks local directory first, then falls back to model name for HF cache.
    Returns the local path if model is there, otherwise returns the model name
    (which will trigger HuggingFace cache loading).
    """
    # First check local directory
    local_path = get_local_model_path(model_name, device)
    if is_model_downloaded_local(model_name, device):
        return local_path

    # Fall back to model name (will use HF cache or download)
    return model_name


def has_any_model_downloaded(device=None):
    """Ellenőrzi, hogy van-e BÁRMILYEN letöltött modell

    Args:
        device: "mlx", "cuda", "cpu" vagy None

    Returns:
        (bool, str or None): (van-e modell, első talált modell neve)
    """
    for model_name in MODEL_INFO.keys():
        if is_model_downloaded(model_name, device):
            return True, model_name
    return False, None


def get_current_device():
    """Visszaadja a ténylegesen használt device-t (platform-alapú)"""
    # Platform detekció - macOS Apple Silicon mindig MLX
    gpu_type = platform_handler.get_gpu_type()
    if gpu_type == "mlx":
        return "mlx"
    elif gpu_type == "cuda":
        return "cuda"

    # Egyéb esetben config-ból
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get("device", "cpu")
    except:
        return "cpu"


def delete_model(model_name, device=None):
    """
    Modell törlése a cache-ből

    Args:
        model_name: Modell neve (pl. "large-v3")
        device: "mlx", "cuda", "cpu" vagy None (aktuális device a configból)

    Returns: (success: bool, message: str)
    """
    # Ha nincs megadva device, használjuk a config-ból
    if device is None:
        device = get_current_device()

    # Aktív modell ellenőrzés
    if model_name == get_active_model():
        return False, "active_model_cannot_delete"

    # Először ellenőrizzük a lokális mappát (új struktúra)
    local_path = get_local_model_path(model_name, device)
    if os.path.exists(local_path) and os.path.isdir(local_path):
        try:
            shutil.rmtree(local_path)
            return True, f"model_deleted:{model_name}"
        except Exception as e:
            return False, f"delete_error:{str(e)}"

    # Ha nincs lokálisan, ellenőrizzük a legacy cache-t
    legacy_path = get_cache_path(model_name, device)
    if os.path.exists(legacy_path) and os.path.isdir(legacy_path):
        try:
            shutil.rmtree(legacy_path)
            return True, f"model_deleted:{model_name}"
        except Exception as e:
            return False, f"delete_error:{str(e)}"

    return False, "model_not_found"


def delete_all_unused():
    """
    Összes nem használt modell törlése
    Returns: (deleted_count: int, freed_bytes: int, errors: list)
    """
    active_model = get_active_model()
    deleted_count = 0
    freed_bytes = 0
    errors = []

    for model in get_downloaded_models():
        if model["name"] != active_model:
            success, message = delete_model(model["name"])
            if success:
                deleted_count += 1
                freed_bytes += model["size"]
            else:
                errors.append(f"{model['name']}: {message}")

    return deleted_count, freed_bytes, errors


def get_total_cache_size():
    """Összes cache méret"""
    models = get_downloaded_models()
    return sum(m["size"] for m in models)


def get_freeable_size():
    """Felszabadítható méret (aktív modell nélkül)"""
    active_model = get_active_model()
    models = get_downloaded_models()
    return sum(m["size"] for m in models if m["name"] != active_model)


# Tesztelés
if __name__ == "__main__":
    print("=== Whisper Model Manager ===\n")

    print(f"Aktív modell: {get_active_model()}")
    print(f"Cache könyvtár: {HF_CACHE_DIR}\n")

    models = get_downloaded_models()
    print(f"Letöltött modellek ({len(models)}):")
    for m in models:
        active = "●" if m["name"] == get_active_model() else " "
        print(f"  {active} {m['name']:20} {m['size_formatted']:>10}")

    print(f"\nÖsszes méret: {format_size(get_total_cache_size())}")
    print(f"Felszabadítható: {format_size(get_freeable_size())}")
