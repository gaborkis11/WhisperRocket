# PyInstaller runtime hook: let sounddevice find the PortAudio bundled in the
# AppImage.
#
# sounddevice looks PortAudio up with ctypes.util.find_library('portaudio'),
# which only searches the system (ldconfig cache, gcc, ld) - never the
# PyInstaller bundle. On a system without libportaudio2 installed the app died
# at import with "OSError: PortAudio library not found", although the library
# was right there in _internal/. A system PortAudio still wins when there is
# one, so machines that already worked keep using the same library.
import ctypes.util
import os
import sys

_bundled = os.path.join(getattr(sys, "_MEIPASS", ""), "libportaudio.so.2")

if os.path.exists(_bundled):
    _system_find_library = ctypes.util.find_library

    def _find_library(name):
        found = _system_find_library(name)
        if found is None and name == "portaudio":
            return _bundled
        return found

    ctypes.util.find_library = _find_library
