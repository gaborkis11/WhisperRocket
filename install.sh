#!/bin/bash

set -e  # Exit on error

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     WhisperRocket Installer              ║"
echo "║     Speech-to-Text for Linux             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# 1. DISTRIBUTION DETECTION
# =============================================================================
log_info "Detecting distribution..."

source "$(dirname "$(readlink -f "$0")")/install_lib.sh"

DISTRO=$(detect_distro_id)
PKG_MANAGER=$(detect_pkg_manager) || true

case $PKG_MANAGER in
    apt)    log_ok "Debian/Ubuntu-based system detected ($DISTRO)" ;;
    dnf)    log_ok "Fedora/RHEL-based system detected ($DISTRO)" ;;
    pacman) log_ok "Arch-based system detected ($DISTRO)" ;;
    zypper) log_ok "openSUSE system detected ($DISTRO)" ;;
    *)
        log_error "Unsupported distribution: $DISTRO (no apt/dnf/pacman/zypper found)"
        log_error "Install these dependencies manually, then re-run with your package"
        log_error "manager skipped: python3 + venv + pip, portaudio, xdotool, xclip,"
        log_error "pulseaudio-utils (and on Wayland: wtype, wl-clipboard, gtk-layer-shell)"
        exit 1
        ;;
esac

# =============================================================================
# 2. GPU DETECTION
# =============================================================================
log_info "Detecting GPU..."

GPU_TYPE="cpu"
HAS_NVIDIA=false

if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        GPU_TYPE="nvidia"
        HAS_NVIDIA=true
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        log_ok "NVIDIA GPU detected: $GPU_NAME"
    fi
fi

if [ "$GPU_TYPE" = "cpu" ]; then
    if lspci 2>/dev/null | grep -i "amd\|radeon" | grep -i "vga\|3d" &> /dev/null; then
        GPU_TYPE="amd"
        log_warn "AMD GPU detected - will run in CPU mode (AMD not supported for GPU acceleration)"
    elif lspci 2>/dev/null | grep -i "intel" | grep -i "vga\|graphics" &> /dev/null; then
        GPU_TYPE="intel"
        log_warn "Intel GPU detected - will run in CPU mode"
    else
        log_warn "No dedicated GPU found - will run in CPU mode"
    fi
fi

# =============================================================================
# 3. SYSTEM PACKAGES INSTALLATION
# =============================================================================
log_info "Installing system packages..."

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
        # -S --needed instead of -Syu: installing an app must not trigger a
        # full system upgrade (kernel/nvidia updates mid-session on Arch).
        if ! sudo pacman -S --needed --noconfirm \
            python \
            python-pip \
            portaudio \
            xdotool \
            xclip \
            libpulse \
            xcb-util-cursor; then
            log_error "pacman install failed. If packages were not found (404),"
            log_error "your package database is stale - run: sudo pacman -Syu"
            log_error "then re-run this installer."
            exit 1
        fi
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

log_ok "System packages installed"

# =============================================================================
# 4. WAYLAND/X11 DETECTION & INPUT GROUP
# =============================================================================
log_info "Detecting display server..."

SESSION_TYPE="${XDG_SESSION_TYPE:-unknown}"
NEEDS_RELOGIN=false

# Fallback detection if XDG_SESSION_TYPE is not set
if [ "$SESSION_TYPE" = "unknown" ]; then
    if [ -n "$WAYLAND_DISPLAY" ]; then
        SESSION_TYPE="wayland"
    elif [ -n "$DISPLAY" ]; then
        SESSION_TYPE="x11"
    fi
fi

if [ "$SESSION_TYPE" = "wayland" ]; then
    log_ok "Wayland session detected"
    log_info "Wayland requires 'input' group membership for global hotkeys"

    # Check if user is in input group
    if groups "$USER" | grep -q '\binput\b'; then
        log_ok "User is already in 'input' group"
    else
        log_warn "User is NOT in 'input' group"
        echo ""
        echo -e "${YELLOW}┌─────────────────────────────────────────────────────────────┐${NC}"
        echo -e "${YELLOW}│  WAYLAND HOTKEY SUPPORT                                     │${NC}"
        echo -e "${YELLOW}├─────────────────────────────────────────────────────────────┤${NC}"
        echo -e "${YELLOW}│  Wayland sessions require the user to be in the 'input'    │${NC}"
        echo -e "${YELLOW}│  group for global hotkey support.                          │${NC}"
        echo -e "${YELLOW}│                                                            │${NC}"
        echo -e "${YELLOW}│  Without this, the recording hotkey will NOT work.         │${NC}"
        echo -e "${YELLOW}└─────────────────────────────────────────────────────────────┘${NC}"
        echo ""
        read -p "Add user '$USER' to 'input' group? [Y/n] " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Nn]$ ]]; then
            log_warn "Skipping input group addition"
            log_warn "Hotkeys may not work on Wayland!"
        else
            sudo usermod -a -G input "$USER"
            if [ $? -eq 0 ]; then
                log_ok "User added to 'input' group"
                NEEDS_RELOGIN=true
            else
                log_error "Failed to add user to 'input' group"
                log_warn "You can manually run: sudo usermod -a -G input $USER"
            fi
        fi
    fi
