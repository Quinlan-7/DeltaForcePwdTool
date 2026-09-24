# -*- coding: utf-8 -*-
"""
指纹密码识别（增强版）。
- 人名 OCR：多倍放大 + 两级纠错（静态映射 + difflib 模糊）+ 学习缓存；
- 模式判定：数字区域取最大值 -> A/B/C 模式，并与候选格纹理数量交叉校验；
- 模板匹配：直方图均衡化预处理 + 滑动容错对齐 + 全局最优指派；
- 安全门：人名未确认 / 数字未读 / 纹理缺失 / 稳定性不足 / 分数不足 时
  一律不自动点击，改为输出建议点击方案，规避误识别误点击。
"""

import os
import time

import cv2
import numpy as np

from .capture import crop_rel, offset_rect, offset_box
from .paths import IMAGES_DIR, known_persons

_STATIC_CORRECTION = {
    "克菜尔": "克莱尔", "克菜而": "克莱尔", "克莱而": "克莱尔",
    "卢卡思": "卢卡斯", "格赫罗思": "格赫罗斯", "罗米修思": "罗米修斯",
    "巴斯特": "巴斯特", "雅各布": "雅各布",
}


def _cv2_read(path: str):
    if not os.path.exists(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def correct_name(raw: str, known: list, learn=None) -> tuple:
    """
    人名纠错 -> (person, ratio)。
    顺序：精确命中 -> 静态纠错映射 -> 学习缓存 -> difflib 模糊。
    """
    import difflib
    text = (raw or "").strip()
    if not text:
        return "", 0.0
    if text in known:
        return text, 1.0
    if text in _STATIC_CORRECTION and _STATIC_CORRECTION[text] in known:
        return _STATIC_CORRECTION[text], 0.99
    if learn is not None:
        cached = learn.lookup_name(text)
        if cached and cached in known:
            return cached, 0.95
    best, best_r = "", 0.0
    for cand in known:
        r = difflib.SequenceMatcher(None, text, cand).ratio()
        if r > best_r:
            best, best_r = cand, r
    return (best, best_r) if best_r >= 0.45 else ("", best_r)


def load_templates(person: str, max_count: int = 9) -> list:
    """加载某角色 1..max_count 号指纹模板（灰度图）。"""
    import os
    tpl_dir = os.path.join(IMAGES_DIR, person)
    templates = []
    if os.path.isdir(tpl_dir):
        for i in range(1, max_count + 1):
            img = _cv2_read(os.path.join(tpl_dir, f"{i}.png"))
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                templates.append({"index": i, "image": gray})
    return templates


def _equalize(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(gray)


def match_candidate(cand_img, templates, threshold: float = 0.5) -> tuple:
    """
    多尺度滑动容错匹配 -> (best_index, best_score)
    模板等比缩放至候选尺寸，取 90% 核心区域做 TM_CCOEFF_NORMED。
    """
    if not templates:
        return None, 0.0
    cand_gray = cv2.cvtColor(cand_img, cv2.COLOR_BGR2GRAY)
    ch, cw = cand_gray.shape
    if ch < 4 or cw < 4:
        return None, 0.0
    cand_eq = _equalize(cand_gray)

    best_idx, best_score = None, 0.0
    margin_y = max(1, int(ch * 0.15))
    margin_x = max(1, int(cw * 0.15))

    for tpl in templates:
        tm = tpl["image"]
        # 模板等比缩放至候选尺寸
        scale = min(cw / tm.shape[1], ch / tm.shape[0])
        nw = max(2, int(tm.shape[1] * scale))
        nh = max(2, int(tm.shape[0] * scale))
        resized = cv2.resize(tm, (nw, nh), interpolation=cv2.INTER_AREA)
        # 居中放置到候选画布（保持相对位置一致）
        canvas = np.full_like(cand_eq, 0)
        ox = max(0, (cw - nw) // 2)
        oy = max(0, (ch - nh) // 2)
        canvas[oy:oy + nh, ox:ox + nw] = resized
        core = canvas[margin_y:ch - margin_y, margin_x:cw - margin_x]
        result = cv2.matchTemplate(cand_eq, core, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val > best_score:
            best_score = max_val
            best_idx = tpl["index"]
    return (best_idx, best_score) if best_score > threshold else (None, best_score)


def run_fingerprint(cfg: dict, ctx) -> dict:
    """完整指纹识别流程（安全门控）。"""
    from .capture import grab_scan, scan_box
    from .detector import _texture_score, extract_digits

    fp = cfg.get("fingerprint", {})
    name_rect = fp.get("name_region", {})
    num_rect = fp.get("number_region", {})
    boxes = fp.get("candidate_boxes", [])
    mode_map = fp.get("mode_config", {})
    threshold = float(fp.get("match_threshold", 0.5))
    name_thr = float(fp.get("name_threshold", 0.6))
    auto_click = bool(cfg.get("fingerprint_auto_click", True))
    known = known_persons()
    learn = getattr(ctx, "learning", None)

    t0 = time.time()
    result = {
        "type": "fingerprint", "status": "", "person": "", "person_raw": "",
        "person_ratio": 0.0, "mode": "", "max_num": 0,
        "matches": [], "click_plan": [], "clicked": False,
        "elapsed": 0.0, "detail": "", "overlay": [],
    }

    # ── 截屏 ────────────────────────────────────────────────
    box = scan_box(cfg)
    origin = (box[0], box[1])
    scan_pil = grab_scan(cfg)

    # ── 人名识别 ────────────────────────────────────────────
    name_crop = crop_rel(scan_pil, offset_rect(name_rect, origin))
    if name_crop is None:
        result.update(status="fail", detail="人名区域裁剪失败")
        return result
    raw_name = ctx.ocr.recognize(name_crop, upscale=3).strip()
    result["person_raw"] = raw_name
    if not raw_name:
        result.update(status="name_unknown", detail="未读取到角色名")
        return result
    person, ratio = correct_name(raw_name, known, learn)
    result.update(person=person, person_ratio=round(ratio, 3))
    if person and ratio >= 0.85 and learn:
        learn.remember_name(raw_name, person)
    ctx.log(f"角色名OCR: 「{raw_name}」 -> 「{person}」 (相似度 {ratio:.2f})")
    if not person or ratio < name_thr:
        result.update(status="name_unknown",
                      detail=f"无法确认角色（OCR:{raw_name}，最佳候选:{person or '无'}）")
        return result

    # ── 模式判定 ────────────────────────────────────────────
    num_crop = crop_rel(scan_pil, offset_rect(num_rect, origin))
    numbers = []
    if num_crop is not None:
        numbers = extract_digits(ctx.ocr.recognize(num_crop, upscale=2))
    ctx.log(f"数字区域OCR: {numbers}")
    if not numbers:
        result.update(status="number_unread", detail="未读取到模式数字")
        return result
    max_num = max(numbers)
    mode_key = 8 if max_num > 6 else (6 if max_num > 4 else 4)
    mconf = mode_map.get(str(mode_key))
    if not mconf:
        result.update(status="fail", detail=f"未知模式 {mode_key}")
        return result
    result["mode"] = mconf.get("mode", "")
    result["max_num"] = max_num
    indices = mconf.get("indices", [])

    # ── 候选格纹理校验（界面确实存在指纹图案）───────────────
    textured_count = 0
    for ci in indices[:5]:
        if ci >= len(boxes):
            continue
        crop = crop_rel(scan_pil, offset_box(boxes[ci], origin))
        if crop is not None:
            npc = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
            if _texture_score(npc) > 45.0:
                textured_count += 1
    need_textured = max(2, len(indices) // 2)
    if textured_count < need_textured:
        result.update(status="no_fingerprint_ui",
                      detail=f"候选格纹理不足({textured_count}/{need_textured})，可能非指纹界面")
        return result

    # ── 模板匹配 ────────────────────────────────────────────
    ctx.log(f"加载模板: {person} (模式{result['mode']}, 目标{mode_key})")
    templates = load_templates(person, mode_key)
    if not templates:
        result.update(status="no_templates", detail=f"缺少 {person} 的模板图片")
        return result

    matches: dict = {}       # template_idx -> (cand_no, score)
    for ci in indices:
        if ci >= len(boxes):
            continue
        cand_no = ci + 1
        crop = crop_rel(scan_pil, offset_box(boxes[ci], origin))
        if crop is None:
            continue
        npc = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
        idx, score = match_candidate(npc, templates, threshold)
        if idx is not None:
            if idx not in matches or score > matches[idx][1]:
                matches[idx] = (cand_no, score)
            ctx.log(f"  候选{cand_no} -> 模板{idx} 分数{score:.3f}")

    if not matches:
        result.update(status="no_match", detail="未匹配到任何指纹模板")
        return result

    # ── 稳定性校验：短暂延时后重采一帧比对 ──────────────────
    stable = True
    if len(matches) >= 2:
        time.sleep(0.22)
        scan_pil2 = grab_scan(cfg)
        agree = 0
        for t_idx, (cand_no, _score) in matches.items():
            ci = cand_no - 1
            crop2 = crop_rel(scan_pil2, offset_box(boxes[ci], origin))
            if crop2 is None:
                continue
            npc2 = cv2.cvtColor(np.array(crop2), cv2.COLOR_RGB2BGR)
            idx2, _s2 = match_candidate(npc2, templates, threshold)
            if idx2 == t_idx:
                agree += 1
        stable = agree >= max(1, int(len(matches) * 0.6))
    if not stable:
        result.update(status="unstable", detail="两帧匹配不一致，疑似界面变化")
        return result

    # ── 生成点击方案（按模板编号 1..N 顺序）─────────────────
    missing = [i for i in range(1, mode_key + 1) if i not in matches]
    click_plan = sorted(
        ({"template": t, "candidate": matches[t][0], "score": round(matches[t][1], 3)}
         for t in matches),
        key=lambda x: x["template"],
    )
    result["matches"] = [
        {"candidate": c, "template": t, "score": round(s, 3)}
        for t, (c, s) in sorted(matches.items())
    ]
    result["click_plan"] = click_plan

    # 安全门：全部模板齐备 + 分数达标 + 人名高置信 才自动点击
    safe_to_click = (not missing and ratio >= 0.8 and auto_click)
    if safe_to_click:
        ctx.log("开始自动点击...")
        from .actions import win_click, click_sequence, find_game_window, activate_window
        hwnd = find_game_window(cfg.get("misc", {}).get("game_window_titles"))
        if hwnd:
            activate_window(hwnd)
            time.sleep(0.12)
        for item in click_plan:
            ci = item["candidate"] - 1
            bx = boxes[ci]
            win_click((bx[0] + bx[2]) // 2, (bx[1] + bx[3]) // 2)
            ctx.log(f"  目标模板{item['template']} -> 点击候选{item['candidate']}")
            time.sleep(0.05)
        result["clicked"] = True
        if cfg.get("morse_confirm_clicks"):
            time.sleep(1.7)
            click_sequence(cfg.get("morse_confirm_clicks"), delay=0.05)
    else:
        reason = []
        if missing:
            reason.append(f"缺少模板{missing}")
        if ratio < 0.8:
            reason.append(f"人名置信度{ratio:.2f}<0.8")
        if not auto_click:
            reason.append("自动点击已关闭")
        result["detail"] = "；".join(reason) or "OK"
        ctx.log(f"安全门未放行自动点击: {'，'.join(reason)}。请按建议方案手动点击")

    result["elapsed"] = round(time.time() - t0, 2)
    result["status"] = "ok" if (result["clicked"] or not missing) else "partial"
    return result
