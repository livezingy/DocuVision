"""Task content routes: result / layout / blocks / figures / page-image / export.

Moved from main.py (v1.8.2 C2). No ``prefix`` on the APIRouter — paths are
written in full so the OpenAPI contract is unchanged.

Behaviour fix (approved, option B): the ``/layout`` empty-result branch had a
lost newline that commented out ``from app.models.layout_result import
LayoutAnalysisResult`` (→ NameError, surfaced as HTTP 500). The newline is
restored, and three pre-existing U+FFFD mojibake characters (docstring + two
log strings) are cleaned.
"""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from loguru import logger

from app.core.config import settings
from app.core.runtime import export_service, tasks, unified_layout_service
from app.services.pack_export_service import PackTooLargeError, build_task_pack_zip

router = APIRouter()


@router.get("/api/v1/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed")
    return task["result"]

@router.get("/api/v1/tasks/{task_id}/layout")
async def get_unified_layout_analysis(task_id: str, page_number: int = 1):
    """
    获取统一格式的版面分析结果
    Returns unified layout analysis result in standard format
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logger.info(f"[Layout API] Fetching layout analysis for task {task_id}")

    # 从task结果中获取原始的layout数据
    result = task.get("result", {})
    file_path = task.get("file_path")

    logger.info(f"[Layout API] Result keys: {list(result.keys())}")

    try:
        # 根据文件类型获取image_info
        image_info = {}
        if file_path:
            from PIL import Image as PILImage
            try:
                with PILImage.open(file_path) as img:
                    image_info = {
                        "width": img.width,
                        "height": img.height,
                        "format": img.format
                    }
                logger.info(f"[Layout API] Image info: {image_info}")
            except Exception as e:
                logger.warning(f"[Layout API] Failed to get image info: {e}")
                image_info = {"width": 0, "height": 0}

        # 检查是否有layout数据
        layout_result = result.get("layout")

        if not layout_result:
            logger.warning(f"[Layout API] No layout data in result for task {task_id}")
            # 返回空结果而不是错误
            from app.models.layout_result import LayoutAnalysisResult
            empty_result = LayoutAnalysisResult()
            return empty_result.to_dict()

        logger.info(f"[Layout API] Layout data type: {type(layout_result)}")

        # 尝试转换layout数据为统一格式
        try:
            unified_result = unified_layout_service.analyze_paddleocr_result(
                layout_result,
                image_info=image_info,
                page_number=page_number
            )

            logger.info(f"[Layout API] Successfully analyzed layout with {len(unified_result.elements)} elements")
            return unified_result.to_dict()

        except Exception as e:
            logger.error(f"[Layout API] Error analyzing paddleocr result: {e}", exc_info=True)
            # Return empty result on conversion error
            from app.models.layout_result import LayoutAnalysisResult
            empty_result = LayoutAnalysisResult()
            return empty_result.to_dict()

    except Exception as e:
        logger.error(f"[Layout API] Error getting unified layout analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


def _normalize_flat_bbox(raw_bbox: Any) -> List[float]:
    """Normalize heterogeneous bbox formats to [x1, y1, x2, y2]."""
    if isinstance(raw_bbox, dict):
        x = float(raw_bbox.get("x", 0))
        y = float(raw_bbox.get("y", 0))
        w = float(raw_bbox.get("width", 0))
        h = float(raw_bbox.get("height", 0))
        return [x, y, x + w, y + h]
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 4:
        return [
            float(raw_bbox[0]),
            float(raw_bbox[1]),
            float(raw_bbox[2]),
            float(raw_bbox[3]),
        ]
    return [0.0, 0.0, 0.0, 0.0]


@router.get("/api/v1/tasks/{task_id}/blocks")
async def get_task_blocks(task_id: str, page_number: int = 1, content_limit: int = 120):
    """Return frontend-oriented flat blocks payload from the view layer."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed")

    # Primary source: view layer from Phase 1 envelope
    envelope = task.get("envelope") or {}
    view_layer = envelope.get("view") or {}
    preprocessing = envelope.get("preprocessing") or {}

    # Derive image dimensions from preprocessing metadata
    coord_space = preprocessing.get("coordinate_space", "preprocessed")
    if coord_space == "original":
        size_dict = preprocessing.get("input_size") or {}
    else:
        size_dict = preprocessing.get("output_size") or preprocessing.get("input_size") or {}
    image_width = int(size_dict.get("width", 0) or 0)
    image_height = int(size_dict.get("height", 0) or 0)

    # Fallback to legacy page_image_meta when envelope not present
    if image_width == 0 or image_height == 0:
        result = task.get("result", {}) or {}
        page_meta = (result.get("document_info", {}) or {}).get("page_image_meta", {}) or {}
        image_width = image_width or int(page_meta.get("width_px", 0) or 0)
        image_height = image_height or int(page_meta.get("height_px", 0) or 0)

    blocks: List[Dict[str, Any]] = []

    # Build blocks from view layer pages
    view_pages = view_layer.get("pages", [])
    view_page = next((p for p in view_pages if p.get("page_num", 1) == page_number), None)

    if view_page is not None:
        # Use page-level dimensions if available
        image_width = image_width or int(view_page.get("width", 0) or 0)
        image_height = image_height or int(view_page.get("height", 0) or 0)
        _elem_count = len(view_page.get("elements", []))
        logger.info(
            f"[Blocks] task={task_id} page={page_number} "
            f"source=envelope_view elements={_elem_count}"
        )
        for elem in view_page.get("elements", []):
            if not isinstance(elem, dict):
                continue
            polygon = elem.get("polygon") or []
            # Convert flat polygon [x0,y0,x1,y0,x1,y1,x0,y1] → bbox [x0,y0,x1,y1]
            if len(polygon) >= 4:
                xs = [polygon[i] for i in range(0, len(polygon), 2)]
                ys = [polygon[i] for i in range(1, len(polygon), 2)]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
            else:
                bbox = [0.0, 0.0, 0.0, 0.0]
            payload = elem.get("payload") or {}
            text = str(payload.get("text") or "")
            confidence_raw = payload.get("confidence", elem.get("confidence", 0))
            confidence = float(confidence_raw or 0)
            role = str(elem.get("kind") or "paragraph")
            blocks.append({
                "id": elem.get("id") or f"block_{len(blocks)}",
                "page": page_number,
                "role": role,
                "type": role,
                "confidence": confidence,
                "score": confidence,
                "bbox": bbox,
                "text": text,
                "content": text,
                "content_truncated": text[:content_limit],
                "processing_status": elem.get("processing_status", "succeeded"),
                # GLM trial P0-B: surface the envelope reading_order so the
                # frontend can render a reading-order overlay for multi-column
                # pages. Non-breaking: absent in legacy fallback below.
                "reading_order": elem.get("reading_order", 0),
            })
    else:
        # Fallback: read from legacy result layout elements
        result = task.get("result", {}) or {}
        source_blocks = (
            result.get("semantic_text_blocks")
            or result.get("layout", {}).get("elements")
            or result.get("text_blocks")
            or []
        )
        _fallback_reason = "envelope_missing" if not envelope else (
            "view_missing" if not view_layer.get("pages") else "page_not_found"
        )
        logger.warning(
            f"[Blocks] task={task_id} page={page_number} "
            f"source=legacy_fallback reason={_fallback_reason} "
            f"source_blocks={len(source_blocks)}"
        )
        for idx, block in enumerate(source_blocks):
            if not isinstance(block, dict):
                continue
            page = int(block.get("page", page_number) or page_number)
            if page != page_number:
                continue
            text = str(block.get("text") or block.get("content") or "")
            bbox = _normalize_flat_bbox(block.get("bbox") or block.get("bounding_box"))
            score = block.get("score")
            confidence = float(block.get("confidence", score if score is not None else 0) or 0)
            role = str(block.get("semantic_role") or block.get("type") or block.get("element_type") or "Paragraph")
            blocks.append({
                "id": block.get("id") or block.get("block_id") or f"block_{idx}",
                "page": page,
                "role": role,
                "type": role,
                "confidence": confidence,
                "score": confidence,
                "bbox": bbox,
                "text": text,
                "content": text,
                "content_truncated": text[:content_limit],
            })

    return {
        "task_id": task_id,
        "page": page_number,
        "image_width": image_width,
        "image_height": image_height,
        "coord_space": coord_space,
        "blocks": blocks,
    }


