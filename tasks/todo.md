# WhisperTalk - Todo Lista

## Aktuális Feladat

_Nincs aktív feladat_

---

## Befejezett: Hangjelzések felvétel indításkor/leállításkor

**Cél:** Hangvisszajelzés, hogy a felhasználó tudja, mikor indul/áll le a felvétel.

**Megoldás:**
- [x] `play_sound()` függvény létrehozása (`paplay` használata)
- [x] Hang lejátszása `start_recording()` és `stop_recording()` függvényben
- [x] `--volume=65536` paraméter a hangerő garantálásához
- [x] Warmup hang az alkalmazás indításakor
- [x] Tesztelés - működik!

**Megjegyzés:** Az eredeti terv tartalmazott Input/Output eszközválasztókat, de ezek eltávolításra kerültek a megbízhatóság érdekében. Az alkalmazás mindig a rendszer alapértelmezett audio eszközeit használja (GNOME Settings-ben állítható).

---

## Tervezett Fejlesztések

- [ ] Popup ablak hullámforma vizualizációval
- [ ] Modern beállítások UI (PyQt6)
- [ ] Cross-platform támogatás (Windows, macOS)

---

## Befejezett Feladatok

- [x] Alapvető speech-to-text funkció
- [x] System Tray ikon státusz jelzéssel
- [x] Smart paste (Ctrl+V vs Ctrl+Shift+V terminálokhoz)
- [x] System Tray menü (jobb klikk → Kilépés)
- [x] Linux app launcher (.desktop fájl)
- [x] Alkalmazás ikon (assets/whispertalk.png)

---

## Review - 2025-12-20

### Elvégzett módosítások

**1. System Tray menü**
- `whisper_gui.py`: Import bővítve (`Menu, MenuItem`)
- `whisper_gui.py`: Új `quit_app()` függvény hozzáadva
- `whisper_gui.py`: Tray ikon menüvel létrehozva
- Jobb klikk a tray ikonra → "Kilépés" opció

**2. Linux App Launcher**
- `assets/whispertalk.png`: 256x256 mikrofon ikon generálva
- `whispertalk.desktop`: Freedesktop szabványú launcher fájl
- `install.sh`: Frissítve desktop fájl telepítéssel

### Új fájlok
- `assets/whispertalk.png`
- `whispertalk.desktop`

### Módosított fájlok
- `whisper_gui.py` (3 módosítás)
- `install.sh` (1 módosítás)

### Tesztelés
- System Tray menü működik
- Alkalmazás megjelenik az alkalmazások menüben
- Desktop fájl telepítve: `~/.local/share/applications/whispertalk.desktop`
