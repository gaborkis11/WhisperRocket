#!/bin/bash
# build_macos.sh - Build WhisperRocket macOS app and DMG

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  WhisperRocket macOS Build"
echo "============================================"
echo ""

cd "$PROJECT_DIR"

# Check we're in the right directory
if [ ! -f "whisper_gui.py" ]; then
    echo "ERROR: Run from project root!"
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    echo "[INFO] Activating virtual environment..."
    source venv/bin/activate
else
    echo "ERROR: venv not found! Run install_macos.sh first."
    exit 1
fi

# Check PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "[INFO] Installing PyInstaller..."
    pip install pyinstaller
fi

# Step 1: Create icon
echo ""
echo "[1/4] Creating app icon..."
"$SCRIPT_DIR/create_icns.sh"

# Step 2: Build with PyInstaller
echo ""
echo "[2/4] Building with PyInstaller..."
echo "      This may take a few minutes..."
pyinstaller WhisperRocket.spec --clean --noconfirm

# Step 3: Ad-hoc code signing
echo ""
echo "[3/4] Code signing (ad-hoc)..."
codesign --force --deep --sign - "dist/WhisperRocket.app"

# Step 4: Create DMG
echo ""
echo "[4/4] Creating DMG..."
"$SCRIPT_DIR/create_dmg.sh"

echo ""
echo "============================================"
echo "  Build Complete!"
echo "============================================"
echo ""
echo "  App:  dist/WhisperRocket.app"
echo "  DMG:  dist/WhisperRocket-1.0.0-macOS-arm64.dmg"
echo ""
echo "  To test:"
echo "    open dist/WhisperRocket.app"
echo ""
echo "  To install:"
echo "    open dist/WhisperRocket-1.0.0-macOS-arm64.dmg"
echo "    Drag WhisperRocket to Applications"
echo ""
echo "============================================"
