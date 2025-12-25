#!/bin/bash
#
# WhisperRocket - macOS Installer
# Optimized for Apple Silicon (M1/M2/M3)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "  WhisperRocket - macOS Installer"
echo "================================================"
echo ""

# System checks
echo "[1/5] Checking system requirements..."

# macOS check
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}ERROR: This script only runs on macOS!${NC}"
    exit 1
fi

# macOS version check (14.0+ required for MLX)
MACOS_VERSION=$(sw_vers -productVersion)
MACOS_MAJOR=$(echo "$MACOS_VERSION" | cut -d. -f1)
if [[ "$MACOS_MAJOR" -lt 14 ]]; then
    echo -e "${YELLOW}  ! macOS $MACOS_VERSION - MLX requires macOS 14.0+${NC}"
    echo "    Without MLX, only CPU support will be available."
else
    echo -e "${GREEN}  ✓ macOS $MACOS_VERSION${NC}"
fi

# Apple Silicon check
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo -e "${GREEN}  ✓ Apple Silicon ($ARCH) detected${NC}"
else
    echo -e "${YELLOW}  ! Intel Mac ($ARCH) - CPU only support${NC}"
fi

# Homebrew check
HAS_BREW=false
if command -v brew &> /dev/null; then
    echo -e "${GREEN}  ✓ Homebrew installed${NC}"
    HAS_BREW=true
else
    echo -e "${YELLOW}  ! Homebrew not installed${NC}"
fi

# Python version check
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11  # Minimum 3.11, recommended 3.12

# Find the best Python version
PYTHON_CMD=""
PYTHON_VERSION=""

# First try python3.12
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    PYTHON_VERSION="3.12"
# Then python3.11
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    PYTHON_VERSION="3.11"
# Finally generic python3
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
fi

if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "${RED}ERROR: Python 3 not found!${NC}"
    echo ""
    if [[ "$HAS_BREW" == true ]]; then
        echo "Install with Homebrew:"
        echo "  brew install python@3.12"
    else
        echo "Install Python 3.12: https://www.python.org/downloads/"
    fi
    exit 1
fi

# Version check
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt "$REQUIRED_PYTHON_MAJOR" ]] || \
   [[ "$PYTHON_MAJOR" -eq "$REQUIRED_PYTHON_MAJOR" && "$PYTHON_MINOR" -lt "$REQUIRED_PYTHON_MINOR" ]]; then
    echo -e "${RED}  ✗ Python $PYTHON_VERSION - version too old!${NC}"
    echo ""
    echo -e "${YELLOW}WhisperRocket requires Python 3.11+ (recommended: 3.12)${NC}"
    echo ""

    if [[ "$HAS_BREW" == true ]]; then
        echo "Would you like to install Python 3.12? (Homebrew)"
        read -p "[y/n]: " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Installing Python 3.12..."
            brew install python@3.12
            PYTHON_CMD="python3.12"
            PYTHON_VERSION="3.12"
            echo -e "${GREEN}  ✓ Python 3.12 installed${NC}"
        else
            echo "Please install manually: brew install python@3.12"
            exit 1
        fi
    else
        echo "Please install Python 3.12:"
        echo "  1. Homebrew: https://brew.sh then: brew install python@3.12"
        echo "  2. Or: https://www.python.org/downloads/"
        exit 1
    fi
else
    echo -e "${GREEN}  ✓ Python $PYTHON_VERSION ($PYTHON_CMD)${NC}"
fi

# ARM native Python check (important for MLX)
if [[ "$ARCH" == "arm64" ]]; then
    # Use 'file' command to check if Python binary is ARM native
    PYTHON_PATH=$(which $PYTHON_CMD)
    PYTHON_FILE_INFO=$(file "$PYTHON_PATH")
    if [[ "$PYTHON_FILE_INFO" != *"arm64"* ]]; then
        echo -e "${YELLOW}  ! Python running under Rosetta - MLX will not work${NC}"
        echo "    Install native ARM Python: brew install python@3.12"
    else
        echo -e "${GREEN}  ✓ Native ARM Python${NC}"
    fi
fi

echo ""

# Virtual environment
echo "[2/5] Creating virtual environment..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    echo "  Removing existing venv..."
    rm -rf "$VENV_DIR"
fi

# Create venv with the correct Python version
$PYTHON_CMD -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo -e "${GREEN}  ✓ venv created: $VENV_DIR${NC}"

echo ""

# Install dependencies
echo "[3/5] Installing dependencies..."
echo "  (This may take a few minutes...)"

pip install --upgrade pip wheel setuptools > /dev/null 2>&1

# macOS specific requirements
if [ -f "$SCRIPT_DIR/requirements-macos.txt" ]; then
    pip install -r "$SCRIPT_DIR/requirements-macos.txt"
else
    echo -e "${RED}ERROR: requirements-macos.txt not found!${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ Dependencies installed${NC}"

echo ""

# Create config directory
echo "[4/5] Creating config directory..."

CONFIG_DIR="$HOME/Library/Application Support/WhisperRocket"
mkdir -p "$CONFIG_DIR"
echo -e "${GREEN}  ✓ $CONFIG_DIR${NC}"

echo ""

# Create start script
echo "[5/5] Creating start script..."

START_SCRIPT="$SCRIPT_DIR/start_macos.sh"
cat > "$START_SCRIPT" << EOF
#!/bin/bash
SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
source "\$SCRIPT_DIR/venv/bin/activate"
cd "\$SCRIPT_DIR"
python whisper_gui.py
EOF

chmod +x "$START_SCRIPT"
echo -e "${GREEN}  ✓ start_macos.sh created${NC}"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "To start:"
echo -e "  ${YELLOW}./start_macos.sh${NC}"
echo ""
echo "IMPORTANT - Permissions:"
echo "  1. Accessibility: System Settings > Privacy & Security"
echo "     > Accessibility > Enable Terminal/iTerm"
echo ""
echo "  2. Microphone: The app will request access on first run"
echo ""
echo "Hotkey: Alt+S (default)"
echo ""
