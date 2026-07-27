"""Audio playback with interruptible (barge-in capable) output."""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
import sounddevice as sd

from ..config import AudioConfig


class Player:
    """Plays float32 mono audio and supports being stopped mid-playback."""

    def __init__(self, cfg: AudioConfig):
        self.cfg = cfg
        self.sample_rate = cfg.output_sample_rate
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def play(self, audio: np.ndarray, sample_rate: Optional[int] = None) -> None:
        """Play a full audio array, blocking until done or stopped."""
        sr = sample_rate or self.sample_rate
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        self._stop.clear()

        with self._lock:
            block = int(sr * 0.05)  # 50 ms chunks so we can interrupt quickly
            with sd.OutputStream(
                samplerate=sr,
                channels=1,
                dtype="float32",
                device=self.cfg.output_device,
            ) as stream:
                for start in range(0, len(audio), block):
                    if self._stop.is_set():
                        break
                    stream.write(audio[start : start + block])

    def stop(self) -> None:
        """Request that any in-progress playback stops as soon as possible."""
        self._stop.set()

    @property
    def is_playing(self) -> bool:
        return self._lock.locked()
