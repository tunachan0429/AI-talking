#!/usr/bin/env python3
"""Web entry point: Live2D avatar UI + voice pipeline over WebSocket.

Run:
    python server.py            # then open http://127.0.0.1:8000

Architecture:
    Browser (Live2D + audio playback + lip-sync)
        <-- WebSocket -->  this server
    this server runs the voice pipeline (VAD/STT/LLM/TTS) in a background
    thread. Instead of playing TTS audio locally, it streams the audio (WAV,
    base64) to the browser, which plays it and drives the mouth parameter.

The microphone is captured on this machine (server side), so make sure the
browser is on the same PC (localhost). VOICEVOX must be running for TTS.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import threading
from typing import Optional, Set

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import Config

CFG = Config.load(os.environ.get("AITALK_CONFIG", "config.yaml"))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

app = FastAPI(title="AI-talking Live2D")

_clients: "Set[WebSocket]" = set()
_loop: Optional[asyncio.AbstractEventLoop] = None
_pipeline = None
_pipeline_started = False
_start_lock = threading.Lock()


def _wav_base64(audio: np.ndarray, sample_rate: int) -> str:
    """Encode a float32 waveform as base64 16-bit PCM WAV."""
    buf = io.BytesIO()
    sf.write(buf, audio, int(sample_rate), format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _broadcast(message: dict) -> None:
    """Send a JSON message to all connected browsers (thread-safe)."""
    if _loop is None:
        return
    text = json.dumps(message)
    for ws in list(_clients):
        asyncio.run_coroutine_threadsafe(_safe_send(ws, text), _loop)


async def _safe_send(ws: WebSocket, text: str) -> None:
    try:
        await ws.send_text(text)
    except Exception:
        _clients.discard(ws)


# ---- pipeline callbacks (run on the pipeline thread) ---------------------
def _on_event(event: dict) -> None:
    _broadcast(event)


def _on_speak(audio: np.ndarray, sample_rate: int) -> None:
    _broadcast(
        {
            "type": "speak",
            "sampleRate": int(sample_rate),
            "audio": _wav_base64(audio, sample_rate),
        }
    )


def _run_pipeline() -> None:
    global _pipeline
    from src.pipeline import Pipeline

    try:
        _pipeline = Pipeline(CFG, on_event=_on_event, on_speak=_on_speak)
        _broadcast({"type": "state", "value": "ready"})
        _pipeline.run()
    except Exception as exc:  # surface fatal errors to the browser
        _broadcast({"type": "error", "message": str(exc)})
        raise


def _ensure_pipeline_started() -> None:
    global _pipeline_started
    with _start_lock:
        if _pipeline_started:
            return
        _pipeline_started = True
        _broadcast({"type": "state", "value": "loading"})
        threading.Thread(target=_run_pipeline, name="pipeline", daemon=True).start()


@app.on_event("startup")
async def _startup() -> None:
    global _loop
    _loop = asyncio.get_running_loop()


@app.get("/api/config")
async def api_config() -> JSONResponse:
    return JSONResponse(
        {
            "model": CFG.live2d.model,
            "mouthParam": CFG.live2d.mouth_param,
            "scale": CFG.live2d.scale,
            "yAnchor": CFG.live2d.y_anchor,
        }
    )


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    # Start the (heavy) pipeline lazily on first browser connection.
    _ensure_pipeline_started()
    try:
        while True:
            # We don't need input from the browser yet; just keep the socket
            # open and ignore any incoming messages (e.g. keepalives).
            await websocket.receive_text()
    except WebSocketDisconnect:
        _clients.discard(websocket)
    except Exception:
        _clients.discard(websocket)


# Serve the browser front-end (index.html, app.js, style.css) and the Live2D
# model files copied into web/live2d/. Mounted last so /api and /ws win.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def main() -> None:
    uvicorn.run(app, host=CFG.web.host, port=CFG.web.port, log_level="info")


if __name__ == "__main__":
    main()
