#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页 AI 对话同步器 —— 通用脚本
通过本地 CDP 代理 (http://localhost:3456) 接管用户真实 Chrome，
打开 AI 对话分享链接，等 SPA 完整渲染后，从 DOM 抽取对话正文，落盘 Markdown + JSON。

用法:
  python sync_ai_chat.py "<分享链接>" [输出目录]

依赖: 本地 CDP 代理正在运行 (与 BOSS/抖音采集同一通道)。
"""
import subprocess, json, time, sys, os, re

BASE = "http://localhost:3456"
DEFAULT_OUT = r"E:\ai\job\短视频需求类公司调研\来源参考"

# ---- CDP 代理封装 ----
def curl_post(path, data=None):
    cmd = ["curl", "-s", "-X", "POST", BASE + path]
    if data is not None:
        cmd += ["--data-raw", data]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout

def curl_get(path):
    return subprocess.run(["curl", "-s", BASE + path], capture_output=True, text=True, timeout=60).stdout

def new_tab(url):
    r = curl_post("/new", url)
    try:
        return json.loads(r)["targetId"]
    except Exception:
        raise RuntimeError("开新标签页失败: " + url[:60] + " | 代理返回=" + r[:200])

def eval_js(tid, js):
    raw = curl_post(f"/eval?target={tid}", js)
    try:
        v = json.loads(raw).get("value")
        # 代理把结果 JSON.stringify 一次；若 value 仍是字符串(JS 返回字符串)，再解析一次
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                pass
        return v
    except Exception:
        return None

def close_tab(tid):
    curl_get(f"/close?target={tid}")

# ---- 平台识别 ----
def detect_platform(url):
    u = url.lower()
    if "chatgpt.com" in u or "chat.openai.com" in u:
        return "chatgpt"
    if "claude.ai" in u:
        return "claude"
    if "gemini.google.com" in u:
        return "gemini"
    if "kimi" in u:
        return "kimi"
    if "doubao" in u or "douyin" in u or "bot.tw" in u:
        return "doubao"
    if "tongyi" in u or "qianwen" in u or "aliyun" in u:
        return "tongyi"
    return "generic"

# ---- 渲染等待：滚动触发懒加载，长度稳定即停 ----
def wait_render(tid, max_scrolls=12, scroll_gap=2.5):
    time.sleep(4)  # 首屏渲染
    prev = -1
    for i in range(max_scrolls):
        h1 = eval_js(tid, "(() => (document.body.innerText||'').length)()")
        curl_get(f"/scroll?target={tid}&direction=bottom")
        time.sleep(scroll_gap)
        h2 = eval_js(tid, "(() => (document.body.innerText||'').length)()")
        h1 = h1 if isinstance(h1, int) else -1
        h2 = h2 if isinstance(h2, int) else -1
        if prev != -1 and h2 <= prev:
            break
        prev = h2

# ---- 正文抽取 ----
def extract_chatgpt(tid):
    # 分享页对话容器优先 article，回退 main / body
    js = r"""(() => {
      const el = document.querySelector('article') || document.querySelector('main') || document.body;
      return el ? (el.innerText || '') : '';
    })()"""
    return eval_js(tid, js) or ""

def extract_generic(tid):
    return eval_js(tid, "(() => document.body.innerText || '')()") or ""

# ---- 输出文件名 ----
def slugify(url):
    m = re.search(r"/share/([\w-]+)", url) or re.search(r"/([\w-]{8,})/?$", url)
    if m:
        return m.group(1)
    return re.sub(r"\W+", "_", url)[:40]

# ---- 主流程 ----
def sync(url, out_dir=DEFAULT_OUT):
    os.makedirs(out_dir, exist_ok=True)
    platform = detect_platform(url)
    print(f"[平台] {platform} | {url}")
    tid = new_tab(url)
    try:
        wait_render(tid)
        text = extract_chatgpt(tid) if platform == "chatgpt" else extract_generic(tid)
        text = (text or "").strip()
        if not text:
            print("[warn] 未提取到文本 —— 可能页面未登录/触发验证/链接失效")
        slug = slugify(url)
        ts = time.strftime("%Y%m%d-%H%M%S")
        md_path = os.path.join(out_dir, f"AI对话-{platform}-{slug}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# AI 对话同步存档\n\n")
            f.write(f"- 来源: {url}\n")
            f.write(f"- 平台: {platform}\n")
            f.write(f"- 同步时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 字数: {len(text)}\n\n")
            f.write("---\n\n")
            f.write(text)
        json_path = os.path.join(out_dir, f"AI对话-{platform}-{slug}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"url": url, "platform": platform, "text": text},
                      f, ensure_ascii=False, indent=1)
        print(f"[完成] 字数={len(text)} | {md_path}")
        return md_path
    finally:
        close_tab(tid)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sync_ai_chat.py <分享链接> [输出目录]")
        sys.exit(1)
    url = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    sync(url, out)
