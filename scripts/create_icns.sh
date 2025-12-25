#!/bin/bash
# create_icns.sh - PNG to ICNS converter for WhisperRocket

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SOURCE="$PROJECT_DIR/assets/whisperrocket.png"
OUTPUT="$PROJECT_DIR/assets/whisperrocket.icns"
ICONSET_DIR="$PROJECT_DIR/WhisperRocket.iconset"

# Check source exists
if [ ! -f "$SOURCE" ]; then
    echo "ERROR: Source icon not found: $SOURCE"
    exit 1
fi

echo "Creating ICNS from: $SOURCE"

# Create iconset directory
mkdir -p "$ICONSET_DIR"

# Generate different sizes
sips -z 16 16     "$SOURCE" --out "$ICONSET_DIR/icon_16x16.png" 2>/dev/null
sips -z 32 32     "$SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png" 2>/dev/null
sips -z 32 32     "$SOURCE" --out "$ICONSET_DIR/icon_32x32.png" 2>/dev/null
sips -z 64 64     "$SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png" 2>/dev/null
sips -z 128 128   "$SOURCE" --out "$ICONSET_DIR/icon_128x128.png" 2>/dev/null
sips -z 256 256   "$SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" 2>/dev/null
sips -z 256 256   "$SOURCE" --out "$ICONSET_DIR/icon_256x256.png" 2>/dev/null
sips -z 512 512   "$SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" 2>/dev/null
sips -z 512 512   "$SOURCE" --out "$ICONSET_DIR/icon_512x512.png" 2>/dev/null
sips -z 1024 1024 "$SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png" 2>/dev/null

# Convert to ICNS
iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT"

# Cleanup
rm -rf "$ICONSET_DIR"

echo "Created: $OUTPUT"
