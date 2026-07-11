---
name: 苦工ai-agnes
description: 免费的多模态体力活外包系统。将体力活（文本/批量/翻译/做图/做视频）委托给 Agnes 免费 API 执行，主AI只负责动脑子和决策。触发词："苦工"/"Agnes"/"免费API"/"体力活"/"批量处理"/"翻译"/"做图"/"做视频"
---

# 苦工AI Agnes — 免费的多模态体力活外包系统

> **一句话原则：动脑子的主AI干，动手的Agnes干。**

## 核心概念

| 角色 | 谁 | 做什么 | 成本 |
|:----|:---|:------|:----|
| **主AI** | Codex/Claude | 复杂推理、写代码、决策、调浏览器 | 贵（按token计费） |
| **苦工Agnes** | agnes 免费API | 纯体力活：文本/批量/翻译/做图/做视频 | **免费**（9 Key轮换） |

---

## API 能力总览

苦工Agnes 提供 **三大免费 API**，全部兼容 OpenAI 风格，无需额外费用：

| 能力 | 模型 | API 端点 | 费用 |
|:----|:-----|:---------|:----|
| 💬 **文本对话** | agnes-2.0-flash | POST `/v1/chat/completions` | **免费** |
| 🖼️ **图片生成** | agnes-image-2.1-flash | POST `/v1/images/generations` | **免费**（原价$0.003/张） |
| 🎬 **视频生成** | agnes-video-v2.0 | POST `/v1/videos` → GET 查结果 | **免费**（原价$0.005/秒） |

所有 API 公用同一个 **Key Pool**，自动轮换、容错。

---

## Key Pool 配置

苦工有 **9个免费API Key**，以 Key Pool 形式存放在本地配置文件中。

**配置加载优先级：**
1. `scripts/config.local.json`（与本 skill 同目录）← **推荐方式**
2. `E:\ai\vedio_maker\config.local.json`（项目旧路径，兼容）
3. 环境变量 `AGNES_KEYS`（JSON 数组字符串）

**配置模板（`scripts/config.example.json`）：**

```json
{
    "agnes_keys": [
        "sk-your_key_1_here",
        "sk-your_key_2_here",
        "sk-your_key_3_here"
    ]
}
```

| 特性 | 说明 |
|:-----|:------|
| 来源 | `scripts/config.local.json`（或向下兼容旧路径） |
| Key数量 | 9个 |
| 轮换策略 | round-robin，自动切到下一个 |
| 容错 | 某个Key被rate limit，60秒后自动切下一个重试 |
| Base URL | `https://apihub.agnes-ai.com/v1` |
| 费用 | **永久免费** |```

| 特性 | 说明 |
|:-----|:------|
| 来源 | `E:\ai\vedio_maker\config.local.json` |
| Key数量 | 9个 |
| 轮换策略 | round-robin，自动切到下一个 |
| 容错 | 某个Key被rate limit，60秒后自动切下一个重试 |
| Base URL | `https://apihub.agnes-ai.com/v1` |
| 费用 | **永久免费** |

---

## 决策树：什么时候叫苦工

```
当前任务 →
  ↓
需要写代码/改模板/调浏览器/操作文件/Git？ → YES → 主AI自己干
需要复杂判断/选方案/设计架构？            → YES → 主AI自己干
  ↓ NO
需要批量文本处理/格式化/翻译/总结？       → YES → 叫苦工做文本！💬
需要生成图片/编辑图片？                   → YES → 叫苦工做图！🖼️
需要生成视频/图生视频？                   → YES → 叫苦工做视频！🎬
```

### 典型场景判断表

| 任务类型 | 用谁 | 调用方式 |
|:---------|:----|:---------|
| 写代码/改模板/调浏览器 | 主AI | — |
| Git/部署/系统操作 | 主AI | — |
| 决策/选方案/设计架构 | 主AI | — |
| --- | --- | --- |
| **把采集的数据格式化成JSON** | **Agnes文本** | `agnesChat()` |
| **批量写FAQ/描述/OG标签** | **Agnes文本** | `agnesBatch()` |
| **翻译/总结/提炼要点** | **Agnes文本** | `agnesChat()` |
| **整理定价/功能数据** | **Agnes文本** | `formatToolsJson()` |
| **生成产品/封面/配图** | **Agnes图片** | `agnesImage()` |
| **风格迁移/图片编辑** | **Agnes图片** | `agnesImageEdit()` |
| **文生营销/展示视频** | **Agnes视频** | `agnesVideo()` |
| **图生视频（图片动起来）** | **Agnes视频** | `agnesVideoFromImage()` |

