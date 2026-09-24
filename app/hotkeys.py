# -*- coding: utf-8 -*-
"""
全局热键管理：基于 Win32 RegisterHotKey + 消息循环线程实现。
- 无需管理员权限（原版 keyboard 库需要管理员）。
- 通过消息队列向主线程投递事件，由 tkinter 轮询分发。
- 支持自定义键位：单键（~ / f7 / f8 / f 等）或带修饰键（ctrl+f1）。
"""

import ctypes
import queue
import threading
import time
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
HWND_MESSAGE = ctypes.c_void_p(-3)
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

_VK = {
    "~": 0xC0, "`": 0xC0,
    "escape": 0x1B, "esc": 0x1B, "enter": 0x0D, "space": 0x20,
    "tab": 0x09, "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "capslock": 0x14, "printscreen": 0x2C, "scrolllock": 0x91,
    "pause": 0x13, "numlock": 0x90,
    "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}


def _vk_of(key: str) -> int | None:
    k = (key or "").strip().lower()
    if not k:
        return None
    if k in _VK:
        return _VK[k]
    if k.startswith("f") and k[1:].isdigit():
        n = int(k[1:])
        if 1 <= n <= 24:
            return 0x70 + n - 1
    if len(k) == 1:
        if k.isdigit():
            return 0x30 + int(k)
        if k.isalpha():
            return ord(k.upper())
    return None


class HotkeyManager:
    """全局热键管理器。使用方式：
        hk = HotkeyManager()
        hk.set_bindings({"manual": "~", "pause": "f7", "exit": "f8", "interact": "f"})
        hk.start()
        # 主循环轮询 hk.drain()
        hk.stop()
    """

    def __init__(self):
        self.events: queue.Queue = queue.Queue()
        self._bindings: dict = {}      # name -> key_str
        self._vk_map: dict = {}        # name -> (modifiers, vk)
        self._id_map: dict = {}        # name -> hotkey id
        self._thread = None
        self._stop = threading.Event()
        self._hwnd = None
        self._ready = threading.Event()
        self._last_error = ""

    # ── 绑定管理 ────────────────────────────────────────────
    def set_bindings(self, bindings: dict) -> list:
        """设置 {名称: 键位}，返回无效键位列表。"""
        invalid = []
        new_vk = {}
        for name, key in bindings.items():
            vk = _vk_of(key)
            if vk is None:
                invalid.append((name, key))
                continue
            mods = MOD_NOREPEAT
            parts = str(key).lower().split("+")
            if len(parts) > 1:
                mods = 0
                bad_mod = False
                for p in parts[:-1]:
                    if p == "ctrl":
                        mods |= MOD_CONTROL
                    elif p == "alt":
                        mods |= MOD_ALT
                    elif p == "shift":
                        mods |= MOD_SHIFT
                    else:
                        invalid.append((name, key))
                        bad_mod = True
                        break
                if bad_mod:
                    continue
                vk = _vk_of(parts[-1])
                if vk is None:
                    invalid.append((name, key))
                    continue
            new_vk[name] = (mods, vk)
        self._bindings = {n: k for n, k in bindings.items() if (n, k) not in invalid}
        self._vk_map = new_vk
        if self._thread and self._thread.is_alive():
            self._rebuild()
        return invalid

    def bindings(self) -> dict:
        return dict(self._bindings)

    # ── 生命周期 ────────────────────────────────────────────
    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="hotkey-loop")
        self._thread.start()
        self._ready.wait(timeout=3.0)
        return self._hwnd is not None

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None

    def _rebuild(self) -> None:
        self.stop()
        self.start()

    def _register_all(self, hwnd) -> None:
        idx = 1
        for name, (mods, vk) in self._vk_map.items():
            ok = _user32.RegisterHotKey(hwnd, idx, mods, vk)
            if ok:
                self._id_map[name] = idx
            else:
                err = ctypes.get_last_error()
                self._last_error = f"热键 {name}({self._bindings.get(name)}) 注册失败, WinError={err}"
            idx += 1

    def _unregister_all(self, hwnd) -> None:
        for hid in set(self._id_map.values()):
            _user32.UnregisterHotKey(hwnd, hid)
        self._id_map.clear()

    def _loop(self) -> None:
        try:
            hinst = _kernel32.GetModuleHandleW(None)
            hwnd = _user32.CreateWindowExW(
                0, "STATIC", "DeltaPwdTool_HotkeyWindow", 0,
                0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
        except Exception:
            hwnd = None
        if not hwnd:
            self._ready.set()
            return
        self._hwnd = hwnd
        self._register_all(hwnd)
        self._ready.set()

        msg = wintypes.MSG()
        while not self._stop.is_set():
            res = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                name = next((n for n, i in self._id_map.items() if i == msg.wParam), None)
                if name:
                    self.events.put(name)
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        self._unregister_all(hwnd)
        _user32.DestroyWindow(hwnd)
        self._hwnd = None

    # ── 事件读取 ────────────────────────────────────────────
    def drain(self, timeout: float = 0) -> list:
        """非阻塞取出当前所有热键事件。"""
        out = []
        try:
            while True:
                out.append(self.events.get_nowait())
        except queue.Empty:
            pass
        return out

    def last_error(self) -> str:
        return self._last_error


def preview_key(key: str) -> str:
    """把键位字符串转为友好显示（用于 UI）。"""
    vk = _vk_of(key)
    if vk is None:
        return "无效"
    if vk == 0xC0:
        return "~ (反引号)"
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x70 + 1}"
    if 0x30 <= vk <= 0x39:
        return str(vk - 0x30)
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    return key or "?"
