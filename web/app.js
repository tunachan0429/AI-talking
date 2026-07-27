/* AI-talking — Live2D front-end (PixiJS v7 + pixi-live2d-display-lipsyncpatch)
 *
 * - Loads a Cubism 4 Live2D model.
 * - Connects to the Python backend over WebSocket.
 * - Plays TTS audio (base64 WAV) using the plugin's built-in `model.speak`,
 *   which also drives the mouth (lip-sync) automatically.
 */

"use strict";

const els = {
  canvas: document.getElementById("live2d-canvas"),
  overlay: document.getElementById("overlay"),
  overlayStatus: document.getElementById("overlay-status"),
  startBtn: document.getElementById("start-btn"),
  badge: document.getElementById("state-badge"),
  userLine: document.getElementById("user-line"),
  assistantLine: document.getElementById("assistant-line"),
};

const STATE_TEXT = {
  loading: ["読み込み中...", "state-loading"],
  ready: ["待機中", "state-idle"],
  idle: ["待機中", "state-idle"],
  listening: ["聞いてるよ", "state-listening"],
  thinking: ["考え中...", "state-thinking"],
  speaking: ["おはなし中", "state-speaking"],
  error: ["エラー", "state-error"],
};

let app = null;
let model = null;

// audio queue (played sequentially via model.speak)
const audioQueue = [];
let speaking = false;

// Surface any JS error on screen (so you don't need to open DevTools).
window.addEventListener("error", (e) => {
  if (els.assistantLine) els.assistantLine.textContent = "JSエラー: " + e.message;
});
window.addEventListener("unhandledrejection", (e) => {
  const m = e.reason && e.reason.message ? e.reason.message : String(e.reason);
  if (els.assistantLine) els.assistantLine.textContent = "JSエラー: " + m;
});

function setState(value) {
  const [text, cls] = STATE_TEXT[value] || [value, "state-idle"];
  els.badge.textContent = text;
  els.badge.className = cls;
}

// ---- Live2D --------------------------------------------------------------
async function initLive2D() {
  if (!window.PIXI || !PIXI.live2d || !PIXI.live2d.Live2DModel) {
    throw new Error("Live2D ライブラリの読み込みに失敗しました（ネット接続と live2dcubismcore.min.js を確認）");
  }

  const cfg = await (await fetch("/api/config")).json();
  const heightFraction = cfg.scale || 0.9;
  const yAnchor = cfg.yAnchor != null ? cfg.yAnchor : 0.5;

  app = new PIXI.Application({
    view: els.canvas,
    autoStart: true,
    resizeTo: window,
    backgroundAlpha: 0,
    antialias: true,
  });

  const url = encodeURI(cfg.model);
  model = await PIXI.live2d.Live2DModel.from(url); // auto-updates via window.PIXI
  app.stage.addChild(model);
  try { model.anchor.set(0.5, 0.5); } catch (e) { /* older API */ }

  const layout = () => {
    if (!model) return;
    model.scale.set(1);
    const im = model.internalModel || {};
    const baseH = model.height || im.originalHeight || 1000;
    let fit = (window.innerHeight * heightFraction) / baseH;
    if (!isFinite(fit) || fit <= 0) fit = 0.2;
    model.scale.set(fit);
    model.position.set(window.innerWidth / 2, window.innerHeight * yAnchor);
  };
  layout();
  window.addEventListener("resize", layout);
  console.log("[live2d] loaded", { model: url, baseHeight: model.height });
}

// ---- audio playback + lip-sync (built into the plugin) -------------------
function enqueueAudio(b64) {
  audioQueue.push(b64);
  if (!speaking) playNext();
}

function playNext() {
  if (audioQueue.length === 0) {
    speaking = false;
    return;
  }
  speaking = true;
  const b64 = audioQueue.shift();
  const dataUrl = "data:audio/wav;base64," + b64;
  try {
    // model.speak plays the audio AND lip-syncs the mouth automatically.
    model.speak(dataUrl, {
      volume: 1.0,
      onFinish: () => playNext(),
      onError: () => playNext(),
    });
  } catch (e) {
    playNext();
  }
}

// ---- WebSocket -----------------------------------------------------------
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 15000);
  };

  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }

    switch (msg.type) {
      case "state":
        setState(msg.value);
        break;
      case "name":
        document.title = `AI-talking — ${msg.value}`;
        break;
      case "user":
        els.userLine.textContent = "あなた: " + msg.text;
        break;
      case "assistant":
        els.assistantLine.textContent = msg.text;
        break;
      case "speak":
        enqueueAudio(msg.audio);
        break;
      case "error":
        setState("error");
        els.assistantLine.textContent = "エラー: " + msg.message;
        break;
    }
  };

  ws.onclose = () => setState("error");
}

// ---- start flow ----------------------------------------------------------
async function boot() {
  setState("loading");
  try {
    await initLive2D();
    els.startBtn.disabled = false;
    els.startBtn.textContent = "はじめる";
    els.overlayStatus.textContent = "準備OK！ボタンを押してね";
  } catch (e) {
    els.overlayStatus.textContent = String(e.message || e);
    els.startBtn.textContent = "エラー";
  }
}

els.startBtn.addEventListener("click", () => {
  // A user gesture unlocks browser audio playback.
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
  } catch (e) { /* ignore */ }

  els.overlay.classList.add("hidden");
  connect();
});

boot();
