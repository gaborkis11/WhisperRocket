#!/bin/bash
# create_dmg.sh - Create DMG installer for WhisperRocket

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="WhisperRocket"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${VERSION}-macOS-arm64"
APP_PATH="$PROJECT_DIR/dist/${APP_NAME}.app"
DMG_PATH="$PROJECT_DIR/dist/${DMG_NAME}.dmg"
VOLUME_NAME="${APP_NAME} ${VERSION}"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: ${APP_PATH} not found!"
    echo "Run build first: ./scripts/build_macos.sh"
    exit 1
fi

# Cleanup previous DMG
TEMP_DMG="$PROJECT_DIR/dist/${DMG_NAME}-temp.dmg"
rm -f "$DMG_PATH" "$TEMP_DMG"

# Calculate DMG size (app size + 100MB buffer)
APP_SIZE=$(du -sm "$APP_PATH" | cut -f1)
DMG_SIZE=$((APP_SIZE + 100))

echo "Creating DMG (${DMG_SIZE}MB)..."

# Create empty DMG
hdiutil create -size ${DMG_SIZE}m -fs HFS+ -volname "${VOLUME_NAME}" "$TEMP_DMG"

# Mount
MOUNT_POINT="/Volumes/${VOLUME_NAME}"
hdiutil attach "$TEMP_DMG" -mountpoint "$MOUNT_POINT"

# Copy app
echo "Copying app to DMG..."
cp -R "$APP_PATH" "$MOUNT_POINT/"

# Create Applications symlink
ln -s /Applications "$MOUNT_POINT/Applications"

# Unmount
hdiutil detach "$MOUNT_POINT"

# Convert to compressed DMG
echo "Compressing DMG..."
hdiutil convert "$TEMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG_PATH"

# Cleanup
rm -f "$TEMP_DMG"

echo ""
echo "============================================"
echo "  DMG Created Successfully!"
echo "============================================"
echo "  File: $DMG_PATH"
echo "  Size: $(du -h "$DMG_PATH" | cut -f1)"
echo "============================================"
