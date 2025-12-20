#!/bin/bash

echo "======================================"
echo "Whisper Speech-to-Text Telepítő"
echo "======================================"
echo ""

# Rendszer csomagok
echo "[1/5] Rendszer csomagok telepítése..."
sudo apt update
sudo apt install -y python3-venv python3-dev portaudio19-dev xclip gir1.2-ayatanaappindicator3-0.1

# Virtual environment
echo "[2/5] Python környezet létrehozása..."
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Python csomagok
echo "[3/5] Python függőségek telepítése..."
pip install --upgrade pip
pip install --break-system-packages -r requirements.txt

# LD_LIBRARY_PATH beállítása .bashrc-be
echo "[4/5] CUDA könyvtárak beállítása..."
if ! grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Whisper Speech-to-Text CUDA libraries" >> ~/.bashrc
    echo "export LD_LIBRARY_PATH=\`python3 -c 'import nvidia.cudnn; print(nvidia.cudnn.__path__[0])' 2>/dev/null\`/lib:\`python3 -c 'import nvidia.cublas; print(nvidia.cublas.__path__[0])' 2>/dev/null\`/lib:\$LD_LIBRARY_PATH # WHISPER_LD_LIBRARY_PATH" >> ~/.bashrc
fi

# Desktop fájl telepítése (alkalmazás launcher)
echo "[5/5] Alkalmazás launcher telepítése..."
mkdir -p ~/.local/share/applications
cp whispertalk.desktop ~/.local/share/applications/
chmod +x start.sh
echo "WhisperTalk hozzáadva az alkalmazások menühöz"

echo ""
echo "======================================"
echo "Telepítés sikeres!"
echo "======================================"
echo ""
echo "Indítás:"
echo "  - Alkalmazások menüből: WhisperTalk"
echo "  - Terminálból: ./start.sh"
echo ""
