#!/bin/bash
# A script saját könyvtárának meghatározása (bárhonnan hívható)
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
cd "$SCRIPT_DIR"

# Ellenőrzés: fut-e már az alkalmazás
if pgrep -f "python whisper_gui.py" > /dev/null; then
    echo "WhisperRocket már fut!"
    exit 0
fi

source venv/bin/activate
export LD_LIBRARY_PATH=`python -c 'import nvidia.cudnn; print(nvidia.cudnn.__path__[0])'`/lib:`python -c 'import nvidia.cublas; print(nvidia.cublas.__path__[0])'`/lib:$LD_LIBRARY_PATH
PYTHONUNBUFFERED=1 nohup python whisper_gui.py > /tmp/whisper_stdout.log 2>&1 &
echo "Whisper Speech-to-Text elindítva háttérben!"
echo "Tray ikon megjelenik a taskbar-on."
