#!/usr/bin/env python3
"""
WhisperRocket - Config path resolution

Single source of truth for where config.json lives. Historically each module
resolved this on its own and they drifted apart, which meant the setup wizard
wrote to a file the app never read.

  - Source install (dev mode): <project>/config.json
  - Bundled app / AppImage:    ~/.config/whisperrocket/config.json

Secrets never live here - see secrets_manager.py.
"""
import os
import sys


def get_config_dir() -> str:
    """Directory holding config.json for the current runtime mode"""
    if getattr(sys, 'frozen', False):
        # Bundled app - the app directory is read-only, use the user config dir
        import platform as py_platform
        if py_platform.system() == "Darwin":
            config_dir = os.path.expanduser("~/Library/Application Support/WhisperRocket")
        else:
            config_dir = os.path.expanduser("~/.config/whisperrocket")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    # Dev mode - project directory
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path() -> str:
    """Full path to config.json for the current runtime mode"""
    return os.path.join(get_config_dir(), 'config.json')
