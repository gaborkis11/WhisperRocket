"""
WhisperRocket - Platform Abstraction Module
Platform-specifikus műveletek absztrakciója
"""

from .utils import get_platform, get_platform_handler

__all__ = ['get_platform', 'get_platform_handler']
