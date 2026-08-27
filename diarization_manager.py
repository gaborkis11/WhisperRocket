#!/usr/bin/env python3
"""
WhisperRocket - Diarization Manager
Optional speaker diarization using pyannote-audio.
Gracefully degrades if pyannote is not installed.
"""
import os
import json
from typing import Dict, List, Optional, Tuple

import config_paths
import secrets_manager
from transcription_engine import TranscriptionSegment

# Env var names HuggingFace itself honours; the first one is what we write
HF_TOKEN_ENV_VARS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")

# Key an older version used inside config.json - migrated away on sight
_LEGACY_CONFIG_KEY = "hf_token"


def is_available() -> bool:
    """Check if pyannote-audio is installed"""
    try:
        import pyannote.audio
        return True
    except ImportError:
        return False


def _migrate_legacy_config_token() -> Optional[str]:
    """
    Move a token left in config.json by an older version into the secrets file.

    config.json sits in the project directory for source installs, so a token
    there is one `git add` away from being published. Relocate it once, then
    strip it out so it cannot be committed.
    """
    config_path = config_paths.get_config_path()
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception:
        return None

    token = config.get(_LEGACY_CONFIG_KEY)
    if not token:
        return None

    try:
        secrets_manager.set_secret(HF_TOKEN_ENV_VARS[0], token)
        config.pop(_LEGACY_CONFIG_KEY, None)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"[INFO] HuggingFace token moved out of config.json into "
              f"{secrets_manager.get_env_path()}")
    except Exception as e:
        print(f"[WARN] Could not migrate HuggingFace token out of config.json: {e}")

    return token


def get_token() -> Optional[str]:
    """
    Get the HuggingFace token.

    Order: real env var -> ~/.config/whisperrocket/.env -> legacy config.json
    (migrated out) -> token stored by `huggingface-cli login`.
    """
    # 1. Environment / secrets file
    for var in HF_TOKEN_ENV_VARS:
        token = secrets_manager.get_secret(var)
        if token:
            return token

    # 2. Legacy location - migrate it out of the repo on the way
    token = _migrate_legacy_config_token()
    if token:
        return token

    # 3. HuggingFace CLI stored token
    try:
        from huggingface_hub import HfFolder
        token = HfFolder.get_token()
        if token:
            return token
    except Exception:
        pass

    return None


def has_token() -> bool:
    """Check if HuggingFace token is configured"""
    return get_token() is not None


def save_token(token: str):
    """Save the HuggingFace token to ~/.config/whisperrocket/.env (mode 0600)"""
    secrets_manager.set_secret(HF_TOKEN_ENV_VARS[0], token)


def clear_token():
    """Remove the stored HuggingFace token"""
    for var in HF_TOKEN_ENV_VARS:
        secrets_manager.delete_secret(var)


class DiarizationManager:
    """Speaker diarization using pyannote-audio"""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self.pipeline = None

    def load_pipeline(self):
        """Load pyannote speaker diarization pipeline"""
        from pyannote.audio import Pipeline
        import torch

        token = get_token()

        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=token,
        )

        if self.device == "cuda" and torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

    def diarize(self, audio_path: str) -> Dict[Tuple[float, float], str]:
        """
        Run speaker diarization on an audio file.

        Returns:
            Dict mapping (start, end) time tuples to speaker labels
        """
        import tempfile
        import subprocess

        if not self.pipeline:
            self.load_pipeline()

        # Convert non-WAV files to WAV to avoid pyannote sample count issues
        tmp_wav = None
        ext = os.path.splitext(audio_path)[1].lower()
        if ext != ".wav":
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", tmp_wav.name],
                    capture_output=True, timeout=120,
                )
                audio_path = tmp_wav.name
            except Exception:
                # If ffmpeg fails, try with original file anyway
                pass

        try:
            output = self.pipeline(audio_path)
            # pyannote 4.x returns DiarizeOutput, 3.x returns Annotation
            if hasattr(output, 'speaker_diarization'):
                diarization = output.speaker_diarization
            else:
                diarization = output
            result = {}
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                result[(turn.start, turn.end)] = speaker
            return result
        finally:
            if tmp_wav and os.path.exists(tmp_wav.name):
                try:
                    os.unlink(tmp_wav.name)
                except Exception:
                    pass


def merge_speakers(
    segments: List[TranscriptionSegment],
    diarization: Dict[Tuple[float, float], str],
) -> List[TranscriptionSegment]:
    """
    Assign speaker labels to transcription segments based on temporal overlap.
    Uses maximum overlap matching.
    """
    for seg in segments:
        best_speaker = ""
        best_overlap = 0.0

        for (turn_start, turn_end), speaker in diarization.items():
            overlap_start = max(seg.start, turn_start)
            overlap_end = min(seg.end, turn_end)
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker

        seg.speaker = best_speaker

    return segments
