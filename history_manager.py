"""
History Manager - Transzkripciók előzményeinek kezelése
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Maximális history méret (100 MB)
MAX_HISTORY_SIZE_BYTES = 100 * 1024 * 1024

def get_history_path() -> Path:
    """History JSON fájl elérési útja"""
    config_dir = Path.home() / ".config" / "whisperwarp"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "history.json"

def load_history() -> Dict:
    """History betöltése JSON fájlból"""
    path = get_history_path()
    if not path.exists():
        return {"entries": []}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "entries" not in data:
                data["entries"] = []
            return data
    except (json.JSONDecodeError, IOError):
        return {"entries": []}

def save_history(data: Dict) -> bool:
    """History mentése JSON fájlba"""
    path = get_history_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False

def add_entry(text: str, duration_sec: float, language: str) -> Optional[str]:
    """
    Új bejegyzés hozzáadása a history-hoz

    Returns:
        Az új bejegyzés ID-ja, vagy None hiba esetén
    """
    if not text or not text.strip():
        return None

    data = load_history()

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "text": text.strip(),
        "duration_sec": round(duration_sec, 2),
        "language": language
    }

    # Új bejegyzés az elejére (legfrissebb elöl)
    data["entries"].insert(0, entry)

    # Méret limit ellenőrzés
    enforce_size_limit(data)

    if save_history(data):
        return entry["id"]
    return None

def get_recent(limit: int = 20) -> List[Dict]:
    """Legutóbbi N bejegyzés lekérése"""
    data = load_history()
    return data["entries"][:limit]

def get_entry_by_id(entry_id: str) -> Optional[Dict]:
    """Egy bejegyzés lekérése ID alapján"""
    data = load_history()
    for entry in data["entries"]:
        if entry.get("id") == entry_id:
            return entry
    return None

def clear_history() -> bool:
    """Teljes history törlése"""
    return save_history({"entries": []})

def get_stats() -> Dict:
    """
    History statisztikák

    Returns:
        {"count": int, "size_bytes": int, "size_formatted": str}
    """
    path = get_history_path()
    data = load_history()

    count = len(data["entries"])

    if path.exists():
        size_bytes = path.stat().st_size
    else:
        size_bytes = 0

    # Méret formázás
    if size_bytes < 1024:
        size_formatted = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_formatted = f"{size_bytes / 1024:.1f} KB"
    else:
        size_formatted = f"{size_bytes / (1024 * 1024):.1f} MB"

    return {
        "count": count,
        "size_bytes": size_bytes,
        "size_formatted": size_formatted
    }

def enforce_size_limit(data: Dict) -> None:
    """
    100 MB limit betartása - régi bejegyzések törlése ha szükséges

    Args:
        data: A history dict (helyben módosítja)
    """
    # Ellenőrzés: JSON méret becslése
    json_str = json.dumps(data, ensure_ascii=False)
    current_size = len(json_str.encode("utf-8"))

    # Ha túl nagy, töröljük a legrégebbi bejegyzéseket
    while current_size > MAX_HISTORY_SIZE_BYTES and len(data["entries"]) > 0:
        data["entries"].pop()  # Legrégebbi törlése (lista végéről)
        json_str = json.dumps(data, ensure_ascii=False)
        current_size = len(json_str.encode("utf-8"))

def format_timestamp(iso_timestamp: str) -> str:
    """ISO timestamp formázása olvasható formátumra (HH:MM:SS)"""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return iso_timestamp

def format_preview(text: str, max_length: int = 40) -> str:
    """Szöveg előnézet formázása (első N karakter)"""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."
