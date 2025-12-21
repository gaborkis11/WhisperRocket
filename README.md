# WhisperWarp

**Silent speech-to-text — Local, fast, private**

WhisperWarp is a desktop application that converts speech to text in real-time using the Whisper AI model. It runs entirely locally on your machine - no cloud services, no API keys, complete privacy.

## Features

- **Real-time transcription** - Whisper large-v3 model with multi-language support
- **GPU acceleration** - NVIDIA CUDA support for fast processing
- **Global hotkey** - Press Alt+S (configurable) anywhere to start/stop recording
- **Auto-paste** - Transcribed text is automatically pasted into the active window
- **Smart paste detection** - Automatically uses Ctrl+Shift+V for terminals
- **Visual feedback** - Modern popup with equalizer visualization during recording
- **Rocket animation** - Fun animated rocket with witty messages during processing
- **System tray** - Runs quietly in the background with color-coded status
- **Configurable** - Adjust language, model, hotkey, popup duration, and more

## Screenshots

| Recording | Processing | Result |
|-----------|------------|--------|
| Equalizer visualization | Rocket animation | Text preview |

## Requirements

- **OS**: Linux (Ubuntu/Debian recommended)
- **Python**: 3.10+
- **GPU**: NVIDIA GPU with CUDA support (recommended)
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

This will:
- Create a Python virtual environment
- Install all dependencies
- Download the Whisper model
- Set up the desktop launcher

### 3. Start the application

```bash
./start.sh
```

Or launch "WhisperWarp" from your application menu.

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
| Blue | Ready |
| Red | Recording |
| Yellow | Processing |
| Green | Done (text copied) |

## Configuration

Right-click the tray icon → **Settings** to configure:

- **Language** - Transcription language (Hungarian, English, German, etc.)
- **Hotkey** - Global shortcut key
- **Model** - Whisper model size (tiny, base, small, medium, large-v3)
- **Device** - GPU (CUDA) or CPU
- **Popup duration** - How long the result popup stays visible (1-30 seconds)
- **Autostart** - Launch on system startup

Configuration is stored in `config.json`.

## Dependencies

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Optimized Whisper implementation
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Audio recording
- [pynput](https://pynput.readthedocs.io/) - Global hotkey handling
- [pyperclip](https://pyperclip.readthedocs.io/) - Clipboard operations

## Project Structure

```
whisper-test/
├── whisper_gui.py        # Main application
├── popup_window.py       # Popup window (equalizer, rocket, text)
├── settings_window.py    # Settings dialog
├── model_manager.py      # Whisper model management
├── download_manager.py   # Model download handling
├── config.json           # User configuration
├── start.sh              # Startup script
├── install.sh            # Installation script
└── assets/               # Icons and sounds
```

## Troubleshooting

### No audio input
- Check your microphone permissions
- Verify the correct input device in system settings

### Slow transcription
- Ensure CUDA is properly installed
- Use a smaller model (small or medium) for faster results

### Hotkey not working
- Some desktop environments require accessibility permissions
- Try running with `sudo` once to register the hotkey

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - The amazing speech recognition model
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - CTranslate2-based Whisper implementation
- Inspired by [SuperWhisper](https://superwhisper.com/)
