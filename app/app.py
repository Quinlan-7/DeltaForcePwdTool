# -*- coding: utf-8 -*-
"""应用控制器：串联配置 / OCR / 热键 / 引擎 / 学习 / 托盘 / GUI。"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from .config_store import ConfigStore
from .engine import Engine
from .gui import MainWindow, ACCENT, AMBER, DANGER, DIM, OK
from .hotkeys import HotkeyManager
from .learning import Experience
from .ocr_engine import OcrEngine
from .paths import ensure_dirs
from .tray import TrayIcon


class AppController:
    def __init__(self):
        ensure_dirs()
        self.cfg_store = ConfigStore()
        self.ocr = OcrEngine()
        self.learning = Experience(enabled=self.cfg_store.effective.get(
            "ui", {}).get("learning", True))
        self.hotkeys = HotkeyManager()
        self.engine = Engine(self.cfg_store, self.ocr, self.learning,
                             self.hotkeys)
        self.tray = TrayIcon()
        self.gui = None
        self._exit_requested = False
        self._perf_tick = 0

    # ── 启动 ────────────────────────────────────────────────
    def run(self):
        self.gui = MainWindow(self)
        # 全局异常捕获（防止程序闪退，只显示不写盘）
        self._install_exception_hooks()

        # 后台初始化 OCR
        threading.Thread(target=self._init_ocr, daemon=True,
                         name="ocr-init").start()

        # 注册热键
        self._apply_hotkeys_internal(silent=True)

        # 启动轮询
        self.gui.after(80, self._poll)
        self.gui.append_log("程序启动成功。游戏内按 F 交互后自动检测密码界面；"
                            "按 ~ 手动扫描；F7 暂停/恢复；F8 完全退出。")
        self.gui.mainloop()

    # ── OCR 初始化（后台线程）───────────────────────────────
    def _init_ocr(self):
        self.gui.set_badge("ocr", "初始化中...", AMBER)
        ok = self.ocr.init()
        if ok:
            mode = "本地模型" if self.ocr.using_local_models else "内置模型"
            self.gui.set_badge("ocr", f"就绪（{mode}）", OK)
            self.append_log(f"OCR 引擎初始化成功（{mode}，离线可用，无微信依赖）")
        else:
            self.gui.set_badge("ocr", "失败", DANGER)
            self.append_log(f"OCR 引擎初始化失败: {self.ocr.error}")

    # ── 轮询 ────────────────────────────────────────────────
    def _poll(self):
        try:
            for name in self.hotkeys.drain():
                self.engine.handle(name)

            while not self.engine.outbox.empty():
                msg = self.engine.outbox.get()
                kind = msg.get("kind")
                if kind == "log":
                    self.append_log(msg.get("text", ""))
                elif kind == "status":
                    self.gui.set_badge("state", msg.get("text", ""), ACCENT)
                elif kind == "result":
                    result = msg["result"]
                    self.gui.show_result(result)
                    self.gui.set_badge("state", "识别完成", OK)
                elif kind == "state":
                    self._sync_state_badges()
                elif kind == "exit":
                    self._final_exit()
                    return

            self._perf_tick += 1
            if self._perf_tick % 12 == 0:   # 约 1s 一次
                self.gui.update_perf(self.engine.perf_snapshot())
        except Exception as e:  # noqa: BLE001
            self.append_log(f"轮询异常: {type(e).__name__}: {e}")
        self.gui.after(80, self._poll)

    def _sync_state_badges(self):
        self.gui.set_badge("auto",
                           "暂停中" if self.engine.paused else
                           ("开启" if self.engine.auto_enabled else "关闭"),
                           AMBER if self.engine.paused else
                           (OK if self.engine.auto_enabled else DIM))
        self.gui.set_badge("hk",
                           "启用" if self.engine.hotkey_enabled else "关闭",
                           OK if self.engine.hotkey_enabled else DIM)
        self.gui.set_badge("state",
                           "识别中..." if self.engine.busy else "空闲", ACCENT)

    # ── 异常钩子 ────────────────────────────────────────────
    def _install_exception_hooks(self):
        def hook(exc_type, exc, tb):
            import traceback
            text = "".join(traceback.format_exception(exc_type, exc, tb))
            self.append_log(f"[异常] {text[:800]}")
            # 保持程序运行，不写任何日志文件

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

    def on_hotkey_toggle(self, enabled: bool):
        self.engine.set_hotkey_enabled(bool(enabled))

    def on_manual_click(self):
        self.engine.handle("manual")

    def on_pause_click(self):
        self.engine.handle("pause")
        self._sync_state_badges()
        self.gui.btn_pause.config(
            text="恢复自动识别" if self.engine.paused else "暂停自动识别")

    def apply_hotkeys(self):
        bindings = {}
        for key, var in self.gui.hk_vars.items():
            bindings[key] = var.get().strip().lower()
        invalid = self.hotkeys.set_bindings(bindings)
        if invalid:
            self.append_log("无效热键被忽略: " +
                            "，".join(f"{n}={k}" for n, k in invalid))
        # 同步到配置
        for key, val in bindings.items():
            if key not in [n for n, _ in invalid]:
                self.cfg_store.raw.setdefault("hotkeys", {})[key] = val
        self.cfg_store.save()
        if self.engine.hotkey_enabled:
            self.hotkeys.start()
        self.append_log("热键已更新：" +
                        "  ".join(f"{k}={preview_key(v)}" for k, v in
                                  self.cfg_store.raw.get("hotkeys", {}).items()))
        self._sync_state_badges()

    def _apply_hotkeys_internal(self, silent=False):
        hk = self.cfg_store.effective.get("hotkeys", {})
        self.hotkeys.set_bindings(hk)
        self.hotkeys.start()
        if not silent:
            self.append_log("全局热键已注册：" +
                            "  ".join(f"{k}={preview_key(v)}" for k, v in
                                      hk.items()))

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
            self.append_log(f"配置已导入: {path}")
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
        # 重新注册热键
        self.hotkeys.set_bindings(self.cfg_store.effective.get("hotkeys", {}))
        self.hotkeys.start()
        self.append_log("设置已同步")

    def on_clear_learn(self):
        if not messagebox.askyesno("清空学习缓存",
                                   "确定清空全部自主学习经验吗？"):
            return
        self.learning.clear()
        self.append_log("自主学习缓存已清空")

    # ── 关闭 / 退出 ─────────────────────────────────────────
    def on_close_request(self):
        """点窗口 X：隐藏到托盘（若启用），否则退出。"""
        tray_on = self.cfg_store.effective.get("ui", {}).get("tray", True)
        if tray_on and self.tray._available:
            self.gui.withdraw()
            self.append_log("已最小化到系统托盘，双击托盘图标可恢复")
        else:
            self._final_exit()

    def _final_exit(self):
        if self._exit_requested:
            return
        self._exit_requested = True
        try:
            self.hotkeys.stop()
            self.ocr.destroy()
            self.learning.save(force=True)
            self.tray.stop()
        except Exception:
            pass
        try:
            self.gui.destroy_all()
        except Exception:
            pass
        import os
        os._exit(0)


def preview_key(key: str) -> str:
    from .hotkeys import preview_key as _p
    return _p(key)
