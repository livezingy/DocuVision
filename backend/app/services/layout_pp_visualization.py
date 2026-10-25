"""PP-StructureV3 visualization mixin (S1 batch-6 verbatim extraction): the rotation
rebuild / inverse-transform helpers and the block-box visualization savers move
byte-identical from the PPStructureEngine class. _image_shape_hw and
_normalize_bbox_coords are host-class / sibling-mixin members reached through the
MRO, same pattern as the parse mixin."""

from typing import Dict, Any
from loguru import logger
import os
import cv2
import numpy as np


class LayoutPPVisualizationMixin:
    """Rotation-aware block visualization for PP-StructureV3 outputs."""

    @staticmethod
    def _build_rotation_matrix(angle, orig_h, orig_w):
        """
        Rebuild the affine matrix used by rotate_image (including padding offset).
        angle = -1 or 0 returns None (no rotation).
        """
        if angle < 1e-7:
            return None, orig_w, orig_h
        center = (orig_w / 2, orig_h / 2)
        matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        cos = np.abs(matrix[0, 0])
        sin = np.abs(matrix[0, 1])
        new_w = int((orig_h * sin) + (orig_w * cos))
        new_h = int((orig_h * cos) + (orig_w * sin))
        matrix[0, 2] += (new_w - orig_w) / 2
        matrix[1, 2] += (new_h - orig_h) / 2
        return matrix, new_w, new_h

    @staticmethod
    def _transform_bbox_inv(bbox, matrix_inv):
        """
        Map [x1,y1,x2,y2] back to original coordinates via inverse affine matrix.
        """
        x1, y1, x2, y2 = bbox
        corners = np.array(
            [
                [x1, y1, 1],
                [x2, y1, 1],
                [x2, y2, 1],
                [x1, y2, 1],
            ],
            dtype=np.float64,
        )
        transformed = corners @ matrix_inv.T
        x_coords = transformed[:, 0]
        y_coords = transformed[:, 1]
        return (
            float(np.min(x_coords)),
            float(np.min(y_coords)),
            float(np.max(x_coords)),
            float(np.max(y_coords)),
        )

    def save_pp_structure_v3_block_vis(self, results, src_image_path: str, out_image_path: str) -> Dict[str, Any]:
        """
        Draw block bounding boxes from pipeline.predict results and save visualization.
        Automatically handles coordinate offsets caused by document preprocessing:
          - Rotation only: invert affine matrix and map boxes back to original coordinates.
          - Unwarping enabled: no exact inverse warp map, draw on output_img instead.
        """
        if not isinstance(results, (list, tuple)):
            results = list(results)
        if not results:
            raise ValueError("results is empty")

        res = results[0]

        doc_pre = res.get("doc_preprocessor_res", None)
        use_unwarping = False
        angle = -1
        orig_h, orig_w = None, None

        if doc_pre is not None:
            model_settings = doc_pre.get("model_settings", {})
            use_unwarping = model_settings.get("use_doc_unwarping", False)
            angle = doc_pre.get("angle", -1)
            orig_img = doc_pre.get("input_img")
            if orig_img is not None:
                orig_h, orig_w = self._image_shape_hw(orig_img)

        if doc_pre is None:
            base_img = cv2.imread(src_image_path)
            if base_img is None:
                raise ValueError(f"Unable to read source image: {src_image_path}")
            matrix_inv = None
            warn_msg = None
        elif use_unwarping:
            output_img = doc_pre.get("output_img")
            if output_img is None:
                raise ValueError("doc_preprocessor_res missing output_img for unwarping visualization")
            out_h, out_w = self._image_shape_hw(output_img)
            if out_h <= 0 or out_w <= 0:
                raise ValueError("doc_preprocessor output_img has invalid shape")
            if hasattr(output_img, "shape") and len(output_img.shape) >= 3 and output_img.shape[2] == 3:
                base_img = cv2.cvtColor(output_img, cv2.COLOR_RGB2BGR)
            else:
                base_img = output_img.copy() if hasattr(output_img, "copy") else cv2.imread(src_image_path)
            matrix_inv = None
            warn_msg = (
                "[WARN] use_doc_unwarping=True: no inverse warp map available; "
                "boxes are drawn on preprocessed output_img, not on original input image."
            )
        else:
            if orig_img is None or orig_h <= 0 or orig_w <= 0:
                base_img = cv2.imread(src_image_path)
                if base_img is None:
                    raise ValueError(f"Unable to read source image: {src_image_path}")
                matrix_inv = None
                warn_msg = None
            else:
                if hasattr(orig_img, "shape") and len(orig_img.shape) >= 3 and orig_img.shape[2] == 3:
                    base_img = cv2.cvtColor(orig_img, cv2.COLOR_RGB2BGR)
                else:
                    base_img = orig_img.copy() if hasattr(orig_img, "copy") else cv2.imread(src_image_path)
                matrix, _, _ = self._build_rotation_matrix(angle, orig_h, orig_w)
                matrix_inv = cv2.invertAffineTransform(matrix) if matrix is not None else None
                warn_msg = None

        if warn_msg:
            logger.warning(warn_msg)

        h_canvas, w_canvas = base_img.shape[:2]

        blocks = res.get("parsing_res_list", [])
        use_parsing_blocks = bool(blocks)
        if not use_parsing_blocks:
            blocks = res.get("layout_det_res", {}).get("boxes", [])

        text_labels = {
            "text", "doc_title", "paragraph_title", "abstract", "content",
            "reference", "algorithm", "formula", "abstract_title",
            "reference_title", "content_title", "header", "footer",
            "footnote", "aside_text", "number",
        }
        table_labels = {"table"}
        image_labels = {"image", "figure", "chart", "flowchart", "seal"}

        color_map = {
            "text": (0, 255, 0),
            "table": (255, 0, 0),
            "image": (0, 165, 255),
        }

        cnt = {"text": 0, "table": 0, "image": 0}

        for b in blocks:
            if use_parsing_blocks:
                label = getattr(b, "label", None)
                bbox = getattr(b, "bbox", None)
            else:
                label = b.get("label", None)
                bbox = b.get("coordinate", None)

            norm_bbox = self._normalize_bbox_coords(bbox)
            if not norm_bbox:
                continue

            if label in text_labels:
                cls = "text"
            elif label in table_labels:
                cls = "table"
            elif label in image_labels:
                cls = "image"
            else:
                continue

            x1, y1, x2, y2 = norm_bbox
            if matrix_inv is not None:
                x1, y1, x2, y2 = self._transform_bbox_inv((x1, y1, x2, y2), matrix_inv)

            x1 = max(0, min(int(x1), w_canvas - 1))
            y1 = max(0, min(int(y1), h_canvas - 1))
            x2 = max(0, min(int(x2), w_canvas - 1))
            y2 = max(0, min(int(y2), h_canvas - 1))
            if x2 <= x1 or y2 <= y1:
                continue

            color = color_map[cls]
            cv2.rectangle(base_img, (x1, y1), (x2, y2), color, 2)
            tag = f"{cls}:{label}"
            ty = y1 - 8 if y1 - 8 > 10 else y1 + 18
            cv2.putText(base_img, tag, (x1, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)
            cnt[cls] += 1

        out_dir = os.path.dirname(out_image_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        if not cv2.imwrite(out_image_path, base_img):
            raise RuntimeError(f"Failed to save visualization image: {out_image_path}")

        return {
            "out_image_path": out_image_path,
            "text_count": cnt["text"],
            "table_count": cnt["table"],
            "image_count": cnt["image"],
            "used_parsing_blocks": use_parsing_blocks,
            "has_unwarping": use_unwarping,
            "rotation_angle": angle,
        }

    def _save_visualization_outputs(self, result: Any, img_path: str) -> None:
        """Best-effort save block visualization for PPStructureV3 prediction outputs."""
        # Use file-relative path to support both local and cloud environments
        # __file__ points to: {project_root}/backend/app/services/layout_service.py
        # We need to go up 3 levels to reach project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(project_root, "outputs", "ppstructure_visualizations", "blocks")

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create PPStructure output directory {output_dir}: {e}")
            return

        image_stem = os.path.splitext(os.path.basename(img_path))[0]
        out_image_path = os.path.join(output_dir, f"{image_stem}_ppv3_blocks.png")

        try:
            vis_info = self.save_pp_structure_v3_block_vis(
                results=result,
                src_image_path=img_path,
                out_image_path=out_image_path,
            )
            logger.info(
                "PPStructure block visualization saved: "
                f"{vis_info['out_image_path']} | text={vis_info['text_count']} "
                f"table={vis_info['table_count']} image={vis_info['image_count']} "
                f"use_parsing={vis_info['used_parsing_blocks']}"
            )
        except Exception as e:
            logger.debug(f"PPStructure block visualization failed for {img_path}: {e}")
