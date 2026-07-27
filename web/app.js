/* AI-talking — Live2D front-end
 *
 * - Loads a Cubism 4 Live2D model with pixi-live2d-display.
 * - Connects to the Python backend over WebSocket.
 * - Plays TTS audio (sent as base64 WAV) via the Web Audio API and drives the
 *   model's mouth parameter from the live audio level (lip-sync).
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
let mouthParam = "ParamMouthOpenY";
let mouth = 0; // smoothed 0..1

// ---- audio / lip-sync ----------------------------------------------------
let audioCtx = null;
let analyser = null;
let timeData = null;
let isSpeaking = false;
const audioQueue = [];
let playing = false;

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
  mouthParam = cfg.mouthParam || "ParamMouthOpenY";
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
  // Let the plugin auto-update the model on the shared ticker (the reliable,
  // documented default). We only override the mouth parameter afterwards.
  model = await PIXI.live2d.Live2DModel.from(url);
  app.stage.addChild(model);
  try { model.anchor.set(0.5, 0.5); } catch (e) { /* older API */ }

  const layout = () => {
    if (!model) return;
    // Measure the model's native height at scale 1, then fit it to the screen.
    model.scale.set(1);
    const im = model.internalModel || {};
    const baseH = model.height || im.originalHeight || 1000;
    let fit = (window.innerHeight * heightFraction) / baseH;
    if (!isFinite(fit) || fit <= 0) fit = 0.2; // safety fallback
    model.scale.set(fit);
    model.position.set(window.innerWidth / 2, window.innerHeight * yAnchor);
  };
  layout();
  window.addEventListener("resize", layout);
  console.log("[live2d] loaded", { model: url, baseHeight: model.height });

  // Drive the mouth from the live audio level (runs each frame).
  app.ticker.add(() => {
    if (!model) return;
    let target = 0;
    if (isSpeaking && analyser) {
      analyser.getFloatTimeDomainData(timeData);
      let sum = 0;
      for (let i = 0; i < timeData.length; i++) sum += timeData[i] * timeData[i];
      const rms = Math.sqrt(sum / timeData.length);
      target = Math.min(1, rms * 6.0); // gain
    }
    mouth += (target - mouth) * 0.35; // smoothing
    try {
      model.internalModel.coreModel.setParameterValueById(mouthParam, mouth);
    } catch (e) {
      /* param name mismatch — ignore */
    }
  });
}

// ---- audio playback + lip-sync ------------------------------------------
function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const len = bin.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function enqueueAudio(b64) {
  audioQueue.push(b64);
  if (!playing) playNext();
}

async function playNext() {
  if (audioQueue.length === 0) {
    playing = false;
    isSpeaking = false;
    return;
  }
  playing = true;
  const b64 = audioQueue.shift();

  let buffer;
  try {
    buffer = await audioCtx.decodeAudioData(base64ToArrayBuffer(b64));
  } catch (e) {
    return playNext();
  }

  const source = audioCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(analyser);
  analyser.connect(audioCtx.destination);

  isSpeaking = true;
  source.onended = () => playNext();
  source.start();
}

// ---- WebSocket -----------------------------------------------------------
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    // keepalive
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
  // A user gesture is required to unlock audio playback in the browser.
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;
  timeData = new Float32Array(analyser.fftSize);
  if (audioCtx.state === "suspended") audioCtx.resume();

  els.overlay.classList.add("hidden");
  connect();
});

boot();
