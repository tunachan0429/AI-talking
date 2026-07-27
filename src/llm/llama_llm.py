"""Local chat LLM via llama-cpp-python (GGUF models, no API key)."""
from __future__ import annotations

import os
from collections import deque
from typing import Deque, Dict, Iterator, List

from ..config import LLMConfig


class LlamaLLM:
    def __init__(self, cfg: LLMConfig, device: str = "cpu"):
        self.cfg = cfg
        if not os.path.exists(cfg.model_path):
            raise FileNotFoundError(
                f"LLM model not found: {cfg.model_path}\n"
                "Download a GGUF chat model and set llm.model_path in config.yaml "
                "(see README)."
            )

        from llama_cpp import Llama

        n_gpu_layers = cfg.n_gpu_layers if device == "cuda" else 0
        self.llm = Llama(
            model_path=cfg.model_path,
            n_ctx=cfg.n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )
        # rolling conversation memory (user/assistant turns, not the system msg)
        self._history: Deque[Dict[str, str]] = deque(maxlen=cfg.history_turns * 2)

    def _messages(self, user_text: str) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = [
            {"role": "system", "content": self.cfg.system_prompt}
        ]
        msgs.extend(self._history)
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def reply(self, user_text: str) -> str:
        """Generate a full reply (blocking)."""
        out = self.llm.create_chat_completion(
            messages=self._messages(user_text),
            max_tokens=self.cfg.max_tokens,
            temperature=self.cfg.temperature,
            top_p=self.cfg.top_p,
        )
        text = out["choices"][0]["message"]["content"].strip()
        self._remember(user_text, text)
        return text

    def stream_reply(self, user_text: str) -> Iterator[str]:
        """Yield reply text incrementally, so TTS can start sooner.

        Yields chunks; the caller is responsible for buffering into sentences.
        The full reply is committed to memory when the stream ends.
        """
        stream = self.llm.create_chat_completion(
            messages=self._messages(user_text),
            max_tokens=self.cfg.max_tokens,
            temperature=self.cfg.temperature,
            top_p=self.cfg.top_p,
            stream=True,
        )
        full: List[str] = []
        for part in stream:
            delta = part["choices"][0]["delta"].get("content")
            if delta:
                full.append(delta)
                yield delta
        self._remember(user_text, "".join(full).strip())

    def _remember(self, user_text: str, assistant_text: str) -> None:
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": assistant_text})

    def reset(self) -> None:
        self._history.clear()
