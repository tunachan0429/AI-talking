"""Streaming Voice Activity Detection using Silero VAD v5.

Consumes a stream of arbitrary-length float32 audio blocks (16 kHz mono) and
emits complete utterances (numpy arrays) once the speaker pauses.

Silero VAD v5 processes fixed windows of 512 samples at 16 kHz, so this class
buffers incoming audio and feeds the model one window at a time.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import VADConfig

WINDOW = 512          # samples per Silero window at 16 kHz
SR = 16000            # Silero VAD v5 supports 8k and 16k; we use 16k


class SileroVAD:
    def __init__(self, cfg: VADConfig, device: str = "cpu"):
        self.cfg = cfg
        # Lazy heavy imports so `--help` etc. stay fast.
        import torch
        from silero_vad import load_silero_vad

        self.torch = torch
        self.model = load_silero_vad()  # v5 by default
        try:
            self.model.to(device)
            self.device = device
        except Exception:
            self.device = "cpu"

        # thresholds in windows
        self._min_speech_win = max(1, int(cfg.min_speech_ms * SR / 1000 / WINDOW))
        self._min_silence_win = max(1, int(cfg.min_silence_ms * SR / 1000 / WINDOW))
        self._pad = int(cfg.speech_pad_ms * SR / 1000)

        self._reset()
        self._carry = np.zeros(0, dtype=np.float32)

    def _reset(self) -> None:
        self._triggered = False
        self._speech: List[np.ndarray] = []
        self._silence_run = 0
        self._speech_run = 0
        self._pre: List[np.ndarray] = []  # rolling pre-speech pad buffer
        try:
            self.model.reset_states()
        except Exception:
            pass

    def _prob(self, window: np.ndarray) -> float:
        t = self.torch.from_numpy(window).to(self.device)
        with self.torch.no_grad():
            return float(self.model(t, SR).item())

    def _pre_windows(self) -> int:
        return max(1, self._pad // WINDOW)

    def push(self, block: np.ndarray) -> Optional[np.ndarray]:
        """Feed one audio block. Returns a completed utterance or None.

        The returned array is the full utterance (float32, 16 kHz mono).
        """
        self._carry = np.concatenate([self._carry, block.astype(np.float32)])

        completed: Optional[np.ndarray] = None
        while len(self._carry) >= WINDOW:
            window = self._carry[:WINDOW]
            self._carry = self._carry[WINDOW:]
            prob = self._prob(window)
            is_speech = prob >= self.cfg.threshold

            if not self._triggered:
                # keep a short rolling buffer to prepend as pre-speech padding
                self._pre.append(window)
                if len(self._pre) > self._pre_windows():
                    self._pre.pop(0)

                if is_speech:
                    self._speech_run += 1
                    if self._speech_run >= self._min_speech_win:
                        self._triggered = True
                        self._speech = list(self._pre)  # include padding
                        self._pre = []
                        self._silence_run = 0
                else:
                    self._speech_run = 0
            else:
                self._speech.append(window)
                if is_speech:
                    self._silence_run = 0
                else:
                    self._silence_run += 1
                    if self._silence_run >= self._min_silence_win:
                        utterance = np.concatenate(self._speech)
                        self._reset()
                        completed = utterance
                        break

        return completed
