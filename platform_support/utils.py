"""
WhisperRocket - Platform Detection Utilities
Platform detektálás és handler factory
"""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import PlatformHandler


def get_platform() -> str:
    """Aktuális platform detektálása

    Returns:
        "macos", "linux", "windows", vagy "unknown"
    """
    if sys.platform == 'darwin':
        return 'macos'
    elif sys.platform == 'linux':
        return 'linux'
    elif sys.platform == 'win32':
        return 'windows'
    return 'unknown'


def get_platform_handler() -> "PlatformHandler":
    """Platform handler factory

    Returns:
        Platform-specifikus PlatformHandler instance

    Raises:
        NotImplementedError: Ha a platform nem támogatott
    """
    platform = get_platform()

    if platform == 'macos':
        from .macos import MacOSHandler
        return MacOSHandler()
    elif platform == 'linux':
        from .linux import LinuxHandler
        return LinuxHandler()
    else:
        raise NotImplementedError(f"Platform not supported: {platform}")
