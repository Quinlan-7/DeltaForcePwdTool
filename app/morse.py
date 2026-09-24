# -*- coding: utf-8 -*-
"""
摩斯密码识别（纯视觉 OpenCV 增强版）。
- 亮度掩膜 + 自适应阈值，抗环境亮度变化；
- 形态学处理连接断裂笔画；
- 符号分类（点/划）+ 数量/大小一致性校验，杜绝乱码输入；
- 多次采样投票 + 特征签名缓存（自主学习加速）。
"""

import hashlib

import cv2
import numpy as np

MORSE_TABLE = {
    "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4",
    ".....": "5", "-....": "6", "--...": "7", "---..": "8", "----.": "9",
}
REV_TABLE = {v: k for k, v in MORSE_TABLE.items()}


def _to_gray(pil_img) -> np.ndarray:
    arr = np.array(pil_img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


def pattern_signature(pil_img) -> str:
    """将区域图像归一化为固定小尺寸二值图，取哈希作为界面特征签名。"""
    try:
        gray = _to_gray(pil_img)
        small = cv2.resize(gray, (12, 8), interpolation=cv2.INTER_AREA)
        _, bw = cv2.threshold(small, 0, 1, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return hashlib.md5(bw.astype(np.uint8).tobytes()).hexdigest()
    except Exception:
        return ""


def analyze_region(pil_img, cfg: dict = None) -> dict:
    """
    提取区域中的摩斯符号，返回：
    {morse: 拼接串, count: 符号数, conf: 一致性置信度, symbols: [(x,w,h,kind)]}
    """
    cfg = cfg or {}
    min_area = int(cfg.get("symbol_min_area", 12))
    bright_thr = int(cfg.get("bright_threshold", 140))
    out = {"morse": "", "count": 0, "conf": 0.0, "symbols": []}
    try:
        gray = _to_gray(pil_img)
        h, w = gray.shape
        if h < 3 or w < 3:
            return out

        # 亮度阈值 + Otsu 兜底
        thr = bright_thr
        otsu_val, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        if 90 < otsu_val < 230:
            thr = max(thr, int(otsu_val))
        _, mask = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)

        # 形态学：去噪 + 连接断裂的划（最小核，避免合并相邻符号）
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1)))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        area_limit = max(6, min_area)
        min_h = max(2, int(h * 0.06))
        max_h = max(6, int(h * 0.72))

        symbols = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw * ch < area_limit:
                continue
            if ch < min_h or ch > max_h:
                continue
            if cw > w * 0.92:
                continue
            # 贴边轮廓多为界面边框/噪点，真实符号不会紧贴区域边缘
            if x <= 1 or y <= 1 or (x + cw) >= w - 1 or (y + ch) >= h - 1:
                continue
            kind = "-" if (cw / float(max(ch, 1))) >= 1.8 else "."
            symbols.append({"x": x, "w": cw, "h": ch, "kind": kind})

        symbols.sort(key=lambda s: s["x"])
        if not symbols:
            return out

        morse = "".join(s["kind"] for s in symbols)

        # 一致性置信度：同类符号尺寸应相近
        widths = np.array([s["w"] for s in symbols], dtype=np.float32)
        mean_w = float(widths.mean())
        std_w = float(widths.std()) if len(widths) > 1 else 0.0
        conf = 1.0 - min(1.0, std_w / (mean_w + 1e-6))
        # 数量恰好 5 个且命中字典时置信度最高
        if len(symbols) == 5 and morse in MORSE_TABLE:
            conf = max(conf, 0.98)
        elif len(symbols) != 5:
            conf = min(conf, 0.35)

        out.update({"morse": morse, "count": len(symbols), "conf": conf,
                    "symbols": symbols})
        return out
    except Exception:
        return out


def decode_region(pil_img, cfg: dict = None) -> tuple:
    """
    解码单个区域 -> (digit or None, conf, morse_str)
    校验：必须恰好 5 个符号且命中字典，否则拒绝（宁可不输，不乱输）。
    """
    res = analyze_region(pil_img, cfg)
    morse = res["morse"]
    if res["count"] == 5 and morse in MORSE_TABLE:
        return MORSE_TABLE[morse], max(res["conf"], 0.9), morse
    return None, res["conf"], morse


