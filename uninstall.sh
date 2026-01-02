#!/bin/bash

set -e  # Exit on error

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     WhisperRocket Uninstaller            ║"
echo "║     Removing installed components        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_found() { echo -e "${GREEN}[FOUND]${NC} $1"; }
log_removed() { echo -e "${RED}[REMOVED]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }

# Helper function to get directory size
get_size() {
    local path="$1"
    if [ -e "$path" ]; then
        du -sh "$path" 2>/dev/null | cut -f1
    else
        echo "0"
    fi
}

# Define paths
DESKTOP_LAUNCHER="$HOME/.local/share/applications/whisperrocket.desktop"
AUTOSTART_ENTRY="$HOME/.config/autostart/whisperrocket.desktop"
VENV_DIR="$(pwd)/venv"
CONFIG_DIR="$HOME/.config/whisperrocket"
CUDA_DIR="$HOME/.local/share/whisperrocket"
PROJECT_DIR="$(pwd)"

# =============================================================================
# 1. CHECK RUNNING INSTANCES
# =============================================================================
log_info "Checking for running WhisperRocket instances..."

if pgrep -f "whisper_gui.py" > /dev/null; then
    log_warn "WhisperRocket is currently running"
    read -p "Stop the application before uninstalling? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        pkill -f "whisper_gui.py" 2>/dev/null || true
        sleep 1
        log_ok "Application stopped"
    else
        log_warn "Continuing with uninstall while app is running (not recommended)"
    fi
else
    log_ok "No running instances found"
fi

# =============================================================================
# 2. SCAN INSTALLED COMPONENTS
# =============================================================================
echo ""
log_info "Scanning installed components..."
echo ""

components_found=0

# Desktop launcher
if [ -f "$DESKTOP_LAUNCHER" ]; then
    log_found "Desktop launcher: $DESKTOP_LAUNCHER"
    components_found=$((components_found+1))
fi

# Autostart entry
if [ -f "$AUTOSTART_ENTRY" ]; then
    log_found "Autostart entry: $AUTOSTART_ENTRY"
    components_found=$((components_found+1))
fi

# Virtual environment
if [ -d "$VENV_DIR" ]; then
    venv_size=$(get_size "$VENV_DIR")
    log_found "Virtual environment: $VENV_DIR ($venv_size)"
    components_found=$((components_found+1))
fi

# Configuration directory
if [ -d "$CONFIG_DIR" ]; then
    config_size=$(get_size "$CONFIG_DIR")
    log_found "Configuration: $CONFIG_DIR ($config_size)"
    components_found=$((components_found+1))
fi

# Downloaded models (WhisperRocket models directory)
WHISPERROCKET_MODELS_DIR="$HOME/.cache/huggingface/hub/whisperrocket_models"
models_size="0"
if [ -d "$WHISPERROCKET_MODELS_DIR" ]; then
    models_size=$(get_size "$WHISPERROCKET_MODELS_DIR")
    log_found "Downloaded models: $WHISPERROCKET_MODELS_DIR ($models_size)"
    components_found=$((components_found+1))
fi

# CUDA libraries
if [ -d "$CUDA_DIR" ]; then
    cuda_size=$(get_size "$CUDA_DIR")
    log_found "CUDA libraries: $CUDA_DIR ($cuda_size)"
    components_found=$((components_found+1))
fi

# CUDA bashrc entry
if grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc 2>/dev/null; then
    log_found "CUDA configuration in ~/.bashrc"
    components_found=$((components_found+1))
fi

echo ""

if [ $components_found -eq 0 ]; then
    log_ok "No WhisperRocket components found on this system"
    echo ""
    echo "The application may not have been installed, or has already been uninstalled."
    exit 0
fi

# =============================================================================
# 3. UNINSTALL MENU
# =============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  What would you like to remove?"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  1) Quick uninstall (launcher + venv only)"
echo "     Keeps: config, models, CUDA libraries"
echo ""
echo "  2) Full uninstall (everything)"
echo "     Removes: launcher, venv, config, models, CUDA"
echo ""
echo "  3) Custom (choose what to remove)"
echo ""
echo "  4) Cancel"
echo ""
read -p "Select option [1-4]: " choice

case $choice in
    1)
        MODE="quick"
        ;;
    2)
        MODE="full"
        ;;
    3)
        MODE="custom"
        ;;
    4)
        log_ok "Uninstall cancelled"
        exit 0
        ;;
    *)
        log_warn "Invalid option. Exiting."
        exit 1
        ;;
esac

# =============================================================================
# 4. CONFIRMATION FOR FULL UNINSTALL
# =============================================================================
if [ "$MODE" = "full" ]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  WARNING: FULL UNINSTALL                                     ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║  This will remove ALL WhisperRocket components including:    ║${NC}"
    echo -e "${RED}║    • Application launcher and autostart                      ║${NC}"
    echo -e "${RED}║    • Python virtual environment                              ║${NC}"
    echo -e "${RED}║    • Configuration files and settings                        ║${NC}"
    echo -e "${RED}║    • Downloaded AI models (~1-3GB)                           ║${NC}"
    echo -e "${RED}║    • CUDA libraries (if installed)                           ║${NC}"
    echo -e "${RED}║                                                              ║${NC}"
    echo -e "${RED}║  This action CANNOT be undone!                               ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    read -p "Type 'yes' to confirm full uninstall: " confirm
    if [ "$confirm" != "yes" ]; then
        log_warn "Uninstall cancelled (you must type 'yes' to confirm)"
        exit 0
    fi
