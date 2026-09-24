# -*- coding: utf-8 -*-
"""
三角洲密码工具 入口
By: Quinlan  Qq: 704979478

用法:
    python main.py              正常启动 GUI
    python main.py --selftest   运行自检（模块测试）
"""

import ctypes
import os
import sys

# ── 进程级 DPI 感知（坐标 = 物理像素）────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _single_instance() -> bool:
    """进程单实例限制（防止重复启动）。"""
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "Local\\DeltaPwdTool_SingleInstance")
    return kernel32.GetLastError() != 183   # ERROR_ALREADY_EXISTS


def _show_already_running():
    try:
        ctypes.windll.user32.MessageBoxW(
            None, "三角洲密码工具已在运行中。", "提示", 0x40)
    except Exception:
        pass


def main() -> int:
    if "--selftest" in sys.argv or "-t" in sys.argv:
        from tests.selftest import run_all
        ok = run_all()
        return 0 if ok else 1

    if not _single_instance():
        _show_already_running()
        return 0

    try:
        from app.app import AppController
        app = AppController()
        app.run()
    except Exception as e:  # noqa: BLE001
        try:
            import traceback
            ctypes.windll.user32.MessageBoxW(
                None, f"程序启动失败：\n{type(e).__name__}: {e}",
                "三角洲密码工具", 0x10)
        except Exception:
            print(f"启动失败: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
