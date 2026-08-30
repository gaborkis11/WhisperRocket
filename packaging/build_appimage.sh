#!/bin/bash
# WhisperRocket AppImage Build Script
set -e

echo "========================================="
echo "  WhisperRocket AppImage Builder"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Project root
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="$PROJECT_DIR/packaging"
BUILD_DIR="$PROJECT_DIR/build_appimage"
DIST_DIR="$PROJECT_DIR/dist"

echo -e "${GREEN}[1/8]${NC} Checking dependencies..."

# Check required tools
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}ERROR:${NC} python3 not found!"; exit 1; }
command -v pip >/dev/null 2>&1 || { echo -e "${RED}ERROR:${NC} pip not found!"; exit 1; }

echo -e "${GREEN}[2/8]${NC} Creating build environment..."

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo -e "${GREEN}[3/8]${NC} Setting up virtual environment..."

# Create venv
python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}[4/8]${NC} Installing dependencies (without CUDA)..."

# Install dependencies WITHOUT CUDA libraries
pip install --upgrade pip
pip install pyinstaller

# Install requirements (base only - no CUDA wheels)
cd "$PROJECT_DIR"
pip install faster-whisper sounddevice soundfile pyperclip pynput pillow numpy PySide6 requests evdev huggingface_hub

echo -e "${GREEN}[5/8]${NC} Running PyInstaller..."

# Run PyInstaller with our spec
pyinstaller "$PACKAGING_DIR/whisperrocket.spec" --clean --noconfirm

echo -e "${GREEN}[6/8]${NC} Building AppDir structure..."

# Create AppDir
APPDIR="$BUILD_DIR/WhisperRocket.AppDir"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller output
cp -r "$PROJECT_DIR/dist/whisperrocket/"* "$APPDIR/usr/bin/"

# Copy desktop file
cp "$PACKAGING_DIR/whisperrocket.desktop" "$APPDIR/usr/share/applications/"
cp "$PACKAGING_DIR/whisperrocket.desktop" "$APPDIR/"

# Copy icon
ICON_SOURCE="$PROJECT_DIR/assets/icons/whisperrocket_ico.png"
if [ -f "$ICON_SOURCE" ]; then
    cp "$ICON_SOURCE" "$APPDIR/usr/share/icons/hicolor/256x256/apps/whisperrocket.png"
    cp "$ICON_SOURCE" "$APPDIR/whisperrocket.png"
else
    echo -e "${YELLOW}WARNING:${NC} Icon not found at $ICON_SOURCE"
fi

# Copy AppRun
cp "$PACKAGING_DIR/AppRun" "$APPDIR/"
chmod +x "$APPDIR/AppRun"

echo -e "${GREEN}[7/8]${NC} Downloading appimagetool..."

# Download appimagetool if not present
APPIMAGETOOL="$BUILD_DIR/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    wget -O "$APPIMAGETOOL" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

echo -e "${GREEN}[8/8]${NC} Creating AppImage..."

# Create AppImage with embedded update information so AppImageUpdate (and
# the in-app self-updater's zsync-aware cousins) can find new releases. The
# .zsync file it produces must be uploaded to the GitHub release next to the
# AppImage. If appimagetool cannot embed it (no zsyncmake), fall back to a
# plain build - never leave the release broken.
mkdir -p "$DIST_DIR"
UPDATE_INFO="gh-releases-zsync|gaborkis11|WhisperRocket|latest|WhisperRocket-x86_64.AppImage.zsync"
cd "$DIST_DIR"  # appimagetool writes the .zsync into the current directory
if ARCH=x86_64 "$APPIMAGETOOL" -u "$UPDATE_INFO" "$APPDIR" "$DIST_DIR/WhisperRocket-x86_64.AppImage"; then
    if [ -f "$DIST_DIR/WhisperRocket-x86_64.AppImage.zsync" ]; then
        echo -e "${GREEN}Update info embedded; .zsync generated - upload BOTH files to the release${NC}"
    else
        echo -e "${YELLOW}WARNING: update info embedded but no .zsync produced${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: appimagetool failed with -u (zsyncmake missing?); building WITHOUT update info${NC}"
    ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$DIST_DIR/WhisperRocket-x86_64.AppImage"
fi
cd "$PROJECT_DIR"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  AppImage created successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "Output: ${YELLOW}$DIST_DIR/WhisperRocket-x86_64.AppImage${NC}"
echo ""
echo "Size: $(du -h "$DIST_DIR/WhisperRocket-x86_64.AppImage" | cut -f1)"
echo ""
echo "To test:"
echo "  chmod +x $DIST_DIR/WhisperRocket-x86_64.AppImage"
echo "  $DIST_DIR/WhisperRocket-x86_64.AppImage"
echo ""
