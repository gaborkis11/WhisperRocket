#!/bin/bash

set -e  # Hiba esetén leállás

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     WhisperRocket Telepítő                 ║"
echo "║     Speech-to-Text for Linux             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Színek
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Segédfüggvények
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[FIGYELEM]${NC} $1"; }
log_error() { echo -e "${RED}[HIBA]${NC} $1"; }

# =============================================================================
# 1. DISZTRIBÚCIÓ DETEKTÁLÁS
# =============================================================================
log_info "Disztribúció detektálása..."

DISTRO="unknown"
PKG_MANAGER=""

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
fi

case $DISTRO in
    ubuntu|debian|linuxmint|pop|elementary|zorin)
        PKG_MANAGER="apt"
        log_ok "Ubuntu/Debian alapú rendszer detektálva ($DISTRO)"
        ;;
    fedora|rhel|centos|rocky|almalinux)
        PKG_MANAGER="dnf"
        log_ok "Fedora/RHEL alapú rendszer detektálva ($DISTRO)"
        ;;
    arch|manjaro|endeavouros|garuda)
        PKG_MANAGER="pacman"
        log_ok "Arch alapú rendszer detektálva ($DISTRO)"
        ;;
    opensuse*|suse)
        PKG_MANAGER="zypper"
        log_ok "openSUSE rendszer detektálva ($DISTRO)"
        ;;
    *)
        log_warn "Ismeretlen disztribúció: $DISTRO"
        log_warn "Megpróbáljuk apt-tal..."
        PKG_MANAGER="apt"
        ;;
esac

# =============================================================================
# 2. GPU DETEKTÁLÁS
# =============================================================================
log_info "GPU detektálása..."

GPU_TYPE="cpu"
HAS_NVIDIA=false

if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        GPU_TYPE="nvidia"
        HAS_NVIDIA=true
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        log_ok "NVIDIA GPU detektálva: $GPU_NAME"
    fi
fi

if [ "$GPU_TYPE" = "cpu" ]; then
    if lspci 2>/dev/null | grep -i "amd\|radeon" | grep -i "vga\|3d" &> /dev/null; then
        GPU_TYPE="amd"
        log_warn "AMD GPU detektálva - CPU módban fog futni (AMD nincs támogatva GPU gyorsításhoz)"
    elif lspci 2>/dev/null | grep -i "intel" | grep -i "vga\|graphics" &> /dev/null; then
        GPU_TYPE="intel"
        log_warn "Intel GPU detektálva - CPU módban fog futni"
    else
        log_warn "Nem található dedikált GPU - CPU módban fog futni"
    fi
fi

# =============================================================================
# 3. RENDSZER CSOMAGOK TELEPÍTÉSE
# =============================================================================
log_info "Rendszer csomagok telepítése..."

case $PKG_MANAGER in
    apt)
        sudo apt update
        sudo apt install -y \
            python3 \
            python3-venv \
            python3-dev \
            python3-pip \
            portaudio19-dev \
            libportaudio2 \
            xdotool \
            xclip \
            pulseaudio-utils \
            libxcb-cursor0
        ;;
    dnf)
        sudo dnf install -y \
            python3 \
            python3-devel \
            python3-pip \
            portaudio-devel \
            xdotool \
            xclip \
            pulseaudio-utils \
            xcb-util-cursor
        ;;
    pacman)
        sudo pacman -Syu --noconfirm \
            python \
            python-pip \
            portaudio \
            xdotool \
            xclip \
            libpulse \
            xcb-util-cursor
        ;;
    zypper)
        sudo zypper install -y \
            python3 \
            python3-devel \
            python3-pip \
            portaudio-devel \
            xdotool \
            xclip \
            pulseaudio-utils
        ;;
esac

log_ok "Rendszer csomagok telepítve"

# =============================================================================
# 4. PYTHON KÖRNYEZET
# =============================================================================
log_info "Python virtuális környezet létrehozása..."

# Régi venv törlése ha létezik
if [ -d "venv" ]; then
    rm -rf venv
fi

python3 -m venv venv
source venv/bin/activate

log_ok "Virtuális környezet létrehozva"

