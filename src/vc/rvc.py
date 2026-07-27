"""RVC voice conversion via a local rvc-python API server (HTTP client).

We keep RVC in its own process/server (like VOICEVOX) so its heavy, fragile
dependencies (fairseq etc.) never touch this app's environment. This module
only needs `requests` + `soundfile`.

Start the server separately with your model preloaded, e.g.:
    python -m rvc_python api -p 5050 -pm path/to/your_model.pth

The /convert endpoint takes base64 WAV and returns converted WAV bytes.
"""
from __future__ import annotations

import base64
import io
from typing import Tuple

import numpy as np
import requests
import soundfile as sf

from ..config import RVCConfig


class RVCClient:
    def __init__(self, cfg: RVCConfig, device: str = "cpu"):
        self.cfg = cfg
        self.base_url = cfg.base_url.rstrip("/")

        # Fail early with a friendly message if the server isn't up.
        try:
            requests.get(f"{self.base_url}/models", timeout=4)
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(
                f"RVC サーバーに接続できません ({self.base_url})。\n"
                "先に RVC サーバーを起動してください（別のvenv/端末で）:\n"
                "    python -m rvc_python api -p 5050 -pm path/to/your_model.pth\n"
                "使わない場合は config.yaml の rvc.enabled を false に。"
            ) from exc

    def convert(self, audio: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, int]:
        """Convert a float32 waveform to the target RVC voice.

        Returns (converted_audio_float32, output_sample_rate).
        """
        # encode input as base64 WAV (PCM16)
        in_buf = io.BytesIO()
        sf.write(in_buf, audio, int(sample_rate), format="WAV", subtype="PCM_16")
        audio_b64 = base64.b64encode(in_buf.getvalue()).decode("ascii")

        resp = requests.post(
            f"{self.base_url}/convert",
            json={"audio_data": audio_b64},
            timeout=120,
        )
        resp.raise_for_status()

        data, out_sr = sf.read(io.BytesIO(resp.content), dtype="float32")
        if data.ndim > 1:
            data = data[:, 0]
        return np.asarray(data, dtype=np.float32), int(out_sr)
