"""
Layout Analysis Service - PP-StructureV3 (single layout engine).

Note: An earlier design advertised a LayoutParser fallback engine, but it was
never implemented and a same-family DL fallback offers little value (GPU/CUDA
failures are correlated across DL engines). The multi-engine fallback path has
been removed; only PP-StructureV3 is registered. See
docs/architecture/pp-structurev3-fix-plan.md for rationale.
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from loguru import logger
import os
import inspect
import asyncio
import multiprocessing
import queue as _queue_module
import paddle
import cv2
import numpy as np



class BaseLayoutEngine(ABC):
    """Abstract base class for Layout Analysis engines"""

    # Layout element type mapping (F2: aligned to official PP-DocLayout-L 23
    # categories, see docs/architecture/pp-structurev3-official-findings.md §2).
    LAYOUT_TYPES = {
        'text': 'Text',
        'paragraph_title': 'Paragraph Title',
        'doc_title': 'Document Title',
        'title': 'Title',  # legacy alias kept for backward compat
        'abstract': 'Abstract',
        'content': 'Content',
        'figure': 'Figure',
        'figure_caption': 'Figure Caption',
        'figure_title': 'Figure Title',
        'figure_table_chart_title': 'Figure/Table/Chart Title',
        'table': 'Table',
        'table_caption': 'Table Caption',
        'header': 'Header',
        'header_image': 'Header Image',
        'footer': 'Footer',
        'footer_image': 'Footer Image',
        'footnote': 'Footnote',
        'aside_text': 'Aside Text',
        'reference': 'Reference',
        'reference_content': 'Reference Content',
        'algorithm': 'Algorithm',
        'formula': 'Formula',
        'equation': 'Equation',  # legacy alias kept for backward compat
        'formula_number': 'Formula Number',
        'inline_formula': 'Inline Formula',
        'display_formula': 'Display Formula',
        'chart': 'Chart',
        'image': 'Image',
        'picture': 'Picture',
        'seal': 'Seal',
        'number': 'Page Number',
        'list': 'List',
        'flowchart': 'Flowchart',
    }

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    async def analyze(self, file_path: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class PPStructureEngine(BaseLayoutEngine):
    """
    Primary Layout Engine - PP-StructureV3

    Advantages:
    - 10+ element types detection
    - Table structure recognition >90% accuracy
    - Formula recognition (LaTeX output)
    - Document orientation correction
    - Active community support from Baidu
    """

    def __init__(self, use_gpu: bool = False, recovery: bool = True, lang: str = "en"):
        self._engine = None
        self._ready = False
        self._use_gpu = use_gpu
        self._recovery = recovery
        self._lang = lang
        self._init_engine()

    def _init_engine(self):
        try:
            from paddleocr import PPStructureV3
            import paddleocr

            # Log version for debugging
            try:
                version = paddleocr.__version__
                logger.info(f"PaddleOCR version: {version}")
            except:
                pass

            # PPStructureV3 (3.x) initialization
            # Use minimal parameters to match test script
            init_params = {
                "device": "gpu" if self._use_gpu else "cpu",
                "lang": self._lang,
                # Unwarping applies non-linear image deformation that corrupts PPStructureV3
                # internal text-line detection, causing words to stick together in block["content"].
                # The probe confirms: use_doc_unwarping=False �?correct spacing.
                "use_doc_unwarping": False,
            }

            # Load only mandatory layout/text/table path by default.
            # Optional engines (formula/seal/chart) are disabled here and handled by dedicated services.
            # We gate kwargs by signature to stay compatible with PaddleOCR/PaddleX minor version changes.
            try:
                supported = set(inspect.signature(PPStructureV3.__init__).parameters.keys())
                optional_switches = {
                    "use_formula_recognition": False,
                    "use_seal_recognition": False,
                    "use_chart_parsing": False,
                    "use_chart_recognition": False,
                    # Keep table recognition enabled by default in layout pipeline.
                    "use_table_recognition": True,
                }
                for key, value in optional_switches.items():
                    if key in supported:
                        init_params[key] = value
                logger.info(
                    "PPStructureV3 optional switches applied: "
                    f"{ {k: init_params[k] for k in optional_switches.keys() if k in init_params} }"
                )
            except Exception as _sig_exc:
                logger.debug(f"Could not inspect PPStructureV3 signature for optional switches: {_sig_exc}")

            # Note: use_doc_orientation_classify may cause initialization errors in 3.1.1
            # Removed to match working test script configuration

            self._engine = PPStructureV3(**init_params)
            self._is_v3 = True

            self._ready = True
            logger.info(f"PPStructureV3 layout engine initialized successfully (lang={self._lang})")
        except ImportError as e:
            logger.warning(f"PaddleOCR/PPStructure not installed: {e}")
            self._ready = False
        except RuntimeError as e:
            # Handle PDX already initialized error - PaddleX should only be initialized once in main.py
            if "PDX has already been initialized" in str(e):
                logger.debug(f"PPStructureV3 PDX initialization already done by main.py")
                # Still mark as ready since models are already loaded
                self._ready = True
            else:
                logger.error(f"PP-Structure initialization failed: {e}")
                self._ready = False
        except Exception as e:
            logger.error(f"PP-Structure initialization failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def get_name(self) -> str:
        return "PP-StructureV3"

    def _reinit_engine(self):
        """Destroy and recreate the PPStructureV3 engine.

        Called automatically when a CUDA context error (e.g. CUBLAS_STATUS_NOT_INITIALIZED)
        is detected during inference.  Forcing PaddlePaddle to rebuild its internal cuBLAS
        handle is the only reliable in-process recovery for this class of GPU error.
        """
        logger.info("PPStructureV3: reinitializing engine after CUDA context error...")
        self._ready = False
        self._engine = None
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        self._init_engine()

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

    @staticmethod
    def _image_shape_hw(img_obj) -> tuple:
        """Return (height, width) for numpy/PIL-like images; (0, 0) when unknown."""
        if img_obj is None:
            return 0.0, 0.0
        try:
            if hasattr(img_obj, "shape"):
                shape = img_obj.shape
                if len(shape) >= 2:
                    return float(shape[0]), float(shape[1])
                return 0.0, 0.0
            if hasattr(img_obj, "size") and isinstance(img_obj.size, tuple) and len(img_obj.size) >= 2:
                return float(img_obj.size[1]), float(img_obj.size[0])
        except Exception:
            pass
        return 0.0, 0.0

    @staticmethod
    def _normalize_bbox_coords(bbox) -> Optional[List[float]]:
        """Flatten bbox/coordinate payloads to [x1, y1, x2, y2] when possible."""
        if bbox is None:
            return None
        try:
            import numpy as np

            if isinstance(bbox, np.ndarray):
                flat = bbox.astype(float).reshape(-1).tolist()
            elif isinstance(bbox, (list, tuple)):
                if len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
                    flat = [float(v) for v in bbox]
                elif len(bbox) == 1 and isinstance(bbox[0], (list, tuple)):
                    flat = [float(v) for v in bbox[0][:4]]
                elif len(bbox) >= 4 and isinstance(bbox[0], (list, tuple)):
                    flat = [float(v) for v in bbox[0][:4]]
                else:
                    flat = [float(v) for v in bbox[:4]]
            else:
                return None
        except Exception:
            return None

        if len(flat) < 4:
            return None
        return flat[:4]

    def _call_engine(self, img_path: str, vis_src_path: Optional[str] = None):
        """Call engine with version-compatible method"""
        if hasattr(self, '_is_v3') and self._is_v3:
            predict_kwargs = {
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
            }
            try:
                result = self._engine.predict(img_path, **predict_kwargs)
            except TypeError:
                result = self._engine.predict(img_path)
            except Exception as e:
                err = str(e)
                if "too many indices" in err or "1-dimensional" in err:
                    logger.warning(
                        f"PPStructureV3 predict failed with shape error; retrying without preprocess kwargs: {e}"
                    )
                    result = self._engine.predict(img_path)
                else:
                    raise
        else:
            # PPStructure (2.x) uses direct call
            result = self._engine(img_path)

        self._save_visualization_outputs(result, vis_src_path or img_path)
        return result

    async def analyze(self, file_path: str) -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("PP-Structure engine not ready")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return await self._analyze_pdf(file_path)
        else:
            return await self._analyze_image(file_path)

    async def _analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        import fitz
        from PIL import Image
        import numpy as np

        doc = fitz.open(pdf_path)
        page_count = len(doc)  # 保存页数，避免关闭后访问
        all_elements = []
        page_layouts = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_layout_{page_num}.png"

                # 确保图像�?RGB 格式�?通道），而不�?RGBA�?通道�?
                if pix.alpha:
                    # 如果�?alpha 通道，转换为 RGB
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                    img = img.convert("RGB")
                    img.save(img_path)
                else:
                    pix.save(img_path)

                result = self._call_engine(img_path, vis_src_path=img_path)

                page_elements = self._parse_result(result, page_num + 1)
                all_elements.extend(page_elements)

                page_layout = self._get_page_summary(page_elements)
                page_layout["page"] = page_num + 1
                page_layouts.append(page_layout)

                if os.path.exists(img_path):
                    os.remove(img_path)
        finally:
            doc.close()

        return {
            "engine": "PP-StructureV3",
            "total_pages": page_count,
            "elements": all_elements,
            "page_layouts": page_layouts,
            "summary": self._get_document_summary(all_elements)
        }

    async def _analyze_image(self, img_path: str) -> Dict[str, Any]:
        from PIL import Image

        # 确保图像是 RGB 格式（3 通道）
        img = Image.open(img_path)
        if img.mode == 'RGBA':
            # 转换�?RGB
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])  # 使用 alpha 通道作为 mask
            temp_path = f"{img_path}_rgb.png"
            rgb_img.save(temp_path)
            result = self._call_engine(temp_path, vis_src_path=temp_path)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
                temp_path = f"{img_path}_rgb.png"
                img.save(temp_path)
                result = self._call_engine(temp_path, vis_src_path=temp_path)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            else:
                result = self._call_engine(img_path, vis_src_path=img_path)

        # Extract preprocessed output image and preprocessing metadata.
        # Save output_img whenever doc_preprocessor ran (rotation OR unwarping),
        # so the fused layer always has a stable preprocessed coordinate space.
        preprocessed_path = None
        preprocessed_w = None
        preprocessed_h = None
        angle_deg = 0.0
        use_doc_unwarping = False
        use_doc_orientation_classify = True
        input_w = 0
        input_h = 0
        try:
            _first = result[0] if result else None
            if _first is not None:
                _doc_pre2 = _first.get('doc_preprocessor_res') if hasattr(_first, 'get') else None
                if _doc_pre2 is not None:
                    _ms2 = _doc_pre2.get('model_settings', {}) or {}
                    use_doc_unwarping = bool(_ms2.get('use_doc_unwarping', False))
                    use_doc_orientation_classify = bool(_ms2.get('use_doc_orientation_classify', True))
                    _raw_angle = _doc_pre2.get('angle', -1)
                    angle_deg = float(_raw_angle) if _raw_angle is not None and float(_raw_angle) >= 0 else 0.0
                    _in_img = _doc_pre2.get('input_img')
                    if _in_img is not None:
                        input_h, input_w = self._image_shape_hw(_in_img)
                    _out_img = _doc_pre2.get('output_img')
                    if _out_img is not None:
                        prep_path = f"{img_path}_preprocessed.png"
                        out_h, out_w = self._image_shape_hw(_out_img)
                        if out_h > 0 and out_w > 0:
                            cv2.imwrite(prep_path, _out_img)
                            preprocessed_path = prep_path
                            preprocessed_h, preprocessed_w = out_h, out_w
                            logger.info(
                                f"[Preprocess] Saved output_img: {prep_path} "
                                f"({preprocessed_w}x{preprocessed_h}) "
                                f"angle={angle_deg} unwarping={use_doc_unwarping}"
                            )
        except Exception as _exc2:
            logger.debug(f"[Preprocess] Failed to extract preprocessing metadata: {_exc2}")

        # Fallback: if no preprocessed image was saved, use the original image dimensions
        if input_w == 0 or input_h == 0:
            try:
                from PIL import Image as _PILImage
                with _PILImage.open(img_path) as _img_probe:
                    input_w, input_h = _img_probe.size
            except Exception:
                pass
        if preprocessed_w is None:
            preprocessed_w = input_w
            preprocessed_h = input_h

        elements = self._parse_result(result, 1)

        result_dict: Dict[str, Any] = {
            "engine": "PP-StructureV3",
            "total_pages": 1,
            "elements": elements,
            "page_layouts": [{"page": 1, **self._get_page_summary(elements)}],
            "summary": self._get_document_summary(elements),
            # Preprocessing metadata consumed by envelope_builder
            "angle_deg": angle_deg,
            "use_doc_unwarping": use_doc_unwarping,
            "use_doc_orientation_classify": use_doc_orientation_classify,
            "input_size": {"width": input_w, "height": input_h},
            "output_size": {"width": preprocessed_w or 0, "height": preprocessed_h or 0},
        }
        if preprocessed_path:
            result_dict["preprocessed_image_path"] = preprocessed_path
            result_dict["preprocessed_image_width"] = preprocessed_w
            result_dict["preprocessed_image_height"] = preprocessed_h
        return result_dict

    def _analyze_image_layout_only(self, img_path: str) -> Dict[str, Any]:
        """Single-image layout inference WITHOUT preprocessing metadata extraction.

        Used by the subprocess page-by-page PDF driver so that the multi-page
        result stays behaviorally identical to the former whole-PDF
        ``_analyze_pdf`` path (which never emitted ``preprocessed_image_path``
        / ``angle_deg`` / ``input_size`` fields).  Avoids leaking per-page
        preprocessed PNGs and keeps downstream envelope_builder behavior stable.
        """
        result = self._call_engine(img_path, vis_src_path=img_path)
        elements = self._parse_result(result, 1)
        page_layout = _compute_page_summary(elements)
        page_layout["page"] = 1
        return {"elements": elements, "page_layout": page_layout}

    def _parse_result(self, result: List[Dict], page_num: int) -> List[Dict[str, Any]]:
        """
        Parse layout elements from PPStructureV3 result.

        CRITICAL FIX FOR PaddleOCR 3.3.2 / PaddleX 3.3.12:
        PPStructureV3 returns LayoutParsingResultV2 objects, NOT plain dicts.

        LayoutParsingResultV2 structure:
        - result[0]: LayoutParsingResultV2 object
        - result[0].preds: List of predictions with type, bbox, score
        - result[0].boxes: Alternative attribute name for predictions (version-dependent)
        - result[0].html: Dict for table HTML (used by table_service)

        For layout analysis, we primarily use result[0].preds which contains:
        [
            {
                'type': 'text' | 'title' | 'table' | 'figure' | ...,
                'bbox': [x1, y1, x2, y2],
                'score': confidence_score
            },
            ...
        ]

        Args:
            result: List containing ONE LayoutParsingResultV2 object
            page_num: Page number

        Returns:
            List of parsed layout elements
        """
        elements = []

        if not result or len(result) == 0:
            logger.warning(f"Page {page_num}: Empty result from PPStructureV3")
            return elements

        first_item = result[0]

        # PaddleOCR 3.3.x / PaddleX 3.3.12 fast-path:
        # LayoutParsingResultV2 supports dict-style keys and provides structured
        # parsing_res_list blocks with accurate bbox/content.
        item_keys = []
        try:
            item_keys = list(first_item.keys())
        except (AttributeError, TypeError):
            item_keys = []

        if 'parsing_res_list' in item_keys:
            parsing_blocks = first_item.get('parsing_res_list') or []
            table_res_list = first_item.get('table_res_list') or []

            # NOTE: bboxes are kept in preprocessed coordinate space (output_img space).
            # The inverse rotation / coordinate restoration is handled by view_builder
            # (envelope_builder), not here.  This keeps the fused layer's
            # bbox_preprocessed semantically accurate regardless of rotation or unwarping.

            # Build stable table html list ordered by table_region_id.
            table_html_map = {}
            for t in table_res_list:
                if not isinstance(t, dict):
                    continue
                table_region_id = t.get('table_region_id')
                table_html = t.get('pred_html')
                if table_region_id is None or not isinstance(table_html, str):
                    continue
                if '<table' not in table_html.lower():
                    continue
                try:
                    table_html_map[int(table_region_id)] = table_html
                except Exception:
                    continue

            ordered_table_html = [h for _, h in sorted(table_html_map.items(), key=lambda kv: kv[0])]
            table_cursor = 0

            # Build a (bbox, score) list from layout_det_res.boxes so we can look up
            # the real detection confidence for each parsing block.
            # parsing_res_list items do not carry a score field themselves; the score
            # is only available in the upstream layout detection output.
            _det_score_pairs: list = []
            try:
                _layout_det = (
                    first_item.get('layout_det_res')
                    if isinstance(first_item, dict)
                    else getattr(first_item, 'layout_det_res', None)
                )
                _det_boxes = []
                if isinstance(_layout_det, dict):
                    _det_boxes = _layout_det.get('boxes', [])
                elif _layout_det is not None:
                    _det_boxes = getattr(_layout_det, 'boxes', [])
                for _box in _det_boxes:
                    if isinstance(_box, dict):
                        _coord = _box.get('coordinate', [])
                        _sc = _box.get('score', None)
                    else:
                        _coord = getattr(_box, 'coordinate', [])
                        _sc = getattr(_box, 'score', None)
                    norm_coord = self._normalize_bbox_coords(_coord)
                    if norm_coord and _sc is not None:
                        _det_score_pairs.append((norm_coord, float(_sc)))
            except Exception as _e:
                logger.debug(f"Page {page_num}: Could not build det score map: {_e}")

            for idx, block in enumerate(parsing_blocks):
                if isinstance(block, dict):
                    element_type = str(block.get('label', 'unknown')).lower()
                    bbox = block.get('bbox', [])
                    content = block.get('content', '')
                    block_text = block.get('text', '')
                    block_index = block.get('index', idx)
                    # F1: prefer official `block_order` (Enhanced XYCut reading
                    # order) over detection `index`. Falls back to idx when the
                    # field is absent (older PaddleOCR versions).
                    block_order = block.get('block_order', None)
                else:
                    element_type = str(getattr(block, 'label', 'unknown')).lower()
                    bbox = getattr(block, 'bbox', [])
                    content = getattr(block, 'content', '')
                    block_text = getattr(block, 'text', '')
                    block_index = getattr(block, 'index', idx)
                    block_order = getattr(block, 'order_index', None)
                    if block_order is None:
                        # dict-style fallback (LayoutParsingResultV2 exposes
                        # both attribute and dict access depending on version)
                        block_order = block.get('block_order', None) if isinstance(block, dict) else None

                block_text_str = str(block_text or "")
                content_str = str(content or "")
                logger.info(
                    f"[StructuredBlock] Page {page_num} Block {idx} ({element_type}): "
                    f"text='{block_text_str[:100]}' | content='{content_str[:100]}'"
                )

                norm_bbox = self._normalize_bbox_coords(bbox)
                if not norm_bbox:
                    continue

                raw_bbox = norm_bbox
                # Keep preprocessed-space bbox; view_builder applies inverse transform.
                bbox_dict = self._extract_bbox(raw_bbox)
                # Build flat polygon from bbox corners: [x0,y0, x1,y0, x1,y1, x0,y1]
                x0_p = raw_bbox[0]; y0_p = raw_bbox[1]; x1_p = raw_bbox[2]; y1_p = raw_bbox[3]
                polygon_prep = [x0_p, y0_p, x1_p, y0_p, x1_p, y1_p, x0_p, y1_p]

                # Look up the real layout detection score by bbox proximity.
                # Tolerance of 3px handles float rounding between parsing_res_list
                # and layout_det_res.boxes coordinate representations.
                _block_score = None
                for _det_coord, _det_sc in _det_score_pairs:
                    if all(abs(raw_bbox[i] - _det_coord[i]) < 3.0 for i in range(4)):
                        _block_score = _det_sc
                        break

                element = {
                    "id": f"p{page_num}_e{block_index}",
                    "page": page_num,
                    "type": element_type,
                    "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                    "bbox": bbox_dict,
                    "polygon_preprocessed": polygon_prep,
                    "confidence": float(_block_score) if _block_score is not None else 0.0,
                    # F1: carry official reading order (block_order) downstream.
                    # None when the engine did not assign one (e.g. image/figure_title).
                    "reading_order": int(block_order) if block_order is not None else None,
                }

                if isinstance(content, str) and content.strip():
                    element['text'] = self._normalize_text(content)

                if element_type == 'table' and table_cursor < len(ordered_table_html):
                    table_html = ordered_table_html[table_cursor]
                    table_cursor += 1
                    element['html'] = table_html
                    if 'text' not in element:
                        element['text'] = self._extract_table_summary_text(table_html)

                elements.append(element)

            # F1: sort by official reading order (block_order) when present,
            # falling back to (y, x) bbox order. See _layout_order.py + findings §1.
            from app.services._layout_order import sort_elements_by_reading_order, has_reading_order
            if has_reading_order(elements):
                elements = sort_elements_by_reading_order(elements)
                logger.info(f"Page {page_num}: sorted {len(elements)} elements by reading_order (block_order)")
            else:
                elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))
                logger.info(f"Page {page_num}: sorted {len(elements)} elements by (y, x) fallback (no block_order)")
            elements = self._deduplicate_elements(elements)
            logger.info(
                f"Page {page_num}: Parsed {len(elements)} elements from parsing_res_list "
                f"(tables_with_html={table_cursor})"
            )
            return elements

        # Parse table-only html output first. Some PaddleOCR/PaddleX versions
        # return html dict even when preds/boxes are empty.
        html_dict = None
        if hasattr(first_item, 'html'):
            html_dict = getattr(first_item, 'html', None)
        elif isinstance(first_item, dict):
            html_dict = first_item.get('html')

        if isinstance(html_dict, dict) and html_dict:
            page_bbox = self._infer_page_bbox(first_item)
            table_idx = 0
            for table_key, table_html in html_dict.items():
                if not isinstance(table_html, str) or '<table' not in table_html.lower():
                    continue
                table_idx += 1
                _pb = page_bbox
                _pbx0, _pby0 = float(_pb.get("x", 0)), float(_pb.get("y", 0))
                _pbx1 = _pbx0 + float(_pb.get("width", 0))
                _pby1 = _pby0 + float(_pb.get("height", 0))
                elements.append({
                    "id": f"p{page_num}_table_{table_idx}",
                    "page": page_num,
                    "type": "table",
                    "type_name": self.LAYOUT_TYPES.get("table", "Table"),
                    "bbox": page_bbox,
                    "polygon_preprocessed": [_pbx0, _pby0, _pbx1, _pby0, _pbx1, _pby1, _pbx0, _pby1],
                    "confidence": 0.01,
                    "text": self._extract_table_summary_text(table_html),
                    "html": table_html,
                    "table_key": table_key,
                    "inferred_bbox": True,
                    "overlay_excluded": True,
                })

            if table_idx > 0:
                logger.info(
                    f"Page {page_num}: Added {table_idx} table element(s) from html output "
                    f"with inferred bbox=({page_bbox['x']}, {page_bbox['y']}, "
                    f"{page_bbox['width']}, {page_bbox['height']})"
                )

        # Gather layout predictions from multiple possible fields.
        raw_predictions = None
        if hasattr(first_item, 'preds'):
            raw_predictions = first_item.preds
        elif hasattr(first_item, 'boxes'):
            raw_predictions = first_item.boxes
        elif hasattr(first_item, 'layout_dets'):
            raw_predictions = first_item.layout_dets
        elif isinstance(first_item, dict):
            raw_predictions = (
                first_item.get('preds')
                or first_item.get('boxes')
                or first_item.get('layout_dets')
                or []
            )
        elif isinstance(first_item, (list, tuple)):
            raw_predictions = list(first_item)

        layout_predictions = []
        if raw_predictions is not None:
            if isinstance(raw_predictions, list):
                layout_predictions = raw_predictions
            elif isinstance(raw_predictions, tuple):
                layout_predictions = list(raw_predictions)
            else:
                try:
                    layout_predictions = list(raw_predictions)
                except Exception:
                    logger.warning(
                        f"Page {page_num}: Predictions cannot be converted to list, type={type(raw_predictions)}"
                    )

        if not layout_predictions:
            if elements:
                logger.warning(
                    f"Page {page_num}: No layout predictions found, returning html-derived elements={len(elements)}"
                )
                return elements
            if isinstance(first_item, dict):
                logger.warning(
                    f"Page {page_num}: No layout predictions found | dict keys={list(first_item.keys())}"
                )
            else:
                logger.warning(
                    f"Page {page_num}: No layout predictions found | object type={type(first_item)}"
                )
            logger.warning(f"Page {page_num}: No layout predictions found")
            return elements

        logger.info(f"Page {page_num}: Processing {len(layout_predictions)} layout regions")

        for idx, item in enumerate(layout_predictions):
            # Handle both dict and object-style predictions
            if isinstance(item, dict):
                element_type = item.get('type', item.get('label', item.get('class_name', 'unknown')))
                bbox = item.get('bbox', item.get('coordinate', item.get('box', [])))
                score = item.get('score', 0)
                res = item.get('res', None)
            elif hasattr(item, 'type'):
                # Object-style prediction
                element_type = getattr(item, 'type', 'unknown')
                bbox = getattr(item, 'bbox', getattr(item, 'coordinate', getattr(item, 'box', [])))
                score = getattr(item, 'score', 0)
                res = getattr(item, 'res', None)
            else:
                logger.warning(f"Element {idx}: Cannot parse prediction item, type={type(item)}")
                continue

            # Skip invalid elements
            norm_bbox = self._normalize_bbox_coords(bbox)
            if not norm_bbox:
                logger.debug(f"Element {idx}: Invalid bbox {bbox}")
                continue

            _bbox_raw = norm_bbox
            _bbox_dict = self._extract_bbox(_bbox_raw)
            _bx0, _by0, _bx1, _by1 = _bbox_raw[0], _bbox_raw[1], _bbox_raw[2], _bbox_raw[3]
            element = {
                "id": f"p{page_num}_e{idx}",
                "page": page_num,
                "type": element_type,
                "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                "bbox": _bbox_dict,
                "polygon_preprocessed": [_bx0, _by0, _bx1, _by0, _bx1, _by1, _bx0, _by1],
                "confidence": float(score) if score else 0.0,
            }

            # Extract text content from OCR results
            if res is not None:
                if isinstance(res, list):
                    texts = []
                    for line in res:
                        if isinstance(line, dict) and 'text' in line:
                            texts.append(line['text'])
                        elif isinstance(line, tuple) and len(line) >= 1:
                            texts.append(line[0])
                        elif isinstance(line, str):
                            texts.append(line)

                    # Join texts appropriately based on element type
                    if element_type in ['text', 'paragraph']:
                        combined_text = ' '.join(texts)
                        element['text'] = self._normalize_text(combined_text)
                    else:
                        element['text'] = self._normalize_text('\n'.join(texts))

                elif isinstance(res, dict):
                    # For tables, store HTML separately
                    element['content'] = res
                    if 'html' in res:
                        element['html'] = res['html']
                    if 'text' in res:
                        element['text'] = self._normalize_text(res['text'])

            elements.append(element)

        # Sort by reading order (top to bottom, left to right)
        elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))

        # Apply deduplication for text elements
        elements = self._deduplicate_elements(elements)

        logger.info(f"Page {page_num}: Final {len(elements)} layout elements after processing")

        return elements

    def _infer_page_bbox(self, first_item: Any) -> Dict[str, float]:
        """Infer full-page bbox from result payload for html-only outputs."""
        width = 0.0
        height = 0.0

        img_obj = None
        if hasattr(first_item, 'img'):
            img_obj = getattr(first_item, 'img', None)
        elif isinstance(first_item, dict):
            img_obj = first_item.get('img')

        if img_obj is not None:
            try:
                # numpy-like image array
                if hasattr(img_obj, 'shape') and len(img_obj.shape) >= 2:
                    height = float(img_obj.shape[0])
                    width = float(img_obj.shape[1])
                # PIL-like image
                elif hasattr(img_obj, 'size') and isinstance(img_obj.size, tuple) and len(img_obj.size) >= 2:
                    width = float(img_obj.size[0])
                    height = float(img_obj.size[1])
            except Exception:
                pass

        if width <= 0 or height <= 0:
            # Keep non-zero fallback to ensure front-end can render visible annotation box.
            width = 1000.0
            height = 1400.0

        return {"x": 0.0, "y": 0.0, "width": width, "height": height}

    def _extract_table_summary_text(self, table_html: str) -> str:
        """Extract a short readable summary from table HTML for UI tooltip display."""
        if not table_html:
            return "Table detected"
        try:
            import re
            text = re.sub(r"<[^>]+>", " ", table_html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:220] if text else "Table detected"
        except Exception:
            return "Table detected"

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text to ensure proper spacing between words.
        This fixes issues where OCR returns text without spaces between words.
        """
        if not text:
            return text

        import re

        # First, normalize whitespace: replace multiple spaces/newlines with single space
        # but preserve intentional line breaks (double newlines)
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Preserve paragraph breaks
        text = re.sub(r'[ \t]*\n[ \t]*', ' ', text)  # Single newlines to space

        # Pattern to detect word boundaries:
        # - Lowercase followed by uppercase (e.g., "FuelSaving" -> "Fuel Saving")
        # - Letter followed by number or vice versa
        # - But preserve existing spaces and punctuation

        # Add space between lowercase letter and uppercase letter (word boundary)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

        # Add space between letter and number (if not already spaced)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)

        # Clean up multiple spaces (but preserve paragraph breaks)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\n+', '\n\n', text)  # Multiple paragraph breaks to double newline

        # Trim whitespace
        text = text.strip()

        return text

    def _extract_bbox(self, bbox: List) -> Dict[str, float]:
        if len(bbox) == 4:
            return {
                "x": float(bbox[0]),
                "y": float(bbox[1]),
                "width": float(bbox[2] - bbox[0]),
                "height": float(bbox[3] - bbox[1])
            }
        return {"x": 0, "y": 0, "width": 0, "height": 0}

    def _bbox_contains(self, parent_bbox: Dict[str, float], child_bbox: Dict[str, float], threshold: float = 0.9) -> bool:
        """
        Check if parent_bbox contains child_bbox.

        Args:
            parent_bbox: Parent bounding box with x, y, width, height
            child_bbox: Child bounding box with x, y, width, height
            threshold: Minimum overlap ratio to consider as contained (default 0.9)

        Returns:
            True if parent contains child (with threshold overlap)
        """
        # Calculate parent bounds
        parent_x1 = parent_bbox['x']
        parent_y1 = parent_bbox['y']
        parent_x2 = parent_x1 + parent_bbox['width']
        parent_y2 = parent_y1 + parent_bbox['height']

        # Calculate child bounds
        child_x1 = child_bbox['x']
        child_y1 = child_bbox['y']
        child_x2 = child_x1 + child_bbox['width']
        child_y2 = child_y1 + child_bbox['height']

        # Check if child is within parent bounds (with tolerance)
        # Use percentage-based tolerance (5% of parent dimensions)
        tolerance_x = max(parent_bbox['width'] * 0.05, 10.0)  # At least 10 pixels
        tolerance_y = max(parent_bbox['height'] * 0.05, 10.0)  # At least 10 pixels

        if (child_x1 >= parent_x1 - tolerance_x and
            child_y1 >= parent_y1 - tolerance_y and
            child_x2 <= parent_x2 + tolerance_x and
            child_y2 <= parent_y2 + tolerance_y):

            # Calculate overlap ratio (IoU - Intersection over Union of child)
            child_area = child_bbox['width'] * child_bbox['height']
            if child_area > 0:
                # Calculate intersection
                inter_x1 = max(parent_x1, child_x1)
                inter_y1 = max(parent_y1, child_y1)
                inter_x2 = min(parent_x2, child_x2)
                inter_y2 = min(parent_y2, child_y2)

                if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                    # Use intersection over child area (how much of child is covered by parent)
                    overlap_ratio = inter_area / child_area
                    if overlap_ratio >= threshold:
                        logger.debug(f"Bbox containment: parent={parent_bbox}, child={child_bbox}, overlap_ratio={overlap_ratio:.2%}")
                        return True

        return False

    def _extract_text_from_parent(self, parent_text: str, child_bbox: Dict[str, float], parent_bbox: Dict[str, float]) -> str:
        """
        Extract text for child element from parent text based on bbox position.
        This is a heuristic approach - tries to extract relevant text based on position.

        Args:
            parent_text: Full text from parent element
            child_bbox: Child element bbox
            parent_bbox: Parent element bbox

        Returns:
            Extracted text for child element
        """
        # For now, return the parent text if child text is incomplete
        # A more sophisticated approach would use OCR line positions
        # But since we're working with already extracted text, we'll use a simpler heuristic
        return parent_text

    def _deduplicate_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate elements where parent elements contain complete child elements.
        Only keep the most granular (child) elements.

        Args:
            elements: List of layout elements

        Returns:
            Deduplicated list of elements
        """
        if not elements:
            return elements

        # Only process text/paragraph elements
        text_elements = [e for e in elements if e.get('type') in ['text', 'paragraph'] and e.get('text')]
        other_elements = [e for e in elements if e.get('type') not in ['text', 'paragraph'] or not e.get('text')]

        if len(text_elements) <= 1:
            return elements

        logger.info(f"Deduplicating {len(text_elements)} text/paragraph elements")

        # Find elements to remove (parent elements that contain complete child elements)
        elements_to_remove = set()

        for i, parent_elem in enumerate(text_elements):
            if i in elements_to_remove:
                continue

            parent_bbox = parent_elem.get('bbox', {})
            parent_text = parent_elem.get('text', '')

            if not parent_text or not parent_bbox.get('width') or not parent_bbox.get('height'):
                continue

            # Find child elements contained in this parent
            contained_children = []
            for j, child_elem in enumerate(text_elements):
                if i == j or j in elements_to_remove:
                    continue

                child_bbox = child_elem.get('bbox', {})
                child_text = child_elem.get('text', '')

                if not child_text or not child_bbox.get('width') or not child_bbox.get('height'):
                    continue

                # Check if parent contains child (use lower threshold for bbox containment)
                contains = self._bbox_contains(parent_bbox, child_bbox, threshold=0.70)
                if contains:
                    # Check if child text appears in parent text
                    # Normalize both texts for comparison
                    parent_text_normalized = parent_text.lower().strip()
                    child_text_normalized = child_text.lower().strip()

                    # If child text is a substantial substring of parent text, it's likely contained
                    if child_text_normalized and len(child_text_normalized) > 20:
                        # Strategy 1: Direct substring match (most reliable)
                        if child_text_normalized in parent_text_normalized:
                            contained_children.append((j, child_elem))
                            logger.info(f"Element {i} contains element {j} (direct text match): parent_bbox={parent_bbox}, child_bbox={child_bbox}")
                        else:
                            # Strategy 2: Word-based matching for cases where text might be slightly different
                            child_words = child_text_normalized.split()
                            if len(child_words) > 5:
                                # Check if at least 60% of child words appear in parent (more lenient)
                                matching_words = sum(1 for word in child_words[:20] if word in parent_text_normalized)
                                word_match_ratio = matching_words / len(child_words[:20]) if child_words[:20] else 0
                                if word_match_ratio >= 0.6 and matching_words >= 8:
                                    contained_children.append((j, child_elem))
                                    logger.info(f"Element {i} contains element {j} (word match: {matching_words}/{len(child_words[:20])} words, {word_match_ratio:.1%}): parent_bbox={parent_bbox}, child_bbox={child_bbox}")

            # If parent contains multiple complete children, remove the parent
            # Keep only the child elements
            if len(contained_children) >= 2:
                # Verify children are complete (not just partial matches)
                complete_children = []
                for child_idx, child_elem in contained_children:
                    child_text = child_elem.get('text', '')
                    # Check if child text looks complete (ends with punctuation or is substantial)
                    # More lenient criteria: at least 30 chars and either ends with punctuation or has >8 words
                    if (len(child_text) > 30 and
                        (child_text[-1] in '.!?;' or
                         len(child_text.split()) > 8)):
                        complete_children.append(child_idx)
                        logger.debug(f"  Child {child_idx} is complete: length={len(child_text)}, words={len(child_text.split())}")

                # If we have at least 2 complete children, remove the parent
                if len(complete_children) >= 2:
                    elements_to_remove.add(i)
                    logger.info(f"Removing parent element {i} (text: {parent_text[:80]}...) that contains {len(complete_children)} complete child elements")
                    for child_idx in complete_children:
                        logger.info(f"  - Keeping child element {child_idx} (text: {text_elements[child_idx].get('text', '')[:80]}...)")

        # Remove parent elements and keep children
        filtered_elements = []
        for i, elem in enumerate(text_elements):
            if i not in elements_to_remove:
                filtered_elements.append(elem)

        logger.info(f"After deduplication: {len(filtered_elements)} text/paragraph elements (removed {len(elements_to_remove)} parent elements)")

        # Combine with other elements
        result = filtered_elements + other_elements

        # Sort again by reading order
        result.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))

        return result

    def _get_page_summary(self, elements: List[Dict]) -> Dict[str, int]:
        return _compute_page_summary(elements)

    def _get_document_summary(self, elements: List[Dict]) -> Dict[str, Any]:
        return _compute_document_summary(elements)


def _compute_page_summary(elements: List[Dict]) -> Dict[str, int]:
    """Count element types for a single page (module-level, worker/main agnostic)."""
    summary: Dict[str, int] = {}
    for elem in elements:
        elem_type = elem['type']
        summary[elem_type] = summary.get(elem_type, 0) + 1
    return summary


def _compute_document_summary(elements: List[Dict]) -> Dict[str, Any]:
    """Aggregate element-type counts across the whole document."""
    type_counts: Dict[str, int] = {}
    for elem in elements:
        elem_type = elem['type']
        type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

    return {
        "total_elements": len(elements),
        "type_counts": type_counts,
        "has_tables": type_counts.get('table', 0) > 0,
        "has_figures": type_counts.get('figure', 0) > 0,
        "has_formulas": type_counts.get('equation', 0) > 0,
    }


def _truncate_error(err: str, limit: int = 400) -> str:
    """Keep worker/page error strings short enough for JSON and logs."""
    text = (err or "").strip() or "unknown error"
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _build_pdf_layout_result(
    page_count: int,
    all_elements: List[Dict[str, Any]],
    page_layouts: List[Dict[str, Any]],
    failed_pages: List[int],
    failed_page_errors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assemble a multi-page layout dict.

    ``total_pages`` is the PDF page count, not the number of successful
    pages. Using ``len(page_layouts)`` hid full-document failures as
    ``total_pages=0``.
    """
    return {
        "engine": "PP-StructureV3",
        "total_pages": page_count,
        "elements": all_elements,
        "page_layouts": page_layouts,
        "summary": _compute_document_summary(all_elements),
        "failed_pages": failed_pages,
        "failed_page_errors": failed_page_errors or [],
    }


