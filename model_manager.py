#!/usr/bin/env python3
"""
WhisperTalk - Modell Manager
Whisper modellek cache kezelése (lista, méret, törlés)
"""
import os
import shutil
import json

# Huggingface cache útvonal
HF_CACHE_DIR = os.path.expanduser("~/.cache/huggingface/hub")

# Faster-whisper modell prefix
MODEL_PREFIX = "models--Systran--faster-whisper-"

# Támogatott modellek és méreteik (becsült, letöltés előtti info)
MODEL_INFO = {
    "tiny": {"name": "Tiny", "size_estimate": "39 MB"},
    "base": {"name": "Base", "size_estimate": "74 MB"},
    "small": {"name": "Small", "size_estimate": "244 MB"},
    "medium": {"name": "Medium", "size_estimate": "769 MB"},
    "large-v3-turbo": {"name": "Large-v3-turbo", "size_estimate": "1.6 GB"},
    "large-v3": {"name": "Large-v3", "size_estimate": "3 GB"},
}


def get_cache_path(model_name):
    """Visszaadja a modell cache útvonalát"""
    return os.path.join(HF_CACHE_DIR, f"{MODEL_PREFIX}{model_name}")


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


def get_downloaded_models():
    """
    Visszaadja a letöltött modellek listáját
    Returns: [{"name": "large-v3", "size": 3045678901, "size_formatted": "2.84 GB", "path": "/..."}]
    """
    models = []

    if not os.path.exists(HF_CACHE_DIR):
        return models

    for dirname in os.listdir(HF_CACHE_DIR):
        if dirname.startswith(MODEL_PREFIX):
            model_name = dirname.replace(MODEL_PREFIX, "")
            model_path = os.path.join(HF_CACHE_DIR, dirname)

            if os.path.isdir(model_path):
                size = get_directory_size(model_path)
                models.append({
                    "name": model_name,
                    "display_name": MODEL_INFO.get(model_name, {}).get("name", model_name),
                    "size": size,
                    "size_formatted": format_size(size),
                    "path": model_path
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


def is_model_downloaded(model_name):
    """Ellenőrzi, hogy a modell le van-e töltve"""
    model_path = get_cache_path(model_name)
    return os.path.exists(model_path) and os.path.isdir(model_path)


def delete_model(model_name):
    """
    Modell törlése a cache-ből
    Returns: (success: bool, message: str)
    """
    # Aktív modell ellenőrzés
    if model_name == get_active_model():
        return False, "Az aktív modell nem törölhető!"

    model_path = get_cache_path(model_name)

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
