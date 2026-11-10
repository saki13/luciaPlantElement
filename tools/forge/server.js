#!/usr/bin/env node
/**
 * 植物工坊 · 本地服务（零依赖，只用 Node 内置模块）
 *
 * 为什么需要它：
 *   浏览器不能直连 ModelScope（CORS，实测 TypeError: Failed to fetch）。
 *   Node 没这个限制，所以由它去调 API；页面从本机 http://127.0.0.1:8777 加载，
 *   请求自己这个服务 → 同源 → 没有 CORS。文件也由 Node 直接写盘。
 *
 * 用法：
 *   node server.js            # 默认 8777
 *   node server.js 8888
 *
 * 令牌（三选一）：
 *   环境变量 MODELSCOPE_TOKEN / MS_TOKEN
 *   或 anim_demo/.ms_token 文件（只有一行）
 */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const fsp = fs.promises;

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..");
const ANIM = path.join(ROOT, "anim_demo");
const SPRITES = path.join(ANIM, "assets", "sprites");
const ENEMIES = path.join(SPRITES, "enemies");
const PLANTS_DIR = path.join(ANIM, "assets", "plants");
const DATA = path.join(ROOT, "tdgame", "data");
const PUBLIC = path.join(HERE, "public");
const TOKEN_FILE = path.join(ANIM, ".ms_token");

const PORT = Number(process.argv[2] || process.env.PORT || 8777);
const MS_BASE = "https://api-inference.modelscope.cn";
const MODEL = "Qwen/Qwen-Image-2.1";
const FRAME = 64;
const COLS = 4;
const ROW_FRAMES = [2, 4, 3, 2];
const ROW_NAMES = ["idle", "walk", "attack", "hurt"];
const SLOTS = [];
ROW_FRAMES.forEach((n, r) => {
  for (let c = 0; c < COLS; c++) {
    SLOTS.push({ name: `${ROW_NAMES[r]}_${c}`, row: r, col: c, enabled: c < n });
  }
});

/* ------------------------------------------------------------------ 令牌 */
function loadToken() {
  const env = process.env.MODELSCOPE_TOKEN || process.env.MS_TOKEN || "";
  if (env.trim()) return { token: env.trim(), from: "环境变量" };
  try {
    const t = fs.readFileSync(TOKEN_FILE, "utf-8").trim();
    if (t) return { token: t, from: ".ms_token 文件" };
  } catch (e) { /* 没有文件 */ }
  return { token: "", from: "未配置" };
}

/* ------------------------------------------------------------------ 工具 */
const mime = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".png": "image/png",
  ".json": "application/json; charset=utf-8", ".ico": "image/x-icon",
};

function send(res, code, body, headers) {
  const h = Object.assign({ "Content-Type": "application/json; charset=utf-8" }, headers || {});
  res.writeHead(code, h);
  res.end(typeof body === "string" || Buffer.isBuffer(body) ? body : JSON.stringify(body));
}

function readBody(req, limit = 24 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", c => {
      size += c.length;
      if (size > limit) { reject(new Error("请求体太大")); req.destroy(); return; }
      chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/** 带重试的 HTTPS 请求（ModelScope 偶发 SSL EOF，必须重试） */
async function httpJson(url, { method = "GET", headers = {}, body = null } = {},
                             { tries = 4, timeoutMs = 90000 } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), timeoutMs);
    try {
      const r = await fetch(url, { method, headers, body, signal: ac.signal });
      clearTimeout(timer);
      const text = await r.text();
      if (!r.ok) {
        const err = new Error(`HTTP ${r.status}: ${text.slice(0, 300)}`);
        err.status = r.status;
        // 4xx 不重试（除了 429）
        if (r.status < 500 && r.status !== 429) throw Object.assign(err, { fatal: true });
        throw err;
      }
      try { return JSON.parse(text); } catch { return text; }
    } catch (e) {
      clearTimeout(timer);
      last = e;
      if (e.fatal) throw e;
      if (i < tries - 1) await sleep(1500 + 1500 * i);
    }
  }
  throw last;
}