elif [ "$SESSION_TYPE" = "x11" ]; then
    log_ok "X11 session detected (hotkeys will work without additional setup)"
else
    log_warn "Could not detect display server (SESSION_TYPE: $SESSION_TYPE)"
    log_warn "If hotkeys don't work, you may need to add yourself to the 'input' group:"
    log_warn "  sudo usermod -a -G input \$USER"
fi

# Install wtype (auto-paste) and wl-clipboard (clipboard copy via pyperclip)
if [ "$SESSION_TYPE" = "wayland" ]; then
    log_info "Installing wtype + wl-clipboard for Wayland paste/clipboard support..."
    case $PKG_MANAGER in
        apt)
            sudo apt install -y wtype wl-clipboard 2>/dev/null || log_warn "wtype/wl-clipboard not available in repos, auto-paste may not work"
            ;;
        dnf)
            sudo dnf install -y wtype wl-clipboard 2>/dev/null || log_warn "wtype/wl-clipboard not available in repos, auto-paste may not work"
            ;;
        pacman)
            sudo pacman -S --needed --noconfirm wtype wl-clipboard 2>/dev/null || log_warn "wtype/wl-clipboard not available in repos, auto-paste may not work"
            ;;
        zypper)
            sudo zypper install -y wtype wl-clipboard 2>/dev/null || log_warn "wtype/wl-clipboard not available in repos, auto-paste may not work"
            ;;
    esac

    # Install GTK Layer Shell + PyGObject runtime for the focus-free popup
    # overlay (wayland_overlay.py needs: gi, Gtk 3 typelib, GtkLayerShell
    # typelib, pycairo). The venv is created with --system-site-packages so
    # these system packages are visible to the app.
    log_info "Installing GTK Layer Shell for Wayland overlay support..."
    case $PKG_MANAGER in
        apt)
            sudo apt install -y gir1.2-gtklayershell-0.1 gir1.2-gtk-3.0 python3-gi python3-gi-cairo python3-cairo 2>/dev/null || log_warn "GTK Layer Shell not available, popup may steal focus"
            ;;
        dnf)
            sudo dnf install -y gtk-layer-shell gtk3 python3-gobject python3-cairo 2>/dev/null || log_warn "GTK Layer Shell not available, popup may steal focus"
            ;;
        pacman)
            sudo pacman -S --needed --noconfirm gtk-layer-shell gtk3 python-gobject python-cairo 2>/dev/null || log_warn "GTK Layer Shell not available, popup may steal focus"
            ;;
        zypper)
            sudo zypper install -y gtk-layer-shell typelib-1_0-GtkLayerShell-0_1 typelib-1_0-Gtk-3_0 python3-gobject python3-cairo 2>/dev/null || log_warn "GTK Layer Shell not available, popup may steal focus"
            ;;
    esac
fi

# Test hook: stop after system package phase (used by sandboxed installer tests)
if [ "${WR_INSTALL_STOP_AFTER:-}" = "packages" ]; then
    log_info "Stopping after package phase (WR_INSTALL_STOP_AFTER test hook)"
    exit 0
fi

# =============================================================================
# 5. PYTHON ENVIRONMENT
# =============================================================================
log_info "Creating Python virtual environment..."

# Remove old venv if exists
if [ -d "venv" ]; then
    rm -rf venv
fi

# --system-site-packages: the Wayland overlay needs the distro's PyGObject
# (gi) + GTK typelibs, which cannot come from pip. Pip-installed packages in
# the venv still take precedence over system ones.
python3 -m venv --system-site-packages venv
source venv/bin/activate

log_ok "Virtual environment created"

# =============================================================================
# 5. PYTHON PACKAGES
# =============================================================================
log_info "Installing Python packages..."

