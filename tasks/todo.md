# WhisperRocket - Fejlesztési Terv

## Jelenlegi állapot

### Python verzió (KÉSZ - 95%)
A Python/PySide6 verzió működőképes macOS-en:
- ✅ MLX Whisper backend (Apple Silicon GPU)
- ✅ System Tray ikon
- ✅ Popup ablak (equalizer, rakéta animáció)
- ✅ Settings ablak
- ✅ History kezelés
- ✅ Hotkey (pynput)
- ✅ Automatikus paste
- ✅ Modell letöltés
- ✅ PyInstaller DMG build

**Ismert probléma:**
- DMG-ből telepített bundled app tesztelése még hátra van

---

## Következő fázis: Natív Swift verzió

### Miért Swift?

| Python (jelenlegi) | Swift (cél) |
|-------------------|-------------|
| ~200 MB app méret | ~20-30 MB |
| PyInstaller bundle | Natív macOS app |
| Lassú indulás | Azonnali indulás |
| Nehéz App Store | Egyszerű notarization |

### Fő komponensek

1. **Menu Bar App** (`NSStatusItem`)
2. **Globális Hotkey** (`CGEvent` tap)
3. **Hangfelvétel** (`AVAudioEngine`)
4. **Whisper** (whisper.cpp + Metal GPU)
5. **Popup UI** (SwiftUI)
6. **Settings** (SwiftUI)

---

## Todo

### Python verzió - Lezárás
- [ ] DMG bundled app tesztelése
- [ ] Dokumentáció frissítése

### Swift verzió - Fejlesztés
- [ ] Xcode projekt létrehozása (`swift/`)
- [ ] Menu bar app alap
- [ ] whisper.cpp integráció
- [ ] Hangfelvétel
- [ ] Popup UI
- [ ] Settings UI
- [ ] Hotkey kezelés
- [ ] Auto-paste
- [ ] History
- [ ] Modell letöltés
- [ ] DMG készítés

---

## Fájlstruktúra

```
WhisperWarp/
├── swift/                    # ÚJ: Swift verzió
│   └── WhisperRocket/
│       └── WhisperRocket.xcodeproj
│
├── whisper_gui.py            # Python fő app
├── popup_window.py           # Python popup
├── settings_window.py        # Python settings
├── history_viewer.py         # Python history
├── model_manager.py          # Python modell kezelés
├── download_manager.py       # Python letöltés
├── setup_wizard.py           # Python wizard
├── translations.py           # Python i18n
├── history_manager.py        # Python history
│
├── platform_support/         # Python platform absztrakció
│   ├── __init__.py
│   ├── base.py
│   ├── linux.py
│   ├── macos.py
│   └── utils.py
│
├── assets/                   # Közös erőforrások
├── scripts/                  # Build scriptek
├── tasks/                    # Tervek, todo
│
├── requirements*.txt         # Python függőségek
├── start*.sh                 # Indító scriptek
├── install*.sh               # Telepítő scriptek
│
├── CLAUDE.md                 # Claude instrukciók
├── README.md                 # Dokumentáció
└── LICENSE
```
