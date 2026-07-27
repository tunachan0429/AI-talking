"""Text-To-Speech using VOICEVOX (local Japanese TTS engine, female voices).

VOICEVOX runs as a local HTTP server (default http://127.0.0.1:50021). It needs
NO compilation and provides high-quality Japanese female voices. Download and
run the VOICEVOX app, then this client talks to it over localhost.

Two-step API:
  1. POST /audio_query?text=...&speaker=ID   -> synthesis query (JSON)
  2. POST /synthesis?speaker=ID  (body=query) -> WAV bytes
"""
from __future__ import annotations

import io
from typing import Iterator

import numpy as np
import requests
import soundfile as sf

from ..config import TTSConfig


class VoicevoxTTS:
    def __init__(self, cfg: TTSConfig, device: str = "cpu"):
        self.cfg = cfg
        self.base_url = cfg.base_url.rstrip("/")
        self.speaker = cfg.speaker
        self.speed = cfg.speed
        self.sample_rate = 24000  # VOICEVOX default; updated after synthesis

        # Fail early with a friendly message if the engine isn't running.
        try:
            requests.get(f"{self.base_url}/version", timeout=3)
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(
                f"VOICEVOX に接続できません ({self.base_url})。\n"
                "VOICEVOX アプリを起動してから、もう一度実行してください。\n"
                "ダウンロード: https://voicevox.hiroshiba.jp/"
            ) from exc

    def synth(self, text: str) -> np.ndarray:
        """Synthesize the full text into a single float32 waveform."""
        text = text.strip()
        if not text:
            return np.zeros(0, dtype=np.float32)

        query = requests.post(
            f"{self.base_url}/audio_query",
            params={"text": text, "speaker": self.speaker},
            timeout=30,
        )
        query.raise_for_status()
        query_json = query.json()
        query_json["speedScale"] = self.speed

        synth = requests.post(
            f"{self.base_url}/synthesis",
            params={"speaker": self.speaker},
            json=query_json,
            timeout=60,
        )
        synth.raise_for_status()

        data, sr = sf.read(io.BytesIO(synth.content), dtype="float32")
        self.sample_rate = sr
        if data.ndim > 1:
            data = data[:, 0]
        return np.asarray(data, dtype=np.float32)

    def stream(self, text: str) -> Iterator[np.ndarray]:
        """Yield the synthesized audio (VOICEVOX returns the whole sentence)."""
        audio = self.synth(text)
        if audio.size:
            yield audio
