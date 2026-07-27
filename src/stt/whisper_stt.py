"""Speech-To-Text using faster-whisper (CTranslate2 Whisper)."""
from __future__ import annotations

import numpy as np

from ..config import STTConfig


def _pick_compute_type(requested: str, device: str) -> str:
    if requested != "auto":
        return requested
    # Sensible defaults per device.
    return "float16" if device == "cuda" else "int8"


class WhisperSTT:
    def __init__(self, cfg: STTConfig, device: str = "cpu"):
        self.cfg = cfg
        from faster_whisper import WhisperModel

        compute_type = _pick_compute_type(cfg.compute_type, device)
        self.model = WhisperModel(
            cfg.model,
            device=device,
            compute_type=compute_type,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a float32 mono 16 kHz utterance to text."""
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        segments, _info = self.model.transcribe(
            audio,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            vad_filter=False,  # our own Silero VAD already segmented speech
        )
        text = "".join(seg.text for seg in segments)
        return text.strip()
