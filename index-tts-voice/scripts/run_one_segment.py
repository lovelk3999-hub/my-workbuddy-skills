#!/usr/bin/env python3
"""
Index-TTS 单段合成 — 从 config.local.json 读取路径配置

用法:
  python scripts/run_one_segment.py ^
      --id "01" --name "段落名" ^
      --text "要合成的文案" ^
      --vec "[0.5, 0, 0, 0, 0, 0, 0.3, 0.2]"

配置: scripts/config.local.json
  model_dir    — Index-TTS 模型目录（含 checkpoints/）
  ref_audio    — 参考音频文件名（相对于 model_dir）
  output_dir   — 输出目录
  emo_alpha    — 情感强度 (0.0~1.0)
"""

import os, sys, json, argparse, torch

# 加载配置
script_dir = os.path.dirname(os.path.abspath(__file__))
cfg_path = os.path.join(script_dir, 'config.local.json')
cfg = json.load(open(cfg_path))

parser = argparse.ArgumentParser()
parser.add_argument("--id", required=True)
parser.add_argument("--name", required=True)
parser.add_argument("--text", required=True)
parser.add_argument("--vec", type=json.loads, required=True)
args = parser.parse_args()

model_dir = cfg['model_dir']
ref_audio = os.path.join(model_dir, cfg['ref_audio'])
output_dir = cfg.get('output_dir', './outputs/tts')
if not os.path.isabs(output_dir):
    output_dir = os.path.join(script_dir, '..', output_dir)
os.makedirs(output_dir, exist_ok=True)
emo_alpha = cfg.get('emo_alpha', 0.4)

out = os.path.join(output_dir, f"{args.id}_{args.name}.wav")

sys.path.insert(0, model_dir)
os.chdir(model_dir)

print(f">> 加载模型 (model_dir={model_dir})...")
from indextts.infer_v2 import IndexTTS2
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints",
                 use_fp16=True, use_cuda_kernel=True, use_deepspeed=False)

print(f">> 合成: {args.text[:40]}...")
tts.infer(spk_audio_prompt=ref_audio, text=args.text, output_path=out,
          emo_vector=args.vec, emo_alpha=emo_alpha, verbose=False)

torch.cuda.empty_cache()
size_kb = os.path.getsize(out) / 1024 if os.path.exists(out) else 0
print(f">> 输出: {out} ({size_kb:.0f}KB)")
