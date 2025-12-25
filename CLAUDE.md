# WhisperRocket - Silent Speech-to-Text

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
11. Git commitoknál NE add hozzá a "Generated with Claude Code" vagy "Co-Authored-By: Claude" láblécet. Tiszta, egyszerű commit üzeneteket írj.
12. CSAK akkor commitolj vagy pusholj GitHubra, ha a felhasználó kifejezetten kéri. Soha ne commitolj automatikusan.

---

## Projekt Leírás

**WhisperRocket** egy lokális speech-to-text (beszédfelismerő) alkalmazás, amely az OpenAI Whisper modellt használja valós idejű beszédfelismerésre.

### Támogatott Platformok

| Platform | Backend | GPU | Állapot |
|----------|---------|-----|---------|
| macOS (Apple Silicon) | MLX Whisper | Metal GPU | ✅ Kész |
| Linux | faster-whisper | NVIDIA CUDA | ✅ Kész |

### Fő Funkciók

- **Valós idejű beszédfelismerés** - Whisper large-v3 modell, többnyelvű támogatás
- **GPU gyorsítás** - Apple Metal (macOS) vagy NVIDIA CUDA (Linux)
- **Hotkey vezérlés** - Konfigurálható hotkey (alapért. Cmd+Shift+9 macOS-en)
- **Automatikus beillesztés** - Felismert szöveg automatikusan beillesztésre kerül
- **Smart paste** - Terminál detektálás (Cmd+Shift+V vs Cmd+V)
- **System Tray ikon** - Menu bar app macOS-en
- **Modern Popup ablak** - Equalizer vizualizáció felvétel közben
- **Rakéta animáció** - Feldolgozás közben animált rakéta + vicces üzenetek
- **Szöveg előnézet** - Transzkripció után kattintható szöveg megjelenítés
- **Konfigurálható popup időtartam** - Beállítható, meddig maradjon látható
- **Setup Wizard** - Első indításkor vezeti végig a beállításokon

### Technikai Részletek

| Tulajdonság | macOS | Linux |
|-------------|-------|-------|
| Nyelv | Python 3.10+ | Python 3.10+ |
| UI Framework | PySide6 | PyQt6 |
| Whisper | MLX Whisper | faster-whisper |
| GPU | Apple Metal | NVIDIA CUDA |
| Audio | 16kHz, mono | 16kHz, mono |
| Hotkey | pynput | pynput |
| Paste | AppleScript | xdotool |

### Fájlstruktúra

```
WhisperRocket/
├── whisper_gui.py          # Fő alkalmazás
├── popup_window.py         # Popup ablak (equalizer, rakéta, szöveg)
├── settings_window.py      # Beállítások ablak
├── history_viewer.py       # History ablak
├── history_manager.py      # History kezelés
├── model_manager.py        # Whisper modellek kezelése
├── download_manager.py     # Modell letöltések
├── setup_wizard.py         # Első indítás wizard
├── translations.py         # Többnyelvű fordítások
│
├── platform_support/       # Platform absztrakció
│   ├── __init__.py
│   ├── base.py            # Alap interfész
│   ├── macos.py           # macOS implementáció
│   ├── linux.py           # Linux implementáció
│   └── utils.py           # Segédfüggvények
│
├── assets/
│   ├── whisperrocket.png  # Alkalmazás ikon
│   ├── whisperrocket.icns # macOS ikon
│   └── *.wav              # Hangeffektek
│
├── scripts/               # Build scriptek
│   ├── build_macos.sh     # PyInstaller build
│   └── create_dmg.sh      # DMG készítés
│
├── requirements.txt       # Alap függőségek
├── requirements-macos.txt # macOS függőségek
├── requirements-cuda.txt  # Linux CUDA függőségek
│
├── start.sh              # Linux indító
├── start_macos.sh        # macOS indító
├── install.sh            # Linux telepítő
├── install_macos.sh      # macOS telepítő
│
├── entitlements.plist    # macOS code signing
├── WhisperRocket.spec    # PyInstaller spec (gitignore)
│
├── tasks/
│   └── todo.md           # Todo és tervek
├── CLAUDE.md             # Ez a fájl
├── README.md             # Dokumentáció
└── LICENSE
```

### Konfiguráció

A konfiguráció helye platformtól és futtatási módtól függ:
- **macOS bundled app**: `~/Library/Application Support/WhisperRocket/config.json`
- **macOS dev**: `./config.json`
- **Linux**: `./config.json` vagy `~/.config/whisperrocket/config.json`

```json
{
  "hotkey": "cmd+shift+9",
  "model": "large-v3",
  "device": "mps",
  "compute_type": "float16",
  "language": "hu",
  "sample_rate": 16000,
  "popup_display_duration": 5
}
```

### Indítás

**macOS (fejlesztés):**
```bash
./start_macos.sh
```

**macOS (bundled app):**
- Megnyitni a WhisperRocket.app-ot

**Linux:**
```bash
./start.sh
```

---

## Tervezett Fejlesztések

### Natív Swift verzió

A Python verzió működik, de egy fizetős termékhez natív Swift alkalmazás lenne ideális:

| Python (jelenlegi) | Swift (cél) |
|-------------------|-------------|
| ~200 MB app méret | ~20-30 MB |
| PyInstaller bundle | Natív macOS app |
| Lassú indulás | Azonnali indulás |
| Nehéz App Store | Egyszerű notarization |

**Swift fejlesztés fő komponensei:**
1. Menu Bar App (`NSStatusItem`)
2. Globális Hotkey (`CGEvent` tap)
3. Hangfelvétel (`AVAudioEngine`)
4. Whisper (`whisper.cpp` + Metal GPU)
5. Popup UI (SwiftUI)
6. Settings (SwiftUI)

A Swift verzió a `swift/` könyvtárban lesz.

---

## macOS Specifikus Tudnivalók

### Engedélyek
- **Mikrofon**: Automatikusan kéri a rendszer
- **Input Monitoring**: Szükséges a globális hotkey-hez
- **Accessibility**: Szükséges az automatikus paste-hez

### Bundled App Problémák és Megoldások

1. **Settings bezárása kiléptet**: `qt_app.setQuitOnLastWindowClosed(False)`
2. **Config elérési út**: Bundled app-nál read-only a bundle, ezért `~/Library/Application Support/` kell
3. **Dock ikon**: `LSUIElement=true` az Info.plist-ben elrejti
4. **Popup always-on-top**: `setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)`

### PyInstaller Build

```bash
cd scripts
./build_macos.sh
./create_dmg.sh
```

---

## Elkészült Funkciók

- [x] macOS Apple Silicon támogatás (MLX Whisper)
- [x] Platform absztrakciós réteg
- [x] System Tray / Menu bar app
- [x] Modern beállítások UI
- [x] Modell kezelés (letöltés, törlés)
- [x] Hangjelzések
- [x] Popup ablak equalizer vizualizációval
- [x] Rakéta animáció feldolgozás közben
- [x] Szöveg előnézet
- [x] Konfigurálható popup időtartam
- [x] Escape gomb a felvétel megszakításához
- [x] Setup Wizard első indításhoz
- [x] PyInstaller DMG build macOS-re
- [x] History kezelés