fi

# =============================================================================
# 5. CUSTOM MODE - ASK WHAT TO REMOVE
# =============================================================================
remove_launcher=false
remove_venv=false
remove_config=false
remove_models=false
remove_cuda=false

if [ "$MODE" = "custom" ]; then
    echo ""
    log_info "Select components to remove:"
    echo ""

    if [ -f "$DESKTOP_LAUNCHER" ] || [ -f "$AUTOSTART_ENTRY" ]; then
        read -p "Remove desktop launcher and autostart? [Y/n] " -n 1 -r
        echo ""
        [[ ! $REPLY =~ ^[Nn]$ ]] && remove_launcher=true
    fi

    if [ -d "$VENV_DIR" ]; then
        read -p "Remove virtual environment ($venv_size)? [Y/n] " -n 1 -r
        echo ""
        [[ ! $REPLY =~ ^[Nn]$ ]] && remove_venv=true
    fi

    if [ -d "$CONFIG_DIR" ]; then
        read -p "Remove configuration files? [y/N] " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && remove_config=true
    fi

    if [ -d "$WHISPERROCKET_MODELS_DIR" ]; then
        read -p "Remove downloaded models ($models_size)? [y/N] " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && remove_models=true
    fi

    if [ -d "$CUDA_DIR" ] || grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc 2>/dev/null; then
        read -p "Remove CUDA libraries and configuration? [y/N] " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && remove_cuda=true
    fi

elif [ "$MODE" = "quick" ]; then
    remove_launcher=true
    remove_venv=true
    remove_config=false
    remove_models=false
    remove_cuda=false

elif [ "$MODE" = "full" ]; then
    remove_launcher=true
    remove_venv=true
    remove_config=true
    remove_models=true
    remove_cuda=true
fi

# =============================================================================
# 6. PERFORM UNINSTALL
# =============================================================================
echo ""
log_info "Starting uninstall..."
echo ""

# Remove desktop launcher and autostart
if [ "$remove_launcher" = true ]; then
    if [ -f "$DESKTOP_LAUNCHER" ]; then
        rm -f "$DESKTOP_LAUNCHER"
        log_removed "Desktop launcher removed"
    fi
    if [ -f "$AUTOSTART_ENTRY" ]; then
        rm -f "$AUTOSTART_ENTRY"
        log_removed "Autostart entry removed"
    fi
fi

# Remove virtual environment
if [ "$remove_venv" = true ] && [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    log_removed "Virtual environment removed"
fi

# Remove configuration
if [ "$remove_config" = true ] && [ -d "$CONFIG_DIR" ]; then
    rm -rf "$CONFIG_DIR"
    log_removed "Configuration directory removed"
fi

# Remove downloaded models
if [ "$remove_models" = true ] && [ -d "$WHISPERROCKET_MODELS_DIR" ]; then
    rm -rf "$WHISPERROCKET_MODELS_DIR"
    log_removed "Downloaded Whisper models removed"
fi

# Remove CUDA libraries and configuration
if [ "$remove_cuda" = true ]; then
    if [ -d "$CUDA_DIR" ]; then
        rm -rf "$CUDA_DIR"
        log_removed "CUDA libraries removed"
    fi

    if grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc 2>/dev/null; then
        # Remove the CUDA library path lines from .bashrc
        sed -i '/# WhisperRocket CUDA libraries/d' ~/.bashrc
        sed -i '/WHISPER_LD_LIBRARY_PATH/d' ~/.bashrc
        # Remove empty lines that might have been left
        sed -i '/^$/N;/^\n$/d' ~/.bashrc
        log_removed "CUDA configuration removed from ~/.bashrc"
    fi
fi

# =============================================================================
# 7. SUMMARY
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Uninstall complete!                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [ "$MODE" = "quick" ]; then
    echo "  Mode: Quick uninstall"
    echo ""
    echo "  Removed:"
    echo "    • Desktop launcher and autostart"
    echo "    • Python virtual environment"
    echo ""
    echo "  Preserved:"
    echo "    • Configuration files (can be removed manually from $CONFIG_DIR)"
    echo "    • Downloaded models (can be removed manually from $MODELS_DIR)"

elif [ "$MODE" = "full" ]; then
    echo "  Mode: Full uninstall"
    echo ""
    echo "  All WhisperRocket components have been removed from your system."

elif [ "$MODE" = "custom" ]; then
    echo "  Mode: Custom uninstall"
    echo ""
    echo "  Selected components have been removed."
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Project directory:"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  The project directory has NOT been removed:"
echo "    $PROJECT_DIR"
echo ""
echo "  To completely remove WhisperRocket, delete this directory manually:"
echo "    rm -rf $PROJECT_DIR"
echo ""

if [ "$remove_cuda" = true ] && grep -q "WHISPER_LD_LIBRARY_PATH" ~/.bashrc 2>/dev/null; then
    echo -e "${YELLOW}NOTE: CUDA configuration was removed from ~/.bashrc${NC}"
    echo "      Open a new terminal or run: source ~/.bashrc"
    echo ""
fi

log_ok "Uninstall process finished"
echo ""
