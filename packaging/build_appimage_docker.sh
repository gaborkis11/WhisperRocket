#!/bin/bash
# Build the release AppImage inside an Ubuntu 24.04 container.
#
# Why a container: PyInstaller bundles against the build host's glibc, so an
# AppImage built on a rolling distro (Arch/Omarchy, glibc 2.44) would not start
# on Linux Mint or Ubuntu 24.04. Releases need at most GLIBC_2.39 - the
# Ubuntu 24.04 baseline every earlier release was built on.
#
# Why xvfb-run: pynput refuses to import without a display, and PyInstaller's
# pynput hook then silently drops pynput.mouse and the uinput/dummy backends -
# the AppImage would crash at start on X11.
#
# Only committed files are built (git archive), so personal files in the
# working tree (config.json, dictionaries, .env) can never end up inside.
#
# Usage:  packaging/build_appimage_docker.sh
# Output: dist/WhisperRocket-x86_64.AppImage and .zsync in the project root
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'docker run --rm -v "$WORK_DIR:/work" ubuntu:24.04 rm -rf /work/src >/dev/null 2>&1; rm -rf "$WORK_DIR"' EXIT

mkdir -p "$WORK_DIR/src"
git -C "$PROJECT_DIR" archive HEAD | tar -x -C "$WORK_DIR/src"

docker run --rm -v "$WORK_DIR:/work" ubuntu:24.04 bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip python3-dev binutils wget file zsync \
  xvfb xauth libportaudio2 libgtk-3-0 libjack-jackd2-0 libxcb-cursor0 libxcb-icccm4 \
  libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 \
  libxcb-xinerama0 libxkbcommon-x11-0 libegl1 libgl1 libfontconfig1 libdbus-1-3 \
  libglib2.0-0 >/dev/null
ln -sf /usr/bin/pip3 /usr/local/bin/pip
export APPIMAGE_EXTRACT_AND_RUN=1
cd /work/src
xvfb-run -a bash packaging/build_appimage.sh
chown -R '"$(id -u):$(id -g)"' /work/src/dist
'

mkdir -p "$PROJECT_DIR/dist"
cp "$WORK_DIR/src/dist/WhisperRocket-x86_64.AppImage" \
   "$WORK_DIR/src/dist/WhisperRocket-x86_64.AppImage.zsync" "$PROJECT_DIR/dist/"
echo "AppImage: $PROJECT_DIR/dist/WhisperRocket-x86_64.AppImage"
