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
13. KÉRDÉSRE VÁLASZOLJ, NE CSELEKEDJ. Ha a felhasználó kérdést tesz fel, akkor válaszolj és tegyél javaslatot, de NE kezdj el automatikusan implementálni. Mindig kérj engedélyt a változtatások előtt. A kérdés nem egyenlő a feladattal.

---

## Projekt Leírás

**WhisperRocket** egy lokális speech-to-text (beszédfelismerő) alkalmazás, amely az OpenAI Whisper modellt használja valós idejű beszédfelismerésre.

### Verziók

| Verzió | Állapot | Megjegyzés |
|--------|---------|------------|
| **Swift (natív)** | ✅ Aktív fejlesztés | Fő verzió, macOS-re |
| Python | 🔄 Karbantartás | Linux támogatás |

### Támogatott Platformok

| Platform | Backend | GPU | Állapot |
|----------|---------|-----|---------|
| macOS (Apple Silicon) | WhisperKit | Metal GPU | ✅ Swift verzió |
| macOS (Apple Silicon) | MLX Whisper | Metal GPU | ✅ Python verzió |
| Linux | faster-whisper | NVIDIA CUDA | ✅ Python verzió |

### Fő Funkciók (Swift verzió)

- **Valós idejű beszédfelismerés** - WhisperKit large-v3 modell
- **GPU gyorsítás** - Apple Metal (Apple Silicon natív)
- **Élő transzkripció** - Feldolgozás közben látható a részleges szöveg ("felúszó szavak")
- **Hotkey vezérlés** - Konfigurálható hotkey (Carbon API)
- **Automatikus beillesztés** - Felismert szöveg automatikusan beillesztésre kerül
- **Escape megszakítás** - Felvétel és feldolgozás megszakítható
- **Menu Bar app** - System tray ikon, dock ikon nélkül
- **Modern Popup ablak** - Equalizer vizualizáció felvétel közben
- **Rakéta animáció** - Feldolgozás közben animált rakéta + vicces üzenetek
- **Hangjelzések** - Start/stop hangok felvétel kezdetén és végén
- **Szöveg előnézet** - Transzkripció után kattintható szöveg megjelenítés
- **History** - Korábbi transzkripciók megtekintése
- **Többnyelvű** - Magyar és angol UI, 99 nyelv transzkripció

### Technikai Részletek

| Tulajdonság | Swift (macOS) | Python (Linux) |
|-------------|---------------|----------------|
| Nyelv | Swift 5.9+ | Python 3.10+ |
| UI Framework | SwiftUI | PyQt6 |
| Whisper | WhisperKit | faster-whisper |
| GPU | Apple Metal | NVIDIA CUDA |
| Audio | AVAudioEngine | sounddevice |
| Hotkey | Carbon API | pynput |
| Paste | CGEvent | xdotool |

### Fájlstruktúra

