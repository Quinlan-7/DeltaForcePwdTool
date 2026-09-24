# -*- coding: utf-8 -*-
"""
配置管理：读取 / 保存 / 分辨率缩放 / 导入 / 导出 / 重置。
配置坐标一律以 2K(2560x1440) 为基准存储，加载时按当前分辨率等比缩放（内存态），
写回时永远保存基准坐标，避免二次缩放累积误差。
"""

import copy
import ctypes
import json
import os

from .paths import BASE_DIR, CONFIG_PATH

BASE_W, BASE_H = 2560, 1440

_DEFAULT_CONFIG: dict = {
    "version": 4,
    "hotkeys": {
        "manual": "~",
        "pause": "f7",
        "exit": "f8",
        "interact": "f",
    },
    "auto_detect": True,
    "detect_timeout": 3.0,
    "sample_interval": 0.5,
    "center_scan": True,
    "scan_margin": 0.05,
    "fingerprint_auto_click": True,
    "morse_auto_input": False,
    "morse_confirm_clicks": [],
    "fingerprint": {
        "name_region": {"x1": 706, "y1": 657, "x2": 866, "y2": 689},
        "number_region": {"x1": 1030, "y1": 530, "x2": 1365, "y2": 930},
        "big_fp_region": {"x1": 880, "y1": 420, "x2": 1500, "y2": 1080},
        "candidate_boxes": [
            [1522, 560, 1627, 665], [1650, 560, 1755, 665], [1778, 560, 1883, 665],
            [1522, 687, 1627, 792], [1650, 687, 1755, 792], [1778, 687, 1883, 792],
            [1522, 815, 1627, 920], [1650, 815, 1755, 920], [1778, 815, 1883, 920],
        ],
        "mode_config": {
            "8": {"mode": "C", "candidates": 9, "indices": [0, 1, 2, 3, 4, 5, 6, 7, 8]},
            "6": {"mode": "B", "candidates": 7, "indices": [0, 1, 2, 3, 4, 5, 6]},
            "4": {"mode": "A", "candidates": 5, "indices": [0, 1, 2, 3, 4]},
        },
        "match_threshold": 0.5,
        "name_threshold": 0.6,
    },
    "morse": {
        "symbol_min_area": 12,
        "bright_threshold": 140,
        "max_retries": 3,
        "retry_delay": 0.25,
    },
    "regions": [
        {"name": "区域1", "left": 699, "top": 514, "width": 200, "height": 50},
        {"name": "区域2", "left": 967, "top": 514, "width": 200, "height": 50},
        {"name": "区域3", "left": 1234, "top": 514, "width": 200, "height": 50},
    ],
    "ui": {
        "float_hint": True,
        "region_lock": False,
        "tray": True,
        "learning": True,
        "performance_panel": True,
    },
    "misc": {
        "game_window_titles": ["三角洲", "Delta Force", "delta force"],
        "memory_gc_interval": 120,
        "experience_save_interval": 60,
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _set_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def screen_size() -> tuple:
    _set_dpi_aware()
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _scale_region(reg: dict, sx: float, sy: float) -> dict:
    out = dict(reg)
    for key in ("left", "width", "x1", "x2"):
        if key in out:
            out[key] = int(out[key] * sx)
    for key in ("top", "height", "y1", "y2"):
        if key in out:
            out[key] = int(out[key] * sy)
    return out


def _scale_boxes(boxes, sx, sy):
    return [[int(b[0] * sx), int(b[1] * sy), int(b[2] * sx), int(b[3] * sy)]
            for b in boxes]


def effective_config(cfg: dict) -> dict:
    """返回按当前分辨率缩放后的生效配置（不修改原始基准配置）。"""
    cur_w, cur_h = screen_size()
    if (cur_w, cur_h) == (BASE_W, BASE_H):
        return copy.deepcopy(cfg)
    sx, sy = cur_w / BASE_W, cur_h / BASE_H
    eff = copy.deepcopy(cfg)
    eff["regions"] = [_scale_region(r, sx, sy) for r in cfg.get("regions", [])]
    eff["morse_confirm_clicks"] = [
        {"x": int(c["x"] * sx), "y": int(c["y"] * sy)}
        for c in cfg.get("morse_confirm_clicks", [])
    ]
    fp = eff.setdefault("fingerprint", {})
    for key in ("name_region", "number_region", "big_fp_region"):
        if key in fp:
            fp[key] = _scale_region(fp[key], sx, sy)
    if "candidate_boxes" in fp:
        fp["candidate_boxes"] = _scale_boxes(fp["candidate_boxes"], sx, sy)
    eff["_screen"] = (cur_w, cur_h)
    return eff


class ConfigStore:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self.raw: dict = {}
        self.effective: dict = {}
        self.load()

    def load(self) -> dict:
        if not os.path.exists(self.path):
            self.raw = copy.deepcopy(_DEFAULT_CONFIG)
            self._save_raw()
        else:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except (OSError, ValueError):
                loaded = {}
            self.raw = _merge(_DEFAULT_CONFIG, loaded)
            hk = self.raw.get("hotkeys", {})
            # 旧版迁移：F5/F6/END -> ~ / F7 / F8；交互触发由 F 承担
            if "morse" in hk:
                hk.pop("morse", None)
            if "fingerprint" in hk:
                hk.pop("fingerprint", None)
            if hk.get("exit", "").lower() in ("end", "esc"):
                hk["exit"] = "f8"
            hk.setdefault("manual", "~")
            hk.setdefault("pause", "f7")
            hk.setdefault("exit", "f8")
            hk.setdefault("interact", "f")
        self.refresh()
        return self.effective

    def refresh(self) -> None:
        self.effective = effective_config(self.raw)

    def _save_raw(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.raw, f, ensure_ascii=False, indent=2)

    def save(self) -> None:
        self._save_raw()
        self.refresh()

    @property
    def hotkeys(self) -> dict:
        return self.effective.get("hotkeys", {})

    @property
    def regions(self) -> list:
        return self.effective.get("regions", [])

    @property
    def fingerprint(self) -> dict:
        return self.effective.get("fingerprint", {})

    def export(self, dst_path: str) -> bool:
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with open(dst_path, "w", encoding="utf-8") as f:
                json.dump(self.raw, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def import_(self, src_path: str) -> bool:
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.raw = _merge(_DEFAULT_CONFIG, loaded)
            self._save_raw()
            self.refresh()
            return True
        except (OSError, ValueError):
            return False

    def reset(self) -> None:
        self.raw = copy.deepcopy(_DEFAULT_CONFIG)
        self._save_raw()
        self.refresh()
