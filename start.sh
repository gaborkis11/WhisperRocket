#!/bin/bash
cd ~/whisper-test
source venv/bin/activate
export LD_LIBRARY_PATH=`python -c 'import nvidia.cudnn; print(nvidia.cudnn.__path__[0])'`/lib:`python -c 'import nvidia.cublas; print(nvidia.cublas.__path__[0])'`/lib:$LD_LIBRARY_PATH
nohup python whisper_gui.py > /dev/null 2>&1 &
echo "Whisper Speech-to-Text elindítva háttérben!"
echo "Tray ikon megjelenik a taskbar-on."