def _invoke_worker_command(engine, cmd: str, file_path: str):
    """Dispatch one worker command, sync or async depending on the method.

    ``_analyze_image`` / ``_analyze_pdf`` are coroutines and must be driven
    with ``asyncio.run``. ``_analyze_image_layout_only`` is synchronous.
    Wrapping a sync call in ``asyncio.run(...)`` evaluates the call first
    (so inference may run) then raises ``ValueError: a coroutine was
    expected`` — every PDF page was recorded as failed.

    Official: ``asyncio.run`` requires a coroutine object
    (https://docs.python.org/3.11/library/asyncio-runner.html#asyncio.run).
    """
    if cmd == "analyze_image_layout":
        fn = engine._analyze_image_layout_only
    elif cmd == "analyze_image":
        fn = engine._analyze_image
    elif cmd == "analyze":
        ext = os.path.splitext(file_path)[1].lower()
        fn = engine._analyze_pdf if ext == ".pdf" else engine._analyze_image
    else:
        raise ValueError(f"Unknown PPStructureV3 worker command: {cmd}")

    if inspect.iscoroutinefunction(fn):
        return asyncio.run(fn(file_path))
    return fn(file_path)


# ---------------------------------------------------------------------------
# Subprocess worker helpers
# ---------------------------------------------------------------------------

