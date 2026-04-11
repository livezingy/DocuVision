"""Formula recognition service for optional engines phase.

This service wraps PaddleX `formula_recognition` pipeline and provides
stable outputs for backend envelope integration.
"""

from __future__ import annotations

import collections
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2

from loguru import logger


class FormulaService:
    """Optional formula recognition service with two-stage threshold retry."""

    def __init__(self, device: Optional[str] = None):
        self._ready = False
        self._device = device or self._detect_device()
        self._pipeline = None
        self._init_error: Optional[str] = None
        # Lazy init: delay model loading until first recognize() call.
        self._init_attempted = False

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

            self._pipeline = create_pipeline(
                pipeline="formula_recognition",
                device=self._device,
            )
            self._ready = True
            self._init_error = None
            logger.info(f"FormulaService initialized (device={self._device})")
            return True
        except Exception as exc:
            self._pipeline = None
            self._ready = False
            self._init_error = str(exc)
            logger.warning(f"FormulaService init failed: {exc}")
            return False

    def _ensure_pipeline(self) -> bool:
        if self._pipeline is not None and self._ready:
            return True
        return self._init_pipeline()

    def _rebuild_pipeline(self) -> bool:
        logger.warning("FormulaService rebuilding pipeline after failure...")
        self._pipeline = None
        self._ready = False
        return self._init_pipeline()

    def is_ready(self) -> bool:
        return self._ready and self._pipeline is not None

    def get_status(self) -> Dict[str, Any]:
        return {
            "ready": self.is_ready(),
            "device": self._device,
            "init_error": self._init_error,
        }

    @staticmethod
    def result_to_dict(res: Any) -> Dict[str, Any]:
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

    def _collect_stats(self, unwrapped_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_formula_count = 0
        total_layout_formula_boxes = 0
        label_hist = collections.Counter()
        first_formula: Optional[str] = None

        for item in unwrapped_results:
            boxes = item.get("layout_det_res", {}).get("boxes", []) if isinstance(item.get("layout_det_res", {}), dict) else []
            layout_formula_boxes = 0
            for box in boxes:
                if not isinstance(box, dict):
                    continue
                label = str(box.get("label", "")).lower()
                if label:
                    label_hist[label] += 1
                if label == "formula":
                    layout_formula_boxes += 1
            total_layout_formula_boxes += layout_formula_boxes

            formula_res_list = item.get("formula_res_list", [])
            if isinstance(formula_res_list, list):
                for formula_item in formula_res_list:
                    if not isinstance(formula_item, dict):
                        continue
                    rec_formula = str(formula_item.get("rec_formula", "")).strip()
                    if rec_formula:
                        total_formula_count += 1
                        if first_formula is None:
                            first_formula = rec_formula

            # fallback path: root-level rec_formula
            root_formula = item.get("rec_formula")
            if isinstance(root_formula, str) and root_formula.strip():
                total_formula_count += 1
                if first_formula is None:
                    first_formula = root_formula.strip()

        return {
            "formula_count": total_formula_count,
            "layout_formula_box_count": total_layout_formula_boxes,
            "label_hist": dict(label_hist),
            "first_formula": first_formula,
        }

    def _run_once(
        self,
        image_path: str,
        *,
        disable_layout: bool,
        disable_preprocess: bool,
        layout_threshold: Optional[float],
        pipeline_formula_batch_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        if not self._ensure_pipeline():
            raise RuntimeError(f"FormulaService not ready: {self._init_error or 'unknown init error'}")

        predict_kwargs: Dict[str, Any] = {
            "use_layout_detection": not disable_layout,
        }
        if layout_threshold is not None:
            predict_kwargs["layout_threshold"] = layout_threshold
        if disable_preprocess:
            predict_kwargs["use_doc_orientation_classify"] = False
            predict_kwargs["use_doc_unwarping"] = False

        # best effort: reduce memory pressure
        try:
            inner = getattr(self._pipeline, "_pipeline", None)
            frm_model = getattr(inner, "formula_recognition_model", None)
            if frm_model is not None and hasattr(frm_model, "set_predictor"):
                frm_model.set_predictor(batch_size=max(1, int(pipeline_formula_batch_size)))
        except Exception:
            pass

        results = list(self._pipeline.predict(image_path, **predict_kwargs))
        unwrapped_results = [self.result_to_dict(r) for r in results]
        stats = self._collect_stats(unwrapped_results)
        return unwrapped_results, stats, predict_kwargs

    @staticmethod
    def _normalize_bbox(box: Dict[str, Any]) -> Optional[List[int]]:
        """Normalize a formula bbox to [x1, y1, x2, y2] integer coordinates."""
        try:
            if all(k in box for k in ("x1", "y1", "x2", "y2")):
                x1 = int(round(float(box["x1"])))
                y1 = int(round(float(box["y1"])))
                x2 = int(round(float(box["x2"])))
                y2 = int(round(float(box["y2"])))
                return [x1, y1, x2, y2]

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

    def _crop_formula_rois(
        self,
        image_path: str,
        layout_formula_boxes: List[Dict[str, Any]],
    ) -> Tuple[str, List[str], List[List[int]]]:
        """Crop ROI images for each layout-detected formula block."""
        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"FormulaService could not read image for ROI crop: {image_path}")

        h, w = image.shape[:2]
        roi_dir = os.path.join(
            tempfile.gettempdir(),
            f"docuvision_formula_roi_{uuid.uuid4().hex}",
        )
        os.makedirs(roi_dir, exist_ok=True)

        roi_paths: List[str] = []
        normalized_boxes: List[List[int]] = []

        for i, raw_box in enumerate(layout_formula_boxes):
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

            roi_path = os.path.join(roi_dir, f"formula_roi_{i:04d}.png")
            cv2.imwrite(roi_path, crop)
            roi_paths.append(roi_path)
            normalized_boxes.append([x1, y1, x2, y2])

        return roi_dir, roi_paths, normalized_boxes

    def _predict_formula_rois(
        self,
        roi_paths: List[str],
        predict_kwargs: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Run formula pipeline on ROI list, preferring batch invocation."""
        results: List[Dict[str, Any]] = []
        if not roi_paths:
            return results

        try:
            batched = list(self._pipeline.predict(roi_paths, **predict_kwargs))
            results = [self.result_to_dict(r) for r in batched]
            return results
        except Exception as exc:
            logger.warning(f"FormulaService ROI batch predict failed, fallback to per-ROI: {exc}")

        for roi_path in roi_paths:
            single = list(self._pipeline.predict(roi_path, **predict_kwargs))
            if single:
                results.append(self.result_to_dict(single[0]))
            else:
                results.append({})
        return results

    @staticmethod
    def _extract_rec_formula(result_item: Dict[str, Any]) -> str:
        """Extract recognized formula string from one pipeline result dict."""
        formula_res_list = result_item.get("formula_res_list", [])
        if isinstance(formula_res_list, list):
            for item in formula_res_list:
                if not isinstance(item, dict):
                    continue
                rec = str(item.get("rec_formula", "")).strip()
                if rec:
                    return rec

        root_formula = result_item.get("rec_formula")
        if isinstance(root_formula, str) and root_formula.strip():
            return root_formula.strip()
        return ""

    def _run_once_on_layout_rois(
        self,
        image_path: str,
        layout_formula_boxes: List[Dict[str, Any]],
        *,
        disable_preprocess: bool,
        pipeline_formula_batch_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """Run formula recognition directly on layout-detected ROI crops."""
        if not self._ensure_pipeline():
            raise RuntimeError(f"FormulaService not ready: {self._init_error or 'unknown init error'}")

        predict_kwargs: Dict[str, Any] = {
            # ROI mode disables layout detection to avoid loading layout stacks again.
            "use_layout_detection": False,
        }
        if disable_preprocess:
            predict_kwargs["use_doc_orientation_classify"] = False
            predict_kwargs["use_doc_unwarping"] = False

        try:
            inner = getattr(self._pipeline, "_pipeline", None)
            frm_model = getattr(inner, "formula_recognition_model", None)
            if frm_model is not None and hasattr(frm_model, "set_predictor"):
                frm_model.set_predictor(batch_size=max(1, int(pipeline_formula_batch_size)))
        except Exception:
            pass

        roi_dir = ""
        try:
            roi_dir, roi_paths, normalized_boxes = self._crop_formula_rois(image_path, layout_formula_boxes)
            roi_results = self._predict_formula_rois(roi_paths, predict_kwargs)

            formula_items: List[Dict[str, Any]] = []
            recognized = 0
            for idx, bbox in enumerate(normalized_boxes):
                result_item = roi_results[idx] if idx < len(roi_results) else {}
                rec_formula = self._extract_rec_formula(result_item)
                if rec_formula:
                    recognized += 1
                formula_items.append(
                    {
                        "formula_region_id": idx + 1,
                        "rec_formula": rec_formula,
                        "dt_polys": bbox,
                        "source": "layout_roi",
                    }
                )

            unwrapped_results = [
                {
                    "formula_res_list": formula_items,
                    "layout_det_res": {
                        "boxes": [
                            {
                                "label": "formula",
                                "coordinate": bbox,
                                "score": 1.0,
                            }
                            for bbox in normalized_boxes
                        ]
                    },
                }
            ]

            total_boxes = len(normalized_boxes)
            stats = {
                "formula_count": recognized,
                "layout_formula_box_count": total_boxes,
                "label_hist": {"formula": total_boxes},
                "first_formula": next((it["rec_formula"] for it in formula_items if it["rec_formula"]), None),
                "roi_mode": True,
                "roi_total": total_boxes,
                "roi_recognized": recognized,
            }
            return unwrapped_results, stats, predict_kwargs
        finally:
            if roi_dir and os.path.isdir(roi_dir):
                try:
                    for name in os.listdir(roi_dir):
                        path = os.path.join(roi_dir, name)
                        if os.path.isfile(path):
                            os.remove(path)
                    os.rmdir(roi_dir)
                except Exception as cleanup_exc:
                    logger.debug(f"FormulaService ROI temp cleanup failed: {cleanup_exc}")

    def _run_once_on_layout_rois_with_rebuild(
        self,
        image_path: str,
        layout_formula_boxes: List[Dict[str, Any]],
        *,
        disable_preprocess: bool,
        pipeline_formula_batch_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        try:
            return self._run_once_on_layout_rois(
                image_path,
                layout_formula_boxes,
                disable_preprocess=disable_preprocess,
                pipeline_formula_batch_size=pipeline_formula_batch_size,
            )
        except Exception as exc:
            logger.warning(f"FormulaService ROI mode failed, attempting rebuild and retry once: {exc}")
            if not self._rebuild_pipeline():
                raise
            return self._run_once_on_layout_rois(
                image_path,
                layout_formula_boxes,
                disable_preprocess=disable_preprocess,
                pipeline_formula_batch_size=pipeline_formula_batch_size,
            )

    def _run_once_with_rebuild(
        self,
        image_path: str,
        *,
        disable_layout: bool,
        disable_preprocess: bool,
        layout_threshold: Optional[float],
        pipeline_formula_batch_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        try:
            return self._run_once(
                image_path,
                disable_layout=disable_layout,
                disable_preprocess=disable_preprocess,
                layout_threshold=layout_threshold,
                pipeline_formula_batch_size=pipeline_formula_batch_size,
            )
        except Exception as exc:
            logger.warning(f"FormulaService run failed, attempting rebuild and retry once: {exc}")
            if not self._rebuild_pipeline():
                raise
            return self._run_once(
                image_path,
                disable_layout=disable_layout,
                disable_preprocess=disable_preprocess,
                layout_threshold=layout_threshold,
                pipeline_formula_batch_size=pipeline_formula_batch_size,
            )

    def recognize(
        self,
        image_path: str,
        *,
        disable_layout: bool = False,
        disable_preprocess: bool = False,
        layout_formula_boxes: Optional[List[Dict[str, Any]]] = None,
        roi_source_image_path: Optional[str] = None,
        two_stage_threshold_retry: bool = True,
        primary_layout_threshold: float = 0.5,
        fallback_layout_threshold: float = 0.2,
        layout_threshold: Optional[float] = None,
        pipeline_formula_batch_size: int = 1,
    ) -> Dict[str, Any]:
        if not self._ensure_pipeline():
            return {
                "ok": False,
                "unwrapped_results": [],
                "stats": {},
                "error": f"FormulaService not ready: {self._init_error or 'unknown init error'}",
                "error_level": "hard",
                "error_code": "init_unavailable",
                "failure_stage": "init",
            }

        try:
            roi_boxes = layout_formula_boxes if isinstance(layout_formula_boxes, list) else []
            if roi_boxes:
                roi_image = roi_source_image_path or image_path
                roi_results, roi_stats, roi_kwargs = self._run_once_on_layout_rois_with_rebuild(
                    roi_image,
                    roi_boxes,
                    disable_preprocess=disable_preprocess,
                    pipeline_formula_batch_size=pipeline_formula_batch_size,
                )
                return {
                    "ok": True,
                    "stage": "roi_batch",
                    "unwrapped_results": roi_results,
                    "stats": roi_stats,
                    "predict_kwargs": roi_kwargs,
                    "error_level": "none",
                    "error_code": "",
                    "failure_stage": "",
                }

            if two_stage_threshold_retry and not disable_layout:
                primary_results, primary_stats, primary_kwargs = self._run_once_with_rebuild(
                    image_path,
                    disable_layout=disable_layout,
                    disable_preprocess=disable_preprocess,
                    layout_threshold=primary_layout_threshold,
                    pipeline_formula_batch_size=pipeline_formula_batch_size,
                )
                need_retry = (
                    primary_stats.get("layout_formula_box_count", 0) == 0
                    or primary_stats.get("formula_count", 0) == 0
                )
                if need_retry:
                    fallback_results, fallback_stats, fallback_kwargs = self._run_once_with_rebuild(
                        image_path,
                        disable_layout=disable_layout,
                        disable_preprocess=disable_preprocess,
                        layout_threshold=fallback_layout_threshold,
                        pipeline_formula_batch_size=pipeline_formula_batch_size,
                    )

                    # Only enable rescue pass when layout has detected formula regions
                    # but formula recognition produced no formula text.
                    layout_formula_regions = max(
                        int(primary_stats.get("layout_formula_box_count", 0)),
                        int(fallback_stats.get("layout_formula_box_count", 0)),
                    )
                    fallback_need_rescue = (
                        fallback_stats.get("formula_count", 0) == 0
                        and layout_formula_regions > 0
                    )
                    if fallback_need_rescue:
                        rescue_results, rescue_stats, rescue_kwargs = self._run_once_with_rebuild(
                            image_path,
                            disable_layout=True,
                            disable_preprocess=disable_preprocess,
                            layout_threshold=None,
                            pipeline_formula_batch_size=pipeline_formula_batch_size,
                        )
                        logger.info(
                            "FormulaService rescue pass (no layout) done | "
                            f"formula_count={rescue_stats.get('formula_count', 0)}"
                        )
                        return {
                            "ok": True,
                            "stage": "rescue_no_layout",
                            "unwrapped_results": rescue_results,
                            "stats": rescue_stats,
                            "predict_kwargs": rescue_kwargs,
                            "error_level": "none",
                            "error_code": "",
                            "failure_stage": "",
                        }

                    return {
                        "ok": True,
                        "stage": "fallback",
                        "unwrapped_results": fallback_results,
                        "stats": fallback_stats,
                        "predict_kwargs": fallback_kwargs,
                        "error_level": "none",
                        "error_code": "",
                        "failure_stage": "",
                    }

                return {
                    "ok": True,
                    "stage": "primary",
                    "unwrapped_results": primary_results,
                    "stats": primary_stats,
                    "predict_kwargs": primary_kwargs,
                    "error_level": "none",
                    "error_code": "",
                    "failure_stage": "",
                }

            single_results, single_stats, single_kwargs = self._run_once_with_rebuild(
                image_path,
                disable_layout=disable_layout,
                disable_preprocess=disable_preprocess,
                layout_threshold=layout_threshold,
                pipeline_formula_batch_size=pipeline_formula_batch_size,
            )
            return {
                "ok": True,
                "stage": "single",
                "unwrapped_results": single_results,
                "stats": single_stats,
                "predict_kwargs": single_kwargs,
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
                "stats": {},
                "error": f"FormulaService failed after rebuild retry: {exc}",
                "error_level": "hard" if is_gpu_runtime else "soft",
                "error_code": "gpu_runtime_error" if is_gpu_runtime else "runtime_error",
                "failure_stage": "inference",
            }


def _bbox_to_polygon_xyxy(bbox: List[int]) -> List[int]:
    x1, y1, x2, y2 = bbox
    return [x1, y1, x2, y1, x2, y2, x1, y2]


def adapt_formula_results_for_backend(
    unwrapped_results: List[Dict[str, Any]],
    page_number: int = 1,
    reading_order_start: int = 1,
) -> Dict[str, Any]:
    """Convert formula pipeline unwrapped results into backend-ready structures."""
    view_formulas: List[Dict[str, Any]] = []
    fused_formula_blocks: List[Dict[str, Any]] = []
    formula_idx = 0
    recognized_count = 0

    for result_item in unwrapped_results:
        formula_items = result_item.get("formula_res_list", [])
        if not isinstance(formula_items, list):
            formula_items = []

        if not formula_items and isinstance(result_item.get("rec_formula"), str):
            formula_items = [
                {
                    "formula_region_id": 1,
                    "rec_formula": result_item.get("rec_formula", ""),
                }
            ]

        for formula_item in formula_items:
            rec_formula = str(formula_item.get("rec_formula", "")).strip()
            if not rec_formula:
                continue

            formula_idx += 1
            recognized_count += 1
            fid = f"frm_{formula_idx:04d}"
            rid = int(formula_item.get("formula_region_id", formula_idx))

            polygon: Optional[List[int]] = None
            dt_polys = formula_item.get("dt_polys", None)
            if isinstance(dt_polys, (list, tuple)) and len(dt_polys) == 4:
                try:
                    x1, y1, x2, y2 = [int(round(float(v))) for v in dt_polys]
                    polygon = _bbox_to_polygon_xyxy([x1, y1, x2, y2])
                except Exception:
                    polygon = None

            view_item: Dict[str, Any] = {
                "id": fid,
                "kind": "formula",
                "page_number": page_number,
                "reading_order": reading_order_start + formula_idx - 1,
                "source": "formula_recognition",
                "processing_status": "recognized",
                "payload": {
                    "latex": rec_formula,
                    "mathml": None,
                },
                "formula_region_id": rid,
            }
            view_item["polygon"] = polygon if polygon is not None else []
            view_formulas.append(view_item)

            fused_item: Dict[str, Any] = {
                "block_id": fid,
                "type": "formula",
                "processing_status": "recognized",
                "source": "formula_recognition",
                "confidence": 1.0,
                "payload": {
                    "latex": rec_formula,
                    "mathml": None,
                },
                "provenance": {
                    "primary_source": "formula_recognition",
                    "primary_text": rec_formula,
                    "merge_strategy": "recognized_by_optional_engine",
                    "merged_at": None,
                    "status": "recognized",
                    "block_type": "formula",
                    "formula_region_id": rid,
                },
            }
            if polygon is not None:
                xs = [polygon[i] for i in [0, 2, 4, 6]]
                ys = [polygon[i] for i in [1, 3, 5, 7]]
                fused_item["polygon_preprocessed"] = polygon
                fused_item["bbox_preprocessed"] = [min(xs), min(ys), max(xs), max(ys)]
            else:
                fused_item["polygon_preprocessed"] = []
                fused_item["bbox_preprocessed"] = []
            fused_formula_blocks.append(fused_item)

    quality_patch = {
        "formula_blocks_total": formula_idx,
        "formula_blocks_recognized": recognized_count,
    }

    return {
        "view_formulas": view_formulas,
        "fused_formula_blocks": fused_formula_blocks,
        "quality_patch": quality_patch,
    }
