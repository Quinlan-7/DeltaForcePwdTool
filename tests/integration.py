# -*- coding: utf-8 -*-
"""端到端集成验证：合成游戏画面 -> 界面检测 -> 破译管线（不点击）。"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import capture, detector, fingerprint, morse  # noqa: E402
from app.config_store import ConfigStore  # noqa: E402
from app.learning import Experience  # noqa: E402
from app.ocr_engine import OcrEngine  # noqa: E402


class StubCtx:
    def __init__(self, ocr, learn):
        self.ocr = ocr
        self.learning = learn
        self.cfg = None

    @property
    def cfg(self):
        return self._cfg

    @cfg.setter
    def cfg(self, v):
        self._cfg = v

    def grab_region(self, region):
        return capture.grab((region["left"], region["top"],
                             region["left"] + region["width"],
                             region["top"] + region["height"]))

    def log(self, m):
        print("   [ctx]", m)

    def status(self, m):
        print("   [status]", m)


def build_fingerprint_screen():
    """构造 2560x1440 合成指纹界面。"""
    font_dir = r"C:\Windows\Fonts"
    img = Image.new("RGB", (2560, 1440), (14, 18, 24))
    d = ImageDraw.Draw(img)
    # 名称区
    f_name = ImageFont.truetype(os.path.join(font_dir, "msyh.ttc"), 30)
    d.text((716, 658), "克莱尔", font=f_name, fill=(240, 240, 240))
    # 数字区：多个数字
    f_num = ImageFont.truetype(os.path.join(font_dir, "msyh.ttc"), 60)
    for i, ch in enumerate("846"):
        d.text((1050 + i * 80, 560), ch, font=f_num, fill=(240, 240, 240))
    # 候选格：放入真实模板（截取自游戏截图）
    base = r"C:\Users\Administrator\Doubao\chats\2026-09-24\new-chat\DeltaForcePwdTool\images\克莱尔"
    boxes = [[1522, 560, 1627, 665], [1650, 560, 1755, 665], [1778, 560, 1883, 665],
             [1522, 687, 1627, 792], [1650, 687, 1755, 792], [1778, 687, 1883, 792],
             [1522, 815, 1627, 920], [1650, 815, 1755, 920], [1778, 815, 1883, 920]]
    for i, box in enumerate(boxes[:6]):
        tpl_path = os.path.join(base, f"{i + 1}.png")
        if not os.path.exists(tpl_path):
            continue
        tpl = Image.open(tpl_path).convert("RGB")
        bw, bh = box[2] - box[0], box[3] - box[1]
        tpl = tpl.resize((bw, bh), Image.LANCZOS)
        img.paste(tpl, (box[0], box[1]))
    return img


def build_morse_screen():
    img = Image.new("RGB", (2560, 1440), (14, 18, 24))
    d = ImageDraw.Draw(img)
    for i, digit in enumerate("123"):
        code = morse.REV_TABLE[digit]
        x = 699 + 20 + i * 268
        y = 524
        for ch in code:
            if ch == ".":
                d.rectangle([x, y, x + 8, y + 12], fill=(230, 230, 230))
                x += 20
            else:
                d.rectangle([x, y, x + 30, y + 12], fill=(230, 230, 230))
                x += 42
    return img


def main():
    print("=" * 55)
    print("  端到端集成验证（合成画面）")
    print("=" * 55)
    store = ConfigStore()
    learn = Experience(path=os.path.join(os.path.dirname(__file__),
                                         "..", "experience_test.json"),
                       enabled=False)
    ocr = OcrEngine()
    assert ocr.init(), "OCR init failed"
    ctx = StubCtx(ocr, learn)
    ctx.cfg = store.effective

    ok = True

    # ── 指纹链路 ────────────────────────────────────────────
    print("\n[指纹链路] 构造合成界面...")
    fp_screen = build_fingerprint_screen()
    box = capture.scan_box(store.effective)
    origin = (box[0], box[1])
    scan = fp_screen.crop((box[0], box[1], box[2], box[3]))

    kind, detail = detector.detect(scan, store.effective, origin, ocr, None)
    print(f"  界面检测 -> {kind} {detail}")
    if kind != "fingerprint":
        print("[FAIL] 指纹界面未检出")
        ok = False
    else:
        print("[PASS] 指纹界面检出")

    real_grab = capture.grab
    capture.grab = lambda bbox=None: fp_screen if bbox is None else \
        fp_screen.crop(bbox)
    try:
        result = fingerprint.run_fingerprint(store.effective, ctx)
        print(f"  结果: person={result.get('person')} mode={result.get('mode')} "
              f"status={result.get('status')}")
        print(f"  matches: {result.get('matches')}")
        if result.get("person") == "克莱尔" and result.get("mode") == "C":
            print("[PASS] 指纹识别：人名与模式正确")
        else:
            print(f"[FAIL] 指纹识别异常: {result}")
            ok = False
    finally:
        capture.grab = real_grab

    # ── 摩斯链路 ────────────────────────────────────────────
    print("\n[摩斯链路] 构造合成界面...")
    ms_screen = build_morse_screen()
    box2 = capture.scan_box(store.effective)
    origin2 = (box2[0], box2[1])
    scan2 = ms_screen.crop((box2[0], box2[1], box2[2], box2[3]))
    kind2, _ = detector.detect(scan2, store.effective, origin2, ocr, None)
    print(f"  界面检测 -> {kind2}")
    if kind2 != "morse":
        print("[FAIL] 摩斯界面未检出")
        ok = False
    else:
        print("[PASS] 摩斯界面检出")
    capture.grab = lambda bbox=None: ms_screen if bbox is None else \
        ms_screen.crop(bbox)
    try:
        result2 = morse.run_morse(store.effective, ctx)
        print(f"  密码: {result2.get('password')} conf={result2.get('conf')}")
        if result2.get("password") == "123":
            print("[PASS] 摩斯解码正确")
        else:
            print(f"[FAIL] 摩斯解码异常: {result2}")
            ok = False
    finally:
        capture.grab = real_grab

    learn.clear()
    try:
        os.remove(os.path.join(os.path.dirname(__file__), "..",
                               "experience_test.json"))
    except OSError:
        pass
    print("\n" + ("全部通过" if ok else "存在失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
