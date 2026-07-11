#!/usr/bin/env python3
"""
Index-TTS 批量合成 — 从 config.local.json 读取配置和段落

用法:
  python scripts/batch_synthesize_v2.py

配置: scripts/config.local.json
  参考 config.example.json，segments 数组的格式:
    [id, 名称, 文本, 8维情感向量]
"""

import os, sys, time, json, torch

script_dir = os.path.dirname(os.path.abspath(__file__))
cfg_path = os.path.join(script_dir, 'config.local.json')
cfg = json.load(open(cfg_path))

model_dir = cfg['model_dir']
ref_audio = os.path.join(model_dir, cfg['ref_audio'])
output_dir = cfg.get('output_dir', './outputs/tts')
if not os.path.isabs(output_dir):
    output_dir = os.path.join(script_dir, '..', output_dir)
os.makedirs(output_dir, exist_ok=True)
emo_alpha = cfg.get('emo_alpha', 0.4)
segments = cfg['segments']

sys.path.insert(0, model_dir)
os.chdir(model_dir)

print("=" * 60)
print("Index-TTS 批量合成")
print("=" * 60)
print(f"参考: {ref_audio}")
print(f"输出: {output_dir}")
print(f"共 {len(segments)} 段, alpha={emo_alpha}")
print()

print(">> 加载模型...")
t_start = time.time()
from indextts.infer_v2 import IndexTTS2
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints",
                 use_fp16=True, use_cuda_kernel=True, use_deepspeed=False)
print(f">> 加载完成，耗时 {time.time()-t_start:.1f}s\n")

skip_count = 0
total_start = time.time()
for i, (sid, name, text, vec) in enumerate(segments, 1):
    out = os.path.join(output_dir, f"{sid}_{name}.wav")
    if os.path.exists(out):
        size_kb = os.path.getsize(out) / 1024
        print(f"[{i}/{len(segments)}] {sid}_{name} 已存在 ({size_kb:.0f}KB), 跳过")
        skip_count += 1
        continue
    print(f"[{i}/{len(segments)}] {sid}_{name}...")
    print(f"    向量: {vec}")
    print(f"    文本: {text[:40]}...")
    t1 = time.time()
    try:
        tts.infer(spk_audio_prompt=ref_audio, text=text, output_path=out,
                  emo_vector=vec, emo_alpha=emo_alpha, verbose=False)
        elapsed = time.time() - t1
        size_kb = os.path.getsize(out) / 1024 if os.path.exists(out) else 0
        print(f"    -> 完成! 耗时 {elapsed:.0f}s, {size_kb:.0f}KB")
    except Exception as e:
        print(f"    -> 失败: {e}")
    torch.cuda.empty_cache()
    print()

total_time = time.time() - total_start
done = len(segments) - skip_count
print("=" * 60)
print(f"完成! 本次合成了 {done} 段, 跳过 {skip_count} 段")
print(f"总耗时: {total_time:.0f}s ({total_time/60:.1f}min)")
print(f"输出目录: {output_dir}")
