"""PP-StructureV3 layout engine core: abstract base + in-process engine.

S1 batch-6 verbatim extraction out of layout_service.py: BaseLayoutEngine and the
PPStructureEngine core (init/engine lifecycle, image/PDF analyze chain, page and
document summaries) move byte-identical; the parse and visualization method families
live in sibling mixins (layout_pp_parse / layout_pp_visualization) composed into the
base list (same shape as the batch-5 table split). Deferred heavy imports (fitz/PIL/
paddleocr) travel verbatim inside the moved bodies; the subprocess-isolation family
lives in layout_engine_subprocess.py.
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from loguru import logger
import os
import inspect
import cv2

from app.services._layout_geometry import _LayoutGeometryMixin
from app.services.layout_pp_parse import LayoutPPParseMixin
from app.services.layout_pp_visualization import LayoutPPVisualizationMixin


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


class PPStructureEngine(_LayoutGeometryMixin, LayoutPPParseMixin, LayoutPPVisualizationMixin, BaseLayoutEngine):
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
            # Handle PDX already initialized error - PaddleX should only be initialized once (app.core.runtime banner, P-039)
            if "PDX has already been initialized" in str(e):
                logger.debug(f"PPStructureV3 PDX initialization already done by app.core.runtime")
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

    def _call_engine(self, img_path: str, vis_src_path: Optional[str] = None):
        """Call engine with version-compatible method.

        Do NOT pass ``use_doc_orientation_classify`` / ``use_doc_unwarping`` as
        predict kwargs. ``use_doc_unwarping=False`` is already set in
        ``_init_engine`` init_params, and passing
        ``use_doc_orientation_classify=False`` at predict time triggers a
        PaddleX code path that produces empty layout detections (1D boxes
        array), causing ``IndexError: too many indices for array`` in NMS
        (PaddleOCR issue #17446, unfixed in paddleocr 3.3.2 / paddlex 3.3.12).
        The first failed predict also corrupts the pipeline's internal
        state, so a retry without kwargs on the same instance still fails.
        Calling ``predict(img_path)`` with no overrides (using init-time
        defaults) avoids the bug entirely — confirmed by Cloud diagnostic
        comparing predict-with-kwargs (fails) vs predict-without-kwargs
        (succeeds) on the same page image.
        """
        if hasattr(self, '_is_v3') and self._is_v3:
            result = self._engine.predict(img_path)
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

    def _analyze_image_layout_only(self, img_path: str, page_num: int = 1) -> Dict[str, Any]:
        """Single-image layout inference WITHOUT preprocessing metadata extraction.

        Used by the subprocess page-by-page PDF driver so that the multi-page
        result stays behaviorally identical to the former whole-PDF
        ``_analyze_pdf`` path (which never emitted ``preprocessed_image_path``
        / ``angle_deg`` / ``input_size`` fields).  Avoids leaking per-page
        preprocessed PNGs and keeps downstream envelope_builder behavior stable.

        ``page_num`` is the 1-based page number; it flows into element ids
        (``p{page_num}_e{n}``) and ``page`` fields so multi-page PDFs produce
        globally-unique ids instead of every page reusing ``p1_e*``.
        """
        result = self._call_engine(img_path, vis_src_path=img_path)
        elements = self._parse_result(result, page_num)
        page_layout = _compute_page_summary(elements)
        page_layout["page"] = page_num
        return {"elements": elements, "page_layout": page_layout}

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
