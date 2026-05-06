"""DocumentKIEService：基于 PaddleNLP UIE (uie-m-base) 的 KIE 服务。

架构：
- PPKieSubprocessEngine：每个 document_type 独占一个子进程 worker，
  worker 内常驻一个 Taskflow('information_extraction', model='uie-m-base')
  实例（避免每次推理都重新加载 600MB 权重，避免 CUDA 上下文与 PP-StructureV3
  冲突）。CUDA 错误自动重启 + 重试一次。
- 主进程：拼 OCR 全文（WordIndexer）→ 子进程 UIE 推理 → 主进程做
  UieToAzureMapper + ItemsAggregator + AzureSchemaEmitter，最终输出
  view.fields 兼容 dict。
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import queue
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# Worker: 子进程常驻 PaddleNLP UIE Taskflow
# ============================================================
def _kie_worker_main(
    document_type: str,
    req_q: "multiprocessing.Queue[Any]",
    res_q: "multiprocessing.Queue[Any]",
) -> None:
    """KIE worker 主循环：常驻 Taskflow 实例处理 analyze_text 请求。"""
    try:
        # PPNLP_HOME 由 .env / OS 环境变量配置，不在代码内硬编码路径
        from paddlenlp import Taskflow  # type: ignore

        from app.services.kie.schemas import SCHEMAS

        if document_type not in SCHEMAS:
            raise ValueError(f"Unsupported document_type for KIE: {document_type}")

        schema = SCHEMAS[document_type]
        ie = Taskflow(
            "information_extraction",
            schema=schema,
            model="uie-m-base",
        )
        res_q.put(("ready",))
    except Exception as e:
        res_q.put(("init_error", str(e), traceback.format_exc()))
        sys.exit(1)

    while True:
        try:
            msg = req_q.get()
            if not isinstance(msg, tuple) or not msg:
                continue
            op = msg[0]

            if op == "stop":
                break

            if op == "analyze_text":
                text = msg[1] if len(msg) > 1 else ""
                if not isinstance(text, str) or not text.strip():
                    res_q.put(("ok", []))
                    continue
                results = ie(text)
                res_q.put(("ok", results))
                continue

            res_q.put(("error", f"Unknown op: {op}", ""))
        except Exception as e:
            res_q.put(("error", str(e), traceback.format_exc()))


# ============================================================
# Subprocess Engine: 管理 worker 进程生命周期
# ============================================================
class PPKieSubprocessEngine:
    """单个 document_type 的 UIE worker。"""

    _ctx = multiprocessing.get_context("spawn")
    _INIT_TIMEOUT = 180  # uie-m-base 首次下载可能较久
    _INFER_TIMEOUT = 120
    _CUDA_KEYWORDS = ("CUBLAS", "cuBLAS", "CUDA_STATUS", "CUDNN", "cudnn", "cublas")

    def __init__(self, document_type: str):
        self.document_type = document_type
        self._req_q: Optional["multiprocessing.Queue[Any]"] = None
        self._res_q: Optional["multiprocessing.Queue[Any]"] = None
        self._process: Optional[multiprocessing.Process] = None
        self._ready = False
        self._load_ms: int = 0

        self._start_worker()

    def _start_worker(self) -> None:
        logger.info(
            "Starting KIE subprocess worker for %s (Spawn, model=uie-m-base)...",
            self.document_type,
        )
        self._req_q = self._ctx.Queue()
        self._res_q = self._ctx.Queue()

        self._process = self._ctx.Process(
            target=_kie_worker_main,
            args=(self.document_type, self._req_q, self._res_q),
            daemon=True,
        )

        t0 = time.time()
        self._process.start()

        try:
            msg = self._res_q.get(timeout=self._INIT_TIMEOUT)
            if msg[0] == "ready":
                self._ready = True
                self._load_ms = int((time.time() - t0) * 1000)
                logger.info(
                    "KIE subprocess worker for %s is ready (load=%dms)",
                    self.document_type,
                    self._load_ms,
                )
            elif msg[0] == "init_error":
                self._kill_worker()
                raise RuntimeError(f"KIE Worker init failed: {msg[1]}\n{msg[2]}")
        except queue.Empty:
            self._kill_worker()
            raise TimeoutError(
                f"KIE Worker initialization timed out after {self._INIT_TIMEOUT}s"
            )

    def _kill_worker(self) -> None:
        if self._process and self._process.is_alive():
            logger.info("Terminating KIE subprocess worker...")
            self._process.terminate()
            self._process.join(timeout=5)
            if self._process.is_alive():
                logger.warning("KIE Worker did not terminate, forcing kill...")
                self._process.kill()
                self._process.join(timeout=3)
        self._ready = False

    def _restart_worker(self) -> None:
        logger.info("Restarting KIE subprocess worker (Recovery)...")
        self._kill_worker()
        self._start_worker()

    def is_ready(self) -> bool:
        return (
            self._ready
            and self._process is not None
            and self._process.is_alive()
        )

    @property
    def load_ms(self) -> int:
        return self._load_ms

    def analyze_text(self, text: str) -> List[Dict[str, Any]]:
        """阻塞调用：把 OCR 全文交给 worker 跑 UIE。"""
        if not self.is_ready():
            self._restart_worker()
        assert self._req_q is not None and self._res_q is not None

        self._req_q.put(("analyze_text", text))

        try:
            msg = self._res_q.get(timeout=self._INFER_TIMEOUT)
        except queue.Empty:
            logger.error("KIE Worker analyze_text timeout")
            self._restart_worker()
            raise TimeoutError("KIE analyze_text timed out.")

        if msg[0] == "ok":
            return msg[1] if isinstance(msg[1], list) else []

        if msg[0] == "error":
            err_msg = msg[1] if len(msg) > 1 else ""
            tb_str = msg[2] if len(msg) > 2 else ""

            is_cuda_err = any(kw in err_msg for kw in self._CUDA_KEYWORDS)
            if is_cuda_err:
                logger.warning("CUDA error detected in KIE worker, restarting: %s", err_msg)
                self._restart_worker()
                self._req_q.put(("analyze_text", text))
                retry_msg = self._res_q.get(timeout=self._INFER_TIMEOUT)
                if retry_msg[0] == "ok":
                    return retry_msg[1] if isinstance(retry_msg[1], list) else []
                raise RuntimeError(
                    f"KIE Worker retry failed: {retry_msg[1] if len(retry_msg) > 1 else ''}"
                )
            raise RuntimeError(f"KIE Worker analysis failed: {err_msg}\n{tb_str}")

        raise RuntimeError(f"KIE Worker returned unexpected response: {msg}")

    def close(self) -> None:
        if self._req_q is not None:
            try:
                self._req_q.put(("stop",))
            except Exception:
                pass
        self._kill_worker()


# ============================================================
# Service Layer
# ============================================================
class DocumentKIEService:
    """KIE 服务入口：管理多 document_type 的 worker，对外暴露
    `extract_fields(file_path, document_type, *, layout, table_meta, tables, ...)`.
    """

    def __init__(self) -> None:
        self._engines: Dict[str, PPKieSubprocessEngine] = {}

    def _get_engine(self, document_type: str) -> PPKieSubprocessEngine:
        if document_type not in self._engines:
            logger.info("Initializing new KIE engine for: %s", document_type)
            self._engines[document_type] = PPKieSubprocessEngine(document_type)
        return self._engines[document_type]

    def close(self) -> None:
        for engine in self._engines.values():
            try:
                engine.close()
            except Exception:
                pass
        self._engines.clear()

    async def extract_fields(
        self,
        file_path: str,
        document_type: str,
        *,
        preprocessed_image_path: Optional[str] = None,
        layout: Optional[Dict[str, Any]] = None,
        table_meta: Optional[Dict[str, Any]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """主流程：拼全文 → UIE → BaseField → ItemsAggregator → KieResult。

        返回 dict 字段：
          - fields:        view.fields 兼容 dict
          - confidence_avg: 全部字段平均 UIE probability
          - items_count:   行项目数
          - metadata:      {items_source, kie_model_load_ms, ...}
          - debug_input:   测试与可观测性
        """
        # 主进程仅 import KIE 子包（不引入 paddlenlp）；paddlenlp 仅在 worker 内 import
        from app.services.kie.azure_emitter import AzureSchemaEmitter
        from app.services.kie.azure_schema import BaseField
        from app.services.kie.items_aggregator import ItemsAggregator
        from app.services.kie.uie_to_azure import UieToAzureMapper
        from app.services.kie.word_indexer import WordIndexer

        debug_input = {
            "preprocessed_image_path": preprocessed_image_path,
            "layout_present": bool(layout),
            "table_meta": table_meta or {},
            "ocr_text_length": 0,
        }

        try:
            logger.info(
                "KIE.extract_fields | file=%s | doc_type=%s | preproc=%s | layout=%s | tables=%s",
                file_path,
                document_type,
                bool(preprocessed_image_path),
                bool(layout),
                len(tables) if isinstance(tables, list) else 0,
            )
        except Exception:
            pass

        indexer = WordIndexer.from_layout(layout or {})
        debug_input["ocr_text_length"] = len(indexer.content)

        if not indexer.content.strip():
            return {
                "fields": {},
                "confidence_avg": 0.0,
                "items_count": 0,
                "metadata": {
                    "reason": "empty_ocr_text",
                    "items_source": "n/a",
                    "kie_model_load_ms": 0,
                },
                "debug_input": debug_input,
            }

        engine = self._get_engine(document_type)

        loop = asyncio.get_event_loop()
        t0 = time.time()
        uie_result = await loop.run_in_executor(None, engine.analyze_text, indexer.content)
        infer_ms = int((time.time() - t0) * 1000)

        mapper = UieToAzureMapper(indexer)
        raw_mapped = mapper.map_uie_result(uie_result)

        # 拆出关系字段交给 ItemsAggregator
        items_raw = raw_mapped.pop("Items", None) if isinstance(raw_mapped.get("Items"), list) else None
        payment_raw = (
            raw_mapped.pop("PaymentDetails", None)
            if isinstance(raw_mapped.get("PaymentDetails"), list)
            else None
        )

        single_fields: Dict[str, BaseField] = {
            k: v for k, v in raw_mapped.items() if isinstance(v, BaseField)
        }

        items_list: List[BaseField] = []
        payment_list: List[BaseField] = []
        items_source = "n/a"

        if document_type in {"invoice", "receipt"}:
            agg = ItemsAggregator(indexer, mapper, tables=tables or []).aggregate(
                items_raw, payment_raw
            )
            items_list = agg["Items"]
            payment_list = agg["PaymentDetails"]
            items_source = agg["items_source"]

        emitter = AzureSchemaEmitter(document_type=document_type)
        # kie_model_load_ms = worker 启动 + 本次推理（监控 PPNLP_HOME 缓存是否生效）
        kie_model_load_ms = engine.load_ms + infer_ms
        kie_result = emitter.build(
            single_fields=single_fields,
            items=items_list if items_list else None,
            payment_details=payment_list if payment_list else None,
            metadata={
                "items_source": items_source,
                "kie_model_load_ms": kie_model_load_ms,
                "infer_ms": infer_ms,
                "engine_load_ms": engine.load_ms,
            },
        )

        return {
            "fields": kie_result.to_view_fields(),
            "confidence_avg": kie_result.confidence,
            "items_count": len(items_list),
            "metadata": kie_result.metadata,
            "debug_input": debug_input,
        }
