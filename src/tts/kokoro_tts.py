"""Text-To-Speech using Kokoro (lightweight, multilingual, female voices).

Kokoro outputs 24 kHz mono float32 audio. It synthesizes per-sentence, which
lets the pipeline stream speech out chunk by chunk.
"""
from __future__ import annotations

from typing import Iterator

import numpy as np

from ..config import TTSConfig

KOKORO_SR = 24000


class KokoroTTS:
    sample_rate = KOKORO_SR

    def __init__(self, cfg: TTSConfig, device: str = "cpu"):
        self.cfg = cfg
        from kokoro import KPipeline

        # lang_code: 'j' Japanese, 'a' American English, 'b' British, etc.
        self.pipeline = KPipeline(lang_code=cfg.lang_code)

    def synth(self, text: str) -> np.ndarray:
        """Synthesize the full text into a single float32 waveform."""
        chunks = list(self.stream(text))
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def stream(self, text: str) -> Iterator[np.ndarray]:
        """Yield audio segment by segment (Kokoro splits on sentences)."""
        text = text.strip()
        if not text:
            return
        generator = self.pipeline(
            text,
            voice=self.cfg.voice,
            speed=self.cfg.speed,
        )
        for _graphemes, _phonemes, audio in generator:
            if audio is None:
                continue
            # Kokoro returns a torch tensor; convert to numpy float32.
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            yield np.asarray(audio, dtype=np.float32)


def build_tts(cfg: TTSConfig, device: str = "cpu"):
    """Factory so other TTS engines can be plugged in later."""
    if cfg.engine == "kokoro":
        return KokoroTTS(cfg, device=device)
    raise ValueError(f"Unknown TTS engine: {cfg.engine}")
