import os, sys, json, argparse
import torch

parser = argparse.ArgumentParser()
parser.add_argument("--id", required=True)
parser.add_argument("--name", required=True)
parser.add_argument("--text", required=True)
parser.add_argument("--vec", type=json.loads, required=True)
args = parser.parse_args()

from indextts.infer_v2 import IndexTTS2

REF_WAV = r"E:\ai\tareworkspace\tare\调研专用\抖音运营调研\07 视频内容\语音\参考音色_最佳15s.wav"
OUTPUT_DIR = r"E:\ai\tareworkspace\tare\调研专用\抖音运营调研\07 视频内容\语音\01 ai入门"
os.makedirs(OUTPUT_DIR, exist_ok=True)
out = os.path.join(OUTPUT_DIR, f"{args.id}_{args.name}.wav")

print(f">> 加载模型...")
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints",
                 use_fp16=True, use_cuda_kernel=True, use_deepspeed=False)

print(f">> 合成: {args.text[:40]}...")
tts.infer(spk_audio_prompt=REF_WAV, text=args.text, output_path=out,
          emo_vector=args.vec, emo_alpha=0.4, verbose=False)

torch.cuda.empty_cache()
size_kb = os.path.getsize(out) / 1024 if os.path.exists(out) else 0
print(f">> 输出: {out} ({size_kb:.0f}KB)")