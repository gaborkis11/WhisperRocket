# WhisperTalk - Speech-to-Text Alkalmazás

## Claude Rules

1. Először gondold végig a problémát, olvasd el a releváns fájlokat a kódbázisban, és írj egy tervet a `tasks/todo.md` fájlba.
2. A tervnek tartalmaznia kell egy todo listát, amit kipipálhatsz, ahogy haladasz.
3. Mielőtt elkezdenéd a munkát, egyeztess velem és én jóváhagyom a tervet.
4. Ezután kezdj el dolgozni a todo elemeken, és jelöld késznek őket, ahogy haladasz.
5. Minden lépésnél adj egy magas szintű magyarázatot arról, milyen változtatásokat végeztél.
6. Minden feladatot és kódváltoztatást a lehető legegyszerűbben végezz el. Kerüljük a nagy vagy komplex változtatásokat. Minden változtatás a lehető legkevesebb kódot érintse. Minden az egyszerűségről szól.
7. Végül adj hozzá egy review szekciót a `tasks/todo.md` fájlhoz a változtatások összefoglalójával és minden releváns információval.
8. NE LÉGY LUSTA. SOHA NE LÉGY LUSTA. HA VAN EGY BUG, TALÁLD MEG A GYÖKÉR OKÁT ÉS JAVÍTSD KI. NINCSENEK IDEIGLENES MEGOLDÁSOK. TE EGY SENIOR FEJLESZTŐ VAGY. SOHA NE LÉGY LUSTA.
9. MINDEN JAVÍTÁST ÉS KÓDVÁLTOZTATÁST A LEHETŐ LEGEGYSZERŰBBEN VÉGEZZ. CSAK A FELADATHOZ SZÜKSÉGES KÓDOT ÉRINTSD ÉS SEMMI MÁST. A LEHETŐ LEGKEVESEBB KÓDOT ÉRINTSE. A CÉLOD, HOGY NE VEZESS BE BUGOKAT. MINDEN AZ EGYSZERŰSÉGRŐL SZÓL.
10. A felhasználóval való minden kommunikáció magyar nyelven történjen. Ez szigorú követelmény és soha nem szeghető meg.

---

## Projekt Leírás

**WhisperTalk** egy lokális speech-to-text (beszédfelismerő) alkalmazás, amely az OpenAI Whisper modellt használja (faster-whisper implementáció) valós idejű beszédfelismerésre.

### Fő Funkciók

- **Valós idejű beszédfelismerés** - Whisper large-v3 modell, többnyelvű támogatás
- **GPU gyorsítás** - NVIDIA CUDA támogatás (float16)
- **Hotkey vezérlés** - Konfigurálható hotkey (alapért. Alt+S)
- **Automatikus beillesztés** - Felismert szöveg automatikusan beillesztésre kerül
- **Smart paste** - Terminál/Cursor detektálás (Ctrl+Shift+V vs Ctrl+V)
- **System Tray ikon** - Színes vizuális visszajelzés a státuszról
- **Modern Popup ablak** - Equalizer vizualizáció felvétel közben
- **Rakéta animáció** - Feldolgozás közben animált rakéta + vicces üzenetek
- **Szöveg előnézet** - Transzkripció után kattintható szöveg megjelenítés
- **Konfigurálható popup időtartam** - Beállítható, meddig maradjon látható

### Technikai Részletek

| Tulajdonság | Érték |
|-------------|-------|
| Nyelv | Python 3.10+ |
| Modell | Whisper large-v3 (faster-whisper) |
| GPU | NVIDIA CUDA, float16 compute |
| Audio | 16kHz sample rate, mono |
| Platform | Linux (jelenleg), tervezett: Windows, macOS |

### Fájlstruktúra

```
whisper-test/
├── whisper_gui.py        # Fő alkalmazás (System Tray verzió)
├── popup_window.py       # Popup ablak (equalizer, rakéta animáció, szöveg)
├── settings_window.py    # Beállítások ablak (PyQt6)
├── model_manager.py      # Whisper modellek cache kezelése
├── download_manager.py   # Modell letöltések kezelése
├── config.json           # Konfiguráció (hotkey, modell, nyelv, stb.)
├── start.sh              # Indító script (CUDA env beállítás)
├── install.sh            # Telepítő script
├── requirements.txt      # Python függőségek
├── whispertalk.desktop   # Linux app launcher
├── assets/
│   ├── whispertalk.png   # Alkalmazás ikon (256x256)
│   ├── start_soft_click_smooth.wav  # Felvétel indítás hang
│   └── stop_soft_click_smooth.wav   # Felvétel leállítás hang
├── tasks/
│   └── todo.md           # Todo és tervek
└── CLAUDE.md             # Ez a fájl
```

### Konfiguráció (config.json)

```json
{
  "hotkey": "alt+s",
  "model": "large-v3",
  "device": "cuda",
  "compute_type": "float16",
  "language": "hu",
  "sample_rate": 16000,
  "input_device": null,
  "output_device": null,
  "popup_display_duration": 5
}
```

### Indítás

```bash
./start.sh
```

### Leállítás

```bash
pkill -f whisper_gui.py
```

---

## Tervezett Fejlesztések

- [ ] Cross-platform támogatás (Windows, macOS)

## Elkészült Fejlesztések

- [x] System Tray menü (jobb klikk → Settings, Quit)
- [x] Modern beállítások UI (PyQt6, tab-ok, modell letöltés)
- [x] Telepíthető alkalmazás (.desktop fájl, ikon)
- [x] Modell kezelés (letöltés, törlés, cache méret)
- [x] Autostart támogatás
- [x] Hangjelzések felvétel indításkor/leállításkor
- [x] Popup ablak equalizer vizualizációval
- [x] Processing állapot rakéta animációval
- [x] Véletlenszerű vicces üzenetek feldolgozás közben
- [x] Szöveg előnézet transzkripció után (kattintásra bővíthető)
- [x] Konfigurálható popup megjelenítési idő (1-30 mp)
- [x] Escape gomb a felvétel megszakításához
- [x] Visszaszámláló a popup eltűnéséig
