#!/usr/bin/env python3
"""
WhisperRocket - Diarization Manager
Optional speaker diarization using pyannote-audio.
Gracefully degrades if pyannote is not installed.
"""
import os
import json
from typing import Dict, List, Optional, Tuple

from transcription_engine import TranscriptionSegment


def _get_config_path() -> str:
    """Get config.json path"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def is_available() -> bool:
    """Check if pyannote-audio is installed"""
    try:
        import pyannote.audio
        return True
    except ImportError:
        return False


def get_token() -> Optional[str]:
    """Get HuggingFace token from config, env vars, or HfFolder"""
    # 1. Check config.json
    try:
        with open(_get_config_path(), 'r') as f:
            config = json.load(f)
            token = config.get("hf_token")
            if token:
                return token
    except Exception:
        pass

    # 2. Check environment variables
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if token:
        return token

    # 3. Check HuggingFace CLI stored token
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
    """Save HuggingFace token to config.json"""
    config_path = _get_config_path()
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception:
        config = {}

    config["hf_token"] = token

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


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
