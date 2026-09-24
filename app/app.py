# -*- coding: utf-8 -*-
"""应用控制器：串联配置 / OCR / 引擎 / 学习 / GUI。
全程无全局热键、无键盘钩子——后台自动轮询识别，避免触发游戏反作弊。"""

import threading
from tkinter import filedialog, messagebox

from .config_store import ConfigStore
from .engine import Engine
from .gui import MainWindow, ACCENT, OK
from .learning import Experience
from .ocr_engine import OcrEngine
from .paths import ensure_dirs


class AppController:
    def __init__(self):
        ensure_dirs()
        self.cfg_store = ConfigStore()
        self.ocr = OcrEngine()
        self.learning = Experience(enabled=self.cfg_store.effective.get(
            "ui", {}).get("learning", True))
        self.engine = Engine(self.cfg_store, self.ocr, self.learning)
        self.gui = None
        self._exit_requested = False
        self._perf_tick = 0

    # ── 启动 ────────────────────────────────────────────────
    def run(self):
        self.gui = MainWindow(self)
        self._install_exception_hooks()

        threading.Thread(target=self._init_ocr, daemon=True,
                         name="ocr-init").start()

        # 启动自动轮询引擎（每 0.8s，仅游戏前台时工作）
        self.engine.start_poller()

        self.gui.after(80, self._poll)
        self.gui.append_log("程序启动成功。")
        self.gui.append_log("已开启全自动识别，每 0.8 秒自动检测密码界面。")
        self.gui.mainloop()

    # ── OCR 初始化（后台线程）───────────────────────────────
    def _init_ocr(self):
        self.gui.set_badge("ocr", "初始化中...", ACCENT)
        ok = self.ocr.init()
        if ok:
            self.gui.set_badge("ocr", "就绪", OK)
        else:
            self.gui.set_badge("ocr", "失败", ACCENT)
            self.append_log(f"OCR 引擎初始化失败: {self.ocr.error}")

    # ── 轮询 ────────────────────────────────────────────────
    def _poll(self):
        try:
            while not self.engine.outbox.empty():
                msg = self.engine.outbox.get()
                kind = msg.get("kind")
                if kind == "log":
                    self.append_log(msg.get("text", ""))
                elif kind == "status":
                    self.gui.set_badge("state", msg.get("text", ""), ACCENT)
                elif kind == "result":
                    self.gui.show_result(msg["result"])
                    self.gui.set_badge("state", "识别完成", OK)
                elif kind == "state":
                    self._sync_state_badges()
                elif kind == "exit":
                    self._final_exit()
                    return

            self._perf_tick += 1
            if self._perf_tick % 12 == 0:
                self.gui.update_perf(self.engine.perf_snapshot())
        except Exception as e:  # noqa: BLE001
            self.append_log(f"轮询异常: {type(e).__name__}: {e}")
        self.gui.after(80, self._poll)

    def _sync_state_badges(self):
        self.gui.set_badge("auto",
                           "暂停中" if self.engine.paused else
                           ("开启" if self.engine.auto_enabled else "关闭"),
                           ACCENT if self.engine.paused else
                           (OK if self.engine.auto_enabled else ACCENT))
        self.gui.set_badge("state",
                           "识别中..." if self.engine.busy else "空闲", ACCENT)
        try:
            self.gui.btn_pause.config(
                text="恢复识别" if self.engine.paused else "暂停识别")
        except Exception:
            pass

    # ── 异常钩子 ────────────────────────────────────────────
    def _install_exception_hooks(self):
        def hook(exc_type, exc, tb):
            import traceback
            text = "".join(traceback.format_exception(exc_type, exc, tb))
            self.append_log(f"[异常] {text[:800]}")

        import sys
        sys.excepthook = hook
        threading.excepthook = lambda args: hook(
            args.exc_type, args.exc_value, args.exc_traceback)
        try:
            self.gui.report_callback_exception = hook
        except Exception:
            pass

    # ── UI 回调 ─────────────────────────────────────────────
    def append_log(self, text: str):
        if self.gui:
            self.gui.append_log(text)

    def on_auto_toggle(self, enabled: bool):
        self.cfg_store.raw["auto_detect"] = bool(enabled)
        self.cfg_store.save()
        self.engine.set_auto(bool(enabled))

    # ── GUI 按钮 ───────────────────────────────────────────
    def on_manual_click(self):
        self.engine.start_manual()

    def on_pause_click(self):
        self.engine.toggle_pause()
        self._sync_state_badges()

    # ── 配置导入 / 导出 / 重置 ──────────────────────────────
    def on_export(self):
        path = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".json",
            initialfile="delta_pwd_config.json",
            filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        if self.cfg_store.export(path):
            self.append_log(f"配置已导出: {path}")
        else:
            self.append_log("配置导出失败")

    def on_import(self):
        path = filedialog.askopenfilename(
            title="导入配置", filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        if self.cfg_store.import_(path):
            self.append_log("配置已导入: " + path)
            self._reload_ui_from_config()
        else:
            self.append_log("配置导入失败（文件格式不正确）")

    def on_reset(self):
        if not messagebox.askyesno("重置配置",
                                   "确定恢复全部默认配置吗？坐标将回到 2K 基准。"):
            return
        self.cfg_store.reset()
        self.append_log("配置已重置为默认")
        self._reload_ui_from_config()

    def _reload_ui_from_config(self):
        self.gui._load_controls()
        self.append_log("设置已同步")

    def on_clear_learn(self):
        if not messagebox.askyesno("清空学习缓存",
                                   "确定清空全部自主学习经验吗？"):
            return
        self.learning.clear()
        self.append_log("自主学习缓存已清空")

    # ── 关闭 / 退出 ─────────────────────────────────────────
    def on_close_request(self):
        self._final_exit()

    def _final_exit(self):
        if self._exit_requested:
            return
        self._exit_requested = True
        try:
            self.ocr.destroy()
        except Exception:
            pass
        try:
            self.learning.save(force=True)
        except Exception:
            pass
        try:
            self.engine.shutdown()
        except Exception:
            pass
        try:
            self.gui.destroy_all()
        except Exception:
            pass
        import os
        os._exit(0)
