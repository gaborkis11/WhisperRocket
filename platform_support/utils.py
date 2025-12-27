"""
WhisperRocket - Platform Detection Utilities
Platform detektálás és handler factory (Linux verzió)
"""

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import PlatformHandler


def get_platform() -> str:
    """Aktuális platform detektálása

    Returns:
        "linux" vagy "unknown"
    """
    if sys.platform == 'linux':
        return 'linux'
    return 'unknown'


def get_platform_handler() -> "PlatformHandler":
    """Platform handler factory

    Returns:
        LinuxHandler instance

    Raises:
        NotImplementedError: Ha a platform nem Linux
    """
    platform = get_platform()

    if platform == 'linux':
        from .linux import LinuxHandler
        return LinuxHandler()
    else:
        raise NotImplementedError(f"This version only supports Linux. Detected: {sys.platform}")
