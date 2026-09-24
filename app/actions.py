# -*- coding: utf-8 -*-
"""系统交互：窗口查找/激活、鼠标点击、按键输入（纯 Win32 API，无需管理员权限）。"""

import ctypes
import time
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_0, VK_9 = 0x30, 0x39
VK_BACK = 0x08
VK_RETURN = 0x0D


# ── 窗口查找与激活 ──────────────────────────────────────────
def find_game_window(titles: list = None) -> int:
    if titles is None:
        titles = ["三角洲", "Delta Force", "delta force"]
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum_proc(hwnd, lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        for t in titles:
            if t and t.lower() in title.lower():
                found.append(hwnd)
                return False
        return True

    _user32.EnumWindows(_enum_proc, 0)
    return found[0] if found else 0


def game_window_foreground(titles: list = None) -> bool:
    """当前前台窗口是否为游戏窗口（安全机制：非游戏前台不触发自动扫描）。"""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return False
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return False
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value
    for t in (titles or ["三角洲", "Delta Force", "delta force"]):
        if t and t.lower() in title.lower():
            return True
    return False


def activate_window(hwnd: int) -> None:
    if not hwnd:
        return
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)
    _user32.SetForegroundWindow(hwnd)


# ── 鼠标点击 ────────────────────────────────────────────────
def win_click(x: int, y: int) -> None:
    _user32.SetCursorPos(int(x), int(y))
    _user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    _user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def click_sequence(coords: list, delay: float = 0.08) -> None:
    for pt in coords:
        win_click(pt["x"], pt["y"])
        time.sleep(delay)


# ── 键盘输入 ────────────────────────────────────────────────
def press_key(vk: int) -> None:
    """keybd_event 按下并抬起一个虚拟键。"""
    _user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)


def input_digit(d: str) -> None:
    """输入单个数字 0-9（游戏内数字输入）。"""
    if d.isdigit():
        press_key(VK_0 + int(d))


def input_password(digits: str, interval: float = 0.06) -> None:
    for ch in digits:
        if ch.isdigit():
            input_digit(ch)
            time.sleep(interval)


def type_text(text: str, interval: float = 0.03) -> None:
    """按字符输入普通文本（用于非游戏窗口调试，一般不使用）。"""
    for ch in text:
        if ch.isdigit():
            press_key(VK_0 + int(ch))
        elif ch.isalpha():
            vk = ord(ch.upper())
            _user32.keybd_event(vk, 0, 0, 0)
            _user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(interval)
