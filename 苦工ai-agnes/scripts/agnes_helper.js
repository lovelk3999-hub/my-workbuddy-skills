/**
 * Agnes API 苦工 — 带 Key Pool 自动轮换 + 文本/图片/视频 全套
 * 
 * 9个Key自动轮换，rate limit自动换下一个，60秒后重试
 * Key来源（优先级）:
 *   1. config.local.json（与本脚本同目录）← 推荐
 *   2. E:\ai\vedio_maker\config.local.json（项目旧路径）
 *   3. 环境变量 AGNES_KEYS（JSON数组字符串）
 * API文档: https://agnes-ai.com/doc/overview
 */

const fs = require("fs");
const path = require("path");

// ========== Key Pool ==========

function loadKeys() {
  // 方式1: 本目录的 config.local.json
  var localPath = path.join(__dirname, "config.local.json");
  try {
    var r = fs.readFileSync(localPath, "utf-8").replace(/^\uFEFF/, "");
    var keys = JSON.parse(r).agnes_keys;
    if (keys && keys.length > 0) return keys;
  } catch (e) { /* fall through */ }

  // 方式2: 项目旧路径
  var oldPath = "E:\\ai\\vedio_maker\\config.local.json";
  try {
    var r = fs.readFileSync(oldPath, "utf-8").replace(/^\uFEFF/, "");
    var keys = JSON.parse(r).agnes_keys;
    if (keys && keys.length > 0) return keys;
  } catch (e) { /* fall through */ }

  // 方式3: 环境变量
  var env = process.env.AGNES_KEYS;
  if (env) {
    try { var keys = JSON.parse(env); if (keys && keys.length > 0) return keys; } catch (e) {}
  }

  // 都没找到 — 报错
  throw new Error(
    "❌ 未找到 Agnes API Key！\n" +
    "请创建 " + localPath + "，内容格式见 config.example.json"
  );
}

var keyIndex = 0;
var keyPool = loadKeys();
var failedKeys = {};

function getNextKey() {
  var now = Date.now();
  for (var i = 0; i < keyPool.length; i++) {
    var idx = keyIndex % keyPool.length;
    keyIndex++;
    var k = keyPool[idx];
    if (failedKeys[k] && now - failedKeys[k] < 60000) continue;
    return k;
  }
  failedKeys = {};
  return keyPool[0];
}

var BASE = "https://apihub.agnes-ai.com/v1";

