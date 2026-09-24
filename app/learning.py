# -*- coding: utf-8 -*-
"""
自主学习机制：识别经验缓存。
- 摩斯界面特征签名 -> 数字（同界面秒识别，越用越快）；
- OCR 人名原文 -> 校正后角色名（持续修正误识别）。
数据为学习缓存（非日志），可在设置中关闭；写盘采用原子替换、节流策略。
"""

import json
import os
import threading
import time

from .paths import EXPERIENCE_PATH


class Experience:
    def __init__(self, path: str = EXPERIENCE_PATH, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self._lock = threading.Lock()
        self.morse: dict = {}   # 特征签名 -> 数字
        self.names: dict = {}   # OCR原文 -> 校正角色名
        self._dirty = False
        self._last_save = 0.0
        self._load()

    # ── 读写 ────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.morse = dict(data.get("morse", {}))
                self.names = dict(data.get("names", {}))
        except (OSError, ValueError):
            self.morse, self.names = {}, {}

    def save(self, force: bool = False) -> None:
        if not self.enabled and not force:
            return
        with self._lock:
            if not self._dirty and not force:
                return
            try:
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"morse": self.morse, "names": self.names},
                              f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
                self._dirty = False
                self._last_save = time.time()
            except OSError:
                pass

    def _mark(self) -> None:
        self._dirty = True
        now = time.time()
        if now - self._last_save >= 60:   # 节流：最多每分钟写一次
            self.save()

    # ── 摩斯 ────────────────────────────────────────────────
    def lookup_morse(self, signature: str):
        if not self.enabled or not signature:
            return None
        with self._lock:
            return self.morse.get(signature)

    def remember_morse(self, signature: str, digit: str) -> None:
        if not self.enabled or not signature or not digit.isdigit():
            return
        with self._lock:
            self.morse[signature] = digit
        self._mark()

    # ── 人名 ────────────────────────────────────────────────
    def lookup_name(self, raw: str):
        if not self.enabled or not raw:
            return None
        with self._lock:
            return self.names.get(raw.strip())

    def remember_name(self, raw: str, person: str) -> None:
        if not self.enabled or not raw or not person:
            return
        with self._lock:
            self.names[raw.strip()] = person
        self._mark()

    def stats(self) -> dict:
        with self._lock:
            return {"morse": len(self.morse), "names": len(self.names)}

    def clear(self) -> None:
        with self._lock:
            self.morse.clear()
            self.names.clear()
            self._dirty = True
        self.save(force=True)
