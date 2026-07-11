---
name: index-tts-voice
description: >-
  Index-TTS2 语音合成工作流。使用 Index-TTS2 模型进行音色克隆+情感控制的
  语音合成。支持从参考音频准备、情感边界测试到批量合成的完整流程。
  Triggers: "Index-TTS", "语音合成", "TTS", "配音", "index-tts",
  "克隆声音", "合成语音".
agent_created: true
domain: ["audio", "tts", "voice-cloning", "video-production"]
---

# Index-TTS2 语音合成工作流

基于 IndexTTS2（B站开源）的零样本语音合成，支持情感表达与音色解耦。
适合给短视频配音、旁白合成、声音克隆。

官方仓库: https://github.com/index-tts/index-tts

---

## ⚡ Pre-Flight Check

Before running any command, ALWAYS run this sequence:

### Step 1 — Check GPU

```bash
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, VRAM: {torch.cuda.get_device_properties(0).total_memory/1024**3:.0f}GB')"
```

Expected: `CUDA: True, VRAM: 8+ GB`

### Step 2 — Check model directory

```bash
ls scripts/config.local.json && ls <model_dir>/checkpoints/config.yaml
```

`model_dir` is read from `config.local.json`.

### Step 3 — Check Python venv

```bash
<venv_path> --version
```

Where `<venv_path>` is from `config.local.json`.

---

## Setup (First Time)

### 1. Download the model

```bash
# 克隆仓库
git clone https://github.com/index-tts/index-tts.git E:/ai/index-tts
cd E:/ai/index-tts

# 下载 checkpoints
# 从 HuggingFace 或官方 Release 下载约 5.9GB
# 放到 E:/ai/index-tts/checkpoints/
```

### 2. Create Python environment

```bash
cd E:/ai/index-tts
python3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### 3. Create config.local.json

Copy `scripts/config.example.json` to `scripts/config.local.json`,
fill in your actual `model_dir` and `venv_path`.

### 4. Prepare reference audio

Record 15-30 seconds of clean voice, save as WAV (24000Hz, mono).

---

## Usage

### 1. 准备参考音频（优化片段）

Index-TTS 只取音频前 13.8 秒做音色参考，所以要先找到能量最高的 15 秒：

```bash
# 转格式
ffmpeg -i input.m4a -acodec pcm_s16le -ar 24000 -ac 1 temp.wav

# 运行脚本找最佳片段
python scripts/find_best_ref.py --input temp.wav --output 参考音色_最佳15s.wav
```

### 2. 情感边界测试

```bash
python scripts/test_boundary.py
```

在 emo_alpha=0.0, 0.4, 0.8 三个梯度下测试，找音色不崩的最大值。

### 3. 单段合成

```bash
<venv_path> scripts/run_one_segment.py ^
    --id "01" --name "段落名" ^
    --text "要合成的文案" ^
    --vec "[0.5, 0, 0, 0, 0, 0, 0.3, 0.2]"
```

### 4. 批量合成

编辑 `scripts/config.local.json` 中的 `segments` 数组，
然后运行：

```bash
<venv_path> scripts/batch_synthesize_v2.py
```

---

## 情感控制

### 8维情感向量

固定顺序: `[高兴, 愤怒, 悲伤, 害怕, 厌恶, 忧郁, 惊讶, 平静]`

### 常用向量速查

| 想要的感觉 | 推荐向量 |
|:---------|:----------------------------------------|
| 纯克隆（无情感） | [0, 0, 0, 0, 0, 0, 0, 1.0] |
| 得意/炫耀 | [0.5, 0, 0, 0, 0, 0, 0.3, 0.2] |
| 狡黠/分享秘密 | [0.5, 0, 0, 0, 0, 0, 0, 0.5] |
| 惊讶/设问 | [0, 0, 0, 0, 0, 0, 0.4, 0.6] |
| 耐心教学 | [0.1, 0, 0, 0, 0, 0, 0, 0.9] |
| 自信总结 | [0.4, 0, 0, 0, 0, 0, 0.1, 0.5] |

### 4种情感控制模式

| 模式 | 方式 | 参数 |
|:---:|:----|:-----|
| 0 | 与参考音频相同 | 默认 |
| 1 | 情感参考音频 | `emo_audio_prompt=xxx.wav` |
| **2** | **情感向量 ⭐** | `emo_vector=[...]` + `emo_alpha` |
| 3 | 描述文本 | `use_emo_text=True` + `emo_text="极度悲伤"` |

### 内置偏置表

| 维度 | 偏置 | 说明 |
|:----|:----:|:-----|
| 高兴/愤怒/厌恶/忧郁 | 0.875~0.9375 | 轻微压制 |
| 悲伤/害怕 | 1.0 | 不压 |
| 惊讶 | 0.6875 | 压最多（易出怪声） |
| 平静 | 0.5625 | 最安全 |

---

## 已知问题

### ❌ 音色不像本人
**原因**: 用了全长录音，模型只取前13.8秒（可能含空白）
**解决**: 手动裁剪能量最高的15秒片段

### ❌ 批量合成显存溢出
**原因**: 连续合成导致显存累积
**解决**: 每段跑独立进程（进程退出后显存完全释放），或降低 batch size

### ❌ emo_alpha 太高音色变
**原因**: alpha>=0.6 时情感侵入音色空间
**解决**: 保持 alpha<=0.4

### ⚠️ 无害警告
- `Passing a tuple of past_key_values is deprecated` — transformers 版本提示
- `Failed to load custom CUDA kernel` — 自动回退到 torch，可忽略
- `TypeError: unsupported operand type(s)` — 同上

---

## 性能参考（RTX 3070）

| 音频时长 | 合成耗时 |
|:--------|:--------|
| ~5秒（25字） | ~45s |
| ~10秒（66字） | ~25-60s |
| ~15秒（78字） | ~35-100s |

她 16GB 显存会比这个快很多。

---

## 文件结构

```
index-tts-voice/
├── SKILL.md
├── .gitignore
└── scripts/
    ├── config.example.json    ← Template (safe to share)
    ├── config.local.json      ← YOUR config (per machine, NOT shared)
    ├── run_one_segment.py     ← Single segment synthesize
    ├── batch_synthesize_v2.py ← Batch synthesize from config
    └── find_best_ref.py       ← Find best 15s audio segment
```
