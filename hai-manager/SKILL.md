---
name: hai-manager
description: >-
  Manage Tencent Cloud HAI (GPU) instances: check status, start, stop, and
  wait for boot. Triggers: "查HAI", "开云服务器", "云端GPU", "hai状态",
  "开云实例", "云端HAI".
agent_created: true
domain: ["cloud-computing", "gpu", "tencent-cloud"]
---

# HAI Instance Manager

Manage Tencent Cloud HAI GPU instances: query status, power on/off,
and wait for boot completion.

## When To Use

- "查一下 HAI 状态" / "看看云端服务器"
- "开一下云服务器" / "启动云端"
- "关机" / "关掉云实例"
- "等开机完成" — poll until RUNNING, report IP

---

## ⚡ Mandatory: Pre-Flight Check (run first)

Before running any command, ALWAYS run this sequence to verify the
environment. If any step fails, fix it before proceeding.

### Step 1 — Check Python

```bash
python3 --version
```

Expected: `Python 3.8+`

If not installed or version too old: tell the user Python 3.8+ is
required and stop — do not attempt to install it.

### Step 2 — Check tencentcloud-sdk-python

```bash
python3 -c "import tencentcloud; print('tencentcloud-sdk:', tencentcloud.__version__)"
```

If the import succeeds, skip to Step 3. If it fails:

```bash
pip3 install tencentcloud-sdk-python
```

Then re-check with the import command above. If installation fails,
tell the user and stop.

### Step 3 — Check config.local.json

```bash
ls ~/.workbuddy/skills/hai-manager/scripts/config.local.json
```

- **Exists** → skip to Usage
- **Not exists** → follow [First-Time Setup](#first-time-setup-on-a-new-machine)

### Step 4 — Run the command

Proceed to [Usage](#usage).

### If any check fails

Report the specific failure to the user with the exact error message.
Do not guess or assume. Do not proceed until the issue is resolved.

---

## How Credentials Work (Cross-Machine)

Credentials are stored in a separate local file, never inside the skill.

### On the primary machine (already set up)

`scripts/config.local.json` already exists. Works out of the box.

### On a new machine

When the skill loads on a new machine for the first time, the AI will:

1. Run `pre-flight check Step 3` — find config missing
2. Ask the user for four credentials:
   - `SecretId` — Tencent Cloud API key ID
   - `SecretKey` — Tencent Cloud API key secret
   - `Region` — e.g. `ap-shanghai`
   - `InstanceId` — HAI instance ID (e.g. `hai-2giskk3y`)
3. Write `scripts/config.local.json`
4. Confirm and proceed

The file persists — user only provides credentials once per machine.

### Credential safety

- `config.local.json` is the **only** place credentials live
- `config.example.json` contains only `your_tencent_cloud_xxx` placeholders
- Never paste credentials into chat messages or into SKILL.md
- Never share `config.local.json`

---

## Usage

### Commands

```bash
# 查状态 + IP
python3 ~/.workbuddy/skills/hai-manager/scripts/haimgr.py status

# 开机
python3 ~/.workbuddy/skills/hai-manager/scripts/haimgr.py start

# 关机
python3 ~/.workbuddy/skills/hai-manager/scripts/haimgr.py stop

# 等待开机完成（最多等5分钟），打印新 IP
python3 ~/.workbuddy/skills/hai-manager/scripts/haimgr.py wait
```

### Service ports (after boot)

| Service | Port |
|---------|------|
| ComfyUI | 6889 |
| API Server | 6888 |

---

## Architecture

```
scripts/
├── haimgr.py              ← Main executable
├── config.example.json    ← Template (safe to share, placeholders only)
└── config.local.json      ← YOUR credentials (created per machine, do NOT share)
```

### Config loading order

`haimgr.py` looks for credentials in this order:

1. **`config.local.json`** (next to the script) — persistent config
2. **Environment variables** — `HAI_SECRET_ID`, `HAI_SECRET_KEY`,
   `HAI_REGION`, `HAI_INSTANCE_ID`
3. **None found** → print formatted error, tell user to provide credentials

---

## First-Time Setup (on a new machine)

When `config.local.json` is missing, follow these steps in order:

```
Step 1  Run pre-flight Step 3 → config not found

Step 2  Ask user:
          "我需要四个信息来配置这台机器的云实例连接：
            - 腾讯云 SecretId
            - 腾讯云 SecretKey
            - 地域 Region（默认 ap-shanghai）
            - 实例 ID（InstanceId）"

Step 3  Write scripts/config.local.json:
        {
          "secret_id": "user_provided_value",
          "secret_key": "user_provided_value",
          "region": "ap-shanghai",
          "instance_id": "hai-xxxxxxx"
        }

Step 4  Confirm: "配置已保存，以后这台机器直接用就行，不用再输。"

Step 5  Re-run pre-flight Step 3 to verify file exists.
        Then proceed to run the user's original command.
```

---

## Notes

- Instance costs money while RUNNING. Remind the user to stop when idle.
- The `wait` command polls every 10 seconds for up to 5 minutes.
- IP address may change after stop/start cycles.
- If the script fails with a `ModuleNotFoundError` for `tencentcloud`,
  it means the SDK is missing — see pre-flight Step 2.
