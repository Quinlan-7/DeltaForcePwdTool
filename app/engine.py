# -*- coding: utf-8 -*-
"""
工作流引擎：热键事件分发、自动识别（F 交互后多帧检测）、手动扫描、
暂停/恢复、完全退出、性能统计与内存回收。

自动识别时序（重点修复）：
    F 键交互 → 仅当游戏窗口在前台时启动检测循环
    → 按采样间隔多帧抓取中心扫描区
    → 检测到摩斯界面 → 立即破译；检测到指纹界面 → 立即破译
    → 超时(默认3s)仍未出现密码界面 → 判定为拾取物资/开启盒子，直接跳过
"""

import gc
import os
import queue
import threading
import time

from . import capture, detector, fingerprint, morse
from .actions import game_window_foreground


class ScanContext:
    """向识别管线注入的运行上下文。"""

    def __init__(self, cfg_store, ocr, learning, log_fn, status_fn):
        self.cfg_store = cfg_store
        self.ocr = ocr
        self.learning = learning
        self._log = log_fn
        self._status = status_fn

    @property
    def cfg(self) -> dict:
        return self.cfg_store.effective

    def grab_region(self, region):
        return capture.grab((int(region["left"]), int(region["top"]),
                             int(region["left"]) + int(region["width"]),
                             int(region["top"]) + int(region["height"])))

    def log(self, msg: str) -> None:
        self._log(msg)

    def status(self, msg: str) -> None:
        self._status(msg)


