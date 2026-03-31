#!/usr/bin/env python3
"""
WhisperRocket - Transcription Engine
Backend logic for file transcription with progress reporting and export formats.
"""
import json
import os
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Callable


@dataclass
class TranscriptionSegment:
    """Single transcription segment"""
    start: float = 0.0       # seconds
    end: float = 0.0         # seconds
    text: str = ""
    speaker: str = ""        # e.g. "SPEAKER_00"


@dataclass
class TranscriptionResult:
    """Full transcription result"""
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: str = ""
    duration: float = 0.0    # total audio duration in seconds
    source_file: str = ""
    has_diarization: bool = False


class TranscriptionEngine:
    """Handles file transcription with progress reporting"""

    def __init__(self, model, whisper_backend: str, model_lock: threading.Lock):
        self.model = model
        self.whisper_backend = whisper_backend
        self.model_lock = model_lock
        self._cancel_flag = False

    def transcribe_file(
        self,
        file_path: str,
        language: str,
        vad_enabled: bool = True,
        word_timestamps: bool = False,
        beam_size: int = 5,
        progress_callback: Optional[Callable] = None,
        segment_callback: Optional[Callable] = None,
    ) -> TranscriptionResult:
        """
        Transcribe an audio/video file.

        Args:
            file_path: Path to audio/video file
            language: Language code (e.g. "hu", "en")
            vad_enabled: Enable Voice Activity Detection (skip silence)
            word_timestamps: Enable word-level timestamps
            beam_size: Beam size for decoding
            progress_callback: Called with (float 0.0-1.0, str status_message)
            segment_callback: Called with each TranscriptionSegment as it's ready
        """
        self._cancel_flag = False
        result = TranscriptionResult(
            source_file=os.path.basename(file_path),
            language=language,
        )

        if self.whisper_backend == "mlx":
            return self._transcribe_mlx(file_path, language, result, progress_callback, segment_callback)
        else:
            return self._transcribe_faster_whisper(
                file_path, language, vad_enabled, word_timestamps,
                beam_size, result, progress_callback, segment_callback
            )

    def _transcribe_faster_whisper(
        self, file_path, language, vad_enabled, word_timestamps,
        beam_size, result, progress_callback, segment_callback
    ):
        """Transcribe using faster-whisper backend"""
        # Acquire model lock and consume all segments
        with self.model_lock:
            segments_gen, info = self.model.transcribe(
                file_path,
                language=language,
                beam_size=beam_size,
                vad_filter=vad_enabled,
                word_timestamps=word_timestamps,
            )
            result.duration = info.duration
            raw_segments = list(segments_gen)

        if self._cancel_flag:
            return result

        # Process segments outside the lock
        total = len(raw_segments)
        for i, seg in enumerate(raw_segments):
            if self._cancel_flag:
                break

            ts = TranscriptionSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
            )
            result.segments.append(ts)

            if segment_callback:
                segment_callback(ts)
            if progress_callback:
                progress_callback((i + 1) / max(total, 1), f"{i + 1}/{total}")

        return result

    def _transcribe_mlx(self, file_path, language, result, progress_callback, segment_callback):
        """Transcribe using MLX backend"""
        import mlx_whisper

        if progress_callback:
            progress_callback(0.0, "Processing...")

        with self.model_lock:
            mlx_result = mlx_whisper.transcribe(
                file_path,
                path_or_hf_repo=f"mlx-community/whisper-{self.model['model_name']}-mlx",
                language=language,
            )

        segments_data = mlx_result.get("segments", [])
        result.duration = segments_data[-1]["end"] if segments_data else 0.0

        for i, seg_data in enumerate(segments_data):
            if self._cancel_flag:
                break

            ts = TranscriptionSegment(
                start=seg_data.get("start", 0.0),
                end=seg_data.get("end", 0.0),
                text=seg_data.get("text", "").strip(),
            )
            result.segments.append(ts)

            if segment_callback:
                segment_callback(ts)
            if progress_callback:
                progress_callback((i + 1) / max(len(segments_data), 1), f"{i + 1}/{len(segments_data)}")

        return result

    def cancel(self):
        """Cancel ongoing transcription"""
        self._cancel_flag = True

    @property
    def is_cancelled(self):
        return self._cancel_flag


# --- Export Functions ---

def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds as VTT timestamp: HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def export_srt(result: TranscriptionResult, file_path: str):
    """Export as SRT subtitle format"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(result.segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n")
            prefix = f"{seg.speaker}: " if seg.speaker else ""
            f.write(f"{prefix}{seg.text}\n\n")


def export_vtt(result: TranscriptionResult, file_path: str):
    """Export as WebVTT subtitle format"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        for i, seg in enumerate(result.segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_vtt_time(seg.start)} --> {format_vtt_time(seg.end)}\n")
            prefix = f"<v {seg.speaker}>" if seg.speaker else ""
            f.write(f"{prefix}{seg.text}\n\n")


def export_txt(result: TranscriptionResult, file_path: str):
    """Export as plain text with timestamps"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for seg in result.segments:
            ts = format_timestamp(seg.start)
            speaker = f" {seg.speaker}:" if seg.speaker else ""
            f.write(f"[{ts}]{speaker} {seg.text}\n")


def export_json(result: TranscriptionResult, file_path: str):
    """Export as structured JSON"""
    data = {
        "source_file": result.source_file,
        "language": result.language,
        "duration": result.duration,
        "has_diarization": result.has_diarization,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "speaker": seg.speaker,
            }
            for seg in result.segments
        ]
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
