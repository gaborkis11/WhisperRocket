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

## Building

```bash
cd packaging
./build_appimage.sh
```

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
