# 本地 CDP 代理协议（localhost:3456）

本 skill 与 BOSS 采集、抖音探查共用同一套本地 CDP 代理。代理接管用户的真实 Chrome，提供一组 REST 接口驱动浏览器。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/new` + body=URL | 打开新标签页，返回 `{"targetId":"..."}` |
| POST | `/eval?target={tid}` + body=JS | 在标签内执行 JS，返回 `{"value": <结果>}`（`value` 经一次 JSON 序列化，字符串需再 `JSON.parse` 一次） |
| GET | `/scroll?target={tid}&direction=bottom` | 向底部滚动（触发 SPA 懒加载） |
| GET | `/close?target={tid}` | 关闭标签 |

## 调用约定（Python 片段）

```python
import subprocess, json
BASE = "http://localhost:3456"

def curl_post(path, data=None):
    cmd = ["curl", "-s", "-X", "POST", BASE + path]
    if data is not None:
        cmd += ["--data-raw", data]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout

def curl_get(path):
    return subprocess.run(["curl", "-s", BASE + path], capture_output=True, text=True, timeout=60).stdout

def new_tab(url):
    return json.loads(curl_post("/new", url))["targetId"]

def eval_js(tid, js):
    raw = curl_post(f"/eval?target={tid}", js)
    try:
        return json.loads(raw).get("value")
    except Exception:
        return None
```

## 关键陷阱

1. **`/eval` 的返回值要二次解析**：代理把 JS 结果 `JSON.stringify` 一次，包进 `{"value": "..."}`；若 JS 本身返回字符串，`value` 是带引号的 JSON 字符串，需再 `json.loads` 一次；若返回对象，则 `value` 已是对象，不要重复解析。
2. **滚动触发懒加载**：AI 对话、抖音列表等 SPA 内容常分批渲染，不滚动会丢后半段。先滚再 `eval` 取长度，长度稳定即渲染完毕。
3. **开标签即一次导航**：单会话开太多标签/导航会累积请求量，批量任务之间留拟人间隔。
4. **CDP 代理未启动**：`curl -s http://localhost:3456/` 无响应 → 先启动代理（与 BOSS/抖音同套）再跑。

## 与其他 skill 的关系

- `ai-job-hunter`：BOSS 直聘列表/详情采集，同一 CDP 通道。
- `douyin-account-research` / Claw 项目 `douyin_account_finder.py`：抖音号探查，同一 CDP 通道。
- 本 skill：只读渲染 + 文本抽取，不做任何写入/点击，风险最低。
