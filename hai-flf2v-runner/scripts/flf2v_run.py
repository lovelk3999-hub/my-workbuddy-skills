#!/usr/bin/env python3
"""Local FLF2V job runner for Tencent HAI + ComfyUI.

Daily use:
  python scripts/flf2v_run.py run --job video_projects/flf2v_jobs/test_001 --auto-stop

Debuggable steps:
  python scripts/flf2v_run.py prepare-job --job video_projects/flf2v_jobs/test_001 --start workspace/test/start_720x1280.jpg --end workspace/test/end_720x1280.jpg --prompt workspace/test/提示词.txt
  python scripts/flf2v_run.py health --ip <public-ip>
  python scripts/flf2v_run.py submit --job video_projects/flf2v_jobs/test_001 --ip <public-ip>
  python scripts/flf2v_run.py poll --job video_projects/flf2v_jobs/test_001 --ip <public-ip>
  python scripts/flf2v_run.py download --job video_projects/flf2v_jobs/test_001 --ip <public-ip>
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request


ROOT = Path(__file__).resolve().parents[1]
FLF2V_CONFIG = ROOT / "config" / "flf2v.json"
HAIMGR = ROOT / "scripts" / "haimgr.py"


@dataclass(frozen=True)
class PromptParts:
    positive: str
    negative: str


@dataclass(frozen=True)
class RemoteOutput:
    filename: str
    subfolder: str = ""
    kind: str = "output"


@dataclass(frozen=True)
class Job:
    job_dir: Path
    start_image: Path
    end_image: Path
    prompt: PromptParts
    settings: dict[str, Any]
    state_path: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict[str, Any]:
    cfg = read_json(FLF2V_CONFIG)
    if not cfg:
        raise FileNotFoundError(f"Missing config: {FLF2V_CONFIG}")
    return cfg


def parse_prompt_file(path: Path) -> PromptParts:
    text = path.read_text(encoding="utf-8-sig").strip()
    negative_match = re.search(r"(?:负面提示词|反向提示词|negative\s*prompt)\s*", text, flags=re.I)
    if negative_match:
        positive = text[: negative_match.start()]
        negative = text[negative_match.end() :]
    else:
        positive = text
        negative = ""

    positive = re.sub(r"^\s*(?:正向提示词|正面提示词|positive\s*prompt)\s*", "", positive, flags=re.I)
    return PromptParts(positive=positive.strip(), negative=negative.strip())


def sanitize_prefix(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-") or f"flf2v_{int(time.time())}"


def load_job(job_dir: Path) -> Job:
    cfg = load_config()
    job_dir = job_dir.resolve()
    start_image = job_dir / "start_720x1280.jpg"
    end_image = job_dir / "end_720x1280.jpg"
    prompt_file = job_dir / "prompt.txt"
    for required in (start_image, end_image, prompt_file):
        if not required.exists():
            raise FileNotFoundError(f"Missing job file: {required}")

    settings = dict(cfg.get("default_settings", {}))
    settings.update(read_json(job_dir / "config.json"))
    settings.setdefault("filename_prefix", sanitize_prefix(job_dir.name))

    return Job(
        job_dir=job_dir,
        start_image=start_image,
        end_image=end_image,
        prompt=parse_prompt_file(prompt_file),
        settings=settings,
        state_path=job_dir / "job.json",
    )


def update_state(job: Job, **changes: Any) -> dict[str, Any]:
    state = read_json(job.state_path)
    state.update(changes)
    state["updated_at"] = now_iso()
    write_json(job.state_path, state)
    return state


def comfy_base(ip: str, port: int | str = 6889) -> str:
    if ip.startswith("http://") or ip.startswith("https://"):
        return ip.rstrip("/")
    return f"http://{ip}:{port}"


def command_base(ip: str, port: int | str = 6888) -> str:
    if ip.startswith("http://") or ip.startswith("https://"):
        parsed = parse.urlparse(ip)
        return f"{parsed.scheme}://{parsed.hostname}:{port}"
    return f"http://{ip}:{port}"


def http_json(method: str, url: str, body: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method.upper())
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def http_bytes(url: str, timeout: int = 120) -> bytes:
    with request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def multipart_upload_image(base_url: str, local_path: Path, remote_name: str) -> dict[str, Any]:
    boundary = f"----flf2v-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(remote_name)[0] or "application/octet-stream"
    file_bytes = local_path.read_bytes()

    parts: list[bytes] = []
    for name, value in (("type", "input"), ("overwrite", "true")):
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        (
            f'Content-Disposition: form-data; name="image"; filename="{remote_name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = request.Request(
        f"{base_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def replace_placeholders(value: Any, mapping: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {k: replace_placeholders(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_placeholders(v, mapping) for v in value]
    if not isinstance(value, str):
        return value

    full = re.fullmatch(r"\{\{([A-Z0-9_]+)\}\}", value)
    if full:
        return mapping[full.group(1)]

    result = value
    for key, replacement in mapping.items():
        result = result.replace(f"{{{{{key}}}}}", str(replacement))
    return result


def build_workflow(job: Job, start_remote: str, end_remote: str) -> dict[str, Any]:
    cfg = load_config()
    template_path = Path(job.settings.get("workflow_template") or cfg["workflow_template"])
    if not template_path.is_absolute():
        template_path = ROOT / template_path
    template = read_json(template_path)
    if not template:
        raise FileNotFoundError(f"Missing workflow template: {template_path}")

    s = job.settings
    mapping = {
        "START_IMAGE": start_remote,
        "END_IMAGE": end_remote,
        "POSITIVE_PROMPT": job.prompt.positive,
        "NEGATIVE_PROMPT": job.prompt.negative,
        "WIDTH": s["width"],
        "HEIGHT": s["height"],
        "FRAMES": s["frames"],
        "FPS": s["fps"],
        "STEPS": s["steps"],
        "CFG": s["cfg"],
        "SEED": s["seed"],
        "SAMPLER_NAME": s["sampler_name"],
        "SCHEDULER": s["scheduler"],
        "DENOISE": s["denoise"],
        "BATCH_SIZE": s["batch_size"],
        "WEBP_QUALITY": s["webp_quality"],
        "WEBP_LOSSLESS": s["webp_lossless"],
        "WEBP_METHOD": s["webp_method"],
        "CLIP_TYPE": s["clip_type"],
        "CLIP_CROP": s["clip_crop"],
        "DIFFUSION_MODEL": s["diffusion_model"],
        "DIFFUSION_WEIGHT_DTYPE": s["diffusion_weight_dtype"],
        "TEXT_ENCODER": s["text_encoder"],
        "CLIP_VISION": s["clip_vision"],
        "VAE": s["vae"],
        "FILENAME_PREFIX": s["filename_prefix"],
    }
    return replace_placeholders(template, mapping)


def extract_history_outputs(history: dict[str, Any], prompt_id: str) -> list[RemoteOutput]:
    entry = history.get(prompt_id, history)
    outputs = entry.get("outputs") or {}
    found: list[RemoteOutput] = []
    seen: set[tuple[str, str, str]] = set()
    for node_output in outputs.values():
        for bucket in ("images", "gifs", "videos"):
            for item in node_output.get(bucket, []) or []:
                filename = item.get("filename")
                if not filename:
                    continue
                output = RemoteOutput(
                    filename=filename,
                    subfolder=item.get("subfolder") or "",
                    kind=item.get("type") or "output",
                )
                key = (output.filename, output.subfolder, output.kind)
                if key not in seen:
                    found.append(output)
                    seen.add(key)
    return found


def build_view_url(base_url: str, output: RemoteOutput) -> str:
    query = parse.urlencode(
        {
            "filename": output.filename,
            "subfolder": output.subfolder,
            "type": output.kind,
        }
    )
    return f"{base_url.rstrip('/')}/view?{query}"


def run_haimgr(command: str) -> str:
    result = subprocess.run(
        [sys.executable, str(HAIMGR), command],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def parse_ip(text: str) -> str | None:
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    return match.group(0) if match else None


def resolve_ip(ip: str | None, job: Job | None = None) -> str:
    if ip:
        return ip
    if job:
        state_ip = read_json(job.state_path).get("ip")
        if state_ip:
            return state_ip
    status = run_haimgr("status")
    found = parse_ip(status)
    if not found:
        raise RuntimeError("No IP found. Pass --ip or run haimgr wait after start.")
    return found


def prepare_job(args: argparse.Namespace) -> None:
    job_dir = Path(args.job).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    copies = [
        (Path(args.start).resolve(), job_dir / "start_720x1280.jpg"),
        (Path(args.end).resolve(), job_dir / "end_720x1280.jpg"),
        (Path(args.prompt).resolve(), job_dir / "prompt.txt"),
    ]
    for src, dest in copies:
        if dest.exists() and not args.force:
            raise FileExistsError(f"Refusing to overwrite {dest}; pass --force")
        shutil.copy2(src, dest)

    config_path = job_dir / "config.json"
    if not config_path.exists() or args.force:
        settings = dict(load_config()["default_settings"])
        settings["filename_prefix"] = sanitize_prefix(job_dir.name)
        write_json(config_path, settings)

    state = {
        "state": "prepared",
        "job_dir": str(job_dir),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "remote_inputs": {},
        "remote_outputs": [],
        "local_outputs": [],
    }
    write_json(job_dir / "job.json", state)
    print(f"prepared: {job_dir}")


def health(args: argparse.Namespace) -> None:
    cfg = load_config()
    ip = resolve_ip(args.ip)
    base = comfy_base(ip, cfg["comfy_port"])
    stats = http_json("GET", f"{base}/system_stats", timeout=20)
    print(json.dumps({"ip": ip, "comfy": base, "system_stats": stats}, ensure_ascii=False, indent=2))
    if args.object_info:
        info = http_json("GET", f"{base}/object_info", timeout=60)
        nodes = [
            "LoadImage",
            "UNETLoader",
            "CLIPLoader",
            "CLIPVisionEncode",
            "WanFirstLastFrameToVideo",
            "KSampler",
            "VAEDecode",
            "SaveAnimatedWEBP",
        ]
        print(json.dumps({name: info.get(name) for name in nodes}, ensure_ascii=False, indent=2))


def submit(args: argparse.Namespace) -> None:
    cfg = load_config()
    job = load_job(Path(args.job))
    ip = resolve_ip(args.ip, job)
    base = comfy_base(ip, cfg["comfy_port"])
    prefix = sanitize_prefix(job.settings["filename_prefix"])

    start_upload = multipart_upload_image(base, job.start_image, f"{prefix}_start{job.start_image.suffix}")
    end_upload = multipart_upload_image(base, job.end_image, f"{prefix}_end{job.end_image.suffix}")
    start_name = start_upload.get("name") or f"{prefix}_start{job.start_image.suffix}"
    end_name = end_upload.get("name") or f"{prefix}_end{job.end_image.suffix}"
    workflow = build_workflow(job, start_name, end_name)
    body = {"prompt": workflow, "client_id": f"flf2v-{uuid.uuid4().hex}"}
    response = http_json("POST", f"{base}/prompt", body, timeout=60)
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"No prompt_id returned: {response}")

    update_state(
        job,
        state="submitted",
        ip=ip,
        comfy=base,
        prompt_id=prompt_id,
        submitted_at=now_iso(),
        remote_inputs={"start": start_name, "end": end_name},
        remote_outputs=[],
    )
    print(json.dumps({"prompt_id": prompt_id, "ip": ip}, ensure_ascii=False, indent=2))


def poll(args: argparse.Namespace) -> None:
    cfg = load_config()
    job = load_job(Path(args.job))
    state = read_json(job.state_path)
    prompt_id = state.get("prompt_id")
    if not prompt_id:
        raise RuntimeError("Missing prompt_id in job.json; run submit first")
    ip = resolve_ip(args.ip, job)
    base = comfy_base(ip, cfg["comfy_port"])

    poll_cfg = cfg["poll"]
    interval = args.interval or poll_cfg["interval_seconds"]
    slow_after = args.slow_after or poll_cfg["slow_after_seconds"]
    slow_interval = args.slow_interval or poll_cfg["slow_interval_seconds"]
    timeout = args.timeout or poll_cfg["timeout_seconds"]
    started = time.time()

    while True:
        history = http_json("GET", f"{base}/history/{prompt_id}", timeout=30)
        outputs = extract_history_outputs(history, prompt_id)
        if outputs:
            serialized = [output.__dict__ for output in outputs]
            update_state(
                job,
                state="completed",
                ip=ip,
                completed_at=now_iso(),
                remote_outputs=serialized,
            )
            print(json.dumps({"state": "completed", "outputs": serialized}, ensure_ascii=False, indent=2))
            return

        elapsed = time.time() - started
        if elapsed > timeout:
            update_state(job, state="poll_timeout", ip=ip)
            raise TimeoutError(f"Timed out waiting for {prompt_id}")
        sleep_for = slow_interval if elapsed >= slow_after else interval
        print(f"polling {prompt_id}: {int(elapsed)}s elapsed; next in {sleep_for}s")
        time.sleep(sleep_for)


def download(args: argparse.Namespace) -> None:
    cfg = load_config()
    job = load_job(Path(args.job))
    state = read_json(job.state_path)
    outputs = [RemoteOutput(**item) for item in state.get("remote_outputs", [])]
    if not outputs:
        raise RuntimeError("No remote_outputs in job.json; run poll first")
    ip = resolve_ip(args.ip, job)
    base = comfy_base(ip, cfg["comfy_port"])

    local_outputs = []
    for output in outputs:
        data = http_bytes(build_view_url(base, output), timeout=180)
        if len(data) < args.min_bytes:
            raise RuntimeError(f"Downloaded file too small: {output.filename} ({len(data)} bytes)")
        local_path = job.job_dir / output.filename
        local_path.write_bytes(data)
        local_outputs.append(str(local_path))
        print(f"downloaded: {local_path} ({len(data)} bytes)")

    update_state(job, state="downloaded", ip=ip, downloaded_at=now_iso(), local_outputs=local_outputs)
    if args.convert_mp4:
        convert_outputs(job, local_outputs)


def convert_outputs(job: Job, local_outputs: list[str]) -> None:
    converted = []
    for value in local_outputs:
        src = Path(value)
        if src.suffix.lower() != ".webp":
            continue
        dest = src.with_suffix(".mp4")
        result = convert_webp_to_mp4(src, dest, int(job.settings.get("fps", 16)))
        if result.returncode != 0:
            if dest.exists():
                dest.unlink()
            result = convert_animated_webp_with_pillow(src, dest, int(job.settings.get("fps", 16)))
        converted.append(str(dest))
        print(f"converted: {dest}")
    if converted:
        state = read_json(job.state_path)
        state["converted_outputs"] = converted
        state["updated_at"] = now_iso()
        write_json(job.state_path, state)


def convert_webp_to_mp4(src: Path, dest: Path, fps: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(src),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(dest),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def convert_animated_webp_with_pillow(src: Path, dest: Path, fps: int) -> subprocess.CompletedProcess[str]:
    try:
        from PIL import Image, ImageSequence
    except ImportError as exc:
        raise RuntimeError("Pillow is required to convert animated WEBP files") from exc

    with tempfile.TemporaryDirectory(prefix="flf2v_frames_") as tmp:
        frame_dir = Path(tmp)
        frame_count = 0
        with Image.open(src) as image:
            for frame_count, frame in enumerate(ImageSequence.Iterator(image), start=1):
                frame.convert("RGB").save(frame_dir / f"{frame_count - 1:05d}.png")
        if frame_count == 0:
            raise RuntimeError(f"No frames extracted from {src}")
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(frame_dir / "%05d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(dest),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg conversion failed after WEBP frame extraction")
    return result


def cleanup(args: argparse.Namespace) -> None:
    cfg = load_config()
    job = load_job(Path(args.job))
    ip = resolve_ip(args.ip, job)
    prefix = sanitize_prefix(job.settings["filename_prefix"])
    remote_dir = cfg["remote_comfy_dir"].rstrip("/") + "/output"
    cmd = f"find {remote_dir} -type f -name '{prefix}*' -delete && find {remote_dir} -type f -mtime +1 -delete"
    url = command_base(ip, cfg["command_port"]) + "/?" + parse.urlencode({"cmd": cmd})
    response = http_json("GET", url, timeout=60)
    update_state(job, state="cleaned", ip=ip, cleaned_at=now_iso(), cleanup_response=response)
    print(json.dumps(response, ensure_ascii=False, indent=2))


def start(_: argparse.Namespace) -> None:
    print(run_haimgr("start"), end="")


def wait(_: argparse.Namespace) -> None:
    output = run_haimgr("wait")
    print(output, end="")


def stop(_: argparse.Namespace) -> None:
    print(run_haimgr("stop"), end="")


def status(_: argparse.Namespace) -> None:
    print(run_haimgr("status"), end="")


def run(args: argparse.Namespace) -> None:
    try:
        start(args)
        wait_output = run_haimgr("wait")
        print(wait_output, end="")
        ip = parse_ip(wait_output) or resolve_ip(None)
        args.ip = ip
        health(argparse.Namespace(ip=ip, object_info=args.object_info))
        submit(args)
        poll(args)
        download(args)
        cleanup(args)
    finally:
        if args.auto_stop:
            stop(args)


def resume(args: argparse.Namespace) -> None:
    job = load_job(Path(args.job))
    state = read_json(job.state_path).get("state")
    if state in (None, "prepared"):
        submit(args)
        poll(args)
        download(args)
        cleanup(args)
    elif state == "submitted":
        poll(args)
        download(args)
        cleanup(args)
    elif state == "completed":
        download(args)
        cleanup(args)
    elif state == "downloaded":
        cleanup(args)
    else:
        print(f"nothing to resume for state={state}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare-job")
    p.add_argument("--job", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=prepare_job)

    for name, func in (("status", status), ("start", start), ("wait", wait), ("stop", stop)):
        p = sub.add_parser(name)
        p.set_defaults(func=func)

    p = sub.add_parser("health")
    p.add_argument("--ip")
    p.add_argument("--object-info", action="store_true")
    p.set_defaults(func=health)

    p = sub.add_parser("submit")
    p.add_argument("--job", required=True)
    p.add_argument("--ip")
    p.set_defaults(func=submit)

    p = sub.add_parser("poll")
    p.add_argument("--job", required=True)
    p.add_argument("--ip")
    p.add_argument("--interval", type=int)
    p.add_argument("--slow-after", type=int)
    p.add_argument("--slow-interval", type=int)
    p.add_argument("--timeout", type=int)
    p.set_defaults(func=poll)

    p = sub.add_parser("download")
    p.add_argument("--job", required=True)
    p.add_argument("--ip")
    p.add_argument("--min-bytes", type=int, default=1024 * 1024)
    p.add_argument("--convert-mp4", action="store_true", default=True)
    p.set_defaults(func=download)

    p = sub.add_parser("cleanup")
    p.add_argument("--job", required=True)
    p.add_argument("--ip")
    p.set_defaults(func=cleanup)

    p = sub.add_parser("resume")
    p.add_argument("--job", required=True)
    p.add_argument("--ip")
    p.add_argument("--interval", type=int)
    p.add_argument("--slow-after", type=int)
    p.add_argument("--slow-interval", type=int)
    p.add_argument("--timeout", type=int)
    p.add_argument("--min-bytes", type=int, default=1024 * 1024)
    p.add_argument("--convert-mp4", action="store_true", default=True)
    p.set_defaults(func=resume)

    p = sub.add_parser("run")
    p.add_argument("--job", required=True)
    p.add_argument("--ip")
    p.add_argument("--auto-stop", action="store_true")
    p.add_argument("--object-info", action="store_true")
    p.add_argument("--interval", type=int)
    p.add_argument("--slow-after", type=int)
    p.add_argument("--slow-interval", type=int)
    p.add_argument("--timeout", type=int)
    p.add_argument("--min-bytes", type=int, default=1024 * 1024)
    p.add_argument("--convert-mp4", action="store_true", default=True)
    p.set_defaults(func=run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