class Engine:
    def __init__(self, cfg_store, ocr, learning, hotkeys):
        self.cfg_store = cfg_store
        self.ocr = ocr
        self.learning = learning
        self.hotkeys = hotkeys
        self.outbox: queue.Queue = queue.Queue()

        self.auto_enabled = bool(cfg_store.effective.get("auto_detect", True))
        self.paused = False
        self.hotkey_enabled = True
        self.busy = False
        self._busy_lock = threading.Lock()
        self._cooldown_until = 0.0
        self._scan_count = 0
        self._start_time = time.time()
        self._ocr_ms = 0.0
        self._detect_ms = 0.0
        self._ctx = None

    # ── 内部消息 ────────────────────────────────────────────
    def log(self, msg: str) -> None:
        self.outbox.put({"kind": "log", "text": msg})

    def status(self, msg: str) -> None:
        self.outbox.put({"kind": "status", "text": msg})

    def _push_state(self) -> None:
        self.outbox.put({"kind": "state", "auto": self.auto_enabled,
                         "paused": self.paused,
                         "hotkey": self.hotkey_enabled, "busy": self.busy})

    # ── 热键事件 ────────────────────────────────────────────
    def handle(self, name: str) -> None:
        if name == "manual":
            self._start_manual()
        elif name == "pause":
            self.paused = not self.paused
            self.log("自动识别已暂停" if self.paused else "自动识别已恢复")
            self._push_state()
        elif name == "exit":
            self.log("收到退出指令，正在清理并退出...")
            self.shutdown()
        elif name == "interact":
            self._on_interact()

    # ── 自动识别（F 交互触发）───────────────────────────────
    def _on_interact(self) -> None:
        if not self.hotkey_enabled:
            return
        if not self.auto_enabled:
            return
        if self.paused:
            return
        if self.busy:
            return
        if time.time() < self._cooldown_until:
            return
        titles = self.cfg_store.effective.get("misc", {}).get("game_window_titles")
        if not game_window_foreground(titles):
            self.log("安全机制：游戏窗口不在前台，忽略本次 F 触发")
            return
        threading.Thread(target=self._auto_scan, daemon=True,
                         name="auto-scan").start()

    def _auto_scan(self) -> None:
        with self._busy_lock:
            if self.busy:
                return
            self.busy = True
            self._push_state()
        try:
            cfg = self.cfg_store.effective
            timeout = float(cfg.get("detect_timeout", 3.0))
            interval = float(cfg.get("sample_interval", 0.5))
            ctx = self._make_ctx()
            box = capture.scan_box(cfg)
            origin = (box[0], box[1])
            deadline = time.time() + timeout
            self.status("自动检测中...")
            while time.time() < deadline:
                if self.paused or not self.auto_enabled:
                    break
                t0 = time.time()
                scan_pil = capture.grab(box)
                kind, detail = detector.detect(
                    scan_pil, cfg, origin, self.ocr, self._known())
                self._detect_ms = round((time.time() - t0) * 1000, 1)
                if kind == "morse":
                    self.status("检测到摩斯密码界面，开始破译")
                    result = morse.run_morse(cfg, ctx)
                    self.outbox.put({"kind": "result", "result": result})
                    self._cooldown_until = time.time() + 1.0
                    return
                if kind == "fingerprint":
                    self.status("检测到指纹密码界面，开始破译")
                    result = fingerprint.run_fingerprint(cfg, ctx)
                    self.outbox.put({"kind": "result", "result": result})
                    self._cooldown_until = time.time() + 1.0
                    return
                elapsed = time.time() - t0
                time.sleep(max(0.05, interval - elapsed))
            self.status("未检测到密码界面（拾取物资/盒子场景，已跳过）")
            self.log("3秒内未检测到密码界面，判定为物资/盒子场景，已跳过破译")
        except Exception as e:  # noqa: BLE001
            self.log(f"自动识别异常: {type(e).__name__}: {e}")
        finally:
            with self._busy_lock:
                self.busy = False
            self._scan_count += 1
            if self._scan_count % 20 == 0:
                gc.collect()
            self._push_state()

    # ── 手动扫描（~）────────────────────────────────────────
    def _start_manual(self) -> None:
        if not self.hotkey_enabled:
            return
        if self.busy:
            self.log("已有识别任务进行中，请稍候")
            return
        threading.Thread(target=self._manual_scan, daemon=True,
                         name="manual-scan").start()

    def _manual_scan(self) -> None:
        with self._busy_lock:
            if self.busy:
                return
            self.busy = True
            self._push_state()
        try:
            cfg = self.cfg_store.effective
            ctx = self._make_ctx()
            box = capture.scan_box(cfg)
            origin = (box[0], box[1])
            titles = cfg.get("misc", {}).get("game_window_titles")
            if not game_window_foreground(titles):
                self.log("提示：游戏窗口不在前台，本次扫描可能识别失败")
            self.status("手动扫描中...")
            t0 = time.time()
            scan_pil = capture.grab(box)
            kind, detail = detector.detect(scan_pil, cfg, origin,
                                           self.ocr, self._known())
            if kind == "morse":
                result = morse.run_morse(cfg, ctx)
                self.outbox.put({"kind": "result", "result": result})
            elif kind == "fingerprint":
                result = fingerprint.run_fingerprint(cfg, ctx)
                self.outbox.put({"kind": "result", "result": result})
            else:
                self.status("未检测到密码界面")
                self.log("手动扫描未发现摩斯/指纹密码界面")
        except Exception as e:  # noqa: BLE001
            self.log(f"手动扫描异常: {type(e).__name__}: {e}")
        finally:
            with self._busy_lock:
                self.busy = False
            self._scan_count += 1
            if self._scan_count % 20 == 0:
                gc.collect()
            self._push_state()

    # ── 辅助 ────────────────────────────────────────────────
    def _make_ctx(self) -> ScanContext:
        if self._ctx is None:
            self._ctx = ScanContext(self.cfg_store, self.ocr, self.learning,
                                    self.log, self.status)
        return self._ctx

    def _known(self):
        from .paths import known_persons
        return known_persons()

    # ── 状态控制 ────────────────────────────────────────────
    def set_auto(self, enabled: bool) -> None:
        self.auto_enabled = enabled
        self.log("自动识别已开启" if enabled else "自动识别已关闭")
        self._push_state()

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self.log("自动识别已暂停" if paused else "自动识别已恢复")
        self._push_state()

    def set_hotkey_enabled(self, enabled: bool) -> None:
        self.hotkey_enabled = enabled
        if enabled:
            self.hotkeys.start()
            self.log("全局热键已启用")
        else:
            self.hotkeys.stop()
            self.log("全局热键已关闭")
        self._push_state()

    # ── 性能与内存 ──────────────────────────────────────────
    def perf_snapshot(self) -> dict:
        return {
            "ocr_ms": self._ocr_ms,
            "detect_ms": self._detect_ms,
            "mem_mb": _process_memory_mb(),
            "uptime": int(time.time() - self._start_time),
            "scans": self._scan_count,
        }

    # ── 退出 ────────────────────────────────────────────────
    def shutdown(self) -> None:
        self.outbox.put({"kind": "exit"})
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        try:
            self.ocr.destroy()
        except Exception:
            pass
        try:
            self.learning.save(force=True)
        except Exception:
            pass
        os._exit(0)


def _process_memory_mb() -> float:
    try:
        import ctypes
        from ctypes import wintypes
        psapi = ctypes.WinDLL("psapi")
        PROCESS_MEMORY_COUNTERS = (ctypes.c_ulong * 8)
        counters = PROCESS_MEMORY_COUNTERS()
        psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters), ctypes.sizeof(counters))
        return round(counters[2] / (1024 * 1024), 1)   # WorkingSetSize
    except Exception:
        return 0.0
