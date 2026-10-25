"""Formula engine mixin — PaddleX formula_recognition lifecycle and inference.

Split from the former formula_service.py monolith (S1 batch 7); the service
facade keeps `FormulaService` and composes this mixin into its base list so
monkeypatch points (`_ensure_pipeline` / `_run_once_with_rebuild`) stay on the
class MRO. All paddle/paddlex imports live here and stay lazy (inside
`_detect_device` / `_init_pipeline`); cv2 is the only top-level heavy import.
"""

from __future__ import annotations

import collections
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple

import cv2

from loguru import logger


class FormulaEngineMixin:
    """Engine lifecycle (lazy init / rebuild) plus the whole-page and ROI inference chains."""

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


    def _try_model_level_on_rois(
        self,
        image_path: str,
        layout_formula_boxes: List[Dict[str, Any]],
        *,
        disable_preprocess: bool,
        pipeline_formula_batch_size: int,
    ) -> Optional[Dict[str, Any]]:
        """Skeleton: attempt model-level inference on ROI crops.

        Currently a stub that logs intent and returns None to indicate
        fallback to existing pipeline behavior. Future implementation
        should return a dict matching `recognize`'s successful shape.
        """
        try:
            if self.model_level_backend == "auto":
                # auto: prefer model-level when implemented, else fallback
                logger.info("FormulaService model-level attempt (auto) - not implemented, falling back to pipeline")
                return None
            if self.model_level_backend in ("formulanet", "model"):
                logger.info("FormulaService model-level attempt (requested) - not implemented, falling back")
                return None
        except Exception:
            logger.exception("FormulaService model-level attempt failed unexpectedly")
        return None


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

