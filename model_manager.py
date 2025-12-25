#!/usr/bin/env python3
"""
WhisperRocket - Modell Manager
Whisper modellek cache kezelése (lista, méret, törlés)
"""
import os
import shutil
import json

from platform_support import get_platform_handler

# Platform handler és cache útvonal
platform_handler = get_platform_handler()
HF_CACHE_DIR = str(platform_handler.get_cache_dir())

# Modell prefixek backend-enként
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


def get_cache_path(model_name, device=None):
    """Visszaadja a modell cache útvonalát

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

    if not os.path.exists(HF_CACHE_DIR):
        return models

    # Ha nincs megadva device, használjuk a config-ból
    if device is None:
        device = get_current_device()

    # Prefix kiválasztása device alapján
    if device == "mlx":
        prefix = MODEL_PREFIX_MLX
        suffix = MODEL_SUFFIX_MLX
        backend = "mlx"
    else:
        prefix = MODEL_PREFIX_FASTER_WHISPER
        suffix = ""
        backend = "faster-whisper"

    for dirname in os.listdir(HF_CACHE_DIR):
        if dirname.startswith(prefix):
            # Modell név kinyerése
            model_name = dirname.replace(prefix, "")
            if suffix and model_name.endswith(suffix):
                model_name = model_name[:-len(suffix)]

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


def is_model_downloaded(model_name, device=None):
    """Ellenőrzi, hogy a modell TELJESEN le van-e töltve

    Args:
        model_name: Modell neve (pl. "large-v3")
        device: "mlx", "cuda", "cpu" vagy None (faster-whisper default)

    A HuggingFace cache-ben ellenőrizzük:
    1. Nincs-e .incomplete fájl a blobs könyvtárban
    2. Van-e refs/main fájl VAGY snapshots tartalom
    """
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
    """Visszaadja a config-ban beállított device-t"""
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
        return False, "Az aktív modell nem törölhető!"

    model_path = get_cache_path(model_name, device)

    if not os.path.exists(model_path):
        return False, "A modell nem található!"

    try:
        shutil.rmtree(model_path)
        return True, f"A {model_name} modell törölve!"
    except Exception as e:
        return False, f"Törlési hiba: {str(e)}"


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