async function httpBytes(url, { tries = 3, timeoutMs = 180000 } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), timeoutMs);
    try {
      const r = await fetch(url, { signal: ac.signal });
      clearTimeout(timer);
      if (!r.ok) throw new Error(`下载图片失败 HTTP ${r.status}`);
      return Buffer.from(await r.arrayBuffer());
    } catch (e) {
      clearTimeout(timer);
      last = e;
      if (i < tries - 1) await sleep(1500);
    }
  }
  throw last;
}

/* ------------------------------------------------------------------ 单位清单 */
function unitCn(kind, key) {
  try {
    const f = path.join(DATA, kind, key + ".json");
    return JSON.parse(fs.readFileSync(f, "utf-8")).cn || key;
  } catch { return key; }
}

function listUnits() {
  const out = [];
  const push = (key, kind) => {
    out.push({ key, cn: unitCn(kind, key), kind,
               frames: framesOnDisk(key) });
  };
  try {
    for (const f of fs.readdirSync(SPRITES)) {
      if (f.toLowerCase().endsWith(".png")) push(path.basename(f, ".png"), "plants");
    }
  } catch (e) { /* 没有目录 */ }
  try {
    for (const f of fs.readdirSync(ENEMIES)) {
      if (f.toLowerCase().endsWith(".png")) push(path.basename(f, ".png"), "enemies");
    }
  } catch (e) { /* ignore */ }
  return out.sort((a, b) => a.key.localeCompare(b.key));
}

function projectDir(key) { return path.join(PLANTS_DIR, key); }
function framesDir(key) { return path.join(projectDir(key), "frames"); }
function projectJson(key) { return path.join(projectDir(key), "plant.json"); }

function framesOnDisk(key) {
  const d = framesDir(key);
  const out = {};
  for (const s of SLOTS) {
    if (!s.enabled) continue;
    out[s.name] = fs.existsSync(path.join(d, s.name + ".png"));
  }
  return out;
}

function sheetPath(key) {
  const a = path.join(SPRITES, key + ".png");
  if (fs.existsSync(a)) return a;
  const b = path.join(ENEMIES, key + ".png");
  if (fs.existsSync(b)) return b;
  return null;
}

/* 首帧：优先项目 frames/idle_0，其次从精灵表切 */
function idleFrameFile(key) {
  const f = path.join(framesDir(key), "idle_0.png");
  return fs.existsSync(f) ? f : null;
}

/* ------------------------------------------------------------------ 拼表 */
/* 用浏览器传来的每帧 PNG 拼成 256x256 —— 但 Node 没有图像库。
   变通：让浏览器用 canvas 拼好再上传（页面里做），这里只负责写盘。 */

/* ------------------------------------------------------------------ 道具 */
const PROJ_KINDS = {
  seed: "种子/光球弹",
  blade: "剑气/刀光",
  leaf: "飞叶",
  organ: "延伸器官/触手",
};
const PROJ_HINT = {
  seed: "一颗圆润饱满、带简洁高光的种子形能量弹，略卡通可爱，适合从花口/炮口直线射出",
  blade: "一道月牙形的半透明剑气刀光，带锐利刃缘和清晰的速度拖尾，朝向画面正前方",
  leaf: "一片边缘锋利、叶脉清晰的飞旋叶片，造型利落、带轻微旋转动势",
  organ: "一段可弹射出去的植物延伸器官（如卷须尖、硬刺或孢子囊），造型饱满有弹性",
};
/* 道具出图硬约束：只有道具本身 + 纯白底，便于前端自动去背 */
const PROJ_TAIL =
  "画面中只有这一个道具，不要出现整株植物、角色五官、花盆、地面、手或任何其它物体；" +
  "纯白色干净背景(#FFFFFF)，2D 卡通 Q 版手游道具图标风格，粗深色描边、明快平涂加少量渐变，" +
  "单个道具完整居中、四周充分留白、无地面投影、无文字水印。";

