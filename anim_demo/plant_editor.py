# -*- coding: utf-8 -*-
"""
植物工坊 Plant Forge —— 原创植物手工定制桌面编辑器（Tkinter，标准库零额外安装）。
向导五步：1 描述拼 prompt → 2 立绘连抽 3 张三选一(可退回改词) → 3 动作帧单张重 roll
         → 4 子弹/飞行道具独立透明贴图生成 → 5 一键拼表 + pygame 预览。
运行：D:\\ProgramData\\anaconda3\\python.exe plant_editor.py
数据：每个植物一个目录 assets/plants/<key>/，含 plant.json + base.png + frames/，游戏运行时只读这些定稿资产。
token：优先环境变量 MODELSCOPE_TOKEN/MS_TOKEN，也可在界面填写并保存到本地 .ms_token（请勿提交到仓库）。
"""
import os
import sys
import json
import time
import shutil
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_image_qwen import generate
from gen_plant import TAIL, EDIT_GUARD, COMMON_FRAMES, PLANTS, PLANTS_ROOT
from build_spritesheet import build_dir, crop_asset

SPRITES_DIR = os.path.join(HERE, "assets", "sprites")
# 飞行道具定稿图最长边像素：道具在棋盘格内比植物小，48px 留足旋转/特效余量（可调起点）
PROJ_FIT = 48
TOKEN_FILE = os.path.join(HERE, ".ms_token")
DEMO_PATH = os.path.join(HERE, "sprite_animation_demo.py")
FRAME_NAMES = ["idle_0", "idle_1", "walk_0", "walk_1", "walk_2", "walk_3",
               "attack_0", "attack_1", "attack_2", "hurt_0", "hurt_1"]
LOCKED = {"idle_0": "= 立绘"}

DEFAULT_ATTACK = {
    "attack_0": "攻击蓄力：身体微微后缩下压、集中注意力，眼睛睁大、小嘴张成小O形，像在积蓄向前出招的力量。",
    "attack_1": "向前发力出招：身体前倾并微微拉长，发力瞬间带速度残影，O形嘴用力，充满冲击动感，但不增加任何新器官。",
    "attack_2": "收招回位：身体从前倾恢复到端正直立，嘴巴闭回微笑状，动作收尾。",
}
PROJECTILE_KINDS = [("seed", "种子/光球弹"), ("blade", "剑气/刀光"),
                    ("leaf", "飞叶/叶片"), ("organ", "延伸器官/触手")]
# 各类型的默认形态提示；用户在 desc 里写的具体设定优先并追加在后面
PROJECTILE_KIND_HINT = {
    "seed": "一颗圆润饱满、带简洁高光的种子形能量弹，略卡通可爱，适合从花口/炮口直线射出",
    "blade": "一道月牙形的半透明剑气刀光，带锐利刃缘和清晰的速度拖尾，朝向画面正前方",
    "leaf": "一片边缘锋利、叶脉清晰的飞旋叶片，造型利落、带轻微旋转动势",
    "organ": "一段可弹射出去的植物延伸器官（如卷须尖、硬刺或孢子囊），造型饱满有弹性",
}
# 飞行道具出图硬约束：画面里只能有道具本身，强制白底便于自动去背，风格与角色同一套
PROJECTILE_TAIL = (
    "画面中只有这一个道具，不要出现整株植物、角色五官、花盆、地面、手或任何其它物体；"
    "纯白色干净背景(#FFFFFF)，2D 卡通 Q 版手游道具图标风格，粗深色描边、明快平涂加少量渐变，"
    "单个道具完整居中、四周充分留白、无地面投影、无文字水印。"
)
# 提供立绘做参考时，额外要求配色向参考植物看齐，但仍只画道具
PROJECTILE_REF_HINT = "配色、描边质感与参考图中的植物保持同一套体系，但画面只画道具本身；"


def default_frame_prompts():
    d = dict(COMMON_FRAMES)
    d.update(DEFAULT_ATTACK)
    return d