---

## 使用方式

### 方式一：Node.js (Codex MCP 环境)

> 前置：`scripts/agnes_helper.js` 已复制到项目 `scripts/` 目录

#### 1️⃣ 文本对话

```javascript
const agnes = require('./scripts/agnes_helper');

// 单条调用
const text = await agnes.agnesChat(
  "把以下工具数据格式化成JSON: ...",
  "你是一个数据格式化助手"
);

// 批量调用（自动间隔1秒防rate limit）
const results = await agnes.agnesBatch([
  {prompt: "写Copilot的描述", systemPrompt: "SEO助手"},
  {prompt: "写Cursor的描述", systemPrompt: "SEO助手"},
]);

// JSON格式化 + 自动校验
const json = await agnes.formatToolsJson(rawData);
const check = agnes.validateJson(JSON.stringify(json), {
  requiredFields: ["id","name","url","plans"],
  minCount: 15
});
if (!check.pass) console.log('校验失败:', check.errors);
```

#### 2️⃣ 图片生成

```javascript
const agnes = require('./scripts/agnes_helper');

// 文生图 — 返回图片URL
const imageUrl = await agnes.agnesImage(
  "A luminous floating city above a misty canyon at sunrise, cinematic realism",
  "1024x768"
);
console.log('图片URL:', imageUrl);

// 文生图 — 返回Base64
const base64 = await agnes.agnesImage(
  "A clean product photo of a glass cube, white background",
  "1024x768",
  { returnBase64: true }
);

// 图生图 — 风格迁移
const editedUrl = await agnes.agnesImageEdit(
  "Transform into cyberpunk night with neon reflections",
  "https://example.com/input-image.jpg",
  "1024x768"
);
```

#### 3️⃣ 视频生成

```javascript
const agnes = require('./scripts/agnes_helper');

// 文生视频（异步：提交→轮询）
const video = await agnes.agnesVideo(
  "A young astronaut walking across a red desert planet, cinematic",
  { num_frames: 121, frame_rate: 24 }
);
console.log('视频URL:', video.videoUrl);
console.log('时长:', video.seconds, '秒');

// 图生视频
const video2 = await agnes.agnesVideoFromImage(
  "Animate the character with subtle breathing, hair moving gently",
  "https://example.com/character.jpg",
  { num_frames: 81, frame_rate: 24 }
);
```

#### 4️⃣ 在 node_repl MCP 中直接调用

```javascript
// 在 node_repl 工具的 code 中
var agnes = require("E:\\path\\to\\project\\scripts\\agnes_helper");
var result = await agnes.agnesChat("写一段产品描述");
```

---

### 方式二：Python (vedio_maker 项目)

> 前置：将 `scripts/agnes_helper.py` 复制到项目目录

#### 1️⃣ 文本对话

```python
from agnes_helper import Agnes

agnes = Agnes()

# 单条调用
text = agnes.chat("把以下数据格式化成JSON: ...", "你是一个数据格式化助手")
print(text)

# 批量调用
results = agnes.batch([
    ("写Copilot的描述", "SEO助手"),
    ("写Cursor的描述", "SEO助手"),
])
```

#### 2️⃣ 图片生成

```python
from agnes_helper import Agnes

agnes = Agnes()

# 文生图 — URL输出
url = agnes.image(
    "A futuristic city marketplace with flying vehicles, neon lighting",
    size="1024x768"
)
print(f"图片URL: {url}")

# 文生图 — Base64输出
b64 = agnes.image(
    "A glass cube on white background, soft shadows",
    size="1024x768",
    return_base64=True
)

# 图生图 — 风格编辑
edited = agnes.image_edit(
    "Make it rain-soaked cyberpunk night",
    image_url="https://example.com/input.jpg",
    size="1024x768"
)
```

#### 3️⃣ 视频生成

