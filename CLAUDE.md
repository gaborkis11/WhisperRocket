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

- **Valós idejű beszédfelismerés** - Whisper large-v3 modell, magyar nyelv támogatás
- **GPU gyorsítás** - NVIDIA CUDA támogatás (float16)
- **Hotkey vezérlés** - Alt+S a rögzítés indítása/leállítása
- **Automatikus beillesztés** - Felismert szöveg automatikusan beillesztésre kerül
- **Smart paste** - Terminál/Cursor detektálás (Ctrl+Shift+V vs Ctrl+V)
- **System Tray ikon** - Vizuális visszajelzés a státuszról

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
├── whisper_gui.py      # Fő alkalmazás (System Tray verzió)
├── whisper_app.py      # CLI verzió
├── config.json         # Konfiguráció (hotkey, modell, nyelv)
├── start.sh            # Indító script (CUDA env beállítás)
├── install.sh          # Telepítő script
├── requirements.txt    # Python függőségek
├── tasks/              # Todo és tervek
│   └── todo.md
└── CLAUDE.md           # Ez a fájl
```

### Konfiguráció (config.json)

```json
{
  "hotkey": "alt+s",
  "model": "large-v3",
  "device": "cuda",
  "compute_type": "float16",
  "language": "hu",
  "sample_rate": 16000
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

- [ ] Popup ablak hullámforma vizualizációval (SuperWhisper stílusú)
- [ ] System Tray menü (jobb klikk → Settings, Quit)
- [ ] Modern beállítások UI
- [ ] Telepíthető alkalmazás (.desktop fájl, ikon)
- [ ] Cross-platform támogatás (Windows, macOS)
