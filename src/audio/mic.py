"""Microphone capture as a stream of fixed-size float32 audio blocks."""
from __future__ import annotations

import queue
from typing import Iterator, Optional

import numpy as np
import sounddevice as sd

from ..config import AudioConfig


class Microphone:
    """Continuously captures mono audio and yields fixed-size blocks.

    Blocks are float32 numpy arrays in [-1, 1] of length
    ``sample_rate * block_ms / 1000`` samples.
    """

    def __init__(self, cfg: AudioConfig):
        self.cfg = cfg
        self.block_size = int(cfg.sample_rate * cfg.block_ms / 1000)
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream: Optional[sd.InputStream] = None

    def _callback(self, indata, frames, time_info, status):  # noqa: D401
        if status:
            # Overflows are common and non-fatal; just note them.
            pass
        # indata shape: (frames, channels) -> take channel 0, copy out of buffer
        self._q.put(indata[:, 0].copy())

    def __enter__(self) -> "Microphone":
        self._stream = sd.InputStream(
            samplerate=self.cfg.sample_rate,
            blocksize=self.block_size,
            device=self.cfg.input_device,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def blocks(self) -> Iterator[np.ndarray]:
        """Yield audio blocks forever (until the stream is closed)."""
        while True:
            try:
                yield self._q.get(timeout=1.0)
            except queue.Empty:
                if self._stream is None:
                    return
                continue

    def drain(self) -> None:
        """Discard any queued audio (used after the bot finishes speaking)."""
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