```
WhisperRocket/
│
├── swift/                          # 🎯 SWIFT VERZIÓ (fő)
│   └── WhisperRocket/
│       └── WhisperRocket/
│           ├── WhisperRocketApp.swift    # App entry point
│           ├── AppState.swift            # Fő állapot kezelés
│           ├── ContentView.swift         # Menu bar app
│           ├── PopupWindowController.swift
│           ├── RecordingView.swift       # Equalizer UI
│           ├── ProcessingView.swift      # Rakéta + felúszó szavak
│           ├── ResultView.swift          # Eredmény megjelenítés
│           ├── SettingsView.swift        # Beállítások
│           ├── HistoryView.swift         # History
│           ├── HotkeyManager.swift       # Carbon hotkey kezelés
│           ├── AudioRecorder.swift       # AVAudioEngine
│           ├── SoundManager.swift        # Start/stop hangok
│           ├── PasteService.swift        # CGEvent paste
│           ├── Localizable.xcstrings     # Fordítások
│           └── Assets.xcassets/          # Ikonok, képek
│
├── whisper_gui.py          # Python fő alkalmazás (Linux)
├── popup_window.py         # Popup ablak
├── settings_window.py      # Beállítások ablak
├── history_viewer.py       # History ablak
├── history_manager.py      # History kezelés
├── model_manager.py        # Whisper modellek kezelése
├── translations.py         # Többnyelvű fordítások
│
├── platform_support/       # Python platform absztrakció
│   ├── __init__.py
│   ├── base.py
│   ├── macos.py
│   ├── linux.py
│   └── utils.py
│
├── assets/
│   ├── whisperrocket.png
│   ├── whisperrocket.icns
│   └── *.wav              # Hangeffektek
│
├── scripts/               # Build scriptek
│   ├── build_macos.sh
│   └── create_dmg.sh
│
├── requirements.txt
├── requirements-macos.txt
├── requirements-cuda.txt
│
├── start.sh              # Linux indító
├── install.sh            # Linux telepítő
│
├── tasks/
│   └── todo.md
├── CLAUDE.md
├── README.md
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

### Monetizáció - Fizetős Verzió

A Swift verzió fizetős termékként lesz értékesítve.

**Árképzés terv:**
| Csomag | Ár | Megjegyzés |
|--------|-----|------------|
| 1 eszköz | ~1990 Ft (~$5) | Egyszeri fizetés |

**Értékesítési modell:**
- Egyszeri fizetés (nem előfizetés)
- Weboldal + Stripe integráció
- Licenc kulcs aktiválás
- Offline működés aktiválás után

**Licenc rendszer terv:**
```
1. Vásárlás (Stripe) → Licenc kulcs generálás (kriptográfiai aláírás)
2. Email küldés a licenc kulccsal
3. Első indítás → Licenc beírása → Online aktiválás (egyszer)
4. Aktivációs token mentése lokálisan (hardware ID-val)
5. Utána: teljesen offline működés
```

**Technológiák:**
- Weboldal: Next.js + Vercel
- Fizetés: Stripe Checkout
- Licenc: Aszimmetrikus titkosítás (privát/publikus kulcs)
- Email: Resend
- Adatbázis: Supabase

**Konkurensek:**
| App | Ár | Modell |
|-----|-----|--------|
| MacWhisper Pro | €59 | Egyszeri |
| VoiceInk | $25-49 | Egyszeri |
| Spokenly | $7.99/hó | Előfizetés |

---

## macOS Specifikus Tudnivalók

### Engedélyek
- **Mikrofon**: Automatikusan kéri a rendszer
- **Accessibility**: Szükséges a globális hotkey-hez és automatikus paste-hez

### Swift Verzió - Fontos Tudnivalók

1. **Popup always-on-top**: `NSPanel` + `.nonactivatingPanel` + `level = .floating`
2. **Dock ikon elrejtés**: `LSUIElement = YES` az Info.plist-ben
3. **Hotkey kezelés**: Carbon `RegisterEventHotKey` API (nem CGEvent tap)
4. **Escape kezelés**: Külön hotkey regisztráció, felvétel és feldolgozás alatt aktív
5. **WhisperKit modellek**: `~/Library/Application Support/WhisperRocket/models/`
6. **Hangfájlok**: Bundle-ben (`start_soft_click_smooth.wav`, `stop_soft_click_smooth.wav`)

### Swift Xcode Build

```bash
# Xcode-ban: Product → Archive → Distribute App
# Vagy command line:
xcodebuild -project swift/WhisperRocket/WhisperRocket.xcodeproj -scheme WhisperRocket -configuration Release archive
```

### Python PyInstaller Build (legacy)

```bash
cd scripts
./build_macos.sh
./create_dmg.sh
```

---

## Elkészült Funkciók

### Swift verzió (macOS)

- [x] Natív SwiftUI alkalmazás
- [x] WhisperKit integráció (Metal GPU)
- [x] Menu bar app (NSStatusItem)
- [x] Globális hotkey (Carbon API)
- [x] Popup ablak (NSPanel + SwiftUI)
- [x] Equalizer vizualizáció felvétel közben
- [x] Rakéta animáció feldolgozás közben
- [x] Élő transzkripció - "felúszó szavak" animáció
- [x] Start/stop hangjelzések (AVAudioPlayer)
- [x] Szöveg előnézet kattintható másolással
- [x] Escape billentyű megszakítás (felvétel + feldolgozás)
- [x] Automatikus paste (CGEvent)
- [x] History kezelés
- [x] Beállítások (modell, nyelv, hotkey)
- [x] Tooltipek a beállításoknál
- [x] Többnyelvű UI (magyar, angol)
- [x] About ablak

### Python verzió (Linux + legacy macOS)

- [x] macOS Apple Silicon támogatás (MLX Whisper)
- [x] Linux CUDA támogatás (faster-whisper)
- [x] Platform absztrakciós réteg
- [x] System Tray / Menu bar app
- [x] Modern beállítások UI
- [x] Modell kezelés (letöltés, törlés)
- [x] Hangjelzések
- [x] Popup ablak equalizer vizualizációval
- [x] Rakéta animáció feldolgozás közben
- [x] Szöveg előnézet
- [x] Escape gomb a felvétel megszakításához
- [x] Setup Wizard első indításhoz
- [x] PyInstaller DMG build macOS-re
- [x] History kezelés
