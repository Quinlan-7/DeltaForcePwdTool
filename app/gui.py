# -*- coding: utf-8 -*-
"""
可视化 UI 主窗口（tkinter 深色主题）。
标题：三角洲密码工具 By：Quinlan Qq：704979478
包含：识别状态、结果展示、事件日志、识别控制、参数调节、热键自定义、
配置导入导出、性能监控、结果悬浮提示。
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .hotkeys import preview_key
from .paths import ICON_PATH, known_persons

# ── 主题色板 ────────────────────────────────────────────────
BG = "#0F141A"
CARD = "#1A222E"
CARD2 = "#232E3D"
LINE = "#2C3A4C"
TEXT = "#E8EEF4"
DIM = "#8FA3B8"
ACCENT = "#2DD4BF"
ACCENT_D = "#0E9488"
AMBER = "#F59E0B"
DANGER = "#F87171"
OK = "#34D399"

FONT = "Microsoft YaHei UI"

APP_TITLE = "三角洲密码工具 By：Quinlan Qq：704979478"


def _font(size: int, bold: bool = False):
    return (FONT, size, "bold" if bold else "normal")


class FloatHint:
    """识别结果悬浮小字提示（置顶、可拖动）。"""

    def __init__(self, master):
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#101820")
        self.label = tk.Label(
            self.win, text="", fg=TEXT, bg="#101820",
            font=_font(11), padx=14, pady=8, justify="left")
        self.label.pack()
        self._offset = (0, 0)
        self.label.bind("<ButtonPress-1>", self._press)
        self.label.bind("<B1-Motion>", self._drag)
        self.hidden = False
        self._place_default()
        self.win.after(10, self._fade_in)

    def _place_default(self):
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{sw - 420}+{int(sh * 0.42)}")

    def _press(self, e):
        self._offset = (e.x, e.y)

    def _drag(self, e):
        x = self.win.winfo_pointerx() - self._offset[0]
        y = self.win.winfo_pointery() - self._offset[1]
        self.win.geometry(f"+{x}+{y}")

    def _fade_in(self):
        try:
            self.win.attributes("-alpha", 0.96)
        except Exception:
            pass

    def show(self, text: str, color: str = ACCENT) -> None:
        if self.hidden:
            return
        self.label.config(text=text, fg=color)
        self.win.deiconify()
        self.win.lift()

    def hide(self) -> None:
        self.hidden = True
        self.win.withdraw()

    def unhide(self) -> None:
        self.hidden = False
        self.win.deiconify()

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class MainWindow(tk.Tk):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title(APP_TITLE)
        self.configure(bg=BG)
        try:
            if os.path.isfile(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception:
            pass
        self.minsize(980, 660)
        self.geometry("1040x700")

        self._build_style()
        self._build_layout()
        self._load_controls()
        self._build_float_hint()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── 样式 ────────────────────────────────────────────────
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=_font(9))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=_font(9))
        style.configure("Dim.TLabel", background=CARD, foreground=DIM, font=_font(9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT,
                        font=_font(16, True))
        style.configure("Sub.TLabel", background=BG, foreground=ACCENT,
                        font=_font(10))
        style.configure("Header.TLabel", background=CARD, foreground=ACCENT,
                        font=_font(11, True))
        style.configure("Big.TLabel", background=CARD, foreground=TEXT,
                        font=_font(24, True))
        style.configure("TScale", background=CARD)

    # ── 布局 ────────────────────────────────────────────────
    def _card(self, parent, title: str, row: int, col: int, padx=8, pady=6):
        frame = tk.Frame(parent, bg=CARD, highlightbackground=LINE,
                         highlightthickness=1)
        frame.grid(row=row, column=col, sticky="nsew", padx=padx, pady=pady)
        head = tk.Label(frame, text=title, bg=CARD, fg=ACCENT,
                        font=_font(11, True), anchor="w")
        head.pack(fill="x", padx=10, pady=(8, 2))
        tk.Frame(frame, bg=LINE, height=1).pack(fill="x", padx=6)
        body = tk.Frame(frame, bg=CARD)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        return body

    def _vcard(self, parent, title: str):
        frame = tk.Frame(parent, bg=CARD, highlightbackground=LINE,
                         highlightthickness=1)
        frame.pack(fill="x", padx=4, pady=4)
        head = tk.Label(frame, text=title, bg=CARD, fg=ACCENT,
                        font=_font(11, True), anchor="w")
        head.pack(fill="x", padx=10, pady=(8, 2))
        tk.Frame(frame, bg=LINE, height=1).pack(fill="x", padx=6)
        body = tk.Frame(frame, bg=CARD)
        body.pack(fill="both", expand=True, padx=10, pady=8)
        return body

    def _build_layout(self):
        # 顶部标题区
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        ttl = tk.Label(head, text="三角洲密码工具", bg=BG, fg=TEXT,
                       font=_font(17, True))
        ttl.pack(side="left")
        sub = tk.Label(head, text="By：Quinlan   Qq：704979478", bg=BG,
                       fg=ACCENT, font=_font(10))
        sub.pack(side="left", padx=(10, 0), pady=(6, 0))

        self.badge_frame = tk.Frame(head, bg=BG)
        self.badge_frame.pack(side="right")
        self.badges = {}
        for key, label in (("ocr", "OCR"), ("auto", "自动识别"),
                           ("state", "识别状态"), ("hk", "热键")):
            b = tk.Label(self.badge_frame, text=f"{label}：--", bg=CARD2,
                         fg=DIM, font=_font(9), padx=10, pady=4)
            b.pack(side="left", padx=3)
            self.badges[key] = b

        # 主体两栏
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)

        # 左栏
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self._build_result_card(left)
        self._build_log_card(left)

        # 右栏（可滚动，适配小屏）
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(right, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._right_canvas = canvas

        def _on_wheel(e):
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        def _bind_wheel(w):
            w.bind("<MouseWheel>", _on_wheel)
            for c in w.winfo_children():
                _bind_wheel(c)

        _bind_wheel(inner)

        self._build_control_card(inner)
        self._build_param_card(inner)
        self._build_hotkey_card(inner)
        self._build_config_card(inner)
        self._build_perf_card(inner)

        # 底部提示
        foot = tk.Label(self, text="游戏内按 F 交互自动检测 ｜ ~ 手动扫描 ｜ F7 暂停/恢复自动识别 ｜ F8 完全退出",
                        bg=BG, fg=DIM, font=_font(9))
        foot.pack(fill="x", padx=14, pady=(2, 8))

    # ── 左栏卡片 ────────────────────────────────────────────
    def _build_result_card(self, parent):
        body = self._card(parent, "识别结果", 0, 0)

        self.result_type = tk.Label(body, text="等待识别...", bg=CARD,
                                    fg=DIM, font=_font(12, True))
        self.result_type.pack(anchor="w")

        self.result_big = tk.Label(body, text="--", bg=CARD, fg=TEXT,
                                   font=_font(26, True), anchor="w")
        self.result_big.pack(anchor="w", pady=(2, 4))

        info = tk.Frame(body, bg=CARD)
        info.pack(fill="x")
        info.grid_columnconfigure(1, weight=1)
        self.result_info = {}
        fields = [("人名", "person"), ("模式", "mode"), ("置信度", "conf"),
                  ("状态", "status"), ("耗时", "elapsed"), ("时间", "time")]
        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 2)
            tk.Label(info, text=label, bg=CARD, fg=DIM,
                     font=_font(9)).grid(row=row, column=col * 2, sticky="w", padx=(0, 6), pady=1)
            v = tk.Label(info, text="--", bg=CARD, fg=TEXT, font=_font(9), anchor="w")
            v.grid(row=row, column=col * 2 + 1, sticky="w", pady=1)
            self.result_info[key] = v

        # 人名纠正面板（仅在指纹人名未确认时出现）
        self.correct_frame = tk.Frame(body, bg=CARD2, highlightbackground=AMBER,
                                      highlightthickness=1)
        self.correct_raw = tk.StringVar()
        self.correct_choice = tk.StringVar()
        tk.Label(self.correct_frame, text="OCR人名未确认：", bg=CARD2,
                 fg=AMBER, font=_font(9)).pack(anchor="w", padx=8, pady=(6, 0))
        tk.Label(self.correct_frame, textvariable=self.correct_raw, bg=CARD2,
                 fg=TEXT, font=_font(9), anchor="w").pack(fill="x", padx=8)
        row = tk.Frame(self.correct_frame, bg=CARD2)
        row.pack(fill="x", padx=8, pady=6)
        self.correct_combo = ttk.Combobox(row, textvariable=self.correct_choice,
                                          values=known_persons(), state="readonly",
                                          width=12)
        self.correct_combo.pack(side="left")
        tk.Button(row, text="记住纠正并重试", command=self._confirm_correct,
                  bg=CARD2, fg=AMBER, relief="flat", font=_font(9),
                  activebackground=CARD, activeforeground=AMBER).pack(side="left", padx=6)
        tk.Button(row, text="关闭", command=lambda: self.correct_frame.pack_forget(),
                  bg=CARD2, fg=DIM, relief="flat", font=_font(9),
                  activebackground=CARD).pack(side="left")

    def _build_log_card(self, parent):
        body = self._card(parent, "事件日志（仅内存显示，不写入任何文件）", 1, 0)
        wrap = tk.Frame(body, bg=CARD)
        wrap.pack(fill="both", expand=True)
        self.log_text = tk.Text(wrap, bg="#121A24", fg=TEXT, font=_font(9),
                                relief="flat", wrap="word", padx=6, pady=4,
                                state="disabled", height=10)
        sb = tk.Scrollbar(wrap, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── 右栏卡片 ────────────────────────────────────────────
    def _build_control_card(self, parent):
        body = self._vcard(parent, "识别控制")

        self.var_auto = tk.BooleanVar(value=True)
        self.var_hotkey = tk.BooleanVar(value=True)
        self.var_center = tk.BooleanVar(value=True)
        self.var_lock = tk.BooleanVar(value=False)
        self.var_float = tk.BooleanVar(value=True)

        def cb(flag):
            if flag == "auto":
                self.app.on_auto_toggle(self.var_auto.get())
            elif flag == "hotkey":
                self.app.on_hotkey_toggle(self.var_hotkey.get())
            elif flag == "center":
                self.app.cfg_store.raw["center_scan"] = self.var_center.get()
                self.app.cfg_store.save()
                self.app.append_log("中心区域识别已"
                                    + ("开启" if self.var_center.get() else "关闭"))
            elif flag == "lock":
                self.app.cfg_store.raw.setdefault("ui", {})["region_lock"] = \
                    self.var_lock.get()
                self.app.cfg_store.save()
                self._apply_lock()
                self.app.append_log("识别区域已锁定" if self.var_lock.get()
                                    else "识别区域已解锁")
            elif flag == "float":
                self.app.cfg_store.raw.setdefault("ui", {})["float_hint"] = \
                    self.var_float.get()
                self.app.cfg_store.save()
                if self.var_float.get():
                    self.float_hint.unhide()
                else:
                    self.float_hint.hide()

        for text, var, flag in (
            ("自动识别（游戏内按 F 交互后检测）", self.var_auto, "auto"),
            ("全局热键总开关", self.var_hotkey, "hotkey"),
            ("中心区域识别（降低性能消耗）", self.var_center, "center"),
            ("识别区域记忆锁定", self.var_lock, "lock"),
            ("识别结果悬浮提示", self.var_float, "float"),
        ):
            tk.Checkbutton(body, text=text, variable=var, bg=CARD, fg=TEXT,
                           selectcolor=CARD2, activebackground=CARD,
                           activeforeground=TEXT, font=_font(9),
                           command=lambda f=flag: cb(f)).pack(anchor="w", pady=2)

        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(8, 0))
        self.btn_manual = tk.Button(row, text="手动扫描 (~)",
                                    command=self.app.on_manual_click,
                                    bg=ACCENT, fg="#0B1220", relief="flat",
                                    font=_font(10, True), padx=14, pady=6,
                                    activebackground=ACCENT_D,
                                    activeforeground="#FFFFFF")
        self.btn_manual.pack(side="left", padx=(0, 8))
        self.btn_pause = tk.Button(row, text="暂停自动识别",
                                   command=self.app.on_pause_click,
                                   bg=CARD2, fg=TEXT, relief="flat",
                                   font=_font(10), padx=14, pady=6,
                                   activebackground=CARD)
        self.btn_pause.pack(side="left")

    def _build_param_card(self, parent):
        body = self._vcard(parent, "识别参数")

        self.var_threshold = tk.DoubleVar(value=0.5)
        self.var_interval = tk.DoubleVar(value=0.5)
        self.var_timeout = tk.DoubleVar(value=3.0)

        def on_threshold(v):
            self.app.cfg_store.raw.setdefault("fingerprint", {})[
                "match_threshold"] = float(v)
            self.app.cfg_store.save()
            self.threshold_val.config(text=f"{float(v):.2f}")

        def on_interval(v):
            self.app.cfg_store.raw["sample_interval"] = round(float(v), 2)
            self.app.cfg_store.save()
            self.interval_val.config(text=f"{float(v):.2f}s")

        def on_timeout(v):
            self.app.cfg_store.raw["detect_timeout"] = round(float(v), 2)
            self.app.cfg_store.save()
            self.timeout_val.config(text=f"{float(v):.1f}s")

        for label, var, rng, cmd in (
            ("指纹匹配置信度", self.var_threshold, (0.3, 0.9, 0.05), on_threshold),
            ("动态画面采样间隔", self.var_interval, (0.2, 1.0, 0.1), on_interval),
            ("密码界面检测超时", self.var_timeout, (2.0, 5.0, 0.5), on_timeout),
        ):
            wrap = tk.Frame(body, bg=CARD)
            wrap.pack(fill="x", pady=2)
            tk.Label(wrap, text=label, bg=CARD, fg=DIM,
                     font=_font(9)).pack(side="left")
            sc = tk.Scale(wrap, from_=rng[0], to=rng[1], resolution=rng[2],
                          orient="horizontal", variable=var, command=cmd,
                          bg=CARD, fg=TEXT, troughcolor=CARD2,
                          highlightthickness=0, length=180, font=_font(8))
            sc.pack(side="left", padx=6)
            txt = tk.Label(wrap, text="--", bg=CARD, fg=ACCENT, font=_font(9, True))
            txt.pack(side="left")
            if label.startswith("指纹"):
                self.threshold_val = txt
            elif label.startswith("动态"):
                self.interval_val = txt
            else:
                self.timeout_val = txt
        self.threshold_val.config(text="0.50")
        self.interval_val.config(text="0.50s")
        self.timeout_val.config(text="3.0s")

    def _build_hotkey_card(self, parent):
        body = self._vcard(parent, "热键自定义（点击“应用”后全局生效）")
        self.hk_vars = {}
        grid = tk.Frame(body, bg=CARD)
        grid.pack(fill="x")
        labels = (("手动扫描", "manual"), ("暂停/恢复", "pause"),
                  ("完全退出", "exit"), ("游戏交互键", "interact"))
        for i, (label, key) in enumerate(labels):
            r, c = divmod(i, 2)
            tk.Label(grid, text=label, bg=CARD, fg=DIM,
                     font=_font(9)).grid(row=r, column=c * 2, sticky="w",
                                         padx=(0, 6), pady=3)
            var = tk.StringVar()
            e = tk.Entry(grid, textvariable=var, bg=CARD2, fg=TEXT,
                         insertbackground=TEXT, relief="flat", width=8,
                         justify="center", font=_font(9))
            e.grid(row=r, column=c * 2 + 1, sticky="w", pady=3, ipady=2)
            self.hk_vars[key] = var
        tk.Button(body, text="应用热键", command=self.app.apply_hotkeys,
                  bg=CARD2, fg=ACCENT, relief="flat", font=_font(9),
                  activebackground=CARD).pack(anchor="w", pady=(6, 0))

    def _build_config_card(self, parent):
        body = self._vcard(parent, "配置与学习")
        self.var_learn = tk.BooleanVar(value=True)

        def on_learn():
            self.app.cfg_store.raw.setdefault("ui", {})["learning"] = \
                self.var_learn.get()
            self.app.cfg_store.save()
            self.app.learning.enabled = self.var_learn.get()

        tk.Checkbutton(body, text="自主学习（积累识别经验，越用越快）",
                       variable=self.var_learn, command=on_learn,
                       bg=CARD, fg=TEXT, selectcolor=CARD2,
                       activebackground=CARD, font=_font(9)).pack(anchor="w", pady=2)

        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(6, 0))
        self.cfg_buttons = {}
        for text, cmd in (
            ("导出配置", self.app.on_export), ("导入配置", self.app.on_import),
            ("重置默认", self.app.on_reset), ("清空学习", self.app.on_clear_learn),
        ):
            btn = tk.Button(row, text=text, command=cmd, bg=CARD2, fg=TEXT,
                            relief="flat", font=_font(9), padx=8, pady=4,
                            activebackground=CARD)
            btn.pack(side="left", padx=(0, 6))
            self.cfg_buttons[text] = btn

    def _build_perf_card(self, parent):
        body = self._vcard(parent, "性能监控（内存运行数据）")
        grid = tk.Frame(body, bg=CARD)
        grid.pack(fill="x")
        self.perf_labels = {}
        for i, (label, key) in enumerate(
                (("OCR 平均耗时", "ocr"), ("画面检测耗时", "detect"),
                 ("内存占用", "mem"), ("运行时长", "uptime"),
                 ("累计扫描次数", "scans"))):
            r, c = divmod(i, 2)
            tk.Label(grid, text=label, bg=CARD, fg=DIM,
                     font=_font(9)).grid(row=r, column=c * 2, sticky="w",
                                         padx=(0, 6), pady=2)
            v = tk.Label(grid, text="--", bg=CARD, fg=TEXT,
                         font=_font(9), anchor="w")
            v.grid(row=r, column=c * 2 + 1, sticky="w", pady=2)
            self.perf_labels[key] = v

    # ── 悬浮提示 ────────────────────────────────────────────
    def _build_float_hint(self):
        self.float_hint = FloatHint(self)

    # ── 控件初始化 ──────────────────────────────────────────
    def _load_controls(self):
        cfg = self.app.cfg_store.effective
        self.var_auto.set(bool(cfg.get("auto_detect", True)))
        self.var_hotkey.set(True)
        self.var_center.set(bool(cfg.get("center_scan", True)))
        ui = cfg.get("ui", {})
        self.var_lock.set(bool(ui.get("region_lock", False)))
        self.var_float.set(bool(ui.get("float_hint", True)))
        self.var_learn.set(bool(ui.get("learning", True)))
        self.var_threshold.set(float(cfg.get("fingerprint", {}).get(
            "match_threshold", 0.5)))
        self.var_interval.set(float(cfg.get("sample_interval", 0.5)))
        self.var_timeout.set(float(cfg.get("detect_timeout", 3.0)))
        hk = cfg.get("hotkeys", {})
        for key, var in self.hk_vars.items():
            var.set(hk.get(key, ""))
        self.threshold_val.config(text=f"{self.var_threshold.get():.2f}")
        self.interval_val.config(text=f"{self.var_interval.get():.2f}s")
        self.timeout_val.config(text=f"{self.var_timeout.get():.1f}s")
        self._apply_lock()
        if not self.var_float.get():
            self.float_hint.hide()

    def _apply_lock(self):
        locked = self.var_lock.get()
        state = "disabled" if locked else "normal"
        for btn in getattr(self, "cfg_buttons", {}).values():
            btn.configure(state=state)
        try:
            for w in (self.btn_manual, self.btn_pause):
                w.configure(state="normal")
        except Exception:
            pass

    # ── 状态更新（由主线程轮询调用）─────────────────────────
    _BADGE_TEXT = {"ocr": "OCR", "auto": "自动识别", "state": "识别状态",
                   "hk": "热键"}

    def set_badge(self, key: str, text: str, color: str = DIM):
        b = self.badges.get(key)
        if b:
            b.config(text=f"{self._BADGE_TEXT.get(key, key)}：{text}", fg=color)

    def append_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 400:
            self.log_text.delete("1.0", f"{lines - 300}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def show_result(self, result: dict):
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        rtype = result.get("type", "")
        if rtype == "morse":
            pwd = result.get("password", "")
            confs = result.get("conf", [])
            self.result_type.config(text="摩斯密码识别", fg=ACCENT)
            self.result_big.config(text=pwd if pwd else "识别失败", fg=TEXT)
            self.result_info["person"].config(text="-")
            self.result_info["mode"].config(text="-")
            self.result_info["conf"].config(
                text=" / ".join(f"{c:.2f}" for c in confs))
            self.result_info["status"].config(
                text="已输入" if result.get("clicked") else "待手动输入",
                fg=OK if result.get("clicked") else AMBER)
            self.result_info["elapsed"].config(text=f"{result.get('elapsed', 0)}s")
            self.result_info["time"].config(text=now)
            self.float_hint.show(f"摩斯密码  {pwd}", ACCENT)
            self.correct_frame.pack_forget()
        elif rtype == "fingerprint":
            person = result.get("person", "") or "?"
            mode = result.get("mode", "")
            status_map = {
                "name_unknown": ("人名未确认", AMBER),
                "number_unread": ("数字未读取", DANGER),
                "no_fingerprint_ui": ("非指纹界面", DANGER),
                "no_templates": ("缺少模板", DANGER),
                "no_match": ("未匹配", DANGER),
                "unstable": ("画面不稳定", AMBER),
                "ok": ("识别成功", OK),
                "partial": ("部分匹配", AMBER),
                "fail": ("失败", DANGER),
            }
            st, st_color = status_map.get(result.get("status", ""),
                                          (result.get("status", "?"), DIM))
            plan = result.get("click_plan", [])
            self.result_type.config(text="指纹密码识别", fg=ACCENT)
            self.result_big.config(
                text=f"{person}  {mode}模式" if person and person != "?"
                else "指纹识别", fg=TEXT)
            self.result_info["person"].config(text=person)
            self.result_info["mode"].config(text=mode)
            self.result_info["conf"].config(
                text=f"{result.get('person_ratio', 0):.2f}")
            self.result_info["status"].config(text=st, fg=st_color)
            self.result_info["elapsed"].config(text=f"{result.get('elapsed', 0)}s")
            self.result_info["time"].config(text=now)
            self.float_hint.show(
                f"{person} {mode}模式  {st}\n"
                + ("  ".join(f"#{p['template']}→候选{p['candidate']}"
                             for p in plan[:4])),
                st_color)
            self._maybe_show_correct(result)
        else:
            self.result_type.config(text="等待识别...", fg=DIM)
            self.result_big.config(text="--", fg=TEXT)

    def _maybe_show_correct(self, result: dict):
        if result.get("status") == "name_unknown" and result.get("person_raw"):
            self.correct_raw.set(result.get("person_raw", ""))
            self.correct_choice.set("")
            self.correct_frame.pack(fill="x", pady=(8, 0))
        else:
            self.correct_frame.pack_forget()

    def _confirm_correct(self):
        raw = self.correct_raw.get().strip()
        person = self.correct_choice.get()
        if not raw or not person:
            return
        self.app.learning.remember_name(raw, person)
        try:
            from . import fingerprint
            fingerprint._STATIC_CORRECTION[raw] = person
        except Exception:
            pass
        self.append_log(f"已记住纠错：{raw} -> {person}")
        self.correct_frame.pack_forget()
        self.app.on_manual_click()

    # ── 性能 ────────────────────────────────────────────────
    def update_perf(self, perf: dict):
        self.perf_labels["ocr"].config(text=f"{perf.get('ocr_ms', 0):.0f} ms")
        self.perf_labels["detect"].config(text=f"{perf.get('detect_ms', 0):.0f} ms")
        self.perf_labels["mem"].config(text=f"{perf.get('mem_mb', 0):.1f} MB")
        u = perf.get("uptime", 0)
        self.perf_labels["uptime"].config(
            text=f"{u // 3600}h {(u % 3600) // 60}m {u % 60}s")
        self.perf_labels["scans"].config(text=str(perf.get("scans", 0)))

    def _on_close(self):
        self.app.on_close_request()

    def destroy_all(self):
        try:
            self.float_hint.destroy()
        except Exception:
            pass
        self.destroy()
