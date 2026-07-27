/* AI-talking — Live2D VTuber stream overlay
 *
 * - Loads a Cubism 4 Live2D model (PixiJS v7 + pixi-live2d-display-lipsyncpatch).
 * - Connects to the Python backend over WebSocket.
 * - Plays TTS audio with the plugin's built-in `model.speak` (auto lip-sync).
 * - Renders the conversation as a live "COMMENTS" feed and a speech bubble,
 *   with animated pastel decorations.
 */

"use strict";

const els = {
  canvas: document.getElementById("live2d-canvas"),
  overlay: document.getElementById("overlay"),
  overlayStatus: document.getElementById("overlay-status"),
  startBtn: document.getElementById("start-btn"),
  buildTag: document.getElementById("build-tag"),
  badge: document.getElementById("state-badge"),
  titleMain: document.getElementById("title-main"),
  titleSub: document.getElementById("title-sub"),
  liveLabel: document.getElementById("live-label"),
  commentsHeader: document.getElementById("comments-header"),
  commentList: document.getElementById("comment-list"),
  tagHashtag: document.getElementById("tag-hashtag"),
  tagHandle: document.getElementById("tag-handle"),
  speechBubble: document.getElementById("speech-bubble"),
  speechText: document.getElementById("speech-text"),
  bgStars: document.getElementById("bg-stars"),
  bgSparkles: document.getElementById("bg-sparkles"),
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

const MAX_COMMENTS = 40;
let app = null;
let model = null;
let personaName = "AI";

// audio queue (played sequentially via model.speak)
const audioQueue = [];
let speaking = false;

// Surface any JS error on screen (so you don't need to open DevTools).
window.addEventListener("error", (e) => {
  if (els.overlayStatus) els.overlayStatus.textContent = "JSエラー: " + e.message;
});
window.addEventListener("unhandledrejection", (e) => {
  const m = e.reason && e.reason.message ? e.reason.message : String(e.reason);
  if (els.overlayStatus) els.overlayStatus.textContent = "JSエラー: " + m;
});

function setState(value) {
  const [text, cls] = STATE_TEXT[value] || [value, "state-idle"];
  els.badge.textContent = text;
  els.badge.className = cls;
}

// ===== decorations ========================================================
function spawnDecorations() {
  const pastel = ["#ffffff", "#fff3a8", "#ffd6ec", "#c9b6ff", "#b8f2e6"];
  // twinkling stars
  for (let i = 0; i < 46; i++) {
    const s = document.createElement("div");
    s.className = "star";
    const size = 6 + Math.random() * 18;
    s.style.width = size + "px";
    s.style.height = size + "px";
    s.style.left = Math.random() * 100 + "vw";
    s.style.top = Math.random() * 100 + "vh";
    s.style.background = pastel[(Math.random() * pastel.length) | 0];
    s.style.setProperty("--dur", (2 + Math.random() * 4).toFixed(2) + "s");
    s.style.animationDelay = (-Math.random() * 5).toFixed(2) + "s";
    els.bgStars.appendChild(s);
  }
  // floating + / x sparkle marks
  const marks = ["+", "x", "*", "+", "x"];
  for (let i = 0; i < 26; i++) {
    const m = document.createElement("div");
    m.className = "spark";
    m.textContent = marks[(Math.random() * marks.length) | 0];
    m.style.left = Math.random() * 100 + "vw";
    m.style.top = Math.random() * 100 + "vh";
    m.style.fontSize = (12 + Math.random() * 22).toFixed(0) + "px";
    m.style.setProperty("--dur", (5 + Math.random() * 6).toFixed(2) + "s");
    m.style.animationDelay = (-Math.random() * 6).toFixed(2) + "s";
    els.bgSparkles.appendChild(m);
  }
}

// ===== comments feed ======================================================
function addComment(name, text, isAI) {
  const row = document.createElement("div");
  row.className = "comment-row" + (isAI ? " is-ai" : "");
  const n = document.createElement("span");
  n.className = "comment-name";
  n.textContent = name;
  const t = document.createElement("span");
  t.className = "comment-text";
  t.textContent = text;
  row.appendChild(n);
  row.appendChild(t);
  els.commentList.appendChild(row);
  while (els.commentList.children.length > MAX_COMMENTS) {
    els.commentList.removeChild(els.commentList.firstChild);
  }
  els.commentList.scrollTop = els.commentList.scrollHeight;
}

function showBubble(text) {
  els.speechText.textContent = text;
  els.speechBubble.classList.remove("hidden");
}
function hideBubble() {
  els.speechBubble.classList.add("hidden");
}

// ===== idle motion (keeps the avatar lively, not a fixed loop) ============
const idle = {
  t0: performance.now(),
  gaze: { x: 0, y: 0 },
  gazeTarget: { x: 0, y: 0 },
  nextGaze: 0,
  mood: 0,
  moodTarget: 0,
  nextMood: 0,
  lean: 0,
  leanTarget: 0,
  nextLean: 0,
};

function setParam(core, id, v) {
  try { core.setParameterValueById(id, v); } catch (e) { /* param absent */ }
}

// Called right before the model renders (in 'afterMotionUpdate'), so our
// values win over the default idle pose. Combines several out-of-phase sines
// with slow random-walk targets, so the motion never repeats exactly.
function animateIdle() {
  const core = model && model.internalModel && model.internalModel.coreModel;
  if (!core) return;
  const now = performance.now();
  const t = (now - idle.t0) / 1000;

  if (now > idle.nextGaze) {
    idle.gazeTarget.x = Math.random() * 2 - 1;
    idle.gazeTarget.y = Math.random() * 2 - 1;
    idle.nextGaze = now + 1400 + Math.random() * 3200;
  }
  if (now > idle.nextMood) {
    idle.moodTarget = Math.random() * 2 - 1;
    idle.nextMood = now + 5000 + Math.random() * 6000;
  }
  if (now > idle.nextLean) {
    idle.leanTarget = Math.random() * 2 - 1;
    idle.nextLean = now + 6000 + Math.random() * 7000;
  }
  idle.gaze.x += (idle.gazeTarget.x - idle.gaze.x) * 0.02;
  idle.gaze.y += (idle.gazeTarget.y - idle.gaze.y) * 0.02;
  idle.mood += (idle.moodTarget - idle.mood) * 0.01;
  idle.lean += (idle.leanTarget - idle.lean) * 0.01;

  // head
  setParam(core, "ParamAngleX", 9 * Math.sin(t * 0.5) + idle.gaze.x * 20 + idle.lean * 6);
  setParam(core, "ParamAngleY", 7 * Math.sin(t * 0.43) + idle.gaze.y * 12 + idle.mood * 4);
  setParam(core, "ParamAngleZ", 5 * Math.sin(t * 0.31) + idle.lean * 10);
  // eyes follow the gaze
  setParam(core, "ParamEyeBallX", idle.gaze.x);
  setParam(core, "ParamEyeBallY", idle.gaze.y);
  // body sway
  setParam(core, "ParamBodyAngleX", 5 * Math.sin(t * 0.3) + idle.gaze.x * 8);
  setParam(core, "ParamBodyAngleY", 3 * Math.sin(t * 0.24));
  setParam(core, "ParamBodyAngleZ", 4 * Math.sin(t * 0.27) + idle.lean * 4);
  // breathing
  setParam(core, "ParamBreath", 0.5 + 0.5 * Math.sin(t * 0.9));
}

// Occasionally change facial expression for extra variety.
function scheduleExpression() {
  const delay = 9000 + Math.random() * 9000;
  setTimeout(() => {
    try { if (model && model.expression) model.expression(); } catch (e) { /* none */ }
    scheduleExpression();
  }, delay);
}

// ===== Live2D =============================================================
async function initLive2D() {
  if (!window.PIXI || !PIXI.live2d || !PIXI.live2d.Live2DModel) {
    throw new Error("Live2D ライブラリの読み込みに失敗しました（ネット接続を確認）");
  }

  const cfg = await (await fetch("/api/config")).json();
  applyOverlayText(cfg.overlay);
  els.buildTag.textContent = "PIXI " + (PIXI.VERSION || "?") +
    " / core:" + (window.Live2DCubismCore ? "ok" : "NG");

  const zoom = cfg.scale || 1.8;
  const topFrac = cfg.yAnchor != null ? cfg.yAnchor : 0.05;
  const xFrac = cfg.xAnchor != null ? cfg.xAnchor : 0.72;

  app = new PIXI.Application({
    view: els.canvas,
    autoStart: true,
    resizeTo: window,
    backgroundAlpha: 0,
    antialias: true,
  });

  const url = encodeURI(cfg.model);
  model = await PIXI.live2d.Live2DModel.from(url, {
    autoInteract: false,
    onError: (e) => {
      els.overlayStatus.textContent =
        "モデルエラー: " + (e && e.message ? e.message : String(e));
    },
  });
  app.stage.addChild(model);

  const layout = () => {
    if (!model) return;
    try { model.anchor.set(0.5, 0.0); } catch (e) { /* older API */ }
    model.scale.set(1);
    const im = model.internalModel || {};
    const baseH = model.height || im.originalHeight || 1000;
    let fit = (window.innerHeight * zoom) / baseH;
    if (!isFinite(fit) || fit <= 0) fit = 0.5;
    model.scale.set(fit);
    model.position.set(window.innerWidth * xFrac, window.innerHeight * topFrac);
  };
  layout();
  window.addEventListener("resize", layout);

  // Inject our idle motion right before each render so it isn't overwritten
  // by the model's default pose, and start random expression changes.
  try {
    if (model.internalModel && model.internalModel.on) {
      model.internalModel.on("afterMotionUpdate", animateIdle);
    } else {
      app.ticker.add(animateIdle); // fallback
    }
  } catch (e) {
    app.ticker.add(animateIdle);
  }
  scheduleExpression();

  console.log("[live2d] loaded", { model: url, baseHeight: model.height });
}

function applyOverlayText(o) {
  if (!o) return;
  if (o.title) els.titleMain.textContent = o.title;
  if (o.subtitle) els.titleSub.textContent = o.subtitle;
  if (o.liveLabel) els.liveLabel.textContent = o.liveLabel;
  if (o.commentsTitle) els.commentsHeader.textContent = o.commentsTitle;
  if (o.hashtag) els.tagHashtag.textContent = o.hashtag;
  if (o.handle) els.tagHandle.textContent = o.handle;
}

// ===== audio playback + lip-sync (built into the plugin) ==================
function enqueueAudio(b64) {
  audioQueue.push(b64);
  if (!speaking) playNext();
}

function playNext() {
  if (audioQueue.length === 0) {
    speaking = false;
    hideBubble();
    return;
  }
  speaking = true;
  const b64 = audioQueue.shift();
  const dataUrl = "data:audio/wav;base64," + b64;
  try {
    model.speak(dataUrl, {
      volume: 1.0,
      onFinish: () => playNext(),
      onError: () => playNext(),
    });
  } catch (e) {
    playNext();
  }
}

// ===== WebSocket ==========================================================
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
        personaName = msg.value || personaName;
        document.title = `AI-talking — ${personaName}`;
        break;
      case "user":
        addComment("あなた", msg.text, false);
        break;
      case "assistant":
        addComment(personaName, msg.text, true);
        showBubble(msg.text);
        break;
      case "speak":
        enqueueAudio(msg.audio);
        break;
      case "error":
        setState("error");
        addComment("system", msg.message, true);
        break;
    }
  };

  ws.onclose = () => setState("error");
}

// ===== start flow =========================================================
async function boot() {
  setState("loading");
  spawnDecorations();
  try {
    await initLive2D();
    els.startBtn.disabled = false;
    els.startBtn.textContent = "配信スタート";
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
