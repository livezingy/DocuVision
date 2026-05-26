"""Optional Supabase persistence with local JSON fallback for trial PoC."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


class SupabaseStore:
    def __init__(self) -> None:
        self.url = (settings.SUPABASE_URL or "").rstrip("/")
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY or ""
        self.fallback_dir = Path(settings.DEMO_VALIDATION_DIR)
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.service_key)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "backend": "supabase" if self.enabled else "local_json",
            "url": self.url or None,
            "fallback_dir": str(self.fallback_dir),
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def persist_extraction(
        self,
        *,
        job_id: str,
        filename: str,
        mapped_transactions: List[Dict[str, Any]],
        raw_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        document_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        if self.enabled:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    doc_resp = await client.post(
                        f"{self.url}/rest/v1/documents",
                        headers=self._headers(),
                        json={
                            "id": document_id,
                            "job_id": job_id,
                            "filename": filename,
                            "status": "pending_validation",
                            "raw_result": raw_result,
                            "created_at": now,
                        },
                    )
                    doc_resp.raise_for_status()

                    if mapped_transactions:
                        rows = [
                            {
                                "document_id": document_id,
                                "row_index": idx,
                                "payload": tx,
                                "internal_code": tx.get("internal_code"),
                                "created_at": now,
                            }
                            for idx, tx in enumerate(mapped_transactions)
                        ]
                        tx_resp = await client.post(
                            f"{self.url}/rest/v1/transactions",
                            headers=self._headers(),
                            json=rows,
                        )
                        tx_resp.raise_for_status()

                return {
                    "persisted": True,
                    "backend": "supabase",
                    "document_id": document_id,
                    "transaction_count": len(mapped_transactions),
                    "message": "Saved to Supabase documents/transactions",
                }
            except Exception as exc:
                return {
                    "persisted": False,
                    "backend": "supabase",
                    "document_id": None,
                    "transaction_count": 0,
                    "message": f"Supabase persist failed: {exc}",
                }

        record = {
            "document_id": document_id,
            "job_id": job_id,
            "filename": filename,
            "status": "pending_validation",
            "transaction_count": len(mapped_transactions),
            "created_at": now,
            "mapped_transactions": mapped_transactions,
        }
        path = self.fallback_dir / f"{document_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "persisted": True,
            "backend": "local_json",
            "document_id": document_id,
            "transaction_count": len(mapped_transactions),
            "message": f"Saved locally at {path.name}",
        }

    async def list_validation_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.enabled:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        f"{self.url}/rest/v1/documents",
                        headers=self._headers(),
                        params={
                            "select": "id,filename,status,created_at,job_id",
                            "order": "created_at.desc",
                            "limit": str(limit),
                        },
                    )
                    resp.raise_for_status()
                    docs = resp.json()
                    records: List[Dict[str, Any]] = []
                    for doc in docs:
                        tx_resp = await client.get(
                            f"{self.url}/rest/v1/transactions",
                            headers=self._headers(),
                            params={
                                "document_id": f"eq.{doc['id']}",
                                "select": "payload,internal_code,row_index",
                                "order": "row_index.asc",
                            },
                        )
                        tx_resp.raise_for_status()
                        txs = [row.get("payload") or row for row in tx_resp.json()]
                        records.append(
                            {
                                "document_id": doc["id"],
                                "filename": doc.get("filename") or "",
                                "status": doc.get("status") or "pending_validation",
                                "transaction_count": len(txs),
                                "created_at": doc.get("created_at"),
                                "mapped_transactions": txs,
                            }
                        )
                    return records
            except Exception:
                pass

        records: List[Dict[str, Any]] = []
        for path in sorted(self.fallback_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(
                    {
                        "document_id": data.get("document_id", path.stem),
                        "filename": data.get("filename", ""),
                        "status": data.get("status", "pending_validation"),
                        "transaction_count": data.get("transaction_count", 0),
                        "created_at": data.get("created_at"),
                        "mapped_transactions": data.get("mapped_transactions") or [],
                    }
                )
            except json.JSONDecodeError:
                continue
        return records


_store: Optional[SupabaseStore] = None


def get_supabase_store() -> SupabaseStore:
    global _store
    if _store is None:
        _store = SupabaseStore()
    return _store