class Project:
    """一个植物目录的数据模型，配置落在 plant.json。"""

    def __init__(self, key):
        self.key = key
        self.root = os.path.join(PLANTS_ROOT, key)
        self.frames_dir = os.path.join(self.root, "frames")
        self.cand_dir = os.path.join(self.root, "candidates")
        self.hist_dir = os.path.join(self.root, "frame_history")
        self.json_path = os.path.join(self.root, "plant.json")
        self.base_path = os.path.join(self.root, "base.png")
        self.sheet_path = os.path.join(SPRITES_DIR, key + ".png")
        self.data = {}

    # ---------- 生命周期 ----------
    @classmethod
    def create(cls, key, cn, base_desc):
        p = cls(key)
        os.makedirs(p.frames_dir, exist_ok=True)
        os.makedirs(p.cand_dir, exist_ok=True)
        p.data = {
            "key": key, "cn": cn, "base_desc": base_desc,
            "frames": default_frame_prompts(),
            "projectile": {"enabled": False, "kind": "seed", "desc": "", "file": None},
            "sheet": os.path.relpath(p.sheet_path, HERE),
            "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        p.save()
        return p

    @classmethod
    def open(cls, key):
        p = cls(key)
        if os.path.exists(p.json_path):
            with open(p.json_path, "r", encoding="utf-8") as f:
                p.data = json.load(f)
        else:
            # 兼容工坊出现前已存在的植物目录：用内置配置或默认模板补建 plant.json
            tmpl = PLANTS.get(key, {})
            frames = default_frame_prompts()
            frames.update(tmpl.get("attack", {}))
            p.data = {
                "key": key, "cn": tmpl.get("cn", key),
                "base_desc": tmpl.get("base_desc", ""),
                "frames": frames,
                "projectile": {"enabled": False, "kind": "seed", "desc": "", "file": None},
                "sheet": os.path.relpath(p.sheet_path, HERE),
                "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            os.makedirs(p.frames_dir, exist_ok=True)
            p.save()
        return p

    def save(self):
        self.data["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(self.root, exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ---------- 路径/状态辅助 ----------
    def frame_path(self, name):
        return os.path.join(self.frames_dir, name + ".png")

    def base_prompt(self):
        return "2D 游戏植物精灵立绘，" + self.data.get("base_desc", "") + TAIL

    def frame_prompt(self, name):
        return EDIT_GUARD + self.data["frames"].get(name, "") + TAIL

    def frame_status(self, name):
        if name == "idle_0":
            return "立绘" if os.path.exists(self.base_path) else "缺立绘"
        return "已出" if os.path.exists(self.frame_path(name)) else "未生成"

    def all_frames_ready(self):
        return os.path.exists(self.base_path) and all(
            name == "idle_0" or os.path.exists(self.frame_path(name)) for name in FRAME_NAMES)

    # ---------- 飞行道具（独立透明 PNG，不进 4×4 精灵表） ----------
    def projectile_path(self):
        return os.path.join(self.root, "projectile.png")

    def projectile_raw_path(self):
        return os.path.join(self.root, "projectile_raw.png")

    def projectile_hist_dir(self):
        return os.path.join(self.root, "projectile_history")

    def projectile_ready(self):
        return os.path.exists(self.projectile_path())

    def projectile_prompt(self):
        pj = self.data.setdefault("projectile",
                                  {"enabled": False, "kind": "seed", "desc": "", "file": None})
        kind = pj.get("kind", "seed")
        parts = ["2D 游戏飞行道具图标，", PROJECTILE_KIND_HINT.get(kind, PROJECTILE_KIND_HINT["seed"]), "。"]
        desc = (pj.get("desc") or "").strip()
        if desc:
            parts.append("具体设定：" + desc + "。")
        if os.path.exists(self.base_path):
            parts.append(PROJECTILE_REF_HINT)
        parts.append(PROJECTILE_TAIL)
        return "".join(parts)


class ApiHub:
    """后台线程执行网络/重活，结果回传队列，主线程 after 消费，避免 Tk 卡死。"""

    def __init__(self, root):
        self.root = root
        self.q = __import__("queue").Queue()
        self.busy = 0
        self.progress_cb = None
        self.root.after(100, self._drain)

    def run(self, fn, on_done, on_progress=None):
        self.busy += 1
        self.progress_cb = on_progress

        def work():
            try:
                res = fn()
                self.q.put((on_done, None, res))
            except BaseException as e:  # generate 失败用 SystemExit，需捕获 BaseException
                self.q.put((on_done, str(e), None))
            finally:
                self.q.put(("__busy__", None, -1))
        threading.Thread(target=work, daemon=True).start()

    def emit(self, payload):
        """供后台任务推送中途进度事件，主线程 _drain 统一消费。

        队列元素固定为 (回调标识, err, res) 三元组，进度载荷放在 res 位。
        """
        self.q.put(("__progress__", None, payload))

    def _drain(self):
        try:
            while True:
                cb, err, res = self.q.get_nowait()
                if cb == "__busy__":
                    self.busy = max(0, self.busy - 1)
                    self.progress_cb = None
                elif cb == "__progress__":
                    if self.progress_cb:
                        try:
                            self.progress_cb(res)
                        except Exception as e:
                            messagebox.showerror("进度回调异常", repr(e))
                else:
                    try:
                        cb(err, res)
                    except Exception as e:
                        messagebox.showerror("回调异常", repr(e))
        except Exception:
            pass
        self.root.after(120, self._drain)


def load_token():
    if os.environ.get("MODELSCOPE_TOKEN"):
        return os.environ["MODELSCOPE_TOKEN"].strip()
    if os.environ.get("MS_TOKEN"):
        return os.environ["MS_TOKEN"].strip()
    if os.path.exists(TOKEN_FILE):
        return open(TOKEN_FILE, "r", encoding="utf-8").read().strip()
    return ""


def thumb(path, size=(96, 96)):
    im = Image.open(path).convert("RGBA")
    im.thumbnail(size, Image.LANCZOS)
    return ImageTk.PhotoImage(im)


def finalize_projectile(raw_path, out_path, fit=PROJ_FIT):
    """白底原图 → 去背 → 裁到不透明 bbox → 最长边压到 fit 内（只缩不放），存紧凑透明 PNG。"""
    im = crop_asset(raw_path)
    bbox = im.getbbox()
    if not bbox or im.width == 0 or im.height == 0:
        raise RuntimeError("去背后没有保留任何不透明像素，疑似背景不是纯白，请换一张重试")
    scale = min(fit / im.width, fit / im.height, 1.0)
    if scale < 1.0:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                       Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    im.save(out_path)
    return out_path, im.size


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("植物工坊 Plant Forge —— 原创植物定制")
        self.geometry("1040x720")
        self.minsize(960, 660)
        self.api = ApiHub(self)
        self.proj = None
        self._img_refs = []
        self._build_topbar()
        self._build_body()
        self.refresh_project_list()
        self._goto(0)

    # ============ 顶部栏 ============
    def _build_topbar(self):
        bar = ttk.Frame(self, padding=(10, 6))
        bar.pack(fill="x")
        ttk.Label(bar, text="植物工坊", font=("Microsoft YaHei UI", 15, "bold")).pack(side="left")
        self.token_btn = ttk.Button(bar, text="设置 Token", command=self.open_token)
        self.token_btn.pack(side="right")
        self.token_state = ttk.Label(bar, text="")
        self.token_state.pack(side="right", padx=8)
        self._render_token_state()

    def _render_token_state(self):
        self.token_state.config(text="Token：已就绪" if load_token() else "Token：未设置")

    def open_token(self):
        win = tk.Toplevel(self)
        win.title("ModelScope Token")
        win.geometry("520x180")
        ttk.Label(win, text="粘贴 ModelScope API Token（仅存于本地 .ms_token，请勿提交仓库）：",
                  wraplength=480).pack(anchor="w", padx=12, pady=(12, 4))
        var = tk.StringVar(value=load_token())
        ent = ttk.Entry(win, textvariable=var, width=60, show="*")
        ent.pack(padx=12, fill="x")

        def save():
            tok = var.get().strip()
            if tok:
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(tok)
                os.environ["MS_TOKEN"] = tok
            self._render_token_state()
            win.destroy()
        ttk.Button(win, text="保存", command=save).pack(pady=12)

    # ============ 主体布局 ============
    def _build_body(self):
        body = ttk.Frame(self, padding=8)
        body.pack(fill="both", expand=True)
        # 左：项目与导航
        left = ttk.Frame(body, width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        proj_box = ttk.LabelFrame(left, text="植物项目", padding=6)
        proj_box.pack(fill="x")
        self.proj_combo = ttk.Combobox(proj_box, state="readonly")
        self.proj_combo.pack(fill="x")
        self.proj_combo.bind("<<ComboboxSelected>>", lambda e: self.open_project())
        row = ttk.Frame(proj_box)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="新建植物", command=self.new_project_dialog).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="刷新", command=self.refresh_project_list).pack(side="left", padx=(6, 0))
        nav = ttk.LabelFrame(left, text="步骤", padding=6)
        nav.pack(fill="x", pady=(10, 0))
        self.step_buttons = []
        for i, name in enumerate(["1 描述与 Prompt", "2 立绘三选一", "3 动作帧", "4 子弹/道具", "5 拼表预览"]):
            b = ttk.Button(nav, text=name, command=lambda i=i: self._goto(i))
            b.pack(fill="x", pady=3)
            self.step_buttons.append(b)
        # 右：步骤容器
        self.content = ttk.Frame(body)
        self.content.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.steps = []
        for builder in (self._step_desc, self._step_base, self._step_frames,
                        self._step_projectile, self._step_build):
            f = ttk.Frame(self.content)
            builder(f)
            self.steps.append(f)
        self.status = ttk.Label(self, text="就绪", anchor="w", padding=(10, 2))
        self.status.pack(fill="x", side="bottom")

    def _goto(self, i):
        for j, f in enumerate(self.steps):
            f.place_forget() if str(f.place_info()) else None
        self.steps[i].place(x=0, y=0, relwidth=1, relheight=1)
        if i == 1:
            self._refresh_base_step()
        if i == 2:
            self._refresh_frame_grid()
        if i == 3:
            self._load_projectile_form()
        if i == 4:
            self._refresh_build_step()

    def set_status(self, text):
        self.status.config(text=text)

    def require_project(self):
        if not self.proj:
            messagebox.showinfo("提示", "请先在左侧新建或打开一个植物项目")
            return False
        return True

    def require_token(self):
        if not load_token():
            messagebox.showwarning("缺少 Token", "请先在右上角设置 ModelScope Token")
            return False
        os.environ["MS_TOKEN"] = load_token()
        return True

    # ============ 项目管理 ============
    def refresh_project_list(self):
        os.makedirs(PLANTS_ROOT, exist_ok=True)
        keys = sorted(d for d in os.listdir(PLANTS_ROOT)
                      if os.path.isdir(os.path.join(PLANTS_ROOT, d)))
        self.proj_combo["values"] = keys
        if self.proj and self.proj.key in keys:
            self.proj_combo.set(self.proj.key)

    def new_project_dialog(self):
        win = tk.Toplevel(self)
        win.title("新建植物")
        win.geometry("560x420")
        ttk.Label(win, text="英文标识 key（用作文件夹名，小写英文/数字/下划线）：").pack(anchor="w", padx=12, pady=(12, 2))
        key_var = tk.StringVar()
        ttk.Entry(win, textvariable=key_var).pack(fill="x", padx=12)
        ttk.Label(win, text="中文名称：").pack(anchor="w", padx=12, pady=(8, 2))
        cn_var = tk.StringVar()
        ttk.Entry(win, textvariable=cn_var).pack(fill="x", padx=12)
        ttk.Label(win, text="外观描述（它长什么样、什么颜色、有什么器官/武器，越具体越好）：").pack(anchor="w", padx=12, pady=(8, 2))
        desc = scrolledtext.ScrolledText(win, height=10, wrap="word")
        desc.pack(fill="both", expand=True, padx=12)

        def ok():
            key = key_var.get().strip().lower()
            cn = cn_var.get().strip()
            text = desc.get("1.0", "end").strip()
            if not key or not all(c.isalnum() or c == "_" for c in key):
                messagebox.showwarning("校验", "key 只能含小写英文、数字、下划线", parent=win)
                return
            if not cn or not text:
                messagebox.showwarning("校验", "中文名和外观描述都要填写", parent=win)
                return
            if os.path.exists(os.path.join(PLANTS_ROOT, key)):
                messagebox.showwarning("校验", f"已存在 {key}，请直接打开或换个 key", parent=win)
                return
            self.proj = Project.create(key, cn, text)
            self.refresh_project_list()
            self.proj_combo.set(key)
            win.destroy()
            self._load_into_form()
            self._goto(0)
            self.set_status(f"已新建植物 {cn}（{key}）")
        ttk.Button(win, text="创建并进入描述步骤", command=ok).pack(pady=10)

    def open_project(self):
        key = self.proj_combo.get()
        if not key:
            return
        self.proj = Project.open(key)
        self._load_into_form()
        self._goto(0)
        self.set_status(f"已打开 {self.proj.data.get('cn', key)}")

    # ============ 步骤 1：描述 ============
    def _step_desc(self, f):
        ttk.Label(f, text="① 描述植物，工坊会自动拼上统一风格模板生成完整 Prompt",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(f, text="中文名称").pack(anchor="w", pady=(8, 2))
        self.f_cn = ttk.Entry(f)
        self.f_cn.pack(fill="x")
        ttk.Label(f, text="外观描述（base_desc）").pack(anchor="w", pady=(8, 2))
        self.f_desc = scrolledtext.ScrolledText(f, height=8, wrap="word")
        self.f_desc.pack(fill="both", expand=True)
        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="保存描述并刷新 Prompt 预览", command=self._save_desc).pack(side="left")
        ttk.Button(btns, text="下一步：抽立绘 →", command=lambda: self._goto(1)).pack(side="right")
        ttk.Label(f, text="完整立绘 Prompt（只读，自动拼接）").pack(anchor="w", pady=(8, 2))
        self.f_prompt = scrolledtext.ScrolledText(f, height=8, wrap="word", state="disabled",
                                                  background="#f4f6f8")
        self.f_prompt.pack(fill="both", expand=True)

    def _load_into_form(self):
        if not self.proj:
            return
        self.f_cn.delete(0, "end")
        self.f_cn.insert(0, self.proj.data.get("cn", ""))
        self.f_desc.delete("1.0", "end")
        self.f_desc.insert("1.0", self.proj.data.get("base_desc", ""))
        self._render_prompt_preview()

    def _save_desc(self):
        if not self.require_project():
            return
        self.proj.data["cn"] = self.f_cn.get().strip()
        self.proj.data["base_desc"] = self.f_desc.get("1.0", "end").strip()
        self.proj.save()
        self._render_prompt_preview()
        self.set_status("描述已保存")

    def _render_prompt_preview(self):
        if not self.proj:
            txt = ""
        else:
            self.proj.data["cn"] = self.f_cn.get().strip()
            self.proj.data["base_desc"] = self.f_desc.get("1.0", "end").strip()
            txt = self.proj.base_prompt()
        self.f_prompt.config(state="normal")
        self.f_prompt.delete("1.0", "end")
        self.f_prompt.insert("1.0", txt)
        self.f_prompt.config(state="disabled")

    # ============ 步骤 2：立绘三选一 ============
    def _step_base(self, f):
        ttk.Label(f, text="② 连抽 3 张立绘，选一张定稿；都不满意就返回改描述重抽",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", pady=8)
        ttk.Button(ctrl, text="连抽 3 张", command=self.draw_three_base).pack(side="left")
        ttk.Button(ctrl, text="← 返回改描述", command=lambda: self._goto(0)).pack(side="left", padx=8)
        self.base_progress = ttk.Label(ctrl, text="")
        self.base_progress.pack(side="left", padx=10)
        self.base_current = ttk.Label(f, text="当前定稿立绘：无")
        self.base_current.pack(anchor="w")
        self.base_cur_img = ttk.Label(f)
        self.base_cur_img.pack(anchor="w", pady=4)
        cand = ttk.LabelFrame(f, text="本批候选（点“选它”定稿为 base.png）", padding=8)
        cand.pack(fill="both", expand=True, pady=8)
        self.cand_slots = []
        for i in range(3):
            slot = ttk.Frame(cand, relief="groove", padding=6)
            slot.grid(row=0, column=i, padx=8, sticky="n", pady=6)
            lab = ttk.Label(slot, text="（待抽取）")
            lab.pack()
            btn = ttk.Button(slot, text="选它", state="disabled")
            btn.pack(pady=6)
            self.cand_slots.append({"frame": slot, "lab": lab, "btn": btn, "path": None})

    def _refresh_base_step(self):
        if not self.proj:
            return
        if os.path.exists(self.proj.base_path):
            self.base_current.config(text="当前定稿立绘：base.png（重抽会覆盖，动作帧以它为基准）")
            img = thumb(self.proj.base_path, (130, 130))
            self._img_refs.append(img)
            self.base_cur_img.config(image=img)
        else:
            self.base_current.config(text="当前定稿立绘：无")
            self.base_cur_img.config(image="")

    def draw_three_base(self):
        if not self.require_project() or not self.require_token():
            return
        if self.api.busy:
            messagebox.showinfo("请稍候", "已有生成任务在进行，完成后再抽立绘")
            return
        self._save_desc()
        prompt = self.proj.base_prompt()
        ts = time.strftime("%Y%m%d_%H%M%S")
        outs = [os.path.join(self.proj.cand_dir, f"cand_{ts}_{i+1}.png") for i in range(3)]
        for slot in self.cand_slots:
            slot["lab"].config(image="", text="抽取中…")
            slot["btn"].config(state="disabled")
            slot["path"] = None
        self.base_progress.config(text="并发抽取 3 张，约 30–80 秒…")

        def task():
            def one(i):
                try:
                    generate(prompt, outs[i])
                    return True, outs[i]
                except BaseException as e:
                    return False, str(e)
            with ThreadPoolExecutor(max_workers=3) as ex:
                return list(ex.map(one, range(3)))

        def done(err, results):
            self.base_progress.config(text="本批完成" if not err else f"出错：{err}")
            for i, (ok, val) in enumerate(results or []):
                slot = self.cand_slots[i]
                if ok:
                    slot["path"] = val
                    img = thumb(val, (150, 150))
                    self._img_refs.append(img)
                    slot["lab"].config(image=img, text="")
                    slot["btn"].config(state="normal",
                                       command=lambda p=val: self.choose_base(p))
                else:
                    slot["lab"].config(image="", text="失败：" + val[:60])
                    slot["btn"].config(state="disabled")
        self.api.run(task, done)

    def choose_base(self, path):
        if not self.require_project():
            return
        shutil.copyfile(path, self.proj.base_path)
        idle0 = self.proj.frame_path("idle_0")
        shutil.copyfile(path, idle0)
        self._refresh_base_step()
        self.set_status("立绘已定稿，idle_0 已同步；已进入动作帧，可先一键生成全部再逐张精修")
        self._goto(2)

    # ============ 步骤 3：动作帧 ============
    def _step_frames(self, f):
        ttk.Label(f, text="③ 动作帧：先一键批量生成全部，再点任意格逐张重 roll 精修（idle_0 锁定为立绘）",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        batch_bar = ttk.Frame(f)
        batch_bar.pack(fill="x", pady=(6, 4))
        self.batch_btn = ttk.Button(batch_bar, text="一键生成全部动作帧", command=self.generate_all_frames)
        self.batch_btn.pack(side="left")
        self.batch_lab = ttk.Label(batch_bar, text="")
        self.batch_lab.pack(side="left", padx=10)
        wrap = ttk.Frame(f)
        wrap.pack(fill="both", expand=True, pady=4)
        grid = ttk.Frame(wrap)
        grid.pack(side="left", fill="y")
        self.frame_btns = {}
        for idx, name in enumerate(FRAME_NAMES):
            r, c = divmod(idx, 4)
            cell = ttk.Frame(grid, relief="ridge", padding=4)
            cell.grid(row=r, column=c, padx=4, pady=4, sticky="n")
            ttk.Label(cell, text=name + ("  " + LOCKED[name] if name in LOCKED else "")).pack()
            lab = ttk.Label(cell, text="—")
            lab.pack()
            state = ttk.Label(cell, text="")
            state.pack()
            self.frame_btns[name] = {"lab": lab, "state": state, "cell": cell}
            if name != "idle_0":
                cell.bind("<Button-1>", lambda e, n=name: self.select_frame(n))
                lab.bind("<Button-1>", lambda e, n=name: self.select_frame(n))
        # 右侧详情
        detail = ttk.LabelFrame(wrap, text="帧详情", padding=8)
        detail.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.sel_name = tk.StringVar(value="未选择")
        ttk.Label(detail, textvariable=self.sel_name, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        ttk.Label(detail, text="该帧动作描述（可手工改写后再抽）").pack(anchor="w", pady=(6, 2))
        self.frame_text = scrolledtext.ScrolledText(detail, height=7, wrap="word")
        self.frame_text.pack(fill="both", expand=True)
        dbtns = ttk.Frame(detail)
        dbtns.pack(fill="x", pady=6)
        self.roll_btn = ttk.Button(dbtns, text="重 roll 这一帧", command=self.roll_frame)
        self.roll_btn.pack(side="left")
        self.undo_btn = ttk.Button(dbtns, text="回退上一版", command=self.undo_frame)
        self.undo_btn.pack(side="left", padx=6)
        self.frame_msg = ttk.Label(detail, text="")
        self.frame_msg.pack(anchor="w")
        self.selected_frame = None

    def _refresh_frame_grid(self):
        if not self.proj:
            return
        for name in FRAME_NAMES:
            w = self.frame_btns[name]
            path = self.proj.base_path if name == "idle_0" else self.proj.frame_path(name)
            w["state"].config(text=self.proj.frame_status(name))
            if os.path.exists(path):
                img = thumb(path, (78, 78))
                self._img_refs.append(img)
                w["lab"].config(image=img, text="")
            else:
                w["lab"].config(image="", text="—")
        if hasattr(self, "batch_btn"):
            self._update_batch_button()

    def _missing_frames(self):
        """除锁定的 idle_0 外、尚未出图的动作帧。"""
        return [n for n in FRAME_NAMES if n != "idle_0" and not os.path.exists(self.proj.frame_path(n))]

    def _update_batch_button(self):
        if not self.proj:
            return
        total_slots = len(FRAME_NAMES) - 1  # 不含 idle_0
        missing = self._missing_frames()
        done_cnt = total_slots - len(missing)
        if not missing:
            self.batch_btn.config(text="动作帧已全部生成 ✓", state="disabled")
            self.batch_lab.config(text="已完成 %d/%d，可点单格重 roll 精修，或去第 5 步拼表" % (done_cnt, total_slots))
        else:
            label = ("一键生成全部动作帧（%d）" % len(missing)) if done_cnt == 0 \
                else ("补齐缺失帧（剩 %d）" % len(missing))
            self.batch_btn.config(text=label, state="disabled" if self.api.busy else "normal")
            self.batch_lab.config(text="已完成 %d/%d（串行生成，约 30–80 秒/张，中途失败不影响其它帧）"
                                  % (done_cnt, total_slots))

    def generate_all_frames(self):
        if not self.require_project() or not self.require_token():
            return
        if not os.path.exists(self.proj.base_path):
            messagebox.showwarning("缺立绘", "请先在步骤 2 定稿立绘")
            return
        if self.api.busy:
            messagebox.showinfo("请稍候", "已有生成任务在进行，完成后再试")
            return
        missing = self._missing_frames()
        if not missing:
            return
        total = len(missing)
        self._batch_failed = []
        self.batch_btn.config(state="disabled")
        self.roll_btn.config(state="disabled")

        def task():
            for i, name in enumerate(missing, 1):
                self.api.emit({"phase": "start", "idx": i, "total": total, "name": name})
                try:
                    generate(self.proj.frame_prompt(name), self.proj.frame_path(name),
                             ref_path=self.proj.base_path)
                    self.api.emit({"phase": "ok", "idx": i, "total": total, "name": name})
                except BaseException as e:  # 单帧失败隔离，继续后续帧
                    self.api.emit({"phase": "fail", "idx": i, "total": total,
                                   "name": name, "err": str(e)})
            return total

        def on_progress(p):
            name = p["name"]
            if p["phase"] == "start":
                self.frame_btns[name]["state"].config(text="生成中 %d/%d" % (p["idx"], p["total"]))
                self.set_status("批量生成 %s（%d/%d），约 30–80 秒/张…" % (name, p["idx"], p["total"]))
            elif p["phase"] == "ok":
                self._refresh_frame_grid()
            else:
                self._batch_failed.append(name)
                self.frame_btns[name]["state"].config(text="失败")
                self.set_status("%s 失败，继续生成后续帧，结束后可单张重 roll" % name)

        def done(err, res):
            self.roll_btn.config(state="normal")
            self._refresh_frame_grid()
            self._update_batch_button()
            if err:
                messagebox.showerror("批量生成中断", err)
                self.set_status("批量生成异常中断")
                return
            failed = list(self._batch_failed)
            ok_n = total - len(failed)
            self.set_status("批量生成结束：成功 %d/%d" % (ok_n, total))
            if failed:
                messagebox.showwarning(
                    "批量完成（有失败）",
                    "成功 %d/%d，失败：%s\n点对应格子后用“重 roll 这一帧”单独补即可。"
                    % (ok_n, total, "、".join(failed)))
            else:
                messagebox.showinfo("批量完成", "全部 %d 个动作帧生成完毕，可前往第 5 步拼表预览。" % total)
        self.api.run(task, done, on_progress)

    def select_frame(self, name):
        if not self.require_project() or name == "idle_0":
            return
        self.selected_frame = name
        self.sel_name.set(name)
        self.frame_text.delete("1.0", "end")
        self.frame_text.insert("1.0", self.proj.data["frames"].get(name, ""))
        self.frame_msg.config(text="")

    def roll_frame(self):
        if not self.require_project() or not self.require_token() or not self.selected_frame:
            return
        if not os.path.exists(self.proj.base_path):
            messagebox.showwarning("缺立绘", "请先在步骤 2 定稿立绘")
            return
        if self.api.busy:
            messagebox.showinfo("请稍候", "批量生成进行中，结束后再单帧重 roll")
            return
        name = self.selected_frame
        self.proj.data["frames"][name] = self.frame_text.get("1.0", "end").strip()
        self.proj.save()
        target = self.proj.frame_path(name)
        os.makedirs(self.proj.hist_dir, exist_ok=True)
        backup = None
        if os.path.exists(target):
            backup = os.path.join(self.proj.hist_dir, f"{name}_{int(time.time())}.png")
            shutil.copyfile(target, backup)
        self.roll_btn.config(state="disabled")
        self.frame_msg.config(text="生成中…（约 30–80 秒）")
        prompt = self.proj.frame_prompt(name)

        def task():
            generate(prompt, target, ref_path=self.proj.base_path)
            return target

        def done(err, res):
            self.roll_btn.config(state="normal")
            self.frame_msg.config(text="完成" if not err else "失败：" + err)
            self._refresh_frame_grid()
        self.api.run(task, done)

    def undo_frame(self):
        if not self.selected_frame:
            return
        name = self.selected_frame
        pref = os.path.join(self.proj.hist_dir, name + "_")
        hist = sorted([os.path.join(self.proj.hist_dir, x) for x in os.listdir(self.proj.hist_dir)
                       if x.startswith(name + "_")], reverse=True)
        if not hist:
            self.frame_msg.config(text="没有可回退的历史版本")
            return
        shutil.copyfile(hist[0], self.proj.frame_path(name))
        os.remove(hist[0])
        self.frame_msg.config(text="已回退到上一版")
        self._refresh_frame_grid()

    # ============ 步骤 4：子弹 / 飞行道具 ============
    def _step_projectile(self, f):
        ttk.Label(f, text="④ 子弹 / 飞行道具：生成独立透明底 PNG（自动去背裁剪），不占用角色 4×4 精灵表",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(f, wraplength=760, text=(
            "种子弹、剑气刀光、飞叶、延伸器官等飞行道具单独出图，定稿后写入 plant.json 的 projectile.file，"
            "游戏运行时据此加载并绑定到攻击动作；可无限重 roll，旧版自动备份可回退。")).pack(
            anchor="w", pady=(4, 8))
        form = ttk.Frame(f)
        form.pack(fill="x")
        self.proj_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="该植物拥有飞行道具", variable=self.proj_enabled,
                        command=self._render_projectile_prompt).grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="类型").grid(row=1, column=0, sticky="w", pady=6)
        self.proj_kind = ttk.Combobox(form, state="readonly",
                                      values=[f"{k} {v}" for k, v in PROJECTILE_KINDS], width=22)
        self.proj_kind.grid(row=1, column=1, sticky="w")
        self.proj_kind.bind("<<ComboboxSelected>>", lambda e: self._render_projectile_prompt())
        ttk.Label(f, text="道具外观 / 飞行表现描述（留空则按类型默认形态生成）").pack(anchor="w", pady=(6, 2))
        self.proj_desc = scrolledtext.ScrolledText(f, height=5, wrap="word")
        self.proj_desc.pack(fill="x")
        self.proj_desc.bind("<KeyRelease>", lambda e: self._render_projectile_prompt())
        ttk.Label(f, text="实际出图 Prompt（只读，按类型 + 你的描述自动拼接）").pack(anchor="w", pady=(6, 2))
        self.proj_prompt = scrolledtext.ScrolledText(f, height=4, wrap="word", state="disabled",
                                                     background="#f4f6f8")
        self.proj_prompt.pack(fill="x")
        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="保存配置", command=self.save_projectile).pack(side="left")
        self.proj_gen_btn = ttk.Button(btns, text="生成 / 重 roll 子弹贴图", command=self.generate_projectile)
        self.proj_gen_btn.pack(side="left", padx=8)
        self.proj_undo_btn = ttk.Button(btns, text="回退上一版", command=self.undo_projectile)
        self.proj_undo_btn.pack(side="left")
        preview_box = ttk.LabelFrame(f, text="定稿贴图（透明底，最长边 %dpx）" % PROJ_FIT, padding=8)
        preview_box.pack(fill="x")
        holder = tk.Frame(preview_box, background="#d9dde3", width=110, height=110, highlightthickness=1,
                          highlightbackground="#9aa3ad")
        holder.pack(side="left")
        holder.pack_propagate(False)
        self.proj_preview = tk.Label(holder, background="#d9dde3")
        self.proj_preview.pack(expand=True)
        self.proj_file = ttk.Label(preview_box, text="尚未生成贴图", justify="left")
        self.proj_file.pack(side="left", padx=14, anchor="n")
        self.proj_msg = ttk.Label(f, text="")
        self.proj_msg.pack(anchor="w", pady=(6, 0))

    def _sync_projectile_form(self):
        """把第 4 步表单写回内存 data，保留已生成的 file 路径。"""
        if not self.proj:
            return
        old = self.proj.data.get("projectile", {}) or {}
        kind = self.proj_kind.get().split(" ")[0] if self.proj_kind.get() else "seed"
        self.proj.data["projectile"] = {
            "enabled": bool(self.proj_enabled.get()),
            "kind": kind,
            "desc": self.proj_desc.get("1.0", "end").strip(),
            "file": old.get("file"),
        }

    def _render_projectile_prompt(self):
        if not self.proj:
            return
        self._sync_projectile_form()
        txt = self.proj.projectile_prompt()
        self.proj_prompt.config(state="normal")
        self.proj_prompt.delete("1.0", "end")
        self.proj_prompt.insert("1.0", txt)
        self.proj_prompt.config(state="disabled")

    def _load_projectile_form(self):
        if not self.proj:
            return
        pj = self.proj.data.setdefault("projectile",
                                       {"enabled": False, "kind": "seed", "desc": "", "file": None})
        self.proj_enabled.set(bool(pj.get("enabled")))
        kind = pj.get("kind", "seed")
        self.proj_kind.set(next((f"{k} {v}" for k, v in PROJECTILE_KINDS if k == kind),
                                f"{PROJECTILE_KINDS[0][0]} {PROJECTILE_KINDS[0][1]}"))
        self.proj_desc.delete("1.0", "end")
        self.proj_desc.insert("1.0", pj.get("desc", ""))
        self._render_projectile_prompt()
        self._refresh_projectile_preview()

    def _refresh_projectile_preview(self):
        if not self.proj:
            return
        path = self.proj.projectile_path()
        if os.path.exists(path):
            img = thumb(path, (96, 96))
            self._img_refs.append(img)
            self.proj_preview.config(image=img, text="")
            with Image.open(path) as im:
                size = im.size
            rel = os.path.relpath(path, HERE)
            self.proj_file.config(text="定稿：%s\n像素：%d × %d（透明底 RGBA）\n原始白底图：projectile_raw.png"
                                       % (rel, size[0], size[1]))
        else:
            self.proj_preview.config(image="", text="")
            self.proj_file.config(text="尚未生成贴图")
        hist = self.proj.projectile_hist_dir()
        has_hist = os.path.isdir(hist) and any(x.startswith("projectile_") for x in os.listdir(hist))
        self.proj_undo_btn.config(state="normal" if has_hist else "disabled")

    def save_projectile(self):
        if not self.require_project():
            return
        self._sync_projectile_form()
        self.proj.save()
        self.proj_msg.config(text="子弹配置已保存到 plant.json")
        self.set_status("子弹配置已保存")

    def generate_projectile(self):
        if not self.require_project() or not self.require_token():
            return
        if not self.proj_enabled.get():
            messagebox.showwarning("未启用", "请先勾选“该植物拥有飞行道具”，或确认类型后再生成")
            return
        if self.api.busy:
            messagebox.showinfo("请稍候", "已有生成任务在进行，完成后再试")
            return
        self._sync_projectile_form()
        self.proj.save()
        # 备份现有定稿，供“回退上一版”
        final = self.proj.projectile_path()
        if os.path.exists(final):
            os.makedirs(self.proj.projectile_hist_dir(), exist_ok=True)
            backup = os.path.join(self.proj.projectile_hist_dir(),
                                  "projectile_%d.png" % int(time.time()))
            shutil.copyfile(final, backup)
        prompt = self.proj.projectile_prompt()
        raw = self.proj.projectile_raw_path()
        ref = self.proj.base_path if os.path.exists(self.proj.base_path) else None
        self.proj_gen_btn.config(state="disabled")
        self.proj_undo_btn.config(state="disabled")
        self.proj_msg.config(text="生成中…（约 30–80 秒），完成后自动去背裁剪")
        self.set_status("生成飞行道具贴图中…")

        def task():
            generate(prompt, raw, ref_path=ref)
            out, size = finalize_projectile(raw, final)
            return out, size

        def done(err, res):
            self.proj_gen_btn.config(state="normal")
            if err:
                self.proj_msg.config(text="生成失败：" + err)
                self.set_status("子弹贴图生成失败")
                self._refresh_projectile_preview()
                return
            self.proj.data["projectile"]["enabled"] = True
            self.proj.data["projectile"]["file"] = os.path.relpath(final, HERE)
            self.proj.save()
            self.proj_msg.config(text="定稿完成：%s（%d×%d），可继续重 roll 或前往第 5 步"
                                      % (os.path.relpath(final, HERE), res[1][0], res[1][1]))
            self.set_status("子弹贴图已定稿并写入 plant.json")
            self._refresh_projectile_preview()
        self.api.run(task, done)

    def undo_projectile(self):
        if not self.require_project():
            return
        hist_dir = self.proj.projectile_hist_dir()
        if not os.path.isdir(hist_dir):
            self.proj_msg.config(text="没有可回退的历史版本")
            return
        hist = sorted((os.path.join(hist_dir, x) for x in os.listdir(hist_dir)
                       if x.startswith("projectile_")), reverse=True)
        if not hist:
            self.proj_msg.config(text="没有可回退的历史版本")
            return
        shutil.copyfile(hist[0], self.proj.projectile_path())
        os.remove(hist[0])
        self.proj.data["projectile"]["file"] = os.path.relpath(self.proj.projectile_path(), HERE)
        self.proj.save()
        self.proj_msg.config(text="已回退到上一版")
        self._refresh_projectile_preview()

    # ============ 步骤 5：拼表预览 ============
    def _step_build(self, f):
        ttk.Label(f, text="⑤ 去背 → 全局统一缩放 → 拼成 4×4 精灵表，并可启动游戏预览",
                  font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="一键拼表", command=self.build_sheet).pack(side="left")
        ttk.Button(btns, text="启动 pygame 预览", command=self.launch_demo).pack(side="left", padx=8)
        self.build_msg = ttk.Label(btns, text="")
        self.build_msg.pack(side="left", padx=10)
        self.sheet_img = ttk.Label(f)
        self.sheet_img.pack(anchor="w")
        ttk.Label(f, text="拼表/运行日志").pack(anchor="w", pady=(8, 2))
        self.build_log = scrolledtext.ScrolledText(f, height=8, wrap="word", state="disabled",
                                                   background="#1e1e1e", foreground="#d4d4d4")
        self.build_log.pack(fill="both", expand=True)

    def _log(self, text):
        self.build_log.config(state="normal")
        self.build_log.insert("end", text + "\n")
        self.build_log.see("end")
        self.build_log.config(state="disabled")

    def _refresh_build_step(self):
        if self.proj and os.path.exists(self.proj.sheet_path):
            img = thumb(self.proj.sheet_path, (260, 260))
            self._img_refs.append(img)
            self.sheet_img.config(image=img)
            self.build_msg.config(text="已有成表，可重新拼表覆盖")
        else:
            self.sheet_img.config(image="")

    def build_sheet(self):
        if not self.require_project():
            return
        if not self.proj.all_frames_ready():
            messagebox.showwarning("帧不全", "还有动作帧未生成，请先到步骤 3 补齐（idle_0 需已定稿立绘）")
            return
        self.build_msg.config(text="拼表中…")
        self._log("开始拼表：" + self.proj.frames_dir)

        def task():
            build_dir(self.proj.frames_dir, self.proj.sheet_path)
            return self.proj.sheet_path

        def done(err, res):
            if err:
                self.build_msg.config(text="失败")
                self._log("失败：" + err)
            else:
                self.build_msg.config(text="拼表完成")
                self._log("完成：" + res)
                img = thumb(res, (260, 260))
                self._img_refs.append(img)
                self.sheet_img.config(image=img)
        self.api.run(task, done)

    def launch_demo(self):
        if not self.proj or not os.path.exists(self.proj.sheet_path):
            messagebox.showinfo("提示", "请先一键拼表")
            return
        subprocess.Popen([sys.executable, DEMO_PATH, "--sheet", self.proj.sheet_path], cwd=HERE)
        self.set_status("已启动 pygame 预览窗口")


if __name__ == "__main__":
    App().mainloop()
