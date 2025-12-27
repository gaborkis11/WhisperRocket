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

---

## Swift verzió - Fejlesztés folyamatban

### Elkészült (2025-12-26)
- ✅ Xcode projekt létrehozása (`swift/WhisperRocket/`)
- ✅ Menu Bar App (MenuBarExtra + SwiftUI)
- ✅ Globális Hotkey (Carbon RegisterEventHotKey) - **Ctrl+Shift+S**
- ✅ AppState központi állapotkezelés
- ✅ Recording toggle (start/stop)

### Elkészült (2025-12-26) - Hangfelvétel
- ✅ AudioRecorder osztály (AVAudioEngine)
- ✅ WAV fájl mentés (16kHz, mono, 16-bit PCM)
- ✅ Amplitúdó callback (equalizer-hez előkészítve)
- ✅ Mikrofon engedély kezelés

### Elkészült (2025-12-26) - WhisperKit integráció
- ✅ WhisperKit Swift Package integráció
- ✅ WhisperTranscriber osztály
- ✅ ModelManager (modell letöltés/kezelés)
- ✅ Transzkripció (magyar és más nyelvek támogatása)
- ✅ Partial transcription callback (élő szöveg)

### Elkészült (2025-12-26/27) - Popup ablak
- ✅ PopupWindow (borderless, floating)
- ✅ PopupView (SwiftUI)
- ✅ RecordingView + EqualizerView
- ✅ ProcessingView + rakéta animáció + csillagok
- ✅ TextPreviewView (szöveg előnézet)
- ✅ Escape billentyű (felvétel/feldolgozás megszakítás)

### Elkészült (2025-12-27) - Settings és további funkciók
- ✅ SettingsView (modell, nyelv, hotkey, popup időtartam)
- ✅ SettingsWindowController
- ✅ PasteManager (auto-paste AppleScript-tel)
- ✅ HistoryManager + HistoryWindowController
- ✅ AboutWindowController (új ikon)
- ✅ LaunchAtLoginManager
- ✅ Új app ikon (rakéta + hangfülek)

### Elkészült (2025-12-27) - Élő transzkripció progress
- ✅ WhisperKit callback partial transcription-höz
- ✅ "Felúszó szavak" animáció ProcessingView-ban
- ✅ Fade in/out + felfelé mozgás animáció
- ✅ Data flow: WhisperTranscriber → AppState → PopupWindowController → ProcessingView

### Folyamatban
- (nincs)

### Várakozik / Jövőbeli fejlesztések
- [ ] Hotkey testreszabás UI (jelenleg fix Ctrl+Shift+S)
- [ ] App Store előkészítés / notarization
- [ ] Több modell támogatás (base, small, medium, large)

---

## Swift fájlstruktúra

```
swift/WhisperRocket/WhisperRocket/
├── WhisperRocketApp.swift      # App entry point (MenuBarExtra)
├── AppDelegate.swift           # NSApplicationDelegate
├── AppState.swift              # Központi állapotkezelés
├── MenuBarView.swift           # Menu bar menü
├── HotkeyManager.swift         # Carbon hotkey (Ctrl+Shift+S)
├── AudioRecorder.swift         # Hangfelvétel (AVAudioEngine, 16kHz WAV)
├── ContentView.swift           # (nem használt)
├── Info.plist                  # LSUIElement, mikrofon engedély
└── Assets.xcassets/            # Ikonok
```

---

## Technikai megjegyzések

### Hotkey implementáció
- **Carbon RegisterEventHotKey** - legmegbízhatóbb módszer
- NSEvent.addGlobalMonitorForEvents NEM működött megfelelően
- CGEvent.tapCreate Input Monitoring problémák miatt elvetettük

### Engedélyek
- **Accessibility**: Szükséges lesz az auto-paste-hez
- **Microphone**: Szükséges a hangfelvételhez
- **Input Monitoring**: NEM szükséges a Carbon hotkey-hez

---

## Miért Swift?

| Python (jelenlegi) | Swift (cél) |
|-------------------|-------------|
| ~200 MB app méret | ~20-30 MB |
| PyInstaller bundle | Natív macOS app |
| Lassú indulás | Azonnali indulás |
| Nehéz App Store | Egyszerű notarization |
