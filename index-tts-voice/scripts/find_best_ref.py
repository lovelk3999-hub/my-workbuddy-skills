#!/usr/bin/env python3
"""
从录音中找到能量最高的 15 秒片段，用于 Index-TTS 音色克隆参考。
Index-TTS 只取前 13.8 秒，所以必须裁剪出最优片段。

用法:
  python scripts/find_best_ref.py --input 录音.wav --output 参考音色_最佳15s.wav
"""

import argparse, soundfile as sf, numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True, help="输入录音 WAV")
parser.add_argument("--output", required=True, help="输出最佳片段 WAV")
parser.add_argument("--duration", type=float, default=15, help="目标片段时长（秒）")
args = parser.parse_args()

y, sr = sf.read(args.input)
dur_s = int(args.duration * sr)

best_energy, best_start = 0, 0
for start in range(3 * sr, len(y) - dur_s, sr):
    seg = y[start:start + dur_s]
    energy = float(np.sqrt(np.mean(seg ** 2)))
    if energy > best_energy:
        best_energy = energy
        best_start = start

best = y[best_start:best_start + dur_s]
sf.write(args.output, best, sr)
print(f"最佳片段: 偏移 {best_start/sr:.1f}s, 能量 {best_energy:.4f}")
print(f"输出: {args.output}")
