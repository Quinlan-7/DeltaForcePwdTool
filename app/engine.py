# -*- coding: utf-8 -*-
"""
工作流引擎：全自动识别（无任何全局热键/键盘钩子，避免触发游戏反作弊）。
- 后台轮询线程每 sample_interval（默认0.8s）检测一次屏幕中心扫描区；
- 仅当前台是游戏窗口时才抓取识别，其他时候完全静默，低占用；
- 检测到摩斯/指纹密码界面立即破译；未发现则下一周期继续。
- 暂停 / 手动扫描 / 退出均由 GUI 触发，不监听任何全局按键。
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
    def __init__(self, cfg_store, ocr, learning):
        self.cfg_store = cfg_store
        self.ocr = ocr
        self.learning = learning
        self.outbox: queue.Queue = queue.Queue()

        self.auto_enabled = bool(cfg_store.effective.get("auto_detect", True))
        self.paused = False
        self.busy = False
        self._busy_lock = threading.Lock()
        self._cooldown_until = 0.0
        self._scan_count = 0
        self._start_time = time.time()
        self._ocr_ms = 0.0
        self._detect_ms = 0.0
        self._ctx = None
        self._stop = threading.Event()
        self._poll_thread = None

    # ── 内部消息 ────────────────────────────────────────────
    def log(self, msg: str) -> None:
        self.outbox.put({"kind": "log", "text": msg})

    def status(self, msg: str) -> None:
        self.outbox.put({"kind": "status", "text": msg})

    def _push_state(self) -> None:
        self.outbox.put({"kind": "state", "auto": self.auto_enabled,
                         "paused": self.paused, "busy": self.busy})

    # ── 自动轮询主循环（后台线程）──────────────────────────
    def start_poller(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="auto-poll")
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        titles = self.cfg_store.effective.get("misc", {}).get("game_window_titles")
        while not self._stop.is_set():
            try:
                if (self.auto_enabled and not self.paused and not self.busy
                        and time.time() >= self._cooldown_until
                        and game_window_foreground(titles)):
                    self._detect_once()
            except Exception as e:  # noqa: BLE001
                self.log(f"自动检测异常: {type(e).__name__}: {e}")
            interval = float(self.cfg_store.effective.get("sample_interval", 0.8))
            self._stop.wait(max(0.3, interval))

    def _detect_once(self) -> None:
        """抓取一帧并判定是否为密码界面；是则破译。"""
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
            t0 = time.time()
            scan_pil = capture.grab(box)
            kind, detail = detector.detect(
                scan_pil, cfg, origin, self.ocr, self._known())
            self._detect_ms = round((time.time() - t0) * 1000, 1)
            if kind == "morse":
                self.status("检测到摩斯密码界面，开始破译")
                result = morse.run_morse(cfg, ctx)
                self.outbox.put({"kind": "result", "result": result})
                self._cooldown_until = time.time() + 1.5
                return
            if kind == "fingerprint":
                self.status("检测到指纹密码界面，开始破译")
                result = fingerprint.run_fingerprint(cfg, ctx)
                self.outbox.put({"kind": "result", "result": result})
                self._cooldown_until = time.time() + 1.5
                return
        except Exception as e:  # noqa: BLE001
            self.log(f"自动识别异常: {type(e).__name__}: {e}")
        finally:
            with self._busy_lock:
                self.busy = False
            self._scan_count += 1
            if self._scan_count % 25 == 0:
                gc.collect()
            self._push_state()

    # ── 手动扫描（GUI 按钮触发，非热键）─────────────────────
    def start_manual(self) -> None:
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
            self._detect_ms = round((time.time() - t0) * 1000, 1)
            if kind == "morse":
                result = morse.run_morse(cfg, ctx)
                self.outbox.put({"kind": "result", "result": result})
            elif kind == "fingerprint":
                result = fingerprint.run_fingerprint(cfg, ctx)
                self.outbox.put({"kind": "result", "result": result})
            else:
                self.status("未检测到密码界面")
        except Exception as e:  # noqa: BLE001
            self.log("手动扫描异常: " + f"{type(e).__name__}: {e}")
        finally:
            with self._busy_lock:
                self.busy = False
            self._scan_count += 1
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

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.log("自动识别已暂停" if self.paused else "自动识别已恢复")
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
        self._stop.set()
        self.outbox.put({"kind": "exit"})
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
        psapi = ctypes.WinDLL("psapi")
        PROCESS_MEMORY_COUNTERS = (ctypes.c_ulong * 8)
        counters = PROCESS_MEMORY_COUNTERS()
        psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters), ctypes.sizeof(counters))
        return round(counters[2] / (1024 * 1024), 1)
    except Exception:
        return 0.0
