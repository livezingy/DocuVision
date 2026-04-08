"""Formula recognition service for optional engines phase.

This service wraps PaddleX `formula_recognition` pipeline and provides
stable outputs for backend envelope integration.
"""

from __future__ import annotations

import collections
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


class FormulaService:
    """Optional formula recognition service with two-stage threshold retry."""

    def __init__(self, device: Optional[str] = None):
        self._ready = False
        self._device = device or self._detect_device()
        self._pipeline = None
        self._init_error: Optional[str] = None
        self._init_pipeline()

    @staticmethod
    def _detect_device() -> str:
        try:
            import paddle

            if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
                return "gpu"
        except Exception:
            pass
        return "cpu"

    def _init_pipeline(self) -> None:
        try:
            from paddlex import create_pipeline

            self._pipeline = create_pipeline(
                pipeline="formula_recognition",
                device=self._device,
            )
            self._ready = True
            logger.info(f"FormulaService initialized (device={self._device})")
        except Exception as exc:
            self._pipeline = None
            self._ready = False
            self._init_error = str(exc)
            logger.warning(f"FormulaService init failed: {exc}")

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
        if not self.is_ready():
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

    def recognize(
        self,
        image_path: str,
        *,
        disable_layout: bool = False,
        disable_preprocess: bool = False,
        two_stage_threshold_retry: bool = True,
        primary_layout_threshold: float = 0.5,
        fallback_layout_threshold: float = 0.2,
        layout_threshold: Optional[float] = None,
        pipeline_formula_batch_size: int = 1,
    ) -> Dict[str, Any]:
        if not self.is_ready():
            return {
                "ok": False,
                "unwrapped_results": [],
                "stats": {},
                "error": f"FormulaService not ready: {self._init_error or 'unknown init error'}",
            }

        if two_stage_threshold_retry and not disable_layout:
            primary_results, primary_stats, primary_kwargs = self._run_once(
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
                fallback_results, fallback_stats, fallback_kwargs = self._run_once(
                    image_path,
                    disable_layout=disable_layout,
                    disable_preprocess=disable_preprocess,
                    layout_threshold=fallback_layout_threshold,
                    pipeline_formula_batch_size=pipeline_formula_batch_size,
                )

                # Rescue pass: if layout still cannot find formulas (e.g., classified as chart/image),
                # run formula model directly on the full page without layout detection.
                fallback_need_rescue = (
                    fallback_stats.get("formula_count", 0) == 0
                    and fallback_stats.get("layout_formula_box_count", 0) == 0
                )
                if fallback_need_rescue:
                    rescue_results, rescue_stats, rescue_kwargs = self._run_once(
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
                    }

                return {
                    "ok": True,
                    "stage": "fallback",
                    "unwrapped_results": fallback_results,
                    "stats": fallback_stats,
                    "predict_kwargs": fallback_kwargs,
                }

            return {
                "ok": True,
                "stage": "primary",
                "unwrapped_results": primary_results,
                "stats": primary_stats,
                "predict_kwargs": primary_kwargs,
            }

        single_results, single_stats, single_kwargs = self._run_once(
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
            if polygon is not None:
                view_item["polygon"] = polygon
            view_formulas.append(view_item)

            fused_item: Dict[str, Any] = {
                "block_id": fid,
                "type": "formula",
                "processing_status": "recognized",
                "source": "formula_recognition",
                "confidence": None,
                "payload": {
                    "latex": rec_formula,
                    "mathml": None,
                },
                "provenance": None,
            }
            if polygon is not None:
                xs = [polygon[i] for i in [0, 2, 4, 6]]
                ys = [polygon[i] for i in [1, 3, 5, 7]]
                fused_item["polygon_preprocessed"] = polygon
                fused_item["bbox_preprocessed"] = [min(xs), min(ys), max(xs), max(ys)]
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