function projPrompt(kind, desc) {
  const part = (desc || "").trim() || PROJ_HINT[kind] || PROJ_HINT.seed;
  return part + "。" + PROJ_TAIL;
}

/* ------------------------------------------------------------------ 生成 */
async function generateOne(prompt, refBase64) {
  const { token } = loadToken();
  if (!token) {
    const e = new Error("没有配置令牌：请设置环境变量 MODELSCOPE_TOKEN，或在 anim_demo 下放 .ms_token 文件");
    e.fatal = true;
    throw e;
  }
  const payload = { model: MODEL, prompt };
  if (refBase64) payload.image_url = [refBase64];   // 图生图：参考帧，保持同一角色

  const sub = await httpJson(MS_BASE + "/v1/images/generations", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + token,
      "Content-Type": "application/json",
      "X-ModelScope-Async-Mode": "true",
    },
    body: JSON.stringify(payload),
  }, { tries: 4, timeoutMs: 120000 });

  const taskId = sub && sub.task_id;
  if (!taskId) throw new Error("提交成功但没拿到 task_id：" + JSON.stringify(sub).slice(0, 200));

  const POLL = Number(process.env.POLL_SECONDS || 3);
  for (let i = 0; i < 100; i++) {
    await sleep(POLL * 1000);
    const js = await httpJson(`${MS_BASE}/v1/tasks/${taskId}`, {
      headers: {
        "Authorization": "Bearer " + token,
        "X-ModelScope-Task-Type": "image_generation",
      },
    }, { tries: 4, timeoutMs: 60000 });
    const st = js.task_status;
    if (st === "SUCCEED") {
      const imgs = js.output_images || [];
      if (!imgs.length) throw new Error("任务成功但没有图片");
      const buf = await httpBytes(imgs[0]);
      return { taskId, buffer: buf, status: st };
    }
    if (st === "FAILED") throw new Error("生成失败：" + JSON.stringify(js).slice(0, 300));
    if (i % 5 === 4) console.log(`  [${taskId.slice(0, 8)}] 仍在排队/生成 (${i + 1})`);
  }
  throw new Error("轮询超时（约 5 分钟）");
}

