# hai-manager — 技能安装指南

## 从 GitHub 部署到新机器

### 方式一：整个 skills 目录一起托管（推荐）

如果你想把自己写的所有 skill 都同步到多台机器：

```bash
# 1. 在 GitHub 建一个私有仓库，比如叫 my-workbuddy-skills

# 2. 本机推送
cd ~/.workbuddy/skills
git init
git add hai-manager/ apify-pinterest-scraper/   # 只加你想同步的 skill
git commit -m "add hai-manager and apify-pinterest-scraper"
git remote add origin https://github.com/你的用户名/my-workbuddy-skills.git
git push -u origin main

# 3. 新机器拉取
cd ~/.workbuddy/skills
git clone https://github.com/你的用户名/my-workbuddy-skills.git .
```

> ⚠️ `.gitignore` 已配置忽略 `config.local.*`，凭据不会提交。
> 新机器上首次使用 skill 时，AI 会自动引导你填写凭据。

### 方式二：只同步单个 skill

```bash
# 在本机把 hai-manager 复制到随便一个目录
cp -r ~/.workbuddy/skills/hai-manager /path/to/temp/

# 建立 GitHub 仓库，只含这个文件夹
cd /path/to/temp
git init
git add .
git commit -m "add hai-manager skill"
git remote add origin https://github.com/你的用户名/hai-manager.git
git push

# 新机器上
git clone https://github.com/你的用户名/hai-manager.git ~/.workbuddy/skills/hai-manager
```

### 方式三：手动复制（最简单）

```bash
# 本机压缩（不包含 config.local.json）
cd ~/.workbuddy/skills
zip -r hai-manager.zip hai-manager/ -x "*/config.local.*"

# 把 hai-manager.zip 传到新机器
# 新机器上解压到 skills 目录
cd ~/.workbuddy/skills
unzip hai-manager.zip
```

---

## 新机器首次使用

AI 会自动执行 Pre-Flight Check：

1. 检查 Python → 提示安装（如果没有）
2. 检查 tencentcloud-sdk → 自动 pip install
3. 检查 config.local.json → 不存在就问你要凭据
4. 写入凭据 → 正常运行

全程只需要你提供一次 `SecretId / SecretKey / Region / InstanceId`。
