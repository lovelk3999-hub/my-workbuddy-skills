# 网页 AI 对话同步器

读取 / 归档 **AI 对话分享链接**的完整正文（ChatGPT `share`、Claude、Gemini、Kimi、豆包、通义等）。

这类分享页大多是**纯前端 SPA**：对话正文由 JavaScript 在浏览器里渲染后才塞进 DOM。用 `curl` / 普通网页抓取只能拿到空骨架，正文是空的。

本 skill 的做法：**不抓 HTML，而是通过本地 CDP 代理接管你的真实 Chrome，打开分享链接，等页面把完整对话渲染进 DOM，再用 JS 把正文整段抠出来，落盘为 Markdown + JSON。**

---

## ⚠️ 前置：必须先连接「Web Access（浏览器自动化）」技能

本 skill **不自带**浏览器代理，它复用 **Web Access（浏览器自动化）** 技能启动并维护的本地 CDP 代理（`http://localhost:3456`）。

> **所以运行本 skill 前，务必先启用并连接好 `Web Access（浏览器自动化）` 技能。** 没有它，`localhost:3456` 不存在，本脚本无法工作。

连接步骤：

1. 启用 / 加载 **Web Access（浏览器自动化）** 技能。
2. 让它跑一次前置检查，把 CDP 代理拉起来：

   ```bash
   node "<web-access skill 目录>/scripts/check-deps.mjs"
   ```

   脚本会依次检查 Node.js、浏览器调试端口，并确保 Proxy 已连接（未运行则自动启动并等待）。Proxy 启动后会常驻运行。

3. 首次连接时，需要在弹出的浏览器授权框中**允许 CDP 连接**（接管你的真实 Chrome / Edge）。

4. 自检代理是否就绪：

   ```bash
   curl -s http://localhost:3456/targets
   ```

   返回 JSON（tab 列表）即正常；无响应说明代理未启动，回到第 2 步。

---

## 环境要求

| 依赖 | 说明 |
|---|---|
| **Web Access 技能** | 提供 `localhost:3456` CDP 代理，**必须先连接**（见上） |
| **Node.js 22+** | Web Access 的 CDP 代理依赖（使用原生 WebSocket） |
| **Python 3** | 运行 `scripts/sync_ai_chat.py`（仅用标准库，无需 pip 安装） |
| **curl** | 脚本通过 curl 调用 CDP 代理的 HTTP API（Windows 10+/macOS/Linux 均自带） |
| **真实 Chrome / Edge** | 由 CDP 代理接管；若目标链接需登录才能看，请确保该网站在你的浏览器里已登录 |

> ⚠️ 这是你本人的浏览器 + 本人账号，触发风控 = 赌自己的账号。本 skill 仅做**只读渲染 + 文本抽取**，不登录、不输入、不点击、不并发，风险极低。

---

## 使用方法

确认 CDP 代理已就绪后：

```bash
# 基本：读一个分享链接，存到默认目录
python scripts/sync_ai_chat.py "<分享链接>"

# 指定输出目录
python scripts/sync_ai_chat.py "<分享链接>" "D:/path/to/输出目录"
```

示例：

```bash
python scripts/sync_ai_chat.py "https://chatgpt.com/share/xxxxxxxx"
```

### 脚本行为

1. `POST /new <url>` 开新后台标签，自动识别平台（chatgpt / claude / gemini / kimi / doubao / tongyi / generic）。
2. 等待首屏渲染，并多次滚动到底部（间隔 2.5s）触发 AI 对话的**懒加载**，直到文本长度不再增长（最多 12 次）。
3. 抽取正文：
   - **ChatGPT**：优先抓 `<article>`（分享页对话容器），回退 `main` / 整页 `innerText`。
   - **其他平台**：直接取整页 `innerText`（最稳妥，会带少量 UI 噪音但正文完整）。
4. 保存两份到输出目录：
   - `AI对话-<平台>-<slug>.md`（带来源 / 平台 / 时间 / 字数 元信息头 + 正文）
   - `AI对话-<平台>-<slug>.json`（结构化备份）
5. 关闭标签，打印字数。

---

## 输出示例

```
AI对话-chatgpt-abc12345.md
AI对话-chatgpt-abc12345.json
```

`.md` 头部形如：

```markdown
# AI 对话同步存档

- 来源: https://chatgpt.com/share/abc12345
- 平台: chatgpt
- 同步时间: 2026-07-21 02:45:00
- 字数: 8213

---

（对话正文…）
```

---

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `开新标签页失败` / curl 无响应 | CDP 代理没起来 → 先连接 **Web Access** 技能并跑 `check-deps.mjs` |
| 提取到的正文过短 / 为空 | 页面未登录、触发验证、或链接失效 → 在真实 Chrome 里登录对应网站后重试 |
| 长对话只抓到前半段 | 懒加载未触发完 → 脚本已内置滚动，若仍不全可调大 `wait_render` 的 `max_scrolls` |
| `curl https://chatgpt.com/share/xxx` 拿不到正文 | 分享页是 SPA，**必须走 CDP 渲染路径**，不能硬抓 HTML |

---

## 扩展

- **新增平台精提取**：在 `detect_platform` 注册域名，在脚本里加 `extract_<平台>` 函数（用 `querySelector` 精确定位对话容器）即可。
- **批量存档**：循环调用 `sync_ai_chat.py`，每个链接独立开 / 关标签，之间留 3–5s 间隔更像真人。
- **后续分析**：把生成的 `.md` 直接喂给模型做总结即可。

---

## 目录结构

```
网页ai对话同步器/
├── README.md              # 本文件
├── SKILL.md               # skill 定义与要点
├── references/
│   └── cdp-proxy.md       # 本地 CDP 代理协议说明
└── scripts/
    └── sync_ai_chat.py    # 核心脚本
```
