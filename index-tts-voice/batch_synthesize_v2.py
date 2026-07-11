import os, sys, time
import torch

from indextts.infer_v2 import IndexTTS2

REF_WAV = r"E:\ai\tareworkspace\tare\调研专用\抖音运营调研\07 视频内容\语音\参考音色_最佳15s.wav"
OUTPUT_DIR = r"E:\ai\tareworkspace\tare\调研专用\抖音运营调研\07 视频内容\语音\01 ai入门"
os.makedirs(OUTPUT_DIR, exist_ok=True)
EMO_ALPHA = 0.4

segments = [
    ('01', '开场钩子', '聊起AI提效，你是不是觉得，AI帮你干活离你太远？', [0,0,0,0,0,0,0.4,0.6]),
    ('02', '效果展示', '这是我的Word文档，这是我让豆包帮我转的PDF，效果还不错吧？', [0.5,0,0,0,0,0,0.3,0.2]),
    ('03', '引入主题', '今天我就手把手教你，免费让豆包帮你干活，', [0.5,0,0,0,0,0,0,0.5]),
    ('04', '下载', '第一步，下载一个豆包电脑版，手机上你肯定用过，电脑版也一样，说话就行。', [0.2,0,0,0,0,0,0,0.8]),
    ('05', '找入口', '打开之后是这个界面，右边是对话框，左边是历史记录和功能区。我们点新对话，然后看对话框最下面，有一排模块，我们点快速，弹出三个选项，选择办公任务。', [0.1,0,0,0,0,0,0,0.9]),
    ('06', '连文件夹', '点完之后，下面的模块就变了，变成了本地电脑、选择项目、技能这几个。你看，本地电脑已经默认选中了，变成蓝色。这时候，豆包已经能接触到你电脑里的文件了。接下来点选择项目，选一个你电脑上的工作文件夹，这个选择项目的意思就是告诉豆包，你想在这个文件夹里让它帮你工作。', [0.3,0,0,0,0,0,0.1,0.6]),
    ('07', '转PDF演示', '选好之后，我们来试一下，跟它说：看看这个文件夹里有什么文件。你看，它马上就列出来了，说明它已经能看到你文件夹里的东西了。帮我把这些文档都转换成PDF格式。好了，豆包开始干活了。AI干活期间，我们就可以开始摸鱼了，嘿嘿。等了两分钟，豆包做完了，让我们来检查一下。打开文件夹后，我们看到PDF已经做好了，点开看看，嗯，效果还行。', [0.4,0,0,0,0,0,0.3,0.3]),
    ('08', '总结', '如果你想调字体大小排版什么的，你就继续跟豆包说，我觉得排版有问题，你调整一下，就可以了。你看，就这么简单，从下载到连接，三步搞定。这就是你AI办公的第一步。', [0.4,0,0,0,0,0,0.1,0.5]),
    ('09', '结尾CTA', '觉得有用的先收藏起来，下次转PDF不用找会员了。关注我，下期教你用这个功能批量转一百个文件。我是李大牛，带你用AI摸鱼，偷偷涨工资。', [0.5,0,0,0,0,0,0.2,0.3]),
]

print("=" * 60)
print("Index-TTS 批量合成 - AI入门系列第一期")
print("=" * 60)
print(f"参考: {REF_WAV}")
print(f"输出: {OUTPUT_DIR}")
print(f"共 {len(segments)} 段, alpha={EMO_ALPHA}")
print()

print(">> 加载模型...")
t_start = time.time()
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints",
                 use_fp16=True, use_cuda_kernel=True, use_deepspeed=False)
print(f">> 加载完成，耗时 {time.time()-t_start:.1f}s")
print()

# 跳过已存在的文件（断点续跑）
skip_count = 0
total_start = time.time()
for i, (sid, name, text, vec) in enumerate(segments, 1):
    out = os.path.join(OUTPUT_DIR, f"{sid}_{name}.wav")
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
        tts.infer(spk_audio_prompt=REF_WAV, text=text, output_path=out,
                  emo_vector=vec, emo_alpha=EMO_ALPHA, verbose=False)
        elapsed = time.time() - t1
        size_kb = os.path.getsize(out) / 1024 if os.path.exists(out) else 0
        print(f"    -> 完成! 耗时 {elapsed:.0f}s, {size_kb:.0f}KB")
    except Exception as e:
        print(f"    -> 失败: {e}")
    # 清理显存，防止累积溢出
    torch.cuda.empty_cache()
    print()

total_time = time.time() - total_start
done = len(segments) - skip_count
print("=" * 60)
print(f"完成! 本次合成了 {done} 段, 跳过 {skip_count} 段")
print(f"总耗时: {total_time:.0f}s ({total_time/60:.1f}min)")
print(f"输出目录: {OUTPUT_DIR}")