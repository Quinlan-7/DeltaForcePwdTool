# -*- coding: utf-8 -*-
"""屏幕截图：全屏 / 区域 / 中心扫描区，全部内存操作，不写任何磁盘文件。"""

from PIL import ImageGrab

from .config_store import screen_size


def grab(box: tuple = None) -> "Image.Image":
    """截取屏幕指定区域（bbox=(l,t,r,b)），None 为全屏。"""
    if box is None:
        return ImageGrab.grab()
    return ImageGrab.grab(bbox=box)


def grab_regions(regions: list) -> list:
    """对 regions 列表逐区域截图，返回 [(name, PIL.Image)]。"""
    out = []
    for idx, reg in enumerate(regions, start=1):
        left = int(reg["left"])
        top = int(reg["top"])
        box = (left, top, left + int(reg["width"]), top + int(reg["height"]))
        out.append((reg.get("name", f"区域{idx}"), grab(box)))
    return out


def scan_box(cfg: dict) -> tuple:
    """
    计算检测扫描框：覆盖摩斯区域 + 指纹各区域的最小外接矩形，并向外扩边距。
    中心区域识别模式即基于此框采样，避免全屏截图，降低性能消耗。
    """
    w, h = screen_size()
    margin = float(cfg.get("scan_margin", 0.05))
    left, top, right, bottom = w, h, 0, 0

    for reg in cfg.get("regions", []):
        l = int(reg["left"]); t = int(reg["top"])
        r = l + int(reg["width"]); b = t + int(reg["height"])
        left, top = min(left, l), min(top, t)
        right, bottom = max(right, r), max(bottom, b)

    fp = cfg.get("fingerprint", {})
    for key in ("name_region", "number_region", "big_fp_region"):
        r = fp.get(key)
        if not r:
            continue
        l, t = int(r["x1"]), int(r["y1"])
        rr, bb = int(r["x2"]), int(r["y2"])
        left, top = min(left, l), min(top, t)
        right, bottom = max(right, rr), max(bottom, bb)

    for box in fp.get("candidate_boxes", []):
        l, t = int(box[0]), int(box[1])
        rr, bb = int(box[2]), int(box[3])
        left, top = min(left, l), min(top, t)
        right, bottom = max(right, rr), max(bottom, bb)

    pad_x = int(w * margin)
    pad_y = int(h * margin)
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(w, right + pad_x)
    bottom = min(h, bottom + pad_y)
    if right <= left or bottom <= top:
        return (0, 0, w, h)
    return (left, top, right, bottom)


def grab_scan(cfg: dict):
    """截取检测扫描框图像。"""
    return grab(scan_box(cfg))


def offset_region(region: dict, origin: tuple) -> dict:
    """将绝对坐标区域转换为相对某截图原点(origin=(ox,oy))的裁剪框。"""
    ox, oy = origin
    l = int(region["left"]) - ox
    t = int(region["top"]) - oy
    return {"left": l, "top": t,
            "width": int(region["width"]), "height": int(region["height"])}


def offset_rect(rect: dict, origin: tuple) -> tuple:
    """rect={x1,y1,x2,y2} 相对原点裁剪 -> (l,t,r,b)。"""
    ox, oy = origin
    return (int(rect["x1"]) - ox, int(rect["y1"]) - oy,
            int(rect["x2"]) - ox, int(rect["y2"]) - oy)


def offset_box(box: list, origin: tuple) -> tuple:
    ox, oy = origin
    return (int(box[0]) - ox, int(box[1]) - oy,
            int(box[2]) - ox, int(box[3]) - oy)


def crop_rel(img, box: tuple):
    """按相对坐标裁剪，越界自动裁剪并返回 None（空区域）。"""
    w, h = img.size
    l, t, r, b = box
    l = max(0, min(l, w)); t = max(0, min(t, h))
    r = max(0, min(r, w)); b = max(0, min(b, h))
    if r <= l or b <= t:
        return None
    return img.crop((l, t, r, b))
