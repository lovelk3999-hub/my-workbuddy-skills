"""
Agnes API 苦工 — Python 版
带 Key Pool 自动轮换 + 文本/图片/视频 全套能力
Key来源（优先级）:
  1. config.local.json（与本脚本同目录）← 推荐
  2. E:\\ai\\vedio_maker\\config.local.json（项目旧路径）
  3. 环境变量 AGNES_KEYS（JSON数组字符串）
"""

import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://apihub.agnes-ai.com/v1"


class Agnes:
    """Agnes API 苦工：免费的多模态AI工具"""

    def __init__(self, config_path: str = None):
        self._script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = config_path  # 如果传了则优先
        self._key_pool = self._load_keys()
        self._key_index = 0
        self._failed_keys = {}  # key -> timestamp

    # ========== Key Pool ==========

    def _load_keys(self):
        # 方式0: 显式传入路径
        if self.config_path:
            try:
                with open(self.config_path, "r", encoding="utf-8-sig") as f:
                    keys = json.load(f).get("agnes_keys", [])
                    if keys: return keys
            except Exception:
                pass

        # 方式1: 本目录的 config.local.json
        local_path = os.path.join(self._script_dir, "config.local.json")
        try:
            with open(local_path, "r", encoding="utf-8-sig") as f:
                keys = json.load(f).get("agnes_keys", [])
                if keys: return keys
        except Exception:
            pass

        # 方式2: 项目旧路径
        old_path = r"E:\ai\vedio_maker\config.local.json"
        try:
            with open(old_path, "r", encoding="utf-8-sig") as f:
                keys = json.load(f).get("agnes_keys", [])
                if keys: return keys
        except Exception:
            pass

        # 方式3: 环境变量
        env = os.environ.get("AGNES_KEYS")
        if env:
            try:
                keys = json.loads(env)
                if keys: return keys
            except Exception:
                pass

        # 都没找到
        raise RuntimeError(
            "❌ 未找到 Agnes API Key！\n"
            f"请创建 {local_path}，内容格式见 config.example.json"
        )

    def _get_next_key(self):
        now = time.time()
        for _ in range(len(self._key_pool)):
            idx = self._key_index % len(self._key_pool)
            self._key_index += 1
            k = self._key_pool[idx]
            if k in self._failed_keys and (now - self._failed_keys[k]) < 60:
                continue
            return k
        self._failed_keys = {}
        return self._key_pool[0]

    def _fetch(self, endpoint: str, body: dict, timeout_ms: int = 60000) -> dict:
        api_key = self._get_next_key()
        data_bytes = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            BASE + endpoint,
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout_ms / 1000)
            result = json.loads(resp.read().decode("utf-8"))
            if "error" in result and result["error"]:
                raise Exception(result["error"] if isinstance(result["error"], str) else result["error"].get("message", str(result["error"])))
            return result
        except Exception as e:
            self._failed_keys[api_key] = time.time()
            raise e

    def _get(self, url: str, timeout_ms: int = 30000) -> dict:
        """发起 GET 请求（用于查询视频结果）"""
        api_key = self._get_next_key()
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        try:
            resp = urllib.request.urlopen(req, timeout=timeout_ms / 1000)
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self._failed_keys[api_key] = time.time()
            raise e

    # ========== 1. 文本能力 ==========

    def chat(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """单条文本对话"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": "agnes-2.0-flash",
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if kwargs.get("response_format") == "json":
            body["response_format"] = {"type": "json_object"}

        data = self._fetch("/chat/completions", body, kwargs.get("timeout_ms", 60000))
        return data["choices"][0]["message"]["content"]

    def batch(self, prompts: list, delay_ms: int = 1000) -> list:
        """批量文本调用：prompts = [(prompt, system_prompt), ...]"""
        results = []
        for i, (prompt, system_prompt) in enumerate(prompts):
            r = self.chat(prompt, system_prompt)
            results.append(r)
            if i < len(prompts) - 1:
                time.sleep(delay_ms / 1000)
        return results

    def format_json(self, raw_data: str) -> list:
        """将原始数据格式化为JSON"""
        result = self.chat(
            f"将以下数据格式化为标准JSON数组:\n{raw_data}",
            "只输出合法JSON，不要markdown包裹",
            response_format="json",
            temperature=0.3,
        )
        return json.loads(result)

    @staticmethod
    def validate_json(json_str: str, schema: dict = None) -> dict:
        """校验JSON格式和字段完整性"""
        errors = []
        schema = schema or {}
        try:
            data = json.loads(json_str)
            arr = data if isinstance(data, list) else [data]
            min_count = schema.get("minCount")
            if min_count and len(arr) < min_count:
                errors.append(f"数量不足: 需要{min_count}条, 实际{len(arr)}条")
            fields = schema.get("requiredFields", ["id", "name", "url"])
            for i, item in enumerate(arr):
                for f in fields:
                    if f not in item or not item[f]:
                        errors.append(f"第{i + 1}条缺字段: {f}")
            return {"pass": len(errors) == 0, "errors": errors}
        except json.JSONDecodeError as e:
            return {"pass": False, "errors": [f"JSON解析失败: {e}"]}

    # ========== 2. 图片能力 ==========

    def image(self, prompt: str, size: str = "1024x768", **kwargs) -> str:
        """文生图，返回图片URL或Base64"""
        body = {
            "model": "agnes-image-2.1-flash",
            "prompt": prompt,
            "size": size,
        }
        if kwargs.get("return_base64"):
            body["return_base64"] = True
        else:
            body["extra_body"] = {"response_format": "url"}

        data = self._fetch("/images/generations", body, kwargs.get("timeout_ms", 120000))
        img = data["data"][0]
        if kwargs.get("return_base64"):
            return img["b64_json"]
        return img.get("url") or img.get("b64_json")

    def image_edit(self, prompt: str, image_url: str, size: str = "1024x768", **kwargs) -> str:
        """图生图（风格迁移/编辑），返回图片URL"""
        body = {
            "model": "agnes-image-2.1-flash",
            "prompt": prompt,
            "size": size,
            "extra_body": {
                "image": [image_url],
                "response_format": "url",
            },
        }
        data = self._fetch("/images/generations", body, kwargs.get("timeout_ms", 120000))
        return data["data"][0]["url"]

    # ========== 3. 视频能力 ==========

    def video_submit(self, prompt: str, image_url: str = None, **kwargs) -> dict:
        """提交视频生成任务，不等待"""
        body = {
            "model": "agnes-video-v2.0",
            "prompt": prompt,
        }
        if image_url:
            body["image"] = image_url
        for k in ("num_frames", "frame_rate", "width", "height", "negative_prompt", "seed"):
            if k in kwargs:
                body[k] = kwargs[k]

        return self._fetch("/videos", body, kwargs.get("timeout_ms", 30000))

    def video_query(self, video_id: str) -> dict:
        """查询视频生成结果（推荐用 video_id）"""
        url = f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}"
        return self._get(url, 30000)

    def video(self, prompt: str, **kwargs) -> dict:
        """文生视频（提交+自动轮询等待）"""
        return self._video_submit_and_poll(prompt, None, **kwargs)

    def video_from_image(self, prompt: str, image_url: str, **kwargs) -> dict:
        """图生视频（提交+自动轮询等待）"""
        return self._video_submit_and_poll(prompt, image_url, **kwargs)

    def _video_submit_and_poll(self, prompt: str, image_url: str = None, **kwargs) -> dict:
        """内部：提交视频任务+轮询"""
        wait = kwargs.get("wait", True)
        poll_interval = kwargs.get("poll_interval", 5)
        timeout_ms = kwargs.get("timeout_ms", 300000)

        task = self.video_submit(prompt, image_url, **kwargs)
        video_id = task.get("video_id")
        task_id = task.get("task_id") or task.get("id")

        if not wait:
            return {"task_id": task_id, "video_id": video_id, "status": "queued"}

        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            time.sleep(poll_interval)
            result = self.video_query(video_id)
            status = result.get("status")
            if status == "completed":
                return {
                    "task_id": task_id,
                    "video_id": video_id,
                    "video_url": result.get("remixed_from_video_id") or result.get("video_url"),
                    "seconds": result.get("seconds"),
                    "status": "completed",
                    "size": result.get("size"),
                }
            if status == "failed":
                raise Exception(f"视频生成失败: {result.get('error', '未知错误')}")

        raise Exception(f"视频生成超时 ({timeout_ms}ms)")

    @property
    def key_count(self) -> int:
        return len(self._key_pool)
