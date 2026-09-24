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
        self.minsize(500, 820)
        self.geometry("580x1020")

        self._build_style()
        self._build_layout()
        self._build_float_hint()
        self._build_correct_popup()
        self._load_controls()

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
        frame.pack(fill="x", padx=4, pady=2)
        head = tk.Label(frame, text=title, bg=CARD, fg=ACCENT,
                        font=_font(10, True), anchor="w")
        head.pack(fill="x", padx=10, pady=(5, 1))
        tk.Frame(frame, bg=LINE, height=1).pack(fill="x", padx=6)
        body = tk.Frame(frame, bg=CARD)
        body.pack(fill="x", padx=10, pady=4)
        return body

    def _build_layout(self):
        # 顶部标题区
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        ttl = tk.Label(head, text="三角洲密码工具", bg=BG, fg=TEXT,
                       font=_font(16, True))
        ttl.pack(side="left")
        sub = tk.Label(head, text="By：Quinlan  Qq：704979478", bg=BG,
                       fg=ACCENT, font=_font(9))
        sub.pack(side="left", padx=(8, 0), pady=(5, 0))

        self.badge_frame = tk.Frame(self, bg=BG)
        self.badge_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.badges = {}
        for key, label in (("ocr", "OCR"), ("auto", "自动识别"),
                           ("state", "识别状态")):
            b = tk.Label(self.badge_frame, text=f"{label}：--", bg=CARD2,
                         fg=DIM, font=_font(9), padx=8, pady=3)
            b.pack(side="left", padx=3)
            self.badges[key] = b

        # 竖向单列：控制 / 参数 / 配置 / 性能 依次排列
        col = tk.Frame(self, bg=BG)
        col.pack(fill="both", expand=True, padx=8, pady=2)
        col.grid_columnconfigure(0, weight=1)

        self._build_control_card(col)
        self._build_param_card(col)
        self._build_config_card(col)
        self._build_perf_card(col)

        # 事件日志置于底部并占据剩余高度
        self._build_log_card(col)

        # 底部提示
        foot = tk.Label(self, text="全自动识别：游戏前台时每 0.8 秒自动检测密码界面",
                        bg=BG, fg=DIM, font=_font(8))
        foot.pack(fill="x", padx=14, pady=(2, 6))

    # ── 人名纠正弹窗（浮动小窗，不占主界面位置）──────────────
    def _build_correct_popup(self):
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=CARD2, highlightbackground=AMBER,
                      highlightthickness=1)
        win.withdraw()
        self.correct_win = win
        tk.Label(win, text="OCR 人名未确认：", bg=CARD2, fg=AMBER,
                 font=_font(9)).pack(anchor="w", padx=10, pady=(8, 0))
        self.correct_raw = tk.StringVar()
        tk.Label(win, textvariable=self.correct_raw, bg=CARD2, fg=TEXT,
                 font=_font(9), anchor="w", wraplength=240).pack(
            fill="x", padx=10)
        row = tk.Frame(win, bg=CARD2)
        row.pack(fill="x", padx=10, pady=8)
        self.correct_choice = tk.StringVar()
        self.correct_combo = ttk.Combobox(
            row, textvariable=self.correct_choice, values=known_persons(),
            state="readonly", width=10)
        self.correct_combo.pack(side="left")
        tk.Button(row, text="记住并重试", command=self._confirm_correct,
                  bg=CARD, fg=AMBER, relief="flat", font=_font(9),
                  activebackground=CARD).pack(side="left", padx=6)
        tk.Button(row, text="关闭", command=self._hide_correct,
                  bg=CARD, fg=DIM, relief="flat", font=_font(9),
                  activebackground=CARD).pack(side="left")

    def _show_correct(self, raw: str):
        self.correct_raw.set(raw or "")
        self.correct_choice.set("")
        try:
            x = self.winfo_x() + self.winfo_width() - 280
            y = self.winfo_y() + 120
            self.correct_win.geometry(f"280x110+{x}+{y}")
            self.correct_win.deiconify()
            self.correct_win.lift()
        except Exception:
            pass

    def _hide_correct(self):
        try:
            self.correct_win.withdraw()
        except Exception:
            pass

    def _build_log_card(self, parent):
        frame = tk.Frame(parent, bg=CARD, highlightbackground=LINE,
                         highlightthickness=1)
        frame.pack(fill="both", expand=True, pady=(4, 0))
        head = tk.Label(frame, text="事件日志", bg=CARD, fg=ACCENT,
                        font=_font(10, True), anchor="w")
        head.pack(fill="x", padx=10, pady=(5, 1))
        tk.Frame(frame, bg=LINE, height=1).pack(fill="x", padx=6)
        wrap = tk.Frame(frame, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=8, pady=(2, 6))
        self.log_text = tk.Text(wrap, bg="#121A24", fg=TEXT, font=_font(9),
                                relief="flat", wrap="word", padx=6, pady=4,
                                state="disabled", height=5)
        sb = tk.Scrollbar(wrap, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── 卡片 ──────────────────────────────────────────────
    def _build_control_card(self, parent):
        body = self._vcard(parent, "识别控制")

        self.var_auto = tk.BooleanVar(value=True)
        self.var_center = tk.BooleanVar(value=True)
        self.var_lock = tk.BooleanVar(value=False)
        self.var_float = tk.BooleanVar(value=True)

        def cb(flag):
            if flag == "auto":
                self.app.on_auto_toggle(self.var_auto.get())
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
            ("全自动识别", self.var_auto, "auto"),
            ("中心区域识别（降低性能消耗）", self.var_center, "center"),
            ("识别区域记忆锁定", self.var_lock, "lock"),
            ("识别结果悬浮提示", self.var_float, "float"),
        ):
            tk.Checkbutton(body, text=text, variable=var, bg=CARD, fg=TEXT,
                           selectcolor=CARD2, activebackground=CARD,
                           activeforeground=TEXT, font=_font(9),
                           command=lambda f=flag: cb(f)).pack(anchor="w", pady=1)

        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(5, 0))
        self.btn_manual = tk.Button(row, text="立即扫描",
                                    command=self.app.on_manual_click,
                                    bg=ACCENT, fg="#0B1220", relief="flat",
                                    font=_font(10, True), padx=12, pady=4,
                                    activebackground=ACCENT_D,
                                    activeforeground="#FFFFFF")
        self.btn_manual.pack(side="left", padx=(0, 8))
        self.btn_pause = tk.Button(row, text="暂停识别",
                                   command=self.app.on_pause_click,
                                   bg=CARD2, fg=TEXT, relief="flat",
                                   font=_font(10), padx=12, pady=4,
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
            wrap.pack(fill="x", pady=1)
            tk.Label(wrap, text=label, bg=CARD, fg=DIM,
                     font=_font(9)).pack(side="left")
            sc = tk.Scale(wrap, from_=rng[0], to=rng[1], resolution=rng[2],
                          orient="horizontal", variable=var, command=cmd,
                          bg=CARD, fg=TEXT, troughcolor=CARD2,
                          highlightthickness=0, length=150, font=_font(8))
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
                       activebackground=CARD, font=_font(9)).pack(anchor="w", pady=1)

        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(4, 0))
        self.cfg_buttons = {}
        for text, cmd in (
            ("导出配置", self.app.on_export), ("导入配置", self.app.on_import),
            ("重置默认", self.app.on_reset), ("清空学习", self.app.on_clear_learn),
        ):
            btn = tk.Button(row, text=text, command=cmd, bg=CARD2, fg=TEXT,
                            relief="flat", font=_font(9), padx=8, pady=2,
                            activebackground=CARD)
            btn.pack(side="left", padx=(0, 6))
            self.cfg_buttons[text] = btn

    def _build_perf_card(self, parent):
        body = self._vcard(parent, "性能监控")
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
                                         padx=(0, 6), pady=1)
            v = tk.Label(grid, text="--", bg=CARD, fg=TEXT,
                         font=_font(9), anchor="w")
            v.grid(row=r, column=c * 2 + 1, sticky="w", pady=1)
            self.perf_labels[key] = v

    # ── 悬浮提示 ────────────────────────────────────────────
    def _build_float_hint(self):
        self.float_hint = FloatHint(self)

    # ── 控件初始化 ──────────────────────────────────────────
    def _load_controls(self):
        cfg = self.app.cfg_store.effective
        self.var_auto.set(bool(cfg.get("auto_detect", True)))
        self.var_center.set(bool(cfg.get("center_scan", True)))
        ui = cfg.get("ui", {})
        self.var_lock.set(bool(ui.get("region_lock", False)))
        self.var_float.set(bool(ui.get("float_hint", True)))
        self.var_learn.set(bool(ui.get("learning", True)))
        self.var_threshold.set(float(cfg.get("fingerprint", {}).get(
            "match_threshold", 0.5)))
        self.var_interval.set(float(cfg.get("sample_interval", 0.8)))
        self.var_timeout.set(float(cfg.get("detect_timeout", 3.0)))
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
    _BADGE_TEXT = {"ocr": "OCR", "auto": "自动识别", "state": "识别状态"}

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
        rtype = result.get("type", "")
        if rtype == "morse":
            pwd = result.get("password", "")
            confs = result.get("conf", [])
            if pwd:
                self.float_hint.show(f"摩斯密码  {pwd}", ACCENT)
                self.append_log(f"摩斯识别完成：{pwd}  置信度 "
                                + "/".join(f"{c:.2f}" for c in confs)
                                + ("（已自动输入）" if result.get("clicked") else "（待手动输入）"))
            else:
                self.append_log("摩斯识别失败")
            self._hide_correct()
        elif rtype == "fingerprint":
            person = result.get("person", "") or "?"
            mode = result.get("mode", "")
            st = result.get("status", "?")
            if st == "ok":
                self.float_hint.show(f"{person} {mode}模式  识别成功", OK)
                self.append_log(f"指纹识别成功：{person} {mode}模式")
            elif st == "name_unknown" and result.get("person_raw"):
                self.float_hint.show(f"人名未确认：{result.get('person_raw')}", AMBER)
                self._show_correct(result.get("person_raw", ""))
            elif st in ("no_fingerprint_ui",):
                pass
            else:
                self.float_hint.show(f"指纹：{person} {mode} {st}", AMBER)
                self.append_log(f"指纹识别：{person} {mode} {st}")

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
        self._hide_correct()
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
