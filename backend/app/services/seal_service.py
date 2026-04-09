"""Seal recognition service for optional engines phase.

This service wraps PaddleX `seal_recognition` pipeline and provides
stable outputs for backend envelope integration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger


class SealService:
    """Optional seal recognition service with lazy pipeline initialization."""

    def __init__(self, device: Optional[str] = None):
        self._ready = False
        self._device = device or self._detect_device()
        self._pipeline = None
        self._init_error: Optional[str] = None
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
                pipeline="seal_recognition",
                device=self._device,
            )
            self._ready = True
            self._init_error = None
            logger.info(f"SealService initialized (device={self._device})")
            return True
        except Exception as exc:
            self._pipeline = None
            self._ready = False
            self._init_error = str(exc)
            logger.warning(f"SealService init failed: {exc}")
            return False

    def _ensure_pipeline(self) -> bool:
        if self._pipeline is not None and self._ready:
            return True
        return self._init_pipeline()

    def _rebuild_pipeline(self) -> bool:
        logger.warning("SealService rebuilding pipeline after failure...")
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

    def _run_once(self, image_path: str) -> List[Dict[str, Any]]:
        if not self._ensure_pipeline():
            raise RuntimeError(f"SealService not ready: {self._init_error or 'unknown init error'}")

        results = list(self._pipeline.predict(image_path))
        return [self.result_to_dict(r) for r in results]

    def _run_once_with_rebuild(self, image_path: str) -> List[Dict[str, Any]]:
        try:
            return self._run_once(image_path)
        except Exception as exc:
            logger.warning(f"SealService run failed, attempting rebuild and retry once: {exc}")
            if not self._rebuild_pipeline():
                raise
            return self._run_once(image_path)

    @staticmethod
    def _extract_seal_items(result_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        seal_items = result_item.get("seal_res_list", [])
        if isinstance(seal_items, list):
            return [it for it in seal_items if isinstance(it, dict)]

        # Fallback: normalize single-result schema into list form.
        if any(k in result_item for k in ("label", "shape", "text_on_seal", "rec_text", "bbox", "dt_polys")):
            return [result_item]

        return []

    def _collect_stats(self, unwrapped_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        layout_seal_boxes = 0
        recognized_seals = 0

        for item in unwrapped_results:
            boxes = item.get("layout_det_res", {}).get("boxes", []) if isinstance(item.get("layout_det_res", {}), dict) else []
            if isinstance(boxes, list):
                for box in boxes:
                    if not isinstance(box, dict):
                        continue
                    label = str(box.get("label", "")).lower()
                    if label in {"seal", "stamp"}:
                        layout_seal_boxes += 1

            for seal_item in self._extract_seal_items(item):
                label = str(seal_item.get("label") or seal_item.get("category") or "").strip()
                text_on_seal = str(seal_item.get("text_on_seal") or seal_item.get("rec_text") or seal_item.get("text") or "").strip()
                if label or text_on_seal:
                    recognized_seals += 1

        return {
            "seal_count": recognized_seals,
            "layout_seal_box_count": layout_seal_boxes,
        }

    def recognize(self, image_path: str) -> Dict[str, Any]:
        if not self._ensure_pipeline():
            return {
                "ok": False,
                "unwrapped_results": [],
                "stats": {},
                "error": f"SealService not ready: {self._init_error or 'unknown init error'}",
                "error_level": "hard",
                "error_code": "init_unavailable",
                "failure_stage": "init",
            }

        try:
            unwrapped_results = self._run_once_with_rebuild(image_path)
            stats = self._collect_stats(unwrapped_results)
            return {
                "ok": True,
                "stage": "single",
                "unwrapped_results": unwrapped_results,
                "stats": stats,
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
                "error": f"SealService failed after rebuild retry: {exc}",
                "error_level": "hard" if is_gpu_runtime else "soft",
                "error_code": "gpu_runtime_error" if is_gpu_runtime else "runtime_error",
                "failure_stage": "inference",
            }


def _to_polygon(item: Dict[str, Any]) -> List[int]:
    dt_polys = item.get("dt_polys")
    if isinstance(dt_polys, (list, tuple)):
        if len(dt_polys) == 8:
            try:
                return [int(round(float(v))) for v in dt_polys]
            except Exception:
                return []
        if len(dt_polys) == 4:
            try:
                x1, y1, x2, y2 = [int(round(float(v))) for v in dt_polys]
                return [x1, y1, x2, y1, x2, y2, x1, y2]
            except Exception:
                return []

    bbox = item.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x1, y1, x2, y2 = [int(round(float(v))) for v in bbox]
            return [x1, y1, x2, y1, x2, y2, x1, y2]
        except Exception:
            return []

    return []


def adapt_seal_results_for_backend(
    unwrapped_results: List[Dict[str, Any]],
    page_number: int = 1,
    reading_order_start: int = 1,
) -> Dict[str, Any]:
    """Convert seal pipeline unwrapped results into backend-ready structures."""
    view_seals: List[Dict[str, Any]] = []
    fused_seal_blocks: List[Dict[str, Any]] = []
    seal_idx = 0

    for result_item in unwrapped_results:
        seal_items = result_item.get("seal_res_list", [])
        if not isinstance(seal_items, list):
            if any(k in result_item for k in ("label", "shape", "text_on_seal", "rec_text", "bbox", "dt_polys")):
                seal_items = [result_item]
            else:
                seal_items = []

        for seal_item in seal_items:
            if not isinstance(seal_item, dict):
                continue

            label = str(seal_item.get("label") or seal_item.get("category") or "seal").strip() or "seal"
            text_on_seal = str(seal_item.get("text_on_seal") or seal_item.get("rec_text") or seal_item.get("text") or "").strip()
            shape = str(seal_item.get("shape") or "").strip()
            score = float(seal_item.get("score") or seal_item.get("confidence") or 0.0)

            if not label and not text_on_seal:
                continue

            seal_idx += 1
            sid = f"seal_{seal_idx:04d}"
            polygon = _to_polygon(seal_item)

            view_item: Dict[str, Any] = {
                "id": sid,
                "kind": "seal",
                "page_number": page_number,
                "reading_order": reading_order_start + seal_idx - 1,
                "source": "seal_recognition",
                "processing_status": "recognized",
                "payload": {
                    "label": label,
                    "shape": shape,
                    "text_on_seal": text_on_seal,
                    "confidence": score,
                },
            }
            view_item["polygon"] = polygon if polygon else []
            view_seals.append(view_item)

            fused_item: Dict[str, Any] = {
                "block_id": sid,
                "type": "seal",
                "processing_status": "recognized",
                "source": "seal_recognition",
                "confidence": score,
                "payload": {
                    "label": label,
                    "shape": shape,
                    "text_on_seal": text_on_seal,
                },
                "provenance": {
                    "primary_source": "seal_recognition",
                    "primary_text": text_on_seal,
                    "merge_strategy": "recognized_by_optional_engine",
                    "merged_at": None,
                    "status": "recognized",
                    "block_type": "seal",
                },
            }

            if polygon:
                xs = [polygon[i] for i in [0, 2, 4, 6]]
                ys = [polygon[i] for i in [1, 3, 5, 7]]
                fused_item["polygon_preprocessed"] = polygon
                fused_item["bbox_preprocessed"] = [min(xs), min(ys), max(xs), max(ys)]
            else:
                fused_item["polygon_preprocessed"] = []
                fused_item["bbox_preprocessed"] = []
            fused_seal_blocks.append(fused_item)

    recognized_count = len(fused_seal_blocks)
    quality_patch = {
        "seal_blocks_total": seal_idx,
        "seal_blocks_recognized": recognized_count,
        "seal_count": recognized_count,
    }

    return {
        "view_seals": view_seals,
        "fused_seal_blocks": fused_seal_blocks,
        "quality_patch": quality_patch,
    }
