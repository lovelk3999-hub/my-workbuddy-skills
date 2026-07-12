---
name: hai-flf2v-runner
description: Run Tencent Cloud HAI ComfyUI Wan2.1 first-last-frame video jobs. Use for HAI start/stop, FLF2V job preparation, submission, polling, MP4 download, remote cleanup, interrupted-job recovery, or multi-computer HAI control.
---

# Tencent HAI Wan FLF2V Runner

Use the bundled scripts. Do not duplicate their HTTP or Tencent API logic.
Never print, commit, or send the credentials in `config/haimgr.json`.

## Scope and Assumptions

- Tencent Cloud HAI with ComfyUI already deployed.
- Wan2.1 first-last-frame workflow and its models already exist remotely.
- Tested target: V100 32 GB, 80 GB disk.
- Use `wan2.1_flf2v_720p_14B_fp16.safetensors` with loader dtype `fp8_e4m3fn` and batch size `1`.
- Do not use default or FP16 loader dtype on the V100 32 GB target.
- Completion is determined by `GET /history/<prompt_id>`, never an elapsed-time guess.

## Install on a Computer

1. Copy the skill directory into the local skills directory.
2. Create a virtual environment in the skill directory and install `requirements.txt`.
3. Copy `config/haimgr.example.json` to `config/haimgr.json`, then fill in the Tencent Cloud API credentials, region, and HAI instance ID locally.
4. Do not commit `config/haimgr.json`.

```powershell
Set-Location <skill-dir>
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config\haimgr.example.json config\haimgr.json
```

Each computer needs its own private `config/haimgr.json`, Python environment, and copy of this skill. The HAI instance itself is shared.

## Multi-Computer Control

Only one computer is the active controller at a time.

- `start` updates the HAI security-group rules for ports `6888` and `6889` before booting or reusing the instance.
- It authorizes the current computer's Tencent API egress and HTTP egress IPs, then removes earlier managed and public video-port rules.
- A second computer simply runs `start`; it takes over video-port access automatically.
- The instance does not need to be stopped or restarted merely because control changes computers.
- Never run production jobs from two computers at once. Wait for the active job to finish, download it, clean remote output, then switch.

This is intentionally not a multi-user queue. It is a low-cost single-instance handoff mechanism.

## Job Inputs

Create a unique job directory containing:

```text
<job-dir>/
  start_720x1280.jpg
  end_720x1280.jpg
  prompt.txt
  config.json
  job.json
```

`prompt.txt` can contain positive text followed by a `negative prompt` heading.

## Normal Production Command

This starts HAI, waits for ComfyUI, uploads both frames, submits the workflow, polls for completion, downloads WEBP, converts MP4 locally, removes remote output, and stops HAI.

```powershell
Set-Location <skill-dir>
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 run `
  --job <absolute-job-dir> `
  --auto-stop --object-info
```

Keep the job directory after success. `job.json` records the prompt ID, timestamps, remote output, and local MP4 path.

## Prepare a Job

```powershell
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 prepare-job `
  --job <absolute-job-dir> `
  --start <absolute-start-frame.jpg> `
  --end <absolute-end-frame.jpg> `
  --prompt <absolute-prompt.txt>
```

For a V100 short proof, use `848x480`, `49` frames, `16` fps, `10-12` steps, and batch `1`. Use 14 steps only for selected high-value shots. Longer clips, higher resolution, and more steps increase billing and memory pressure.

## Manual Lifecycle

Use individual stages for diagnosis only:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 start
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 wait
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 health --ip <public-ip> --object-info
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 submit --job <absolute-job-dir> --ip <public-ip>
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 poll --job <absolute-job-dir> --ip <public-ip>
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 download --job <absolute-job-dir> --ip <public-ip>
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 cleanup --job <absolute-job-dir> --ip <public-ip>
powershell -ExecutionPolicy Bypass -File scripts\flf2v_run.ps1 stop
```

Run `cleanup` only after a confirmed local download. Finish with `stop` unless the user explicitly needs the instance to stay up.

## Recovery Rules

- Connection error after `submit`: do not submit again. Inspect `job.json`; if it has a `prompt_id`, use `poll` or `resume`.
- Interrupted local process: after HAI and ComfyUI are healthy, run `resume --job <absolute-job-dir>`.
- ComfyUI unreachable before submission: retry `health`; do not change remote models while GPU billing is active.
- WAN model load stalls: stop HAI, then reduce dimensions, frames, or steps; confirm FP8 dtype and batch 1.
- Animated WEBP is converted locally. Pillow frame extraction is the fallback when direct FFmpeg decoding fails.

## Final Check

Report the local MP4 path, submit-to-complete duration from `job.json` when available, and the final HAI status. Do not call a job successful until the local output exists. When `--auto-stop` was used, verify `STOPPED_NO_CHARGE`.
