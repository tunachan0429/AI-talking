"""Orchestrates the voice-to-voice loop: mic -> VAD -> STT -> LLM -> TTS -> speaker.

Flow per turn:
  1. Microphone streams audio blocks.
  2. Silero VAD groups them into a complete utterance (ends on a pause).
  3. Whisper transcribes the utterance to text.
  4. The local LLM generates a reply, streamed sentence by sentence.
  5. Kokoro TTS synthesizes each sentence; the player speaks it.

While the assistant is speaking, incoming mic audio is drained so the model
does not transcribe its own voice (simple echo guard). This gives a natural
push-to-pause, walkie-talkie style conversation.
"""
from __future__ import annotations

import re
import threading
from typing import Iterator

import numpy as np
from rich.console import Console

from .audio.mic import Microphone
from .audio.player import Player
from .config import Config
from .llm.llama_llm import LlamaLLM
from .stt.whisper_stt import WhisperSTT
from .tts.kokoro_tts import build_tts
from .vad.silero_vad import SileroVAD

console = Console()

# Split streamed LLM text into speakable sentences on JP/EN terminators.
_SENTENCE_END = re.compile(r"[。．.!?！？\n]")


def _sentences(chunks: Iterator[str]) -> Iterator[str]:
    """Turn a stream of text deltas into complete sentences for TTS."""
    buf = ""
    for delta in chunks:
        buf += delta
        while True:
            m = _SENTENCE_END.search(buf)
            if not m:
                break
            end = m.end()
            sentence = buf[:end].strip()
            buf = buf[end:]
            if sentence:
                yield sentence
    if buf.strip():
        yield buf.strip()


class Pipeline:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._speaking = threading.Event()

        console.print("[cyan]モデルを読み込み中...[/cyan]")
        self.vad = SileroVAD(cfg.vad, device=cfg.device)
        console.print("  [green]VAD ready[/green] (Silero VAD v5)")
        self.stt = WhisperSTT(cfg.stt, device=cfg.device)
        console.print(f"  [green]STT ready[/green] (whisper {cfg.stt.model})")
        self.llm = LlamaLLM(cfg.llm, device=cfg.device)
        console.print("  [green]LLM ready[/green] (llama.cpp)")
        self.tts = build_tts(cfg.tts, device=cfg.device)
        console.print(f"  [green]TTS ready[/green] ({cfg.tts.engine}: {cfg.tts.voice})")
        self.player = Player(cfg.audio)

    # ---- speaking ---------------------------------------------------------
    def _speak(self, text: str) -> None:
        """Synthesize and play a reply, sentence by sentence."""
        self._speaking.set()
        try:
            for sentence in _sentences(iter([text])):
                for audio in self.tts.stream(sentence):
                    if audio.size:
                        self.player.play(audio, sample_rate=self.tts.sample_rate)
        finally:
            self._speaking.clear()

    def _handle_utterance(self, utterance: np.ndarray) -> None:
        text = self.stt.transcribe(utterance)
        if not text:
            return
        console.print(f"[bold white]あなた:[/bold white] {text}")

        reply = self.llm.reply(text)
        console.print(f"[bold magenta]{self._name()}:[/bold magenta] {reply}")
        self._speak(reply)

    def _name(self) -> str:
        # best-effort persona name for the console label
        first_line = self.cfg.llm.system_prompt.strip().splitlines()[0]
        m = re.search(r"「([^」]+)」", first_line)
        return m.group(1) if m else "AI"

    # ---- main loop --------------------------------------------------------
    def run(self) -> None:
        console.print(
            "\n[bold green]準備完了。話しかけてください。"
            "（Ctrl+C で終了）[/bold green]\n"
        )
        with Microphone(self.cfg.audio) as mic:
            try:
                for block in mic.blocks():
                    # Ignore mic input while the assistant is talking (echo guard).
                    if self._speaking.is_set():
                        continue

                    utterance = self.vad.push(block)
                    if utterance is None:
                        continue

                    self._handle_utterance(utterance)
                    # Drop any audio captured during generation/playback.
                    mic.drain()
            except KeyboardInterrupt:
                self.player.stop()
                console.print("\n[yellow]またね。[/yellow]")