```python
from agnes_helper import Agnes

agnes = Agnes()

# 文生视频（自动轮询直到完成）
video = agnes.video(
    "A young astronaut walking across a red desert planet, cinematic tracking shot",
    num_frames=121,
    frame_rate=24,
    wait=True  # 阻塞等待完成
)
print(f"视频URL: {video['video_url']}")
print(f"时长: {video['seconds']}秒")

# 图生视频
video2 = agnes.video_from_image(
    "Character with subtle breathing, hair moving in wind",
    image_url="https://example.com/char.jpg",
    num_frames=81,
    frame_rate=24,
    wait=True
)

# 非阻塞方式：先提交，后查询
task = agnes.video_submit("A flying dragon over mountains", num_frames=121)
task_id = task["task_id"]
video_id = task["video_id"]
print(f"任务已提交: task_id={task_id}, video_id={video_id}")

# 稍后查询
result = agnes.video_query(video_id)
if result["status"] == "completed":
    print(f"视频就绪: {result['video_url']}")
```

---

## 三级审核机制

苦工干完活不能直接信任，必须审核：

### L1: 自动校验（主AI顺手执行，毫秒级）

```javascript
// JS
const check = agnes.validateJson(agnesOutput, schema);
if (!check.pass) {
  await agnes.agnesChat("修正: " + check.errors.join(", "));
}
```

```python
# Python
check = agnes.validate_json(agnes_output, schema)
if not check["pass"]:
    agnes.chat("修正: " + ", ".join(check["errors"]))
```

### L2: 主AI抽检（~200 tokens）
随机抽20%样本看质量，有问题则反馈给苦工重写。

### L3: 人类审核标记
上线前内容，在 STATUS.md 标记 `[NEEDS_REVIEW]`，等用户终审。

### 审核失败处理
```
苦工输出 → 审核
  ↓ 通过
写入正式文件 → 继续
  ↓ 不通过
反馈重试 → 再审核（最多3次）
  ↓ 3次仍不通过
[NEEDS_USER] 暂停
```

---

## 触发条件

当用户说以下任意内容时使用本 skill：

- **通用**："叫苦工干活"、"让agnes做"、"省点token"、"这个让苦工干"、"别浪费主AI token"
- **文本**："批量处理"、"格式化数据"、"写文案"、"翻译"、"整理数据"
- **图片**："做图"、"生成图片"、"配图"、"封面图"、"图生图"、"风格迁移"
- **视频**："做视频"、"生成视频"、"图生视频"、"视频素材"
- **省token**：任何重复性/批量/体力活任务

---

## 工作流集成

### 配合 Agnes Workflow（todo/doing/done）

1. 从 `todo/` 取任务
2. **主AI判断**：该主AI干还是叫苦工？（文本/图片/视频？）
3. 叫苦工 → 选对应函数 → 审核通过 → 写入文件
4. 主AI干 → 直接执行
5. 更新 Checkpoint → 任务移入 `done/` → 更新 STATUS.md

### 配合 方向筛选 Skill

调研完一个方向后，用苦工批量格式化数据，或用苦工生成配图/演示视频。

---

## 文件结构

```
苦工ai-agnes/
├── SKILL.md                  # 本文档
├── scripts/
│   ├── agnes_helper.js       # JS 工具：Chat / Image / Video / Validate
│   └── agnes_helper.py       # Python 工具：Chat / Image / Video / Validate
└── references/
    └── decision-rules.md     # 决策规则详细说明
```

---




## 图片公网上传：GitHub API 方案

> **问题**：Agnes 图生图/图生视频 要求 `image_url` 必须是公网可访问的 URL，不支持本地路径。
> **解决方案**：用 GitHub API 把本地图片上传到公开仓库，拿到 `raw.githubusercontent.com` 直链。

### 前置条件

```powershell
# 确认 GitHub CLI 已安装并登录
gh --version
gh auth status
# 应看到 ✓ Logged in to github.com account xxx (keyring)
# Token scopes 需包含 'repo'
```

### 方法一：快速上传（推荐，一键式）

