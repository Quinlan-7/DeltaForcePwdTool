# -*- coding: utf-8 -*-
"""系统托盘：后台驻留（pystray 实现，缺依赖时自动降级为无托盘）。"""

import threading

from .paths import ICON_PATH


class TrayIcon:
    def __init__(self, title="三角洲密码工具"):
        self.title = title
        self.icon = None
        self._thread = None
        self._handlers = {}
        self._available = False

    def start(self, on_show=None, on_pause=None, on_exit=None,
              paused_getter=None) -> bool:
        self._handlers = {
            "show": on_show, "pause": on_pause, "exit": on_exit,
            "paused": paused_getter,
        }
        try:
            import pystray
            from PIL import Image, ImageDraw
            from PIL import ImageOps

            icon_img = None
            try:
                icon_img = Image.open(ICON_PATH)
            except Exception:
                icon_img = Image.new("RGBA", (64, 64), (15, 20, 26, 255))
                d = ImageDraw.Draw(icon_img)
                d.polygon([(32, 14), (52, 44), (12, 44)], fill=(45, 212, 191, 255))
                d.ellipse([20, 26, 24, 30], fill=(255, 255, 255, 255))
                d.ellipse([30, 26, 34, 30], fill=(255, 255, 255, 255))
                d.ellipse([40, 26, 44, 30], fill=(255, 255, 255, 255))
            icon_img = ImageOps.fit(icon_img, (64, 64), Image.LANCZOS)

            def _make_menu(paused):
                import pystray
                return pystray.Menu(
                    pystray.MenuItem("显示主界面", self._cb_show, default=True),
                    pystray.MenuItem(
                        "暂停自动识别", self._cb_pause,
                        checked=lambda item: bool(self._is_paused())),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("完全退出", self._cb_exit),
                )

            self.icon = pystray.Icon(
                "delta_pwd_tool", icon_img, self.title,
                menu=_make_menu(False))
            self.icon._on_pause = self._cb_pause
            self._available = True
            self.icon.run_detached()
            return True
        except Exception:
            self._available = False
            return False

    def _is_paused(self) -> bool:
        g = self._handlers.get("paused")
        return bool(g() if g else False)

    def _cb_show(self, icon=None, item=None):
        h = self._handlers.get("show")
        if h:
            h()

    def _cb_pause(self, icon=None, item=None):
        h = self._handlers.get("pause")
        if h:
            h()

    def _cb_exit(self, icon=None, item=None):
        h = self._handlers.get("exit")
        if h:
            h()

    def update_pause(self, paused: bool) -> None:
        if not self._available or self.icon is None:
            return
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def stop(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