def run_morse(cfg: dict, ctx) -> dict:
    """
    完整摩斯识别流程：多次采样投票 + 解码 + 自动输入 + 确认点击。
    ctx 提供 grab_region / log / learning / status 等能力。
    """
    import time

    regions = cfg.get("regions", [])
    mcfg = cfg.get("morse", {})
    retries = int(mcfg.get("max_retries", 3))
    retry_delay = float(mcfg.get("retry_delay", 0.25))
    auto_input = bool(cfg.get("morse_auto_input", False))
    confirm_clicks = cfg.get("morse_confirm_clicks", [])

    ctx.log("摩斯识别：多帧采样校验中...")
    digits, confs, morse_strs, sigs = [], [], [], []
    t0 = time.time()

    for reg in regions:
        name = reg.get("name", "")
        votes: dict = {}
        last_morse = ""
        max_conf = 0.0
        img = None
        for attempt in range(retries):
            img = ctx.grab_region(reg)
            sig = pattern_signature(img)
            # 自主学习：先查特征签名缓存
            cached = ctx.learning.lookup_morse(sig) if ctx.learning else None
            if cached is not None:
                digit, conf, morse = cached, 0.99, ""
                votes[digit] = votes.get(digit, 0) + 2
                max_conf = max(max_conf, conf)
                last_morse = morse
                break
            digit, conf, morse = decode_region(img, mcfg)
            if digit is not None:
                votes[digit] = votes.get(digit, 0) + 1
            else:
                votes["?"] = votes.get("?", 0) + 1
            if conf > max_conf:
                max_conf = conf
            if morse:
                last_morse = morse
            if attempt < retries - 1:
                time.sleep(retry_delay)

        # 投票取最高，且要求出现 >=2 次（或只有一种有效结果）
        best = "?"
        best_n = 0
        for k, n in votes.items():
            if n > best_n:
                best, best_n = k, n
        if best_n < 2 and best != "?":
            best = "?"
        digits.append(best)
        confs.append(round(max_conf, 2) if best != "?" else 0.0)
        morse_strs.append(last_morse)
        sigs.append(sig)

        # 高置信度结果写入学习缓存
        if best != "?" and max_conf >= 0.9 and ctx.learning:
            ctx.learning.remember_morse(sig, best)
        ctx.log(f"  [{name}] 解码 → {best}  置信度 {confs[-1]}")

    password = "".join(digits)
    elapsed = round(time.time() - t0, 2)
    result = {
        "type": "morse", "digits": digits, "password": password,
        "conf": confs, "morse": morse_strs, "elapsed": elapsed,
        "clicked": False, "detail": "",
    }

    all_ok = all(d.isdigit() for d in digits)
    if all_ok and auto_input:
        ctx.log(f"自动输入密码: {password}")
        from .actions import input_password
        input_password(password)
        result["clicked"] = True
        if confirm_clicks:
            time.sleep(0.6)
            from .actions import click_sequence
            click_sequence(confirm_clicks, delay=0.1)
    elif all_ok and not auto_input:
        ctx.log("自动输入已关闭，请手动输入: " + password)
    else:
        ctx.log("存在未识别数字，已拒绝自动输入（防止输入错误密码）")

    ctx.status(f"摩斯识别完成: {password}")
    return result


def render_morse_test(digit: str, size=(200, 50)) -> "Image.Image":
    """构造摩斯码测试图（仅用于自检）。"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, (12, 12, 16))
    d = ImageDraw.Draw(img)
    code = REV_TABLE[digit]
    x = 10
    for ch in code:
        if ch == ".":
            d.rectangle([x, 21, x + 9, 29], fill=(225, 225, 225))
            x += 16
        else:
            d.rectangle([x, 21, x + 30, 29], fill=(225, 225, 225))
            x += 38
    return img