def _ppstructure_worker_main(use_gpu: bool, lang: str, req_q, res_q):
    """
    Entry point for the PPStructureV3 worker subprocess.

    Must be a module-level function so that multiprocessing 'spawn' context
    can pickle and import it in the child process.  The child process has its
    own CUDA context; when CUDA gets corrupted the entire subprocess is killed
    and restarted, giving the next request a completely fresh GPU state.
    """
    import asyncio
    # Ensure spawned worker process does not run model host connectivity checks.
    os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLEX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    # Spawn 子进程不经过 app.main：须在此补注册 aistudio_sdk.snapshot_download shim（见 aistudio_compat）。
    from app.core.aistudio_compat import install_aistudio_snapshot_shim_for_paddlex

    install_aistudio_snapshot_shim_for_paddlex()

    try:
        engine = PPStructureEngine(use_gpu=use_gpu, lang=lang)
        res_q.put(('ready',))
    except Exception as init_err:
        import traceback as _tb
        res_q.put(('init_error', str(init_err), _tb.format_exc()))
        return

    while True:
        try:
            item = req_q.get()
        except Exception:
            break

        if not isinstance(item, tuple) or item[0] == 'stop':
            break

        cmd, file_path = item
        # Commands:
        #   ('analyze', path)             — legacy whole-file call (PDF or image)
        #   ('analyze_image', path)        — single image (one PDF page rasterized by main)
        #   ('analyze_image_layout', path) — single image, layout-only (no preprocess meta)
        try:
            result = _invoke_worker_command(engine, cmd, file_path)
            res_q.put(('ok', result))
        except Exception as e:
            import traceback as _tb
            res_q.put(('error', str(e), _tb.format_exc()))