async function agnesFetch(endpoint, body, timeoutMs) {
  timeoutMs = timeoutMs || 60000;
  var apiKey = getNextKey();
  var controller = new AbortController();
  var timer = setTimeout(function () { controller.abort(); }, timeoutMs);
  try {
    var resp = await fetch(BASE + endpoint, {
      method: "POST",
      headers: { Authorization: "Bearer " + apiKey, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);
    var data = await resp.json();
    if (data.error) throw new Error(typeof data.error === "string" ? data.error : data.error.message);
    return data;
  } catch (e) {
    failedKeys[apiKey] = Date.now();
    clearTimeout(timer);
    throw e;
  }
}

// ========== 1. 文本能力 ==========

async function agnesChat(prompt, systemPrompt, options) {
  options = options || {};
  var messages = [];
  if (systemPrompt) messages.push({ role: "system", content: systemPrompt });
  messages.push({ role: "user", content: prompt });
  var body = {
    model: "agnes-2.0-flash",
    messages: messages,
    temperature: options.temperature || 0.7,
    max_tokens: options.max_tokens || 4096,
  };
  if (options.response_format === "json") body.response_format = { type: "json_object" };
  var data = await agnesFetch("/chat/completions", body, options.timeoutMs);
  return data.choices[0].message.content;
}

async function agnesBatch(prompts, delayMs) {
  delayMs = delayMs || 1000;
  var results = [];
  for (var i = 0; i < prompts.length; i++) {
    var p = prompts[i];
    var r = await agnesChat(p.prompt, p.systemPrompt, p.options);
    results.push(r);
    if (i < prompts.length - 1) await new Promise(function (r2) { setTimeout(r2, delayMs); });
  }
  return results;
}

async function formatToolsJson(rawData) {
  var result = await agnesChat("将以下工具数据格式化为标准JSON数组:\n" + rawData, "只输出合法JSON，不要markdown包裹", {
    response_format: "json",
    temperature: 0.3,
  });
  return JSON.parse(result);
}

function validateJson(jsonStr, schema) {
  var errors = [];
  schema = schema || {};
  try {
    var data = JSON.parse(jsonStr);
    var arr = Array.isArray(data) ? data : [data];
    if (schema.minCount && arr.length < schema.minCount)
      errors.push("数量不足: 需要" + schema.minCount + "条, 实际" + arr.length + "条");
    var fields = schema.requiredFields || ["id", "name", "url"];
    for (var i = 0; i < arr.length; i++)
      for (var f = 0; f < fields.length; f++)
        if (!arr[i][fields[f]]) errors.push("第" + (i + 1) + "条缺字段: " + fields[f]);
    return { pass: errors.length === 0, errors: errors };
  } catch (e) {
    return { pass: false, errors: ["JSON解析失败: " + e.message] };
  }
}

// ========== 2. 图片能力 ==========

/**
 * 文生图
 * @param {string} prompt - 图片描述
 * @param {string} size - 尺寸如 "1024x768"
 * @param {object} options - { returnBase64: bool, timeoutMs: number }
 * @returns {string} 图片URL 或 Base64 字符串
 */
async function agnesImage(prompt, size, options) {
  options = options || {};
  var body = {
    model: "agnes-image-2.1-flash",
    prompt: prompt,
    size: size || "1024x768",
  };
  if (options.returnBase64) {
    body.return_base64 = true;
  } else {
    body.extra_body = { response_format: "url" };
  }
  var data = await agnesFetch("/images/generations", body, options.timeoutMs || 120000);
  var img = data.data[0];
  if (options.returnBase64) return img.b64_json;
  return img.url || img.b64_json;
}

/**
 * 图生图（风格迁移/编辑）
 * @param {string} prompt - 编辑描述
 * @param {string} imageUrl - 公网可访问的图片URL
 * @param {string} size - 尺寸
 * @param {object} options
 * @returns {string} 编辑后的图片URL
 */
async function agnesImageEdit(prompt, imageUrl, size, options) {
  options = options || {};
  var body = {
    model: "agnes-image-2.1-flash",
    prompt: prompt,
    size: size || "1024x768",
    extra_body: {
      image: [imageUrl],
      response_format: "url",
    },
  };
  var data = await agnesFetch("/images/generations", body, options.timeoutMs || 120000);
  return data.data[0].url;
}

// ========== 3. 视频能力 ==========

/**
 * 文生视频（提交 + 自动轮询）
 * @param {string} prompt - 视频描述
 * @param {object} options - { num_frames, frame_rate, width, height, wait, pollInterval, timeoutMs }
 * @returns {object} { task_id, video_id, videoUrl, seconds, status }
 */
async function agnesVideo(prompt, options) {
  options = options || {};
  return await agnesVideoSubmitAndPoll(prompt, null, options);
}

/**
 * 图生视频（提交 + 自动轮询）
 * @param {string} prompt - 视频描述
 * @param {string} imageUrl - 公网图片URL
 * @param {object} options
 * @returns {object}
 */
async function agnesVideoFromImage(prompt, imageUrl, options) {
  options = options || {};
  return await agnesVideoSubmitAndPoll(prompt, imageUrl, options);
}

async function agnesVideoSubmitAndPoll(prompt, imageUrl, options) {
  options = options || {};
  var wait = options.wait !== false;
  var pollInterval = options.pollInterval || 5000;
  var timeoutMs = options.timeoutMs || 300000;

  // 提交任务
  var task = await agnesVideoSubmit(prompt, imageUrl, options);
  var videoId = task.video_id;
  var taskId = task.task_id || task.id;

  if (!wait) return { task_id: taskId, video_id: videoId, status: "queued" };

  // 轮询等待
  var deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise(function (r) { setTimeout(r, pollInterval); });
    var result = await agnesVideoQuery(videoId);
    if (result.status === "completed") {
      return {
        task_id: taskId,
        video_id: videoId,
        videoUrl: result.remixed_from_video_id || result.video_url,
        seconds: result.seconds,
        status: "completed",
        size: result.size,
      };
    }
    if (result.status === "failed") {
      throw new Error("视频生成失败: " + (result.error ? JSON.stringify(result.error) : "未知错误"));
    }
  }
  throw new Error("视频生成超时 (" + timeoutMs + "ms)");
}

/**
 * 提交视频任务（不等待）
 * @param {string} prompt
 * @param {string|null} imageUrl
 * @param {object} options - { num_frames, frame_rate, width, height }
 * @returns {object} { id, task_id, video_id, status }
 */
async function agnesVideoSubmit(prompt, imageUrl, options) {
  options = options || {};
  var body = {
    model: "agnes-video-v2.0",
    prompt: prompt,
  };
  if (options.num_frames) body.num_frames = options.num_frames;
  if (options.frame_rate) body.frame_rate = options.frame_rate;
  if (options.width) body.width = options.width;
  if (options.height) body.height = options.height;
  if (imageUrl) body.image = imageUrl;

  return await agnesFetch("/videos", body, options.timeoutMs || 30000);
}

/**
 * 查询视频结果（推荐用 video_id）
 * @param {string} videoId
 * @returns {object} { status, video_url, remixed_from_video_id, seconds, size, error }
 */
async function agnesVideoQuery(videoId) {
  var apiKey = getNextKey();
  try {
    var resp = await fetch("https://apihub.agnes-ai.com/agnesapi?video_id=" + encodeURIComponent(videoId), {
      method: "GET",
      headers: { Authorization: "Bearer " + apiKey },
    });
    return await resp.json();
  } catch (e) {
    failedKeys[apiKey] = Date.now();
    throw e;
  }
}

module.exports = {
  // 文本
  agnesChat: agnesChat,
  agnesBatch: agnesBatch,
  formatToolsJson: formatToolsJson,
  validateJson: validateJson,
  // 图片
  agnesImage: agnesImage,
  agnesImageEdit: agnesImageEdit,
  // 视频
  agnesVideo: agnesVideo,
  agnesVideoFromImage: agnesVideoFromImage,
  agnesVideoSubmit: agnesVideoSubmit,
  agnesVideoQuery: agnesVideoQuery,
  // 工具
  keyCount: keyPool.length,
  getKeyPool: function () { return keyPool.length; },
};