/* ------------------------------------------------------------------ 路由 */
async function api(req, res, url) {
  const p = url.pathname;

  if (p === "/api/state") {
    const t = loadToken();
    return send(res, 200, {
      ok: true, token: { configured: !!t.token, from: t.from },
      slots: SLOTS, frame: FRAME, cols: COLS, rowFrames: ROW_FRAMES,
      model: MODEL, root: ROOT,
    });
  }

  if (p === "/api/units") return send(res, 200, { ok: true, units: listUnits() });

  if (p === "/api/sheet") {
    const key = url.searchParams.get("key") || "";
    const f = sheetPath(key.replace(/[^\w-]/g, ""));
    if (!f) return send(res, 404, { ok: false, error: "没有这个角色的精灵表" });
    return send(res, 200, fs.readFileSync(f), { "Content-Type": "image/png", "Cache-Control": "no-store" });
  }

  if (p === "/api/frames") {
    const key = url.searchParams.get("key") || "";
    const out = {};
    for (const s of SLOTS) {
      if (!s.enabled) continue;
      const f = path.join(framesDir(key), s.name + ".png");
      out[s.name] = fs.existsSync(f) ? fs.readFileSync(f).toString("base64") : null;
    }
    let prompts = {}, base = "", projectExists = false;
    try {
      const pj = JSON.parse(fs.readFileSync(projectJson(key), "utf-8"));
      prompts = pj.frames || {};
      base = pj.base_desc || "";
      projectExists = true;
    } catch (e) { /* 没有项目文件 */ }
    let projectile = null;
    try {
      const pj = JSON.parse(fs.readFileSync(projectJson(key), "utf-8"));
      projectile = pj.projectile || null;
    } catch (e) { /* ignore */ }
    const projFile = path.join(projectDir(key), "projectile.png");
    const projB64 = fs.existsSync(projFile) ? fs.readFileSync(projFile).toString("base64") : null;
    return send(res, 200, { ok: true, frames: out, prompts, base, projectExists,
                            exists: framesOnDisk(key), projectile, projectileImage: projB64,
                            projectileKinds: PROJ_KINDS });
  }

  if (p === "/api/generate" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    const prompt = (body.prompt || "").trim();
    if (!prompt) return send(res, 400, { ok: false, error: "prompt 为空" });
    const t0 = Date.now();
    try {
      const r = await generateOne(prompt, body.ref || null);
      console.log(`  生成完成 ${((Date.now() - t0) / 1000).toFixed(0)}s  ${(r.buffer.length / 1024).toFixed(0)}KB`);
      return send(res, 200, {
        ok: true, taskId: r.taskId, seconds: Math.round((Date.now() - t0) / 1000),
        image: "data:image/png;base64," + r.buffer.toString("base64"),
      });
    } catch (e) {
      console.log("  生成失败:", e.message);
      return send(res, 400, { ok: false, error: e.message });
    }
  }

  if (p === "/api/generate3" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    const prompt = (body.prompt || "").trim();
    if (!prompt) return send(res, 400, { ok: false, error: "prompt 为空" });
    const n = Math.min(4, Math.max(2, Number(body.n) || 3));
    const t0 = Date.now();
    // 并行提交：三张一起排队，比串行快得多
    const jobs = [];
    for (let i = 0; i < n; i++) jobs.push(generateOne(prompt, body.ref || null));
    const settled = await Promise.allSettled(jobs);
    const images = [], errors = [];
    settled.forEach((r, i) => {
      if (r.status === "fulfilled") images.push("data:image/png;base64," + r.value.buffer.toString("base64"));
      else errors.push(`第${i + 1}张失败：${r.reason && r.reason.message}`);
    });
    console.log(`  三连抽完成 ${images.length}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    if (!images.length) return send(res, 400, { ok: false, error: errors.join("；") || "全部失败" });
    return send(res, 200, { ok: true, images, errors, seconds: Math.round((Date.now() - t0) / 1000) });
  }

  if (p === "/api/projectile" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    const key = String(body.key || "").replace(/[^\w-]/g, "");
    if (!key) return send(res, 400, { ok: false, error: "缺少 key" });
    const b64 = String(body.image || "").replace(/^data:image\/\w+;base64,/, "");
    let data = {};
    try { data = JSON.parse(await fsp.readFile(projectJson(key), "utf-8")); } catch (e) { data = {}; }
    data.key = key;
    data.cn = data.cn || unitCn("plants", key);
    if (b64) {
      await fsp.mkdir(projectDir(key), { recursive: true });
      await fsp.writeFile(path.join(projectDir(key), "projectile.png"), Buffer.from(b64, "base64"));
      data.projectile = { enabled: true, kind: body.kind || "seed", desc: body.desc || "",
                          file: "projectile.png" };
    } else {
      const f = path.join(projectDir(key), "projectile.png");
      if (fs.existsSync(f)) await fsp.unlink(f);
      data.projectile = { enabled: false, kind: body.kind || "seed", desc: body.desc || "", file: null };
    }
    data.updated = new Date().toISOString();
    await fsp.mkdir(projectDir(key), { recursive: true });
    await fsp.writeFile(projectJson(key), JSON.stringify(data, null, 2), "utf-8");
    return send(res, 200, { ok: true, saved: !!b64 });
  }

  if (p === "/api/projectile-prompt" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    return send(res, 200, { ok: true, prompt: projPrompt(body.kind || "seed", body.desc || "") });
  }

  if (p === "/api/project" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    const key = String(body.key || "").replace(/[^\w-]/g, "");
    if (!key) return send(res, 400, { ok: false, error: "缺少 key" });
    let data = {};
    try { data = JSON.parse(await fsp.readFile(projectJson(key), "utf-8")); } catch (e) { data = {}; }
    data.key = key;
    data.cn = data.cn || unitCn("plants", key);
    if (typeof body.base === "string") data.base_desc = body.base;
    if (body.frames && typeof body.frames === "object") {
      data.frames = Object.assign({}, data.frames || {}, body.frames);
    }
    data.updated = new Date().toISOString();
    await fsp.mkdir(projectDir(key), { recursive: true });
    await fsp.writeFile(projectJson(key), JSON.stringify(data, null, 2), "utf-8");
    return send(res, 200, { ok: true, saved: true });
  }

  if (p === "/api/frame" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    const key = String(body.key || "").replace(/[^\w-]/g, "");
    const slot = String(body.slot || "");
    if (!key || !SLOTS.some(s => s.name === slot)) {
      return send(res, 400, { ok: false, error: "key 或 slot 不合法" });
    }
    const b64 = String(body.image || "").replace(/^data:image\/\w+;base64,/, "");
    if (!b64) return send(res, 400, { ok: false, error: "没有图片数据" });
    await fsp.mkdir(framesDir(key), { recursive: true });
    await fsp.writeFile(path.join(framesDir(key), slot + ".png"), Buffer.from(b64, "base64"));

    // 同步 project.json 里的逐帧 prompt
    let data = {};
    try { data = JSON.parse(await fsp.readFile(projectJson(key), "utf-8")); } catch (e) { data = {}; }
    data.key = data.key || key;
    data.cn = data.cn || key;
    data.frames = data.frames || {};
    if (body.prompt) data.frames[slot] = body.prompt;
    data.updated = new Date().toISOString();
    await fsp.mkdir(projectDir(key), { recursive: true });
    await fsp.writeFile(projectJson(key), JSON.stringify(data, null, 2), "utf-8");
    return send(res, 200, { ok: true, saved: slot });
  }

  if (p === "/api/sheet" && req.method === "POST") {
    const body = JSON.parse((await readBody(req)).toString("utf-8"));
    const key = String(body.key || "").replace(/[^\w-]/g, "");
    const b64 = String(body.image || "").replace(/^data:image\/\w+;base64,/, "");
    if (!key || !b64) return send(res, 400, { ok: false, error: "缺少 key 或图片" });
    const target = path.join(SPRITES, key + ".png");
    await fsp.mkdir(path.dirname(target), { recursive: true });
    await fsp.writeFile(target, Buffer.from(b64, "base64"));
    console.log(`  拼表已写入 ${target}`);
    return send(res, 200, { ok: true, path: path.relative(ROOT, target) });
  }

  return send(res, 404, { ok: false, error: "接口不存在: " + p });
}

/* ------------------------------------------------------------------ 静态 */
async function serveStatic(req, res, url) {
  let rel = decodeURIComponent(url.pathname);
  if (rel === "/" ) rel = "/index.html";
  const file = path.join(PUBLIC, rel.replace(/^\/+/, ""));
  if (!file.startsWith(PUBLIC)) return send(res, 403, "forbidden");
  try {
    const buf = await fsp.readFile(file);
    return send(res, 200, buf, { "Content-Type": mime[path.extname(file)] || "application/octet-stream" });
  } catch (e) {
    return send(res, 404, "not found: " + rel);
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  try {
    if (url.pathname.startsWith("/api/")) return await api(req, res, url);
    return await serveStatic(req, res, url);
  } catch (e) {
    console.error("未捕获错误:", e);
    if (!res.headersSent) send(res, 500, { ok: false, error: String(e && e.message || e) });
    else res.end();
  }
});

server.listen(PORT, "127.0.0.1", () => {
  const t = loadToken();
  console.log("=".repeat(54));
  console.log(`  植物工坊已启动  http://127.0.0.1:${PORT}`);
  console.log(`  仓库: ${ROOT}`);
  console.log(`  令牌: ${t.configured ? "已配置（" + t.from + "）" : "未配置 —— 生成会失败，请设置 MODELSCOPE_TOKEN"}`);
  console.log(`  模型: ${MODEL}`);
  console.log("=".repeat(54));
});
