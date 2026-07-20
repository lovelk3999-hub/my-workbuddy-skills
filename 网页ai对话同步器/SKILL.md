---
name: 网页ai对话同步器
description: 用于读取/归档 AI 对话分享链接的完整内容（ChatGPT share、Claude、Gemini、Kimi、豆包、通义等）。当分享页是 JavaScript 渲染的 SPA，普通网页抓取（WebFetch/curl）只能拿到空壳、对话正文为空时，使用此 skill。它通过本地 CDP 代理接管用户的真实 Chrome，让页面完整渲染后再从 DOM 抽取对话正文，保存为 Markdown/JSON。适用于「把我和某 AI 的对话存档」「帮我把这个分享链接的全文读出来」「CDP 渲染抓 SPA 文本」等场景。
agent_created: true
---

# 网页 AI 对话同步器

## Overview

很多 AI 对话分享页（ChatGPT `chatgpt.com/share/...`、Claude `claude.ai/share`、Gemini、Kimi、豆包、通义等）是**纯前端 SPA**：对话正文由 JavaScript 在浏览器里渲染后才塞进 DOM。用 WebFetch / curl 直接抓 HTML，只能拿到一个空骨架，正文是空的。

本 skill 的方法：**不抓 HTML，而是用本地 CDP 代理（`http://localhost:3456`）接管用户的真实 Chrome，打开分享链接，等页面把完整对话渲染进 DOM，再用 JS eval 把对话正文（`innerText`）整段抠出来，落盘成 Markdown/JSON。**

核心脚本 `scripts/sync_ai_chat.py` 封装了「开标签 → 等待+滚动触发懒加载 → 抽取正文 → 保存」全流程。

## 前置条件

- 本地 CDP 代理正在运行，地址 `http://localhost:3456`（同一通道也用于 BOSS / 抖音采集）。
- 该代理已接管用户的**真实 Chrome + 真实登录态**（IP 与账号均为用户本人）。
- 快速自检：`curl -s http://localhost:3456/`，返回 JSON（含 targets 列表）即正常；无响应说明代理未启动，先启动 CDP 代理再跑。
- CDP 协议细节见 `references/cdp-proxy.md`。

> ⚠️ 这是用户本人浏览器 + 本人账号，触发风控 = 赌自己的账号。本 skill 仅做**只读渲染 + 文本抽取**，不登录、不输入、不点击、不并发，风险极低；但若链接本身需登录才能看，请确保对应网站在真实 Chrome 里已登录。

## 用法

```bash
# 基本：读一个分享链接，存到默认目录
python scripts/sync_ai_chat.py "<分享链接>"

# 指定输出目录
python scripts/sync_ai_chat.py "<分享链接>" "E:/ai/job/短视频需求类公司调研/来源参考"
```

脚本行为：
1. `POST /new <url>` 开新标签，自动识别平台（chatgpt/claude/gemini/generic）。
2. 等待首屏渲染，并多次滚动到页面底部（间隔 2.5s）触发 AI 对话的**懒加载**，直到文本长度不再增长。
3. 抽取正文：
   - ChatGPT：优先抓 `article`（分享页对话容器），回退 `main` / 整页 `innerText`。
   - 其他平台：直接取整页 `innerText`。
4. 保存两份：`AI对话-<平台>-<slug>.md`（带元信息头 + 正文）与同名词 `.json`（结构化备份）。
5. 关闭标签，打印字数。

## 平台提取要点（踩坑记录）

- **ChatGPT share**：对话在 `<article>` 内；整页 `innerText` 已包含用户/助手全部轮次。若正文过短，多半是页面未登录或触发了「继续生成」滑块——先确认真实 Chrome 已登录 ChatGPT。
- **Claude / Gemini / Kimi / 豆包 / 通义**：结构各异，统一回退整页 `innerText` 最稳妥（会带一点 UI 噪音，但正文完整）。如需更干净，可在脚本 `extract_generic` 里加 `querySelector` 精确定位。
- **懒加载**：AI 长对话常分批渲染，不滚动会漏掉后半段。脚本默认最多滚 12 次、长度稳定即停。
- **不要硬抓 HTML**：`curl https://chatgpt.com/share/xxx` 拿不到正文，必须走 CDP 渲染路径。

## 扩展

- 想加新平台精提取：在 `detect_platform` 注册域名，在脚本末尾加 `extract_<平台>` 函数即可。
- 想批量存档多个链接：循环调用 `sync_ai_chat.py`，每个链接独立开/关标签，之间留 3–5s 间隔更像真人。
- 抽取结果若需进一步分析（如让模型总结），把 `.md` 直接喂给模型即可。