```powershell
# 1. 创建专用公开仓库（只需一次）
gh repo create 你的账号/image-host --public --description "图床仓库"

# 2. 上传图片（核心命令）
$imgPath = "本地图片路径.jpg"
$base64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($imgPath))

$body = @{
  message = "upload image"
  content = $base64
}
$jsonPath = "$env:TEMP\gh_upload.json"
$body | ConvertTo-Json -Compress | Set-Content -Path $jsonPath -Encoding ASCII

gh api --method PUT /repos/你的账号/image-host/contents/文件夹名/文件名.jpg --input $jsonPath --jq '.content.download_url'
```

**成功返回示例：**
```
https://raw.githubusercontent.com/你的账号/image-host/main/文件夹名/文件名.jpg
```

### 方法二：Node.js 版

```javascript
const { readFileSync } = await import("node:fs");

async function uploadToGitHub(localPath, repoPath, repo = "你的账号/image-host") {
  const base64 = readFileSync(localPath).toString("base64");
  const body = JSON.stringify({
    message: "upload " + repoPath.split("/").pop(),
    content: base64
  });
  const tmpPath = "/tmp/gh_upload_" + Date.now() + ".json";
  require("fs").writeFileSync(tmpPath, body);
  const { execSync } = require("child_process");
  const url = execSync(
    `gh api --method PUT /repos/${repo}/contents/${repoPath} --input ${tmpPath} --jq '.content.download_url'`,
    { encoding: "utf8" }
  ).trim();
  require("fs").unlinkSync(tmpPath);
  return url;
}

const url = await uploadToGitHub("E:/path/to/image.jpg", "agnes/standing.jpg");
console.log(url);
```

### 注意事项

1. **首次需创建仓库**：`gh repo create 你的账号/image-host --public`
2. **文件大小限制**：GitHub 单个文件 ≤ 100MB
3. **仓库需公开**：否则 `raw.githubusercontent.com` 无法访问
4. **图片名建议用英文**：避免 URL 编码问题
5. **覆盖已存在文件**：上传同名文件会自动覆盖


## 注意事项

1. **Key Pool 

### 获取公网 URL：jsDelivr CDN（推荐）

Agnes API **拒绝** `raw.githubusercontent.com` 的 URL，但 `cdn.jsdelivr.net` 的同一份文件可以通过。

**转换规则：**
```
raw.githubusercontent.com → cdn.jsdelivr.net/gh
```

**示例：**
| 本地文件 | GitHub 原始 URL（❌ 被拒） | jsDelivr CDN URL（✅ 可用） |
|:---------|:--------------------------|:--------------------------|
| standing.jpg | `https://raw.githubusercontent.com/你的账号/image-host/main/agnes/standing.jpg` | `https://cdn.jsdelivr.net/gh/你的账号/image-host@main/agnes/standing.jpg` |

**批量转换命令：**
```powershell
# 上传到 GitHub 后，获取 jsDelivr 格式 URL
$localFile = "图片.jpg"
$repoPath = "文件夹/图片.jpg"
$account = "你的账号"
$repo = "image-host"

# 1. 上传到 GitHub
$base64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($localFile))
$body = @{ message = "upload $localFile"; content = $base64 }
$jsonPath = "$env:TEMP\gh_up.json"
$body | ConvertTo-Json -Compress | Set-Content $jsonPath -Encoding ASCII
gh api --method PUT /repos/$account/$repo/contents/$repoPath --input $jsonPath --jq '.content.download_url' | Out-Null

# 2. 直接拿 jsDelivr URL（这才是 Agnes 能用的）
$jsdelivrUrl = "https://cdn.jsdelivr.net/gh/$account/$repo@main/$repoPath"
Write-Output $jsdelivrUrl
```
文件必须存在**：`E:\ai\vedio_maker\config.local.json`
2. **文本模型免费**，有RPM限制，批量调用间隔1秒
3. **图片/视频当前也免费**（原价图片$0.003/张，视频$0.005/秒）
4. **Agnes不保证输出质量**，必须走三级审核
5. **不能替代主AI**：复杂推理、代码、决策必须主AI做
6. **视频是异步任务**：提交后需要轮询等待（通常30秒~几分钟）
7. **图片生成超时较长**：建议客户端超时设60~360秒
8. **图生图的image_url必须公网可访问**：不支持本地路径