pip install --upgrade pip wheel setuptools
pip install -r requirements.txt

log_ok "Base Python packages installed"

# NVIDIA CUDA packages (only if NVIDIA GPU present)
if [ "$HAS_NVIDIA" = true ]; then
    log_info "Installing NVIDIA CUDA packages..."
    pip install -r requirements-cuda.txt
    log_ok "CUDA packages installed"
fi

# =============================================================================
# 7. CONFIGURATION
# =============================================================================
log_info "Setting up configuration..."

# Create/update config.json based on detected GPU
CONFIG_FILE="config.json"

if [ "$HAS_NVIDIA" = true ]; then
    DEVICE="cuda"
    COMPUTE_TYPE="float16"
else
    DEVICE="cpu"
    COMPUTE_TYPE="int8"
fi

# If no config.json exists, create it
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
    "popup_display_duration": 5,
    "ai_enhance_enabled": false,
    "ai_model": "sonnet",
    "ai_trigger_phrases": ["fogalmazzuk meg hogy", "fogalmazd meg hogy", "segíts megfogalmazni", "jarvis segíts megfogalmazni"],
    "ai_timeout_seconds": 120,
    "ai_dictionary_enabled": true
}
EOF
    log_ok "Configuration created ($DEVICE mode)"
else
    log_ok "Existing configuration preserved"
fi

# =============================================================================
# 8. CUDA LIBRARY PATH (NVIDIA only)
# =============================================================================
if [ "$HAS_NVIDIA" = true ]; then
    log_info "Setting up CUDA libraries..."

    if ! grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc 2>/dev/null; then
        cat >> ~/.bashrc << 'EOF'

# WhisperRocket CUDA libraries
export LD_LIBRARY_PATH=$(python3 -c 'import nvidia.cudnn; print(nvidia.cudnn.__path__[0])' 2>/dev/null)/lib:$(python3 -c 'import nvidia.cublas; print(nvidia.cublas.__path__[0])' 2>/dev/null)/lib:$LD_LIBRARY_PATH # WHISPER_LD_LIBRARY_PATH
EOF
        log_ok "CUDA path added to .bashrc"
    else
        log_ok "CUDA path already configured"
    fi
fi

# =============================================================================
# 9. APPLICATION LAUNCHER
# =============================================================================
log_info "Installing application launcher..."

# Dynamically generate .desktop file with installation path
INSTALL_DIR=$(pwd)

mkdir -p ~/.local/share/applications

cat > ~/.local/share/applications/whisperrocket.desktop << EOF
[Desktop Entry]
Type=Application
Name=WhisperRocket
Comment=Local Speech-to-Text with Whisper AI
Exec=$INSTALL_DIR/start.sh
Icon=$INSTALL_DIR/assets/icons/whisperrocket_ico.png
Terminal=false
Categories=AudioVideo;Audio;Utility;
StartupNotify=false
EOF

chmod +x start.sh

log_ok "Application added to menu"

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Installation complete!               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ "$HAS_NVIDIA" = true ]; then
    echo -e "  GPU mode:    ${GREEN}NVIDIA CUDA ($GPU_NAME)${NC}"
    echo "  Performance: Fast (GPU acceleration)"
else
    echo -e "  GPU mode:    ${YELLOW}CPU${NC}"
    echo "  Performance: Slower (no GPU acceleration)"
fi

echo ""
echo "  Launch:"
echo "    • From application menu: WhisperRocket"
echo "    • From terminal: ./start.sh"
echo ""
echo "  Default hotkey: Ctrl+Shift+S (configurable in Settings)"
echo ""

if [ "$HAS_NVIDIA" = true ]; then
    echo -e "${YELLOW}IMPORTANT: Open a new terminal or run:${NC}"
    echo "  source ~/.bashrc"
    echo ""
fi

# Wayland relogin warning
if [ "$NEEDS_RELOGIN" = true ]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  IMPORTANT: LOG OUT AND LOG BACK IN!                         ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║  You were added to the 'input' group for Wayland hotkey      ║${NC}"
    echo -e "${RED}║  support. This change requires you to LOG OUT and LOG BACK   ║${NC}"
    echo -e "${RED}║  IN (or restart your computer) before the hotkey will work.  ║${NC}"
    echo -e "${RED}║                                                              ║${NC}"
    echo -e "${RED}║  After logging back in, launch WhisperRocket from the menu   ║${NC}"
    echo -e "${RED}║  or run: ./start.sh                                          ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
fi