@router.get("/api/v1/tasks/{task_id}/figures")
async def list_task_figures(task_id: str):
    """List figure crops for a task (GLM trial P0-2)."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = task.get("result") or {}
    figures = result.get("figures")
    if not isinstance(figures, dict):
        figures = {"figure_count": 0, "items": []}
    return figures


@router.get("/api/v1/tasks/{task_id}/figures/{figure_id}")
async def get_task_figure_crop(task_id: str, figure_id: str):
    """Serve a single cropped figure PNG (GLM trial P0-2).

    Figure crops live under OUTPUT_DIR/{task_id}/figures/. figure_id is the
    layout element id (e.g. p1_e3); only a safe basename is accepted to
    prevent path traversal.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Path-traversal guard: accept [A-Za-z0-9_-] ids only.
    import re as _re

    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", figure_id or ""):
        raise HTTPException(status_code=400, detail="Invalid figure id")

    crop_path = os.path.join(settings.OUTPUT_DIR, task_id, "figures", f"{figure_id}.png")
    if not os.path.isfile(crop_path):
        raise HTTPException(status_code=404, detail="Figure crop not found")
    return FileResponse(crop_path, media_type="image/png")


@router.get("/api/v1/tasks/{task_id}/page-image/{page_num}")
async def get_page_image(task_id: str, page_num: int = 1):
    """
    Convert PDF page to image for display.
    Returns the first page as PNG image for PDF files, or original image for image files.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # When PaddleOCR performed unwarping during processing, serve the preprocessed
    # image so that bbox coordinates (which are in output_img space) align with
    # the image visible in the frontend.
    preprocessed_path = task.get("preprocessed_image_path")
    if preprocessed_path and os.path.exists(preprocessed_path):
        return FileResponse(preprocessed_path, media_type="image/png")

    file_path = task.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        if file_ext == '.pdf':
            # Convert PDF page to image
            import fitz  # PyMuPDF
            from PIL import Image

            doc = fitz.open(file_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                raise HTTPException(status_code=400, detail=f"Page number {page_num} out of range (1-{len(doc)})")

            page = doc[page_num - 1]  # 0-indexed

            # Render page to image with 2x scale for better quality
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            if pix.alpha:
                img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                img = img.convert("RGB")
            else:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            doc.close()

            # Convert to bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            return Response(
                content=img_bytes.getvalue(),
                media_type="image/png",
                headers={
                    "Content-Disposition": f"inline; filename=page_{page_num}.png"
                }
            )
        else:
            # For image files, return the original file
            return FileResponse(
                file_path,
                media_type=f"image/{file_ext[1:]}",
                headers={
                    "Content-Disposition": f"inline; filename={os.path.basename(file_path)}"
                }
            )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PyMuPDF (fitz) is required for PDF conversion. Please install: pip install PyMuPDF"
        )
    except Exception as e:
        logger.error(f"Error converting page to image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to convert page to image: {str(e)}")


@router.get("/api/v1/tasks/{task_id}/export/{format}")
async def export_result(task_id: str, format: str, include: str = ""):
    """Export results in various formats.

    ``format=zip`` builds a tables + figures artifact pack. Optional
    ``include`` is a comma list: ``tables``, ``figures``, ``json``
    (default ``tables,figures``).
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed")

    result = task["result"]
    format = format.lower()

    try:
        if format == "json":
            json_path = await export_service.to_json(result, task_id)
            return FileResponse(json_path, filename=f"{task_id}_result.json")
        elif format == "csv":
            csv_path = await export_service.to_csv(result, task_id)
            return FileResponse(csv_path, filename=f"{task_id}_tables.csv")
        elif format in ["markdown", "md"]:
            md_content = await export_service.to_markdown(result)
            return JSONResponse(content={"markdown": md_content})
        elif format in ["docx", "word"]:
            docx_path = await export_service.to_docx(result, task_id)
            return FileResponse(docx_path, filename=f"{task_id}_result.docx")
        elif format in ["xlsx", "excel"]:
            xlsx_path = await export_service.to_excel(result, task_id)
            return FileResponse(xlsx_path, filename=f"{task_id}_tables.xlsx")
        elif format == "azure":
            azure_format = await export_service.to_structured_json(result)
            return JSONResponse(content=azure_format)
        elif format == "zip":
            zip_path = await build_task_pack_zip(result, task_id, include=include)
            return FileResponse(
                zip_path,
                filename=f"{task_id}_pack.zip",
                media_type="application/zip",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    except PackTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
