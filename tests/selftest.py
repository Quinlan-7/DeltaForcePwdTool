# -*- coding: utf-8 -*-
"""自检程序：验证核心模块可用性（不启动 GUI、不写日志文件）。"""

import sys

from app import morse
from app.config_store import ConfigStore, screen_size
from app.learning import Experience
from app.ocr_engine import OcrEngine
from app.paths import known_persons

_PASS = 0
_FAIL = 0


def _check(name: str, ok: bool, detail: str = ""):
    global _PASS, _FAIL
    if ok:
        _PASS += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        _FAIL += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))


def _test_config():
    print("[1/5] 配置加载与分辨率缩放")
    try:
        store = ConfigStore()
        eff = store.effective
        _check("配置加载", bool(eff.get("regions")) and eff.get("sample_interval") > 0)
        _check("默认全自动识别", eff.get("auto_detect") is True
               and abs(eff.get("sample_interval", 0) - 0.8) < 0.01,
               f"interval={eff.get('sample_interval')}")
        _check("分辨率适配", len(eff.get("regions", [])) == 3,
               f"屏幕 {screen_size()}")
    except Exception as e:  # noqa: BLE001
        _check("配置加载", False, str(e))


def _test_morse():
    print("[2/5] 摩斯解码（纯视觉）")
    try:
        all_ok = True
        for digit in "0123456789":
            img = morse.render_morse_test(digit)
            d, conf, m = morse.decode_region(img, {})
            if d != digit:
                all_ok = False
                print(f"      {digit}: got {d} morse={m}")
        _check("0-9 全部解码正确", all_ok)
        # 噪声干扰测试：加干扰块应被过滤
        from PIL import Image, ImageDraw
        img = morse.render_morse_test("5")
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 4, 4], fill=(200, 200, 200))   # 角落噪点
        d.rectangle([190, 44, 199, 49], fill=(255, 255, 255))  # 底部噪点
        res = morse.analyze_region(img, {})
        _check("噪声过滤", res["count"] == 5, f"count={res['count']}")
        # 数量非 5 时拒绝
        from PIL import ImageDraw
        img2 = morse.render_morse_test("5")
        d2 = ImageDraw.Draw(img2)
        d2.rectangle([150, 21, 159, 29], fill=(225, 225, 225))  # 额外符号
        d2, _, m2 = morse.decode_region(img2, {})
        _check("非法数量拒绝", d2 is None, f"morse={m2}")
    except Exception as e:  # noqa: BLE001
        _check("摩斯解码", False, str(e))


def _test_ocr():
    print("[3/5] 本地 OCR 引擎（离线）")
    try:
        eng = OcrEngine()
        ok = eng.init()
        _check("引擎初始化（本地模型）", ok and eng.ready,
               eng.error or ("本地" if eng.using_local_models else "内置"))
        if not ok:
            return
        # 渲染中文人名 + 数字
        from PIL import Image, ImageDraw, ImageFont
        font_path = r"C:\Windows\Fonts\msyh.ttc"
        font = ImageFont.truetype(font_path, 40)
        img = Image.new("RGB", (320, 80), (15, 18, 24))
        d = ImageDraw.Draw(img)
        d.text((12, 14), "克莱尔", font=font, fill=(235, 235, 235))
        t, c = eng.recognize_detailed(img, upscale=2)
        hit = "克莱尔" in t or "菜" in t or "来" in t or "克" in t
        _check("中文人名 OCR", hit and c > 0.3, f"text={t!r} conf={c}")
        img2 = Image.new("RGB", (200, 80), (15, 18, 24))
        d2 = ImageDraw.Draw(img2)
        d2.text((10, 14), "86", font=ImageFont.truetype(font_path, 46),
                fill=(235, 235, 235))
        t2, _ = eng.recognize_detailed(img2, upscale=2)
        _check("数字 OCR", any(ch.isdigit() for ch in t2), f"text={t2!r}")
        eng.destroy()
    except Exception as e:  # noqa: BLE001
        _check("OCR 引擎", False, str(e))


def _test_fingerprint():
    print("[4/5] 指纹模板匹配")
    try:
        from app import fingerprint as fp
        from app.paths import IMAGES_DIR
        import os
        import numpy as np
        import cv2
        persons = known_persons()
        _check("模板目录存在", bool(persons), str(persons))
        if not persons:
            return
        person = persons[0]
        templates = fp.load_templates(person, 9)
        _check("模板加载", bool(templates), f"{person}: {len(templates)} 张")
        if not templates:
            return
        # 用模板1自身作为候选图，应匹配到模板1
        t1 = templates[0]["image"]
        cand = cv2.cvtColor(t1, cv2.COLOR_GRAY2BGR)
        # 缩放至与模板一致的格子尺寸
        idx, score = fp.match_candidate(cand, templates, 0.2)
        _check("自匹配命中", idx == 1, f"idx={idx} score={score:.3f}")
        # 人名纠错
        name, ratio = fp.correct_name("克菜尔", persons)
        _check("人名纠错", name == "克莱尔", f"{name} ratio={ratio:.2f}")
        name2, ratio2 = fp.correct_name("完全错误", persons)
        _check("错误人名拒绝", name2 == "" or ratio2 < 0.45,
               f"{name2!r} ratio={ratio2:.2f}")
    except Exception as e:  # noqa: BLE001
        _check("指纹匹配", False, str(e))


def _test_learning():
    print("[5/5] 自主学习缓存")
    try:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "experience_test.json")
        exp = Experience(path=path, enabled=True)
        exp.remember_morse("sig123", "7")
        exp.remember_name("克菜尔", "克莱尔")
        exp.save(force=True)
        exp2 = Experience(path=path, enabled=True)
        _check("摩斯缓存读写", exp2.lookup_morse("sig123") == "7")
        _check("人名缓存读写", exp2.lookup_name("克菜尔") == "克莱尔")
        exp2.clear()
        try:
            os.remove(path)
        except OSError:
            pass
    except Exception as e:  # noqa: BLE001
        _check("学习缓存", False, str(e))


def run_all() -> bool:
    print("=" * 50)
    print("  三角洲密码工具 自检")
    print("=" * 50)
    _test_config()
    _test_morse()
    _test_ocr()
    _test_fingerprint()
    _test_learning()
    print("=" * 50)
    print(f"  通过 {_PASS} 项，失败 {_FAIL} 项")
    print("=" * 50)
    return _FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
