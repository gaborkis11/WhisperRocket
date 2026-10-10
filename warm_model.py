#!/usr/bin/env python3
"""
WhisperRocket - The Whisper model, loaded when needed and let go when idle.

Why (2026-10-10): a loaded large-v3 sits on about 4 GB of VRAM for as long as
the app runs, dictation or not. On a 16 GB card that was enough to freeze a game
running next to it. So the model now leaves the GPU after IDLE_RELEASE_SECONDS
without a dictation and comes back on the next one - measured on an RTX 5070 Ti:
3978 MiB down to 224 MiB (the CUDA context, which stays until the process
exits), and 0.8-0.9 s extra on a dictation that finds it released.

Every user of the model - the hotkey, the phone endpoint, file transcription -
goes through WarmModel.use(). It holds the lock for the whole use, so the idle
release can never pull the model out from under a running transcription, and a
load and a release can never overlap.

Stdlib only: the tests drive it with a fake loader and a fake clock.
"""
import gc
import sys
import threading
import time
from contextlib import contextmanager
from typing import Callable, Optional

# Ten seconds after the last use the model leaves the GPU. Not a setting: it
# is how the app behaves (the user's call, 2026-10-10). Five minutes came
# first; the reload measured 0.8-0.9 s in real dictations, too cheap to be
# worth keeping 4 GB of VRAM taken between them. Ten seconds rather than
# zero keeps the model for a quick follow-up dictation.
IDLE_RELEASE_SECONDS = 10

# How often the background thread looks at the clock: the release lands
# within this much after the idle time is up. A lock test and a subtraction
# every two seconds cost nothing.
IDLE_CHECK_SECONDS = 2


def free_gpu_cache():
    """
    Hand cached GPU memory back to the driver.

    faster-whisper (CTranslate2) frees its VRAM once the model object is gone,
    so gc.collect() is enough for it. torch keeps a cache of its own - it is
    only here when speaker diarization (pyannote) ran - and needs
    empty_cache(). torch is never imported just for this: importing it would
    create a CUDA context and cost the very memory we are trying to give back.
    """
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is None:
        return
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:
        print(f"[MODEL] torch cache not emptied: {e}")


class WarmModel:
    """
    One model, shared by every caller, on the GPU only while it is being used.

    `loader` builds and returns the model; it is called with the lock held,
    on whichever thread first needs the model.
    """

    def __init__(self, loader: Callable[[], object],
                 idle_seconds: float = IDLE_RELEASE_SECONDS,
                 clock: Callable[[], float] = time.monotonic):
        self._loader = loader
        self._idle_seconds = idle_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._model = None
        self._last_used = clock()
        self._loaded_once = False
        self._stop = threading.Event()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def usable(self) -> bool:
        """
        Whether a dictation can be served: the model loaded fine at least once.

        Not the same as is_loaded - after an idle release the model is off the
        GPU but one use() away, and the phone must not be told "still loading"
        for that.
        """
        return self._loaded_once

    @contextmanager
    def use(self, on_loading: Optional[Callable[[bool], None]] = None):
        """
        The model, loaded if it was let go, held until the block ends.

        `on_loading(True)` / `on_loading(False)` bracket a load, and only a
        real one, so the caller can tell the user why this dictation is slower.
        A failed load raises out of here; the next use() tries again.
        """
        with self._lock:
            if self._model is None:
                self._load(on_loading)
            try:
                yield self._model
            finally:
                self._last_used = self._clock()

    def preload(self, on_loading: Optional[Callable[[bool], None]] = None):
        """Load now, so the first dictation after start is not the slow one"""
        with self.use(on_loading):
            pass

    def _load(self, on_loading):
        if on_loading:
            on_loading(True)
        try:
            started = self._clock()
            self._model = self._loader()
            self._loaded_once = True
            print(f"[MODEL] loaded in {self._clock() - started:.1f}s")
        finally:
            if on_loading:
                on_loading(False)

    def release_if_idle(self) -> bool:
        """
        Let the model go if nobody used it for idle_seconds. True if it did.

        Never waits for the lock: a held lock means a transcription is running,
        which is the opposite of idle.
        """
        if self._model is None:
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            idle = self._clock() - self._last_used
            if self._model is None or idle < self._idle_seconds:
                return False
            self._model = None
            free_gpu_cache()
            print(f"[MODEL] released after {idle:.0f}s idle")
            return True
        finally:
            self._lock.release()

    def start_idle_watch(self, check_seconds: float = IDLE_CHECK_SECONDS):
        """The background thread that calls release_if_idle(); a daemon"""
        def loop():
            while not self._stop.wait(check_seconds):
                try:
                    self.release_if_idle()
                except Exception as e:
                    print(f"[MODEL] idle check failed: {e}")

        threading.Thread(target=loop, name="model-idle-watch", daemon=True).start()

    def stop_idle_watch(self):
        self._stop.set()
