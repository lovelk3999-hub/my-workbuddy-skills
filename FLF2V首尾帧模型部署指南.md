# Wan2.1 FLF2V-14B 首尾帧模型部署指南

> 部署到 HAI 云端 A10 24GB
> 模型：首帧+尾帧 → 5秒 720P 视频

---

## 一、模型文件清单

下载以下文件放到 ComfyUI 对应目录（已有文件可跳过）：

### 需要新增的

| 文件 | 大小 | 存放路径 | 来源 |
|:----|:----|:---------|:-----|
| **扩散模型（二选一）** | | `models/diffusion_models/` | HuggingFace |
| └ `wan2.1_flf2v_720p_14B_fp16.safetensors` | ~16GB | ⬆ | ✅ 推荐（质量优先） |
| └ `wan2.1_flf2v_720p_14B_fp8_e4m3fn.safetensors` | ~8GB | ⬆ | ⬆ 省显存方案 |

### 已有的（可以直接复用）

| 文件 | 大小 | 存放路径 | 状态 |
|:----|:----|:---------|:----:|
| VAE (wan_2.1_vae.safetensors) | 243MB | `models/vae/` | ✅ 已有 |
| CLIP Vision (clip_vision_h.safetensors) | 1.2GB | `models/clip_vision/` | ✅ 已有 |
| umt5 (umt5-xxl-enc-bf16.safetensors) | 11GB | `models/text_encoders/` | ✅ 已有 |

---

## 二、A10 24GB 优化方案

### 方案 A：FP16 + VAE Slicing（推荐，质量优先）

```
模型:     wan2.1_flf2v_720p_14B_fp16.safetensors (16GB)
分辨率:   720x1280 
帧数:     81帧 (≈5秒@16fps)
优化:     enable_vae_slicing() + enable_model_cpu_offload()
预计显存: ~21-23GB（A10 24GB 刚好够）
预计耗时: 15-20分钟/段
```

**在 ComfyUI 中的设置：**
- 工作流使用 ComfyUI 原生 FLF2V 节点（`WanFirstLastFrameToVideo`）
- 勾选 `enable_vae_slicing` 和 `enable_model_cpu_offload`
- 如果爆显存 → 切到 480p 或 FP8

### 方案 B：FP8（更快，省显存）

```
模型:     wan2.1_flf2v_720p_14B_fp8_e4m3fn.safetensors (8GB)
分辨率:   720x1280
帧数:     81帧
优化:     基本无需额外优化
预计显存: ~14-16GB
预计耗时: 8-12分钟/段
```

**优缺点：** 速度快 40%，质量损失肉眼几乎不可察觉。推荐先用这个。

### 方案 C：TeaCache + SageAttention（极速）

如需进一步加速，可以安装优化插件：

```bash
# 在 HAI 实例上安装 Triton + SageAttention
cd /home/ubuntu/ComfyUI
source venv/bin/activate
pip install triton sageattention

# TeaCache 已在 WanVideoWrapper 中集成，启用即可
```

预计提速：**30-50%**，生成时间降至 **5-8分钟/段**

---

## 三、安装步骤（在 OrcaTerm 中执行）

### 1. 下载 FLF2V 扩散模型

```bash
cd /home/ubuntu/ComfyUI/models/diffusion_models/

# 方案 A：FP16（16GB，质量优先）
wget https://huggingface.co/Wan-AI/Wan2.1-FLF2V-14B-720P/resolve/main/wan2.1_flf2v_720p_14B_fp16.safetensors

# 方案 B：FP8（8GB，快速）
# wget https://huggingface.co/Wan-AI/Wan2.1-FLF2V-14B-720P/resolve/main/wan2.1_flf2v_720p_14B_fp8_e4m3fn.safetensors
```

> ⚠️ 如果 HuggingFace 下载慢，用镜像：
> ```bash
> export HF_ENDPOINT=https://hf-mirror.com
> ```

### 2. 获取工作流文件

下载 FLF2V 的 ComfyUI 工作流 `.png` 文件（拖入 ComfyUI 即可加载）：
- ComfyUI 官网示例：https://docs.comfy.org/zh/tutorials/video/wan/wan-flf

或者用 Kijai 的 WanVideoWrapper（功能更全）：
```bash
cd /home/ubuntu/ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
```

### 3. 重启 ComfyUI

```bash
sudo systemctl restart comfyui.service
```

---

## 四、使用流程

```
打开 http://<HAI_IP>:6889
  ↓
拖入 FLF2V 工作流
  ↓
上传首帧图片（Start Image）
上传尾帧图片（End Image）
  ↓
写 Prompt（可选，描述画面内容）
  ↓
设置尺寸：720x1280
设置帧数：81（≈5秒）
  ↓
点击 Queue Prompt
  ↓
等待 10-20 分钟 → 出片
```

## 五、故障排查

| 问题 | 原因 | 解决 |
|:----|:-----|:-----|
| OOM / 显存不足 | FP16 模型 + 720p 超 24GB | 换 FP8 模型 / 降到 480p |
| 生成极慢 | 没开优化 | 启用 VAE slicing + CPU offload |
| 首尾帧不一致 | 两张图风格/人物差异太大 | 保证首尾帧是同一个人/场景 |
| 画面闪烁 | noise_aug_strength 太高 | 降到 0.15 |
