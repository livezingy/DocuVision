"""PP-StructureV3 subprocess-isolation family (S1 batch-6 verbatim extraction).

The worker entry stays a module-level function so the spawn context can pickle it
(the child imports this module fresh); dispatch/result helpers and the subprocess
engine move byte-identical out of layout_service.py. The in-process engine class
comes from layout_engine_ppstructure."""

from typing import Any, Dict, List, Optional
from loguru import logger
import os
import asyncio
import inspect
import multiprocessing
import queue as _queue_module

from app.services.layout_engine_ppstructure import (
    BaseLayoutEngine,
    PPStructureEngine,
    _compute_document_summary,
)


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


def _invoke_worker_command(engine, cmd: str, file_path: str, page_num: Optional[int] = None):
    """Dispatch one worker command, sync or async depending on the method.

    ``_analyze_image`` / ``_analyze_pdf`` are coroutines and must be driven
    with ``asyncio.run``. ``_analyze_image_layout_only`` is synchronous.
    Wrapping a sync call in ``asyncio.run(...)`` evaluates the call first
    (so inference may run) then raises ``ValueError: a coroutine was
    expected`` — every PDF page was recorded as failed.

    ``page_num`` (1-based) is forwarded to ``_analyze_image_layout_only`` so
    element ids and page fields carry the real page number instead of the
    hardcoded 1 that caused cross-page id collisions (every page reusing
    ``p1_e*``) and crop-file overwrites.

    Official: ``asyncio.run`` requires a coroutine object
    (https://docs.python.org/3.11/library/asyncio-runner.html#asyncio.run).
    """
    if cmd == "analyze_image_layout":
        fn = engine._analyze_image_layout_only
        # Forward page_num so multi-page PDFs get unique element ids.
        if page_num is not None:
            return fn(file_path, page_num)
        return fn(file_path)
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

        # Commands (2-tuple, legacy):
        #   ('analyze', path)             — legacy whole-file call (PDF or image)
        #   ('analyze_image', path)        — single image (one PDF page rasterized by main)
        #   ('analyze_image_layout', path) — single image, layout-only (no preprocess meta)
        # Commands (3-tuple, page-aware):
        #   ('analyze_image_layout', path, page_num) — single image with 1-based page
        #     number forwarded to _analyze_image_layout_only so element ids are unique.
        if len(item) == 3:
            cmd, file_path, page_num = item
        else:
            cmd, file_path = item
            page_num = None
        try:
            result = _invoke_worker_command(engine, cmd, file_path, page_num)
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

    def _call_worker(self, file_path: str, cmd: str = 'analyze', page_num: Optional[int] = None) -> Dict[str, Any]:
        """Blocking call sent to the worker subprocess (runs in thread executor).

        Args:
            file_path: Path to PDF (legacy whole-file) or image.
            cmd: Worker command — ``analyze`` (whole file), ``analyze_image``
                (single image with preprocessing metadata), or
                ``analyze_image_layout`` (single image, layout-only).
            page_num: 1-based page number forwarded to
                ``_analyze_image_layout_only`` so element ids are unique across
                a multi-page PDF. None keeps the legacy 2-tuple wire format.
        """
        if not self.is_ready():
            raise RuntimeError("PPStructureV3 subprocess worker is not running")

        # 3-tuple carries page_num; 2-tuple stays legacy-compatible.
        request = (cmd, file_path, page_num) if page_num is not None else (cmd, file_path)
        self._req_q.put(request)

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
                self._req_q.put(request)
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
                    # Forward the 1-based page number so the worker produces
                    # globally-unique element ids (p{N}_e{M}) instead of every
                    # page reusing p1_e* which caused crop-file overwrites.
                    page_result = self._call_worker(
                        img_path, cmd='analyze_image_layout', page_num=page_num + 1
                    )
                    elements = page_result.get("elements", []) or []
                    # Defensive: worker now sets page correctly from page_num,
                    # but keep this overwrite in case a legacy worker (2-tuple
                    # wire format, page_num dropped) returns page=1.
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
