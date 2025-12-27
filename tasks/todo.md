# WhisperRocket - Fejlesztési Terv

## Jelenlegi állapot (2025-12-27)

### Swift verzió (macOS) - FŐ VERZIÓ ✅
A natív Swift verzió elkészült a következő funkciókkal:
- ✅ WhisperKit integráció (Apple Silicon GPU)
- ✅ Menu bar app (SwiftUI)
- ✅ Globális hotkey (Carbon API)
- ✅ Popup ablak (equalizer, rakéta animáció)
- ✅ Élő transzkripció ("felúszó szavak" animáció)
- ✅ Start/stop hangjelzések
- ✅ Settings (modell, nyelv, hotkey, popup időtartam)
- ✅ Settings tooltipek
- ✅ History kezelés
- ✅ About ablak
- ✅ Launch at Login
- ✅ Escape megszakítás (felvétel + feldolgozás)
- ✅ Automatikus paste
- ✅ Új app ikon (rakéta design)
- ✅ DMG build

### Python verzió (Linux) - KARBANTARTÁS 🔄
A Python verzió működik, de hiányoznak az új funkciók.

---

## AKTUÁLIS FELADAT: Python/Linux verzió frissítése

A Swift verzióban megvalósított új funkciók implementálása a Python/Linux verzióba.

### 1. Élő Transzkripció ("Felúszó Szavak") 🔴 MAGAS PRIORITÁS

**Leírás:** Feldolgozás közben 2.5 másodpercenként megjelenik egy 2-3 szavas részlet a popup-on.

**Teendők:**
- [ ] `popup_window.py` - `FloatingWordsView` komponens hozzáadása
- [ ] Timer alapú megjelenítés (2.5 másodpercenként)
- [ ] 2-3 szavas kifejezések kinyerése
- [ ] Magyar idézőjelek használata („szöveg")
- [ ] Random pozíció (bal vagy jobb oldalon, NE középen ahol a rakéta van)
- [ ] Fade in/out animáció
- [ ] SF Mono / monospace font
- [ ] Csak teljes szavak megjelenítése (szóköz/írásjel ellenőrzés)
- [ ] `whisper_gui.py` - partial transcription callback bekötése
- [ ] Partial text átadása a popup_window-nak

**Referencia:** `swift/WhisperRocket/WhisperRocket/ProcessingView.swift` - `FloatingWordsView` struct

### 2. About Ablak 🟡 KÖZEPES PRIORITÁS

**Leírás:** Alkalmazás információk megjelenítése (verzió, copyright, stb.)

**Teendők:**
- [ ] `about_window.py` - új fájl létrehozása
- [ ] Ablak design (sötét téma, app ikon, verzió info)
- [ ] App név: "WhisperRocket"
- [ ] Verzió: "1.0.0"
- [ ] Copyright szöveg
- [ ] Website/GitHub link (opcionális)
- [ ] `whisper_gui.py` - Menu-be "About" menüpont hozzáadása

**Referencia:** `swift/WhisperRocket/WhisperRocket/AboutWindowController.swift`

### 3. Settings Tooltipek 🟢 ALACSONY PRIORITÁS

**Leírás:** Magyarázó szövegek a beállításoknál

**Teendők:**
- [ ] `settings_window.py` - Tooltip szövegek hozzáadása
- [ ] Hotkey tooltip: "Press once to start recording, press again to stop and transcribe"
- [ ] Language tooltip: "Transcription will be generated in the selected language"
- [ ] Popup duration tooltip: "How long the text preview stays visible after transcription"
- [ ] `translations.py` - Fordítások hozzáadása (magyar/angol)

**Referencia:** `swift/WhisperRocket/WhisperRocket/SettingsView.swift` - GeneralTabView

### 4. Ikon Frissítés 🟢 ALACSONY PRIORITÁS

**Leírás:** A Swift verzióban új ikon van, a Python verzió még régit használ.

**Megfigyelések:**
- `assets/whisperrocket.png` - Dec 22, 3KB, 256x256 (régi)
- Swift ikonok - Dec 27, 33KB, friss design (új)

**Teendők:**
- [ ] Új 256x256 PNG exportálása a Swift verzióból
- [ ] `assets/whisperrocket.png` felülírása az új ikonnal
- [ ] Tesztelés Linux-on

---

## Technikai Részletek

### Élő Transzkripció Implementáció (Python)

A faster-whisper támogatja a partial transcription-t, de másképp működik mint a WhisperKit:

```python
# faster-whisper callback példa
for segment in segments:
    partial_text = segment.text
    # Küldés a popup-nak
```

**Fontos különbség:**
- WhisperKit: `transcriptionCallback` minden token után hívódik
- faster-whisper: `segments` generator, chunk-onként adja vissza

Megoldás: A `whisper_gui.py`-ban a `transcribe_audio` függvényben kell a partial text-et átadni.

### FloatingWordsView Logika (Python megfelelője)

```python
class FloatingWordsWidget(QWidget):
    def __init__(self):
        self.word_timer = QTimer()
        self.word_timer.timeout.connect(self.show_random_phrase)
        self.word_timer.start(2500)  # 2.5 másodpercenként

        self.current_text = ""
        self.displayed_phrase = ""
        self.opacity = 0.0
        self.offset_x = 0

    def set_text(self, text):
        self.current_text = text

    def show_random_phrase(self):
        if not self.current_text:
            return
        # Csak teljes szavak
        if not self.is_complete_word(self.current_text):
            return
        # 2-3 szó kinyerése
        words = self.current_text.split()[-3:]
        phrase = " ".join(words)
        self.displayed_phrase = f"„{phrase}""
        # Random pozíció (bal vagy jobb)
        # Fade animáció
        self.start_fade_animation()
```

---

## Fájlok Módosítása

| Fájl | Változtatás |
|------|-------------|
| `popup_window.py` | FloatingWordsWidget hozzáadása, ProcessingView módosítás |
| `whisper_gui.py` | Partial transcription callback, popup-nak átadás |
| `about_window.py` | ÚJ FÁJL - About ablak |
| `settings_window.py` | Tooltip szövegek |
| `translations.py` | Új fordítások |
| `assets/whisperrocket.png` | Ikon csere |

---

## Tesztelési Checklist

### Élő Transzkripció
- [ ] Megjelenik a felúszó szöveg feldolgozás közben
- [ ] 2.5 másodpercenként frissül
- [ ] Nem takarja a rakétát (bal/jobb oldalon jelenik meg)
- [ ] Magyar idézőjelek helyesek („szöveg")
- [ ] Fade animáció működik
- [ ] Nem jelenik meg félbevágott szó

### About Ablak
- [ ] Megnyílik a menüből
- [ ] Helyes verzió szám
- [ ] Helyes copyright
- [ ] Bezárható

### Settings Tooltipek
- [ ] Hotkey tooltip megjelenik
- [ ] Language tooltip megjelenik
- [ ] Magyar és angol fordítás

### Ikon
- [ ] System tray ikon frissült
- [ ] About ablakban helyes ikon

---

## Megjegyzések

- A fejlesztést Linux környezetben érdemes folytatni a megfelelő teszteléshez
- A faster-whisper partial transcription más API-t használ mint a WhisperKit
- A Python verzióban a Qt animációk máshogy működnek mint a SwiftUI-ban