class PPStructureSubprocessEngine(BaseLayoutEngine):
    """
    PPStructureV3 engine that runs inference inside a dedicated 'spawn'
    subprocess, completely isolating CUDA context from the main process.

    On CUDA corruption (CUBLAS_STATUS_NOT_INITIALIZED, etc.) the worker
    subprocess is killed and restarted so the next request gets a fresh GPU
    context — no manual cuBLAS handle reset required.
    """

    _CUDA_KEYWORDS = ('CUBLAS', 'cuBLAS', 'CUDA_STATUS', 'ExternalError', 'cublasCreate')

    def _init_timeout_seconds(self) -> int:
        raw = os.environ.get("APP_LAYOUT_WORKER_INIT_TIMEOUT", "").strip()
        if not raw:
            raw = os.environ.get("LAYOUT_WORKER_INIT_TIMEOUT", "").strip()
        if raw.isdigit():
            return max(30, int(raw))
        try:
            from app.core.config import settings
            return max(30, int(settings.LAYOUT_WORKER_INIT_TIMEOUT))
        except Exception:
            return 120

    _INFER_TIMEOUT = 120  # default per-page inference timeout (seconds)

    def _page_timeout_seconds(self) -> int:
        """Per-page inference timeout, configurable via env APP_LAYOUT_PAGE_TIMEOUT."""
        raw = os.environ.get("APP_LAYOUT_PAGE_TIMEOUT", "").strip()
        if raw.isdigit():
            return max(30, int(raw))
        try:
            from app.core.config import settings
            val = getattr(settings, "LAYOUT_PAGE_TIMEOUT", None)
            if val is not None:
                return max(30, int(val))
        except Exception:
            pass
        return self._INFER_TIMEOUT

    def __init__(self, use_gpu: bool = False, lang: str = "en"):
        self._use_gpu = use_gpu
        self._lang = lang
        self._ctx = multiprocessing.get_context('spawn')
        self._process = None
        self._req_q = None
        self._res_q = None
        self._ready = False
        self._infer_timeout = self._page_timeout_seconds()
        self._start_worker()

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _start_worker(self):
        self._req_q = self._ctx.Queue()
        self._res_q = self._ctx.Queue()
        self._process = self._ctx.Process(
            target=_ppstructure_worker_main,
            args=(self._use_gpu, self._lang, self._req_q, self._res_q),
            daemon=True,
        )
        self._process.start()
        logger.info(f"PPStructureV3 subprocess worker started (pid={self._process.pid})")

        try:
            msg = self._res_q.get(timeout=self._init_timeout_seconds())
        except _queue_module.Empty:
            logger.error(
                f"PPStructureV3 worker did not respond within {self._init_timeout_seconds()}s"
            )
            self._kill_worker()
            return

        if msg[0] == 'ready':
            self._ready = True
            logger.info("PPStructureV3 subprocess worker is ready")
        else:
            detail = msg[1] if len(msg) > 1 else str(msg)
            logger.error(f"PPStructureV3 worker init error: {detail}")

    def _kill_worker(self):
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=5)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=3)
        self._process = None

    def _restart_worker(self):
        logger.info("PPStructureV3: restarting subprocess worker (CUDA context recovery)...")
        self._ready = False
        self._kill_worker()
        self._start_worker()

    # ------------------------------------------------------------------
    # BaseLayoutEngine interface
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        return self._ready and self._process is not None and self._process.is_alive()

    def get_name(self) -> str:
        return "PP-StructureV3"

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _call_worker(self, file_path: str, cmd: str = 'analyze') -> Dict[str, Any]:
        """Blocking call sent to the worker subprocess (runs in thread executor).

        Args:
            file_path: Path to PDF (legacy whole-file) or image.
            cmd: Worker command — ``analyze`` (whole file), ``analyze_image``
                (single image with preprocessing metadata), or
                ``analyze_image_layout`` (single image, layout-only).
        """
        if not self.is_ready():
            raise RuntimeError("PPStructureV3 subprocess worker is not running")

        self._req_q.put((cmd, file_path))

        try:
            msg = self._res_q.get(timeout=self._infer_timeout)
        except _queue_module.Empty:
            logger.error(
                f"PPStructureV3 worker timed out after {self._infer_timeout}s (cmd={cmd}) — restarting"
            )
            self._restart_worker()
            raise RuntimeError(
                f"PPStructureV3 worker timed out after {self._infer_timeout}s; worker restarted"
            )

        if msg[0] == 'ok':
            return msg[1]

        if msg[0] == 'error':
            error_msg = msg[1]
            is_cuda = any(kw in error_msg for kw in self._CUDA_KEYWORDS)
            if is_cuda:
                logger.warning("PPStructureV3 worker CUDA error — restarting worker and retrying once...")
                self._restart_worker()
                if not self.is_ready():
                    raise RuntimeError(f"PPStructureV3 worker restart failed. Original: {error_msg}")

                # Retry once with the fresh worker
                self._req_q.put((cmd, file_path))
                try:
                    msg2 = self._res_q.get(timeout=self._infer_timeout)
                except _queue_module.Empty:
                    self._restart_worker()
                    raise RuntimeError("PPStructureV3 worker timed out on retry; restarted")

                if msg2[0] == 'ok':
                    return msg2[1]
                retry_err = msg2[1] if len(msg2) > 1 else str(msg2)
                raise RuntimeError(f"PPStructureV3 failed after worker restart: {retry_err}")

            raise RuntimeError(f"PPStructureV3 worker error: {error_msg}")

        raise RuntimeError(f"PPStructureV3 worker unexpected response: {msg}")

    def _call_worker_pdf_page_by_page(self, pdf_path: str) -> Dict[str, Any]:
        """Drive the worker one PDF page at a time from the main process.

        Rasterization happens in the main process; each page image is sent to
        the worker with the ``analyze_image_layout`` command and a per-page
        timeout. A page that times out or errors is recorded in
        ``failed_pages`` and skipped so the remaining pages still get a layout
        result — instead of failing the whole document on a single bad page.
        """
        import fitz
        from PIL import Image

        doc = fitz.open(pdf_path)
        page_count = len(doc)
        all_elements: List[Dict[str, Any]] = []
        page_layouts: List[Dict[str, Any]] = []
        failed_pages: List[int] = []
        failed_page_errors: List[Dict[str, Any]] = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_layout_{page_num}.png"

                # Ensure RGB (3 channels); PPStructureV3 expects RGB, not RGBA.
                if pix.alpha:
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                    img = img.convert("RGB")
                    img.save(img_path)
                else:
                    pix.save(img_path)

                try:
                    page_result = self._call_worker(img_path, cmd='analyze_image_layout')
                    elements = page_result.get("elements", []) or []
                    for el in elements:
                        el["page"] = page_num + 1
                    all_elements.extend(elements)

                    page_layout = page_result.get("page_layout", {}) or {}
                    page_layout["page"] = page_num + 1
                    page_layouts.append(page_layout)
                except Exception as e:
                    err_text = _truncate_error(str(e))
                    logger.warning(
                        f"PPStructureV3 page {page_num + 1}/{page_count} skipped: {err_text}"
                    )
                    failed_pages.append(page_num + 1)
                    failed_page_errors.append(
                        {"page": page_num + 1, "error": err_text}
                    )
                finally:
                    if os.path.exists(img_path):
                        try:
                            os.remove(img_path)
                        except Exception:
                            pass
        finally:
            doc.close()

        if failed_pages:
            logger.warning(
                f"PPStructureV3 skipped {len(failed_pages)}/{page_count} page(s): {failed_pages}"
            )

        return _build_pdf_layout_result(
            page_count,
            all_elements,
            page_layouts,
            failed_pages,
            failed_page_errors,
        )

    async def analyze(self, file_path: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            # Page-by-page driver: per-page timeout, skip bad pages, never
            # fail the whole document on a single slow/bad page.
            return await loop.run_in_executor(None, self._call_worker_pdf_page_by_page, file_path)
        return await loop.run_in_executor(None, self._call_worker, file_path, 'analyze')


class LayoutService:
    """
    Layout Analysis Service powered by PP-StructureV3.
    """

    def __init__(self, use_gpu: bool = False):
        self.engines: Dict[str, BaseLayoutEngine] = {}
        self.default_engine = "ppstructure"
        self._use_gpu = use_gpu
        self._init_engines()

    def _init_engines(self):
        """Initialize all available layout engines"""
        # Primary: PP-StructureV3 — wrapped in a subprocess engine so CUDA context
        # corruption is isolated and recoverable without restarting the whole server.
        pp_engine = PPStructureSubprocessEngine(use_gpu=self._use_gpu)
        if pp_engine.is_ready():
            self.engines["ppstructure"] = pp_engine

        logger.info(f"Available layout engines: {list(self.engines.keys())}")

    def is_ready(self) -> bool:
        """Check if any layout engine is available"""
        return len(self.engines) > 0

    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())

    def get_engine(self, engine_name: Optional[str] = None) -> BaseLayoutEngine:
        """Get specified engine or default/fallback"""
        if engine_name and engine_name in self.engines:
            return self.engines[engine_name]

        if self.default_engine in self.engines:
            return self.engines[self.default_engine]

        if self.engines:
            return list(self.engines.values())[0]

        raise RuntimeError("No layout engine available")

    async def analyze(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze document layout.

        Only PP-StructureV3 is registered as a layout engine. The ``engine``
        and ``fallback`` parameters are kept for backward compatibility with
        callers (e.g. the orchestrator), but with a single engine there is no
        fallback path; a failure raises directly.

        Args:
            file_path: Path to PDF or image file
            engine: Specific engine name; only ``ppstructure`` is supported.
            fallback: Kept for API compatibility; no-op with a single engine.

        Returns:
            Layout analysis result dictionary
        """
        del fallback  # no alternative layout engine to fall back to

        if engine and engine not in self.engines:
            raise RuntimeError(
                f"Requested layout engine '{engine}' is not available. "
                f"Available: {list(self.engines.keys())}"
            )

        eng_name = engine or self.default_engine
        if eng_name not in self.engines:
            # No layout engine registered at all.
            raise RuntimeError(
                f"No layout engine available (requested='{engine}', "
                f"registered={list(self.engines.keys())})"
            )

        eng = self.engines[eng_name]
        logger.info(f"Trying layout analysis with {eng.get_name()}...")
        result = await eng.analyze(file_path)
        result["engine_used"] = eng_name
        return result
