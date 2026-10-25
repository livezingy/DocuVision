"""Formula recognition service facade for optional engines phase.

This facade keeps `FormulaService` (`__init__` / status / the `recognize`
two-stage-threshold orchestration) and composes the engine mixin; the engine
lifecycle and inference chains live in `formula_engine.py`, the pure backend
adapters in `formula_adapt.py` (S1 batch 7 split of the former monolith).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.formula_adapt import adapt_formula_results_for_backend  # noqa: F401 (re-export; steps/envelope.py lazy-imports it from here)
from app.services.formula_engine import FormulaEngineMixin


class FormulaService(FormulaEngineMixin):
    """Optional formula recognition service with two-stage threshold retry."""

    def __init__(self, device: Optional[str] = None, model_level_backend: str = "auto"):
        self._ready = False
        self._device = device or self._detect_device()
        # model_level_backend: 'auto'|'pipeline'|'formulanet' - skeleton support
        self.model_level_backend = (str(model_level_backend or "auto")).strip().lower()
        self._pipeline = None
        self._init_error: Optional[str] = None
        # Lazy init: delay model loading until first recognize() call.
        self._init_attempted = False

    def is_ready(self) -> bool:
        return self._ready and self._pipeline is not None

    def get_status(self) -> Dict[str, Any]:
        return {
            "ready": self.is_ready(),
            "device": self._device,
            "init_error": self._init_error,
        }

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
        # Determine ROI boxes early so we can attempt model-level inference
        # (skeleton) before triggering pipeline lazy-init.
        roi_boxes = layout_formula_boxes if isinstance(layout_formula_boxes, list) else []

        # Try model-level backend on ROIs first when requested/auto.
        if roi_boxes and self.model_level_backend in ("auto", "formulanet", "model"):
            model_try = self._try_model_level_on_rois(
                roi_source_image_path or image_path,
                roi_boxes,
                disable_preprocess=disable_preprocess,
                pipeline_formula_batch_size=pipeline_formula_batch_size,
            )
            if isinstance(model_try, dict):
                return model_try

        # Fallback: ensure pipeline (lazy init on first use)
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
            # roi_boxes variable computed above
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
