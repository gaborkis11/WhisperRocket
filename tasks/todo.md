# WhisperWarp - Todo Lista

## Aktuális Feladat

_Nincs aktív feladat_

---

## Befejezett: Popup szöveg megjelenítés + kibővítés

**Cél:** Transzkripció után a popup mutassa a leiratott szöveget, kattintásra kibővíthető Copy gombbal.

**Megoldás:**
- [x] `PopupState` enum hozzáadva (HIDDEN, RECORDING, TEXT_PREVIEW, TEXT_EXPANDED)
- [x] `show_text(text)` metódus - szöveg megjelenítése
- [x] `_draw_text_preview()` - rövidített szöveg előnézet
- [x] `_draw_text_expanded()` - teljes szöveg + Copy gomb + X bezárás
- [x] Auto-hide timer (3 másodperc)
- [x] Kattintásra kibővül, marad nyitva
- [x] Copy gomb - vágólapra másol és bezár
- [x] X gomb - bezárás
- [x] `whisper_gui.py` integráció

**Működés:**
1. Recording: waveform vizualizáció (változatlan)
2. Transzkripció után: szöveg előnézet (3mp-ig látszik)
3. Kattintásra: kibővített nézet teljes szöveggel + Copy gomb

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

- [ ] Cross-platform támogatás (Windows, macOS)

---

## Befejezett Feladatok

- [x] Alapvető speech-to-text funkció
- [x] System Tray ikon státusz jelzéssel
- [x] Smart paste (Ctrl+V vs Ctrl+Shift+V terminálokhoz)
- [x] System Tray menü (jobb klikk → Kilépés)
- [x] Linux app launcher (.desktop fájl)
- [x] Alkalmazás ikon (assets/whisperwarp.png)
- [x] Popup ablak waveform vizualizációval
- [x] Modern beállítások UI (PyQt6)
- [x] Popup szöveg megjelenítés + kibővítés

---

## Review - 2025-12-20

### Elvégzett módosítások

**1. System Tray menü**
- `whisper_gui.py`: Import bővítve (`Menu, MenuItem`)
- `whisper_gui.py`: Új `quit_app()` függvény hozzáadva
- `whisper_gui.py`: Tray ikon menüvel létrehozva
- Jobb klikk a tray ikonra → "Kilépés" opció

**2. Linux App Launcher**
- `assets/whisperwarp.png`: 256x256 mikrofon ikon generálva
- `whisperwarp.desktop`: Freedesktop szabványú launcher fájl
- `install.sh`: Frissítve desktop fájl telepítéssel

### Új fájlok
- `assets/whisperwarp.png`
- `whisperwarp.desktop`

### Módosított fájlok
- `whisper_gui.py` (3 módosítás)
- `install.sh` (1 módosítás)

### Tesztelés
- System Tray menü működik
- Alkalmazás megjelenik az alkalmazások menüben
- Desktop fájl telepítve: `~/.local/share/applications/whisperwarp.desktop`
