"""Configuration loading and device resolution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import yaml


def _resolve_device(device: str) -> str:
    """Turn 'auto' into 'cuda' or 'cpu' depending on availability."""
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    block_ms: int = 32
    input_device: Optional[Any] = None
    output_device: Optional[Any] = None
    output_sample_rate: int = 24000


@dataclass
class VADConfig:
    threshold: float = 0.5
    min_speech_ms: int = 250
    min_silence_ms: int = 700
    speech_pad_ms: int = 200


@dataclass
class STTConfig:
    model: str = "small"
    language: Optional[str] = "ja"
    compute_type: str = "auto"
    beam_size: int = 1


@dataclass
class LLMConfig:
    model_path: str = "models/llm/model.gguf"
    n_ctx: int = 4096
    n_gpu_layers: int = -1
    max_tokens: int = 200
    temperature: float = 0.8
    top_p: float = 0.9
    history_turns: int = 12
    system_prompt: str = "You are a friendly companion."


@dataclass
class TTSConfig:
    engine: str = "kokoro"
    voice: str = "jf_alpha"
    lang_code: str = "j"
    speed: float = 1.0


@dataclass
class Config:
    device: str = "cpu"
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        cfg = cls(
            device=_resolve_device(raw.get("device", "auto")),
            audio=AudioConfig(**(raw.get("audio") or {})),
            vad=VADConfig(**(raw.get("vad") or {})),
            stt=STTConfig(**(raw.get("stt") or {})),
            llm=LLMConfig(**(raw.get("llm") or {})),
            tts=TTSConfig(**(raw.get("tts") or {})),
        )
        return cfg
