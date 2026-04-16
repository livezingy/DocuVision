"""Chart recognition service for optional engines phase.

This service consumes layout-detected chart boxes, crops ROI images, and runs
Chart2Table-style parsing with lazy model initialization.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2
from loguru import logger


class ChartService:
    """Optional chart recognition service with ROI-batch inference."""

    # Keep only candidates known to exist in typical paddlex installs.
    # Remove "chart_recognition" which may not exist in some environments
    # and causes create_pipeline to fail eagerly.
    _PIPELINE_CANDIDATES = (
        "chart_parsing",
        "chart2table",
    )

    def __init__(self, device: Optional[str] = None):
        self._ready = False
        self._device = device or self._detect_device()
        self._pipeline = None
        self._init_error: Optional[str] = None
        self._init_attempted = False
        self._pipeline_name: Optional[str] = None

    @staticmethod
    def _detect_device() -> str:
        try:
            import paddle

            if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
                return "gpu"
        except Exception:
            pass
        return "cpu"

    def _init_pipeline(self) -> bool:
        self._init_attempted = True
        try:
            from paddlex import create_pipeline

            last_error = None
            for name in self._PIPELINE_CANDIDATES:
                try:
                    self._pipeline = create_pipeline(
                        pipeline=name,
                        device=self._device,
                    )
                    self._pipeline_name = name
                    self._ready = True
                    self._init_error = None
                    logger.info(f"ChartService initialized (pipeline={name}, device={self._device})")
                    return True
                except Exception as exc:
                    last_error = str(exc)
                    continue

            self._pipeline = None
            self._pipeline_name = None
            self._ready = False
            self._init_error = last_error or "no supported chart pipeline"
            logger.warning(f"ChartService init failed: {self._init_error}")
            return False
        except Exception as exc:
            self._pipeline = None
            self._pipeline_name = None
            self._ready = False
            self._init_error = str(exc)
            logger.warning(f"ChartService init failed: {exc}")
            return False

    def _ensure_pipeline(self) -> bool:
        if self._pipeline is not None and self._ready:
            return True
        return self._init_pipeline()

    def _rebuild_pipeline(self) -> bool:
        logger.warning("ChartService rebuilding pipeline after failure...")
        self._pipeline = None
        self._ready = False
        self._pipeline_name = None
        return self._init_pipeline()

    def is_ready(self) -> bool:
        return self._ready and self._pipeline is not None

    def get_status(self) -> Dict[str, Any]:
        return {
            "ready": self.is_ready(),
            "device": self._device,
            "pipeline_name": self._pipeline_name,
            "init_error": self._init_error,
        }

    @staticmethod
    def _normalize_bbox(box: Dict[str, Any]) -> Optional[List[int]]:
        try:
            if all(k in box for k in ("x1", "y1", "x2", "y2")):
                return [
                    int(round(float(box["x1"]))),
                    int(round(float(box["y1"]))),
                    int(round(float(box["x2"]))),
                    int(round(float(box["y2"]))),
                ]
            if all(k in box for k in ("x", "y", "width", "height")):
                x = float(box["x"])
                y = float(box["y"])
                w = float(box["width"])
                h = float(box["height"])
                return [
                    int(round(x)),
                    int(round(y)),
                    int(round(x + w)),
                    int(round(y + h)),
                ]
        except Exception:
            return None
        return None

    def _crop_chart_rois(
        self,
        image_path: str,
        chart_boxes: List[Dict[str, Any]],
    ) -> Tuple[str, List[str], List[List[int]]]:
        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"ChartService could not read image for ROI crop: {image_path}")

        h, w = image.shape[:2]
        roi_dir = os.path.join(tempfile.gettempdir(), f"docuvision_chart_roi_{uuid.uuid4().hex}")
        os.makedirs(roi_dir, exist_ok=True)

        roi_paths: List[str] = []
        normalized_boxes: List[List[int]] = []

        for i, raw_box in enumerate(chart_boxes):
            if not isinstance(raw_box, dict):
                continue
            norm = self._normalize_bbox(raw_box)
            if norm is None:
                continue

            x1, y1, x2, y2 = norm
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            if x2 <= x1 or y2 <= y1:
                continue

            crop = image[y1:y2, x1:x2]
            if crop is None or crop.size == 0:
                continue

            roi_path = os.path.join(roi_dir, f"chart_roi_{i:04d}.png")
            cv2.imwrite(roi_path, crop)
            roi_paths.append(roi_path)
            normalized_boxes.append([x1, y1, x2, y2])

        return roi_dir, roi_paths, normalized_boxes

    @staticmethod
    def _result_to_dict(res: Any) -> Dict[str, Any]:
        if hasattr(res, "json"):
            data = res.json
        elif hasattr(res, "to_dict"):
            data = res.to_dict()
        elif hasattr(res, "__dict__"):
            data = res.__dict__
        else:
            data = dict(res)

        if isinstance(data, dict) and "res" in data and isinstance(data["res"], dict):
            return data["res"]
        return data if isinstance(data, dict) else {}

    def _predict_chart_rois(self, roi_paths: List[str]) -> List[Dict[str, Any]]:
        if not roi_paths:
            return []
        try:
            batched = list(self._pipeline.predict(roi_paths))
            return [self._result_to_dict(r) for r in batched]
        except Exception as exc:
            logger.warning(f"ChartService ROI batch predict failed, fallback to per-ROI: {exc}")

        out: List[Dict[str, Any]] = []
        for roi_path in roi_paths:
            single = list(self._pipeline.predict(roi_path))
            out.append(self._result_to_dict(single[0]) if single else {})
        return out

    def _run_once_on_layout_rois(
        self,
        image_path: str,
        chart_boxes: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        if not self._ensure_pipeline():
            raise RuntimeError(f"ChartService not ready: {self._init_error or 'unknown init error'}")

        roi_dir = ""
        try:
            roi_dir, roi_paths, normalized_boxes = self._crop_chart_rois(image_path, chart_boxes)
            roi_results = self._predict_chart_rois(roi_paths)

            chart_items: List[Dict[str, Any]] = []
            recognized = 0
            for idx, bbox in enumerate(normalized_boxes):
                result_item = roi_results[idx] if idx < len(roi_results) else {}
                has_payload = bool(result_item)
                if has_payload:
                    recognized += 1
                chart_items.append(
                    {
                        "chart_region_id": idx + 1,
                        "bbox": bbox,
                        "source": "layout_roi",
                        "result": result_item,
                    }
                )

            unwrapped_results = [
                {
                    "chart_res_list": chart_items,
                    "layout_det_res": {
                        "boxes": [
                            {
                                "label": "chart",
                                "coordinate": bbox,
                                "score": 1.0,
                            }
                            for bbox in normalized_boxes
                        ]
                    },
                }
            ]

            stats = {
                "chart_count": recognized,
                "layout_chart_box_count": len(normalized_boxes),
                "roi_mode": True,
                "roi_total": len(normalized_boxes),
                "roi_recognized": recognized,
            }
            return unwrapped_results, stats, {"use_layout_detection": False}
        finally:
            if roi_dir and os.path.isdir(roi_dir):
                try:
                    for name in os.listdir(roi_dir):
                        path = os.path.join(roi_dir, name)
                        if os.path.isfile(path):
                            os.remove(path)
                    os.rmdir(roi_dir)
                except Exception as cleanup_exc:
                    logger.debug(f"ChartService ROI temp cleanup failed: {cleanup_exc}")

    def _run_once_on_layout_rois_with_rebuild(
        self,
        image_path: str,
        chart_boxes: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        try:
            return self._run_once_on_layout_rois(image_path, chart_boxes)
        except Exception as exc:
            logger.warning(f"ChartService ROI mode failed, attempting rebuild and retry once: {exc}")
            if not self._rebuild_pipeline():
                raise
            return self._run_once_on_layout_rois(image_path, chart_boxes)

    def recognize(
        self,
        image_path: str,
        *,
        layout_chart_boxes: Optional[List[Dict[str, Any]]] = None,
        roi_source_image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        chart_boxes = layout_chart_boxes if isinstance(layout_chart_boxes, list) else []
        if not chart_boxes:
            return {
                "ok": True,
                "stage": "no_layout_chart_boxes",
                "unwrapped_results": [],
                "stats": {
                    "chart_count": 0,
                    "layout_chart_box_count": 0,
                    "roi_mode": True,
                    "roi_total": 0,
                    "roi_recognized": 0,
                },
                "predict_kwargs": {"use_layout_detection": False},
                "error_level": "none",
                "error_code": "",
                "failure_stage": "",
            }

        source_image = roi_source_image_path or image_path
        try:
            unwrapped, stats, predict_kwargs = self._run_once_on_layout_rois_with_rebuild(
                source_image,
                chart_boxes,
            )
            return {
                "ok": True,
                "stage": "roi_batch",
                "unwrapped_results": unwrapped,
                "stats": stats,
                "predict_kwargs": predict_kwargs,
                "error_level": "none",
                "error_code": "",
                "failure_stage": "",
            }
        except Exception as exc:
            err = str(exc)
            err_low = err.lower()
            is_gpu_runtime = ("cuda" in err_low) or ("cublas" in err_low)
            return {
                "ok": False,
                "unwrapped_results": [],
                "stats": {
                    "chart_count": 0,
                    "layout_chart_box_count": len(chart_boxes),
                },
                "error": f"ChartService failed after rebuild retry: {exc}",
                "error_level": "hard" if is_gpu_runtime else "soft",
                "error_code": "gpu_runtime_error" if is_gpu_runtime else "runtime_error",
                "failure_stage": "inference",
            }
