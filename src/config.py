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
    engine: str = "voicevox"
    # VOICEVOX settings
    speaker: int = 2
    base_url: str = "http://127.0.0.1:50021"
    # Kokoro settings (only used when engine == "kokoro")
    voice: str = "jf_alpha"
    lang_code: str = "j"
    speed: float = 1.0


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class Live2DConfig:
    # Path (served under /) to your model's .model3.json file.
    model: str = "live2d/model.model3.json"
    # The Live2D parameter that opens/closes the mouth (Cubism default).
    mouth_param: str = "ParamMouthOpenY"
    # zoom = full model height as a multiple of screen height (bigger = larger).
    # ~3.0 gives a large close-up bust view; ~0.9 shows the whole body.
    scale: float = 3.0
    # y_anchor = vertical position of the head top (negative moves the avatar
    # up so more of the lower body comes into frame).
    y_anchor: float = -0.1
    # x_anchor = horizontal position (0=left ... 1=right). ~0.68 fills the
    # space to the right of the comments panel.
    x_anchor: float = 0.68


@dataclass
class OverlayConfig:
    """Stream-overlay (VTuber) look & text."""
    title: str = "AI LIVE"           # small title on the stream
    subtitle: str = "おしゃべり配信中"    # under the title
    hashtag: str = "ai_talking_live"  # decorative # tag (bottom-left)
    handle: str = "my_ai_girlfriend"  # decorative @ handle (bottom-left)
    live_label: str = "NOW LIVE"      # the pulsing badge text
    comments_title: str = "COMMENTS"  # header of the comments panel


@dataclass
class Config:
    device: str = "cpu"
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    web: WebConfig = field(default_factory=WebConfig)
    live2d: Live2DConfig = field(default_factory=Live2DConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)

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
            web=WebConfig(**(raw.get("web") or {})),
            live2d=Live2DConfig(**(raw.get("live2d") or {})),
            overlay=OverlayConfig(**(raw.get("overlay") or {})),
        )
        return cfg
