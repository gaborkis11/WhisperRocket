#!/bin/bash

echo "======================================"
echo "Whisper Speech-to-Text Telepítő"
echo "======================================"
echo ""

# Rendszer csomagok
echo "[1/4] Rendszer csomagok telepítése..."
sudo apt update
sudo apt install -y python3-venv python3-dev portaudio19-dev xclip

# Virtual environment
echo "[2/4] Python környezet létrehozása..."
python3 -m venv venv
source venv/bin/activate

# Python csomagok
echo "[3/4] Python függőségek telepítése..."
pip install --upgrade pip
pip install --break-system-packages -r requirements.txt

# LD_LIBRARY_PATH beállítása .bashrc-be
echo "[4/4] CUDA könyvtárak beállítása..."
if ! grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Whisper Speech-to-Text CUDA libraries" >> ~/.bashrc
    echo "export LD_LIBRARY_PATH=\`python3 -c 'import nvidia.cudnn; print(nvidia.cudnn.__path__[0])' 2>/dev/null\`/lib:\`python3 -c 'import nvidia.cublas; print(nvidia.cublas.__path__[0])' 2>/dev/null\`/lib:\$LD_LIBRARY_PATH # WHISPER_LD_LIBRARY_PATH" >> ~/.bashrc
fi

echo ""
echo "======================================"
echo "✅ Telepítés sikeres!"
echo "======================================"
echo ""
echo "Indítás: ./start.sh"
echo ""
