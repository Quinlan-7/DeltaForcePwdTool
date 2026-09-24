# -*- coding: utf-8 -*-
"""路径管理：兼容源码运行与 EXE 打包两种形态，所有依赖文件与程序同级目录。"""

import os
import sys


def _base_dir() -> str:
    """程序根目录：EXE 形态为 exe 所在目录，脚本形态为项目根目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _base_dir()

CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
MODELS_DIR = os.path.join(BASE_DIR, "models")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")
EXPERIENCE_PATH = os.path.join(BASE_DIR, "experience.json")  # 学习缓存（非日志）


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, IMAGES_DIR, MODELS_DIR, ASSETS_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass


def known_persons() -> list:
    """images/ 下的角色名目录列表（指纹模板目录名）。"""
    try:
        if not os.path.isdir(IMAGES_DIR):
            return []
        return sorted(
            d for d in os.listdir(IMAGES_DIR)
            if os.path.isdir(os.path.join(IMAGES_DIR, d))
        )
    except OSError:
        return []
