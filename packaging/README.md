# WhisperRocket AppImage Packaging

This directory contains scripts and configuration for building a WhisperRocket AppImage.

## Smart AppImage Architecture

The AppImage is built **WITHOUT** CUDA libraries to keep the size small (~150-200MB instead of ~1GB+).

### How it works:

1. **First Run**: AppImage detects NVIDIA GPU
2. **CUDA Download**: Automatically downloads CUDA libraries (~900MB) to `~/.local/share/whisperrocket/cuda_libs/`
3. **Runtime**: Uses downloaded CUDA libraries via `LD_LIBRARY_PATH`

### Benefits:

- Small AppImage size
- Shared CUDA libraries between updates
- CPU-only systems don't download unnecessary files
- Works with normal `install.sh` installation (unchanged)

## Files

- `AppRun` - Entry point script for AppImage
- `whisperrocket.desktop` - Desktop entry file
- `whisperrocket.spec` - PyInstaller specification
- `build_appimage.sh` - Build script
- `build_appimage_docker.sh` - Release build in an Ubuntu 24.04 container
- `rthook_portaudio.py` - Runtime hook that lets sounddevice find the bundled PortAudio

## Building

Release builds go through Docker, so the AppImage runs on Linux Mint and Ubuntu 24.04
whatever distro it is built on (needs Docker and membership in the `docker` group):

```bash
packaging/build_appimage_docker.sh
```

It builds only committed files (`git archive HEAD`) - commit first. The container is
Ubuntu 24.04 (glibc 2.39, the baseline of every release) and runs the build under
`xvfb-run`, because without a display PyInstaller drops part of pynput.

A local build on the current machine (fine for testing, not for a release built on a
newer distro):

```bash
cd packaging
./build_appimage.sh
```

The build host needs `libportaudio2`: PyInstaller only bundles PortAudio when it is
installed, and the build stops with an error otherwise.

Output: `dist/WhisperRocket-x86_64.AppImage`

## Requirements

- Python 3.10+
- pip
- Internet connection (for appimagetool download)

## Testing

```bash
chmod +x ../dist/WhisperRocket-x86_64.AppImage
../dist/WhisperRocket-x86_64.AppImage
```

## Notes

- CUDA libraries are excluded from the AppImage (see `whisperrocket.spec`)
- The `install.sh` installation method remains unchanged
- First run on NVIDIA systems will trigger CUDA download via Setup Wizard
