# Local AI Girlfriend 🎙️

A fully **local**, **offline** voice-to-voice AI companion.
No internet, no API keys, no cloud. Everything runs on your own machine.

Inspired by the "赛博女友 / cyber girlfriend" speech-to-speech setup:

| Stage | What it does | Engine |
|-------|--------------|--------|
| **VAD** | Detects when you start/stop talking | [Silero VAD v5](https://github.com/snakers4/silero-vad) |
| **STT** | Converts your speech to text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| **LLM** | Generates the reply (with a persona + memory) | [llama.cpp](https://github.com/ggerganov/llama.cpp) (GGUF) |
| **TTS** | Speaks the reply in a female voice | [Kokoro](https://github.com/hexgrad/kokoro) |

```
🎤 mic ─► [VAD] ─► [Whisper] ─► [llama.cpp] ─► [Kokoro] ─► 🔊 speaker
```

---

## Requirements

- **Python 3.10 – 3.12**
- A microphone and speakers
- **GPU strongly recommended** (NVIDIA, ~12–15 GB VRAM fits all models). CPU works but is slow.
- OS: Linux / Windows / macOS

---

## 1. Install

```bash
git clone <your-repo-url> local-ai-girlfriend
cd local-ai-girlfriend

python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install -r requirements.txt
```

### PortAudio (needed by `sounddevice`)
- **Linux (Debian/Ubuntu):** `sudo apt install portaudio19-dev`
- **macOS:** `brew install portaudio`
- **Windows:** included with the `sounddevice` wheel, nothing to do.

### GPU acceleration (optional but recommended)
- **torch / faster-whisper:** install a CUDA build of PyTorch from <https://pytorch.org>.
- **llama-cpp-python with CUDA:**
  ```bash
  CMAKE_ARGS="-DGGML_CUDA=on" pip install --force-reinstall --no-cache-dir llama-cpp-python
  ```

---

## 2. Download an LLM (GGUF)

Pick any chat model in GGUF format and point `config.yaml` at it. Good choices:

- **Japanese-capable, small:** [Qwen2.5-7B-Instruct GGUF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF) (e.g. the `q4_k_m` file)
- **Lighter:** Qwen2.5-3B-Instruct GGUF

```bash
mkdir -p models/llm
# example (requires: pip install huggingface_hub)
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF qwen2.5-7b-instruct-q4_k_m.gguf \
  --local-dir models/llm
```

Then set the path in `config.yaml`:

```yaml
llm:
  model_path: models/llm/qwen2.5-7b-instruct-q4_k_m.gguf
```

> Whisper, Silero VAD, and Kokoro models download automatically on first run
> (once), then run fully offline afterward.

---

## 3. Run

```bash
# See your audio devices (find the right mic/speaker index if needed)
python run.py --list-devices

# Start talking
python run.py
```

Speak, pause, and she'll answer out loud. Press **Ctrl+C** to quit.

---

## Configuration (`config.yaml`)

Everything is tunable without touching code. Highlights:

- **`device`** — `auto` / `cuda` / `cpu`.
- **`llm.system_prompt`** — the persona. Default is "ユキ", a warm girlfriend character. Edit freely.
- **`tts.voice`** — the female voice:
  - Japanese: `jf_alpha`, `jf_gongitsune`, `jf_nezumi`, `jf_tebukuro`
  - English: `af_heart`, `af_bella`, `af_sarah` (also set `tts.lang_code: a`)
- **`stt.model`** — `tiny`→`large-v3`. Bigger = more accurate, slower.
- **`vad.min_silence_ms`** — how long a pause ends your turn (lower = snappier, higher = fewer cut-offs).

### Switch to English
```yaml
stt:
  language: en
llm:
  system_prompt: |
    You are "Yuki", a warm, caring girlfriend. Keep replies short (1-3 sentences),
    natural and spoken, no emojis or lists.
tts:
  voice: af_heart
  lang_code: a
```

---

## Project layout

```
local-ai-girlfriend/
├── run.py                # entry point (CLI)
├── config.yaml           # all settings + persona
├── requirements.txt
└── src/
    ├── config.py         # config loading
    ├── pipeline.py       # the mic→VAD→STT→LLM→TTS→speaker loop
    ├── audio/            # microphone capture + playback
    ├── vad/              # Silero VAD v5 (streaming utterance detection)
    ├── stt/              # faster-whisper transcription
    ├── llm/              # llama.cpp chat + conversation memory
    └── tts/              # Kokoro female-voice synthesis
```

## How a turn works

1. The mic streams audio blocks continuously.
2. **Silero VAD** groups them into one utterance and detects when you pause.
3. **Whisper** transcribes that utterance to text.
4. The **local LLM** replies using the persona + recent conversation history.
5. The reply is split into sentences and **Kokoro** speaks each one.

While she's talking, mic input is ignored (a simple echo guard) so she doesn't
hear herself. When she finishes, she listens again.

## Troubleshooting

- **No sound / wrong device:** run `python run.py --list-devices` and set
  `audio.input_device` / `audio.output_device` in `config.yaml` to the right index.
- **`FileNotFoundError: LLM model not found`:** set `llm.model_path` to your GGUF file.
- **Too slow on CPU:** use a smaller Whisper model (`base`/`small`) and a smaller,
  more quantized GGUF (3B, `q4_k_m`), or use a GPU.
- **She interrupts / cuts you off:** raise `vad.min_silence_ms`.

## Notes

- 100% offline after the one-time model downloads. Safe to run with networking disabled.
- Everything is local; no data leaves your machine.


---

## 🇯🇵 RTX 2070（VRAM 8GB）向け かんたんスタート手順

RTX 2070 でも問題なく動きます。VRAM が 8GB なので、**LLM は 3B モデル**を使うのがおすすめです（4つのモデル全部載せても余裕があります）。

### 前提
- NVIDIA ドライバがインストール済み
- Python 3.10〜3.12
- Git

### Windows の場合

```powershell
# 1. リポジトリを取得
git clone https://github.com/tunachan0429/AI-talking.git
cd AI-talking

# 2. 仮想環境を作成
python -m venv .venv
.venv\Scripts\activate

# 3. 基本パッケージをインストール
pip install -r requirements.txt

# 4. GPU版 PyTorch を入れる（RTX 2070 = CUDA対応）
pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121

# 5. llama-cpp-python を GPU(CUDA)対応でビルド
$env:CMAKE_ARGS="-DGGML_CUDA=on"
pip install --force-reinstall --no-cache-dir llama-cpp-python

# 6. LLMモデル（3B・約2GB）をダウンロード
pip install huggingface_hub
mkdir models\llm
huggingface-cli download Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b-instruct-q4_k_m.gguf --local-dir models\llm

# 7. マイク・スピーカーの確認（必要なら config.yaml で番号指定）
python run.py --list-devices

# 8. 起動！話しかけてみてください（Ctrl+C で終了）
python run.py
```

### Linux の場合

```bash
sudo apt install portaudio19-dev            # マイク用ライブラリ
git clone https://github.com/tunachan0429/AI-talking.git
cd AI-talking
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu121
CMAKE_ARGS="-DGGML_CUDA=on" pip install --force-reinstall --no-cache-dir llama-cpp-python
pip install huggingface_hub
mkdir -p models/llm
huggingface-cli download Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b-instruct-q4_k_m.gguf --local-dir models/llm
python run.py
```

### 初回起動について
- Whisper / Silero VAD / Kokoro のモデルは**初回だけ自動ダウンロード**されます（数分）。以降は完全オフラインで動きます。
- 起動時に「モデルを読み込み中...」→「準備完了。話しかけてください。」と出れば成功です。

### VRAM が足りない/OOMエラーが出たら
- `config.yaml` の `stt.model` を `base` に下げる
- `llm.n_ctx` を `2048` に下げる

### もっと賢くしたい（7Bを使いたい）場合
7B（約4.7GB）も 8GB に載りますが、他のモデルと合わせるとギリギリです。試すなら:
```yaml
llm:
  model_path: models/llm/qwen2.5-7b-instruct-q4_k_m.gguf
  n_gpu_layers: 28          # 全部(-1)だとOOMのことがあるので一部だけGPUに
  n_ctx: 2048
```
でダウンロードは:
```bash
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF qwen2.5-7b-instruct-q4_k_m.gguf --local-dir models/llm
```

うまく動かない時はエラーメッセージを教えてください。一緒に直します。
