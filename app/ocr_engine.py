# -*- coding: utf-8 -*-
"""
本地离线 OCR 引擎（RapidOCR / PP-OCRv3，onnxruntime 推理）。
- 模型文件优先从程序同级目录 models/ 加载，实现完全离线、无微信依赖；
- 全部内存操作，不落盘临时图片；
- 线程安全（内部互斥锁），支持置信度返回。
"""

import os
import threading

from PIL import Image, ImageEnhance

from .paths import MODELS_DIR

_PKG_MODELS = None


def _pkg_model_dir() -> str:
    global _PKG_MODELS
    if _PKG_MODELS is None:
        try:
            import rapidocr_onnxruntime as _r
            _PKG_MODELS = os.path.join(os.path.dirname(_r.__file__), "models")
        except Exception:
            _PKG_MODELS = ""
    return _PKG_MODELS


class OcrEngine:
    """本地 OCR 封装。"""

    def __init__(self):
        self.engine = None
        self.ready = False
        self.error = ""
        self._lock = threading.Lock()
        self.using_local_models = False

    def init(self, models_dir: str = MODELS_DIR) -> bool:
        try:
            det = os.path.join(models_dir, "ch_PP-OCRv3_det_infer.onnx")
            rec = os.path.join(models_dir, "ch_PP-OCRv3_rec_infer.onnx")
            cls = os.path.join(models_dir, "ch_ppocr_mobile_v2.0_cls_infer.onnx")
            if all(os.path.isfile(p) for p in (det, rec, cls)):
                from rapidocr_onnxruntime import RapidOCR
                self.engine = RapidOCR(
                    det_model_path=det, rec_model_path=rec, cls_model_path=cls,
                    use_angle_cls=False, print_verbose=False,
                )
                self.using_local_models = True
            else:
                from rapidocr_onnxruntime import RapidOCR
                self.engine = RapidOCR(use_angle_cls=False, print_verbose=False)
                self.using_local_models = False
            self.ready = True
            self.error = ""
            return True
        except Exception as e:  # noqa: BLE001
            self.ready = False
            self.error = f"{type(e).__name__}: {e}"
            return False

    def destroy(self) -> None:
        with self._lock:
            self.engine = None
            self.ready = False

    # ── 预处理 ──────────────────────────────────────────────
    @staticmethod
    def _preprocess(img: Image.Image, upscale: int, enhance: bool) -> Image.Image:
        if upscale > 1:
            img = img.resize(
                (img.width * upscale, img.height * upscale),
                Image.Resampling.LANCZOS,
            )
        if enhance:
            img = ImageEnhance.Contrast(img).enhance(1.6)
            img = ImageEnhance.Sharpness(img).enhance(1.2)
        return img

    # ── 识别 ────────────────────────────────────────────────
    def recognize(self, img: Image.Image, upscale: int = 2, enhance: bool = True) -> str:
        text, _ = self.recognize_detailed(img, upscale, enhance)
        return text

    def recognize_detailed(self, img, upscale=2, enhance=True):
        """返回 (text, avg_conf)。"""
        if not self.ready or self.engine is None:
            return "", 0.0
        with self._lock:
            try:
                prepared = self._preprocess(img, upscale, enhance)
                import numpy as np
                arr = np.array(prepared.convert("RGB"))
                result, _ = self.engine(arr)
                if not result and arr.shape[0] * arr.shape[1] < 200_000:
                    # 小区域文本检测失败时：跳过检测、整图直识（如单个数字/短文本）
                    old = self.engine.use_text_det
                    self.engine.use_text_det = False
                    try:
                        result, _ = self.engine(arr)
                    finally:
                        self.engine.use_text_det = old
                if not result:
                    return "", 0.0
                texts, confs = [], []
                for item in result:
                    # item: [box, text, score]
                    t = str(item[1]).strip()
                    if t:
                        texts.append(t)
                        try:
                            confs.append(float(item[2]))
                        except (TypeError, ValueError):
                            confs.append(0.0)
                if not texts:
                    return "", 0.0
                avg = sum(confs) / len(confs) if confs else 0.0
                return " ".join(texts), round(avg, 3)
            except Exception:  # noqa: BLE001
                return "", 0.0
