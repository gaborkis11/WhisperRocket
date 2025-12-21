# WhisperWarp

**Silent speech-to-text — Local, fast, private**

WhisperWarp is a desktop application that converts speech to text in real-time using the Whisper AI model. It runs entirely locally on your machine - no cloud services, no API keys, complete privacy.

## Features

- **Real-time transcription** - Whisper large-v3 model with multi-language support
- **GPU acceleration** - NVIDIA CUDA support for fast processing (CPU fallback available)
- **Global hotkey** - Press Alt+S (configurable) anywhere to start/stop recording
- **Auto-paste** - Transcribed text is automatically pasted into the active window
- **Smart paste detection** - Automatically uses Ctrl+Shift+V for terminals
- **Visual feedback** - Modern popup with equalizer visualization during recording
- **Rocket animation** - Fun animated rocket with witty messages during processing
- **History** - Browse and copy previous transcriptions from the system tray
- **System tray** - Runs quietly in the background with color-coded status
- **Configurable** - Adjust language, model, hotkey, popup duration, and more

## Requirements

- **OS**: Linux (Ubuntu, Fedora, Arch, openSUSE, and derivatives)
- **Python**: 3.10+
- **GPU**: NVIDIA GPU with CUDA support (recommended) or CPU mode
- **RAM**: 8GB+ (16GB recommended for large-v3 model)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/gaborkis11/WhisperWarp.git
cd WhisperWarp
```

### 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The installer automatically:
- ✅ Detects your Linux distribution (Ubuntu, Fedora, Arch, openSUSE)
- ✅ Detects your GPU (NVIDIA CUDA / AMD / Intel / CPU-only)
- ✅ Installs all required system packages
- ✅ Creates Python virtual environment
- ✅ Installs Python dependencies (CUDA packages only if NVIDIA detected)
- ✅ Configures the application for your hardware
- ✅ Adds WhisperWarp to your application menu

### 3. Start the application

```bash
./start.sh
```

Or launch "WhisperWarp" from your application menu.

> **Note for NVIDIA users**: After installation, open a new terminal or run `source ~/.bashrc` before starting the application.

## GPU Support

| GPU Type | Mode | Performance |
|----------|------|-------------|
| NVIDIA (CUDA) | GPU accelerated | ⚡ Fast (~1-2s for 30s audio) |
| AMD / Intel | CPU fallback | 🐢 Slower (~10-15s for 30s audio) |
| No GPU | CPU mode | 🐢 Slower |

## Usage

1. **Start recording**: Press `Alt+S` (or your configured hotkey)
2. **Speak**: The popup shows an equalizer while recording
3. **Stop recording**: Press `Alt+S` again
4. **Processing**: Watch the rocket animation while Whisper transcribes
5. **Done**: Text is automatically pasted and shown in the popup

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Alt+S | Start/Stop recording |
| Escape | Cancel recording (discard) |

### System Tray Colors

| Color | Status |
|-------|--------|
| 🔵 Blue | Ready |
| 🔴 Red | Recording |
| 🟡 Yellow | Processing |
| 🟢 Green | Done (text copied) |

### History

Right-click the tray icon → **History** to:
- Browse previous transcriptions
- Click any entry to view full text
- Copy text to clipboard
- Clear history

History is stored locally (~/.config/whisperwarp/history.json) with a 100MB limit.

## Configuration

Right-click the tray icon → **Settings** to configure:

- **Language** - Transcription language (Hungarian, English, German, etc.)
- **Hotkey** - Global shortcut key
- **UI Language** - Interface language (English, Hungarian)
- **Model** - Whisper model size (tiny, base, small, medium, large-v3-turbo, large-v3)
- **Device** - GPU (CUDA) or CPU
- **Popup duration** - How long the result popup stays visible (1-30 seconds)
- **Autostart** - Launch on system startup

Configuration is stored in `config.json`.

## Dependencies

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized Whisper implementation
- [PySide6](https://wiki.qt.io/Qt_for_Python) - GUI framework (LGPL license)
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Audio recording
- [pynput](https://pynput.readthedocs.io/) - Global hotkey handling
- [pyperclip](https://pyperclip.readthedocs.io/) - Clipboard operations

## Project Structure

```
WhisperWarp/
├── whisper_gui.py        # Main application
├── popup_window.py       # Popup window (equalizer, rocket, text)
├── settings_window.py    # Settings dialog
├── history_manager.py    # History storage and management
├── history_viewer.py     # History entry viewer window
├── model_manager.py      # Whisper model management
├── download_manager.py   # Model download handling
├── translations.py       # Multi-language UI support (EN/HU)
├── config.json           # User configuration
├── start.sh              # Startup script
├── install.sh            # Installation script
├── requirements.txt      # Python dependencies
├── requirements-cuda.txt # NVIDIA CUDA dependencies
├── whisperwarp.desktop   # Linux desktop launcher
└── assets/               # Icons and sounds
```

## Supported Distributions

The installer has been tested on:
- Ubuntu 22.04+ / Linux Mint / Pop!_OS
- Fedora 38+
- Arch Linux / Manjaro
- openSUSE Tumbleweed

## Troubleshooting

### No audio input
- Check your microphone permissions
- Verify the correct input device in system settings

### Slow transcription
- Ensure CUDA is properly installed (NVIDIA only)
- Use a smaller model (small or medium) for faster results
- Check that GPU mode is enabled in settings

### Hotkey not working
- Some desktop environments require accessibility permissions
- Try running with `sudo` once to register the hotkey

### Wayland compatibility
- Auto-paste (`xdotool`) works best on X11
- On Wayland, use manual Ctrl+V to paste

## License

**Source Available License** - Free for personal, non-commercial use only.

You MAY:
- ✅ Use for personal purposes
- ✅ View and study the source code
- ✅ Report bugs and suggest features

You MAY NOT:
- ❌ Sell or distribute for payment
- ❌ Use commercially
- ❌ Create competing products

See [LICENSE](LICENSE) for full details. For commercial licensing, contact the author.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - The amazing speech recognition model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - CTranslate2-based Whisper implementation
