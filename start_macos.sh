#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# macOS-en sudo szükséges a keyboard figyeléshez
echo "WhisperRocket indítása (sudo szükséges a hotkey működéshez)..."
sudo "$SCRIPT_DIR/venv/bin/python" whisper_gui.py
