# -*- coding: utf-8 -*-
"""
密码界面检测器：判断当前画面是否为「摩斯密码界面」或「指纹密码界面」。
- 摩斯：对 3 个配置区域做廉价符号统计，符号数量落在合理区间即判定；
- 指纹：先做候选格纹理粗检（Laplacian 方差），通过后才运行 OCR 人名确认，
  避免每次采样都跑 OCR，显著降低性能开销。
"""

import re

import cv2
import numpy as np

from . import morse
from .capture import crop_rel, offset_rect, offset_box, offset_region
from .fingerprint import correct_name


def _texture_score(img_np) -> float:
    """边缘纹理强度（指纹图案有大量细密纹理）。"""
    try:
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        return float(lap.var())
    except Exception:
        return 0.0


def _crop_np(pil_img, box):
    crop = crop_rel(pil_img, box)
    if crop is None:
        return None
    return cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)


def morse_present(scan_pil, cfg: dict, origin: tuple) -> bool:
    """摩斯界面判定：每个区域 2~8 个符号、总数 8~20，且符号小而均匀。"""
    total = 0
    for reg in cfg.get("regions", []):
        rel = offset_region(reg, origin)
        crop = crop_rel(scan_pil, (rel["left"], rel["top"],
                                   rel["left"] + rel["width"],
                                   rel["top"] + rel["height"]))
        if crop is None:
            return False
        res = morse.analyze_region(crop, cfg.get("morse", {}))
        n = res["count"]
        if n < 2 or n > 8:
            return False
        total += n
    return 8 <= total <= 20


def fingerprint_present(scan_pil, cfg: dict, origin: tuple,
                        ocr=None, known: list = None) -> tuple:
    """
    指纹界面判定 -> (present: bool, detail: dict)
    1) 候选格纹理粗检（前 3 个格子 + 名称区）；
    2) 通过后 OCR 人名，命中已知角色名即确认。
    """
    fp = cfg.get("fingerprint", {})
    boxes = fp.get("candidate_boxes", [])
    detail = {"textured": 0, "name_hit": False, "name_raw": ""}

    # 候选格纹理粗检
    textured = 0
    for box in boxes[:3]:
        rel = offset_box(box, origin)
        crop = _crop_np(scan_pil, rel)
        if crop is not None and _texture_score(crop) > 25.0:
            textured += 1
    detail["textured"] = textured
    if textured < 2:
        return False, detail

    # 名称区粗检
    name_rect = fp.get("name_region", {})
    rel = offset_rect(name_rect, origin)
    name_crop = _crop_np(scan_pil, rel)
    if name_crop is None or _texture_score(name_crop) < 30.0:
        return False, detail

    # OCR 人名确认（有 OCR 引擎时才做）
    if ocr is not None and ocr.ready:
        from PIL import Image
        name_pil = Image.fromarray(cv2.cvtColor(name_crop, cv2.COLOR_BGR2RGB))
        raw = ocr.recognize(name_pil, upscale=3).strip()
        detail["name_raw"] = raw
        if raw:
            person, ratio = correct_name(raw, known or [])
            detail["name_hit"] = bool(person and ratio >= 0.5)
            return detail["name_hit"], detail
    return True, detail   # 无 OCR 时仅凭纹理判定


def detect(scan_pil, cfg: dict, origin: tuple, ocr=None, known=None) -> tuple:
    """综合检测 -> (kind, detail)，kind ∈ {"morse","fingerprint",None}。"""
    if morse_present(scan_pil, cfg, origin):
        return "morse", {}
    if known is None:
        from .paths import known_persons
        known = known_persons()
    present, detail = fingerprint_present(scan_pil, cfg, origin, ocr, known)
    if present:
        return "fingerprint", detail
    return None, detail


def extract_digits(text: str) -> list:
    return [int(n) for n in re.findall(r"\d+", text or "")]
