import os
import queue
import logging
import traceback
import multiprocessing
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- Worker Subprocess Entry Point ---
def _kie_worker_main(document_type: str, req_q: multiprocessing.Queue, res_q: multiprocessing.Queue):
    """
    Subprocess worker for Document KIE (Invoice/ID Card/Receipt).
    This isolates the PaddleX/OCR models in a separate process to avoid CUDA context conflicts.
    """
    import sys
    try:
        # TODO: Initialize the specific KIE engine based on document_type
        # e.g. PP-ChatOCRv4-doc or specialized models

        # Simulated initialization for now
        logger.info(f"[KIE Worker] Initiating KIE engine for type: {document_type}")

        # Signal that initialization is complete
        res_q.put(('ready',))

    except Exception as e:
        err_msg = str(e)
        res_q.put(('init_error', err_msg, traceback.format_exc()))
        sys.exit(1)

    # Worker Loop
    while True:
        try:
            msg = req_q.get()
            if msg[0] == 'stop':
                break

            elif msg[0] == 'analyze':
                file_path = msg[1]
                logger.info(f"[KIE Worker] Processing file: {file_path}")

                # TODO: Perform actual KIE inference here
                # Simulated result
                result = {
                    "document_type": document_type,
                    "fields": {}
                }

                res_q.put(('ok', result))

        except Exception as e:
            err_msg = str(e)
            res_q.put(('error', err_msg, traceback.format_exc()))

# --- Subprocess Engine Wrapper ---
class PPKieSubprocessEngine:
    """
    Manages the isolated KIE subprocess worker.
    """
    _ctx = multiprocessing.get_context('spawn')
    _INIT_TIMEOUT = 120
    _INFER_TIMEOUT = 180
    _CUDA_KEYWORDS = ('CUBLAS', 'cuBLAS', 'CUDA_STATUS', 'CUDNN', 'cudnn', 'cublas')

    def __init__(self, document_type: str):
        self.document_type = document_type
        self._req_q: Optional[multiprocessing.Queue] = None
        self._res_q: Optional[multiprocessing.Queue] = None
        self._process: Optional[multiprocessing.Process] = None
        self._ready = False

        self._start_worker()

    def _start_worker(self):
        logger.info(f"Starting KIE subprocess worker for {self.document_type} (Spawn)...")
        self._req_q = self._ctx.Queue()
        self._res_q = self._ctx.Queue()

        self._process = self._ctx.Process(
            target=_kie_worker_main,
            args=(self.document_type, self._req_q, self._res_q),
            daemon=True
        )
        self._process.start()

        try:
            msg = self._res_q.get(timeout=self._INIT_TIMEOUT)
            if msg[0] == 'ready':
                self._ready = True
                logger.info(f"KIE subprocess worker for {self.document_type} is ready.")
            elif msg[0] == 'init_error':
                self._kill_worker()
                raise RuntimeError(f"KIE Worker init failed: {msg[1]}\n{msg[2]}")
        except queue.Empty:
            self._kill_worker()
            raise TimeoutError(f"KIE Worker initialization timed out after {self._INIT_TIMEOUT}s")

    def _kill_worker(self):
        if self._process and self._process.is_alive():
            logger.info("Terminating KIE subprocess worker...")
            self._process.terminate()
            self._process.join(timeout=5)
            if self._process.is_alive():
                logger.warning("KIE Worker did not terminate, forcing kill...")
                self._process.kill()
                self._process.join(timeout=3)
        self._ready = False

    def _restart_worker(self):
        logger.info("Restarting KIE subprocess worker (Recovery)...")
        self._kill_worker()
        self._start_worker()

    def is_ready(self) -> bool:
        return self._ready and self._process is not None and self._process.is_alive()

    def _call_worker(self, file_path: str) -> Dict[str, Any]:
        if not self.is_ready():
            self._restart_worker()

        self._req_q.put(('analyze', file_path))

        try:
            msg = self._res_q.get(timeout=self._INFER_TIMEOUT)

            if msg[0] == 'ok':
                return msg[1]

            elif msg[0] == 'error':
                err_msg = msg[1]
                tb_str = msg[2]

                is_cuda_err = any(kw in err_msg for kw in self._CUDA_KEYWORDS)
                if is_cuda_err:
                    logger.warning(f"CUDA error detected in KIE worker, restarting: {err_msg}")
                    self._restart_worker()

                    # Retry once
                    logger.info("Retrying KIE analysis after worker restart...")
                    self._req_q.put(('analyze', file_path))
                    retry_msg = self._res_q.get(timeout=self._INFER_TIMEOUT)
                    if retry_msg[0] == 'ok':
                        return retry_msg[1]
                    else:
                        raise RuntimeError(f"KIE Worker retry failed: {retry_msg[1]}\n{retry_msg[2]}")
                else:
                    raise RuntimeError(f"KIE Worker analysis failed: {err_msg}\n{tb_str}")

        except queue.Empty:
            logger.error("KIE Worker isolation queue timeout!")
            self._restart_worker()
            raise TimeoutError("KIE analysis timed out.")

    def analyze(self, file_path: str) -> Dict[str, Any]:
        """
        Blocking call to analyze. For async contexts, run this in an executor.
        """
        return self._call_worker(file_path)

    def close(self):
        if self._req_q:
            try:
                self._req_q.put(('stop',))
            except Exception:
                pass
        self._kill_worker()


class DocumentKIEService:
    """
    Service layer for Document Key Information Extraction.
    Manages engines for different document types.
    """
    def __init__(self):
        self._engines: Dict[str, PPKieSubprocessEngine] = {}

    def _get_engine(self, document_type: str) -> PPKieSubprocessEngine:
        if document_type not in self._engines:
            logger.info(f"Initializing new KIE engine for: {document_type}")
            self._engines[document_type] = PPKieSubprocessEngine(document_type)
        return self._engines[document_type]

    async def extract_fields(
        self,
        file_path: str,
        document_type: str,
        *,
        preprocessed_image_path: Optional[str] = None,
        layout: Optional[Dict[str, Any]] = None,
        table_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract fields from a document based on its type.
        Accepts optional richer inputs for KIE: `preprocessed_image_path`, `layout`, and `table_meta`.
        Returns a dictionary of fields to be merged into view.fields. For backward compatibility
        this will still call the subprocess engine with the original `file_path` and include the
        received inputs under the `debug_input` key in the returned dict for test assertion.
        """
        import asyncio
        loop = asyncio.get_event_loop()

        engine = self._get_engine(document_type)

        # Log received inputs for observability/tests
        try:
            logger.info(
                "KIE.extract_fields called | file=%s | doc_type=%s | preproc=%s | layout_present=%s | table_meta_keys=%s",
                file_path,
                document_type,
                bool(preprocessed_image_path),
                bool(layout),
                list(table_meta.keys()) if isinstance(table_meta, dict) else None,
            )
        except Exception:
            pass

        # Run blocking subprocess call in executor (engine currently expects file_path)
        result = await loop.run_in_executor(None, engine.analyze, file_path)

        # Ensure returned shape is a dict and contains `fields` key
        if not isinstance(result, dict):
            result = {"fields": {}}
        else:
            if "fields" not in result:
                result["fields"] = {}

        # Attach debug_input for testability and tracing
        result.setdefault("debug_input", {})
        result["debug_input"].update({
            "preprocessed_image_path": preprocessed_image_path,
            "layout_present": bool(layout),
            "table_meta": table_meta or {},
        })

        return result