# =============================================================================
# 5. PYTHON CSOMAGOK
# =============================================================================
log_info "Python csomagok telepítése..."

pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

log_ok "Alap Python csomagok telepítve"

# NVIDIA CUDA csomagok (csak ha van NVIDIA GPU)
if [ "$HAS_NVIDIA" = true ]; then
    log_info "NVIDIA CUDA csomagok telepítése..."
    pip install -r requirements-cuda.txt
    log_ok "CUDA csomagok telepítve"
fi

# =============================================================================
# 6. KONFIGURÁCIÓ
# =============================================================================
log_info "Konfiguráció beállítása..."

# config.json létrehozása/frissítése a detektált GPU alapján
CONFIG_FILE="config.json"

if [ "$HAS_NVIDIA" = true ]; then
    DEVICE="cuda"
    COMPUTE_TYPE="float16"
else
    DEVICE="cpu"
    COMPUTE_TYPE="int8"
fi

# Ha nincs config.json, létrehozzuk
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" << EOF
{
    "hotkey": "ctrl+shift+s",
    "model": "large-v3",
    "device": "$DEVICE",
    "compute_type": "$COMPUTE_TYPE",
    "language": "hu",
    "ui_language": "hu",
    "sample_rate": 16000,
    "input_device": null,
    "output_device": null,
    "popup_display_duration": 5
}
EOF
    log_ok "Konfiguráció létrehozva ($DEVICE mód)"
else
    log_ok "Meglévő konfiguráció megtartva"
fi

# =============================================================================
# 7. CUDA LIBRARY PATH (csak NVIDIA)
# =============================================================================
if [ "$HAS_NVIDIA" = true ]; then
    log_info "CUDA könyvtárak beállítása..."

    if ! grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc 2>/dev/null; then
        cat >> ~/.bashrc << 'EOF'

# WhisperRocket CUDA libraries
export LD_LIBRARY_PATH=$(python3 -c 'import nvidia.cudnn; print(nvidia.cudnn.__path__[0])' 2>/dev/null)/lib:$(python3 -c 'import nvidia.cublas; print(nvidia.cublas.__path__[0])' 2>/dev/null)/lib:$LD_LIBRARY_PATH # WHISPER_LD_LIBRARY_PATH
EOF
        log_ok "CUDA path hozzáadva a .bashrc-hez"
    else
        log_ok "CUDA path már beállítva"
    fi
fi

# =============================================================================
# 8. ALKALMAZÁS LAUNCHER
# =============================================================================
log_info "Alkalmazás launcher telepítése..."

# Frissítjük a desktop fájlban az útvonalat
INSTALL_DIR=$(pwd)
sed -i "s|Exec=.*|Exec=$INSTALL_DIR/start.sh|g" whisperrocket.desktop
sed -i "s|Icon=.*|Icon=$INSTALL_DIR/assets/whisperrocket.png|g" whisperrocket.desktop
sed -i "s|Path=.*|Path=$INSTALL_DIR|g" whisperrocket.desktop

mkdir -p ~/.local/share/applications
cp whisperrocket.desktop ~/.local/share/applications/
chmod +x start.sh

log_ok "Alkalmazás hozzáadva a menühöz"

# =============================================================================
# ÖSSZEFOGLALÓ
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Telepítés sikeres!                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ "$HAS_NVIDIA" = true ]; then
    echo -e "  GPU mód:     ${GREEN}NVIDIA CUDA ($GPU_NAME)${NC}"
    echo "  Teljesítmény: Gyors (GPU gyorsítás)"
else
    echo -e "  GPU mód:     ${YELLOW}CPU${NC}"
    echo "  Teljesítmény: Lassabb (nincs GPU gyorsítás)"
fi

echo ""
echo "  Indítás:"
echo "    • Alkalmazások menüből: WhisperRocket"
echo "    • Terminálból: ./start.sh"
echo ""
echo "  Hotkey: Ctrl+Shift+S (nyomva tartás = felvétel)"
echo ""

if [ "$HAS_NVIDIA" = true ]; then
    echo -e "${YELLOW}FONTOS: Indíts új terminált vagy futtasd:${NC}"
    echo "  source ~/.bashrc"
    echo ""
fi
