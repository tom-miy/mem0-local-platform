"""Small HTTP adapter around the local mem0 runtime."""

from __future__ import annotations

import os
from typing import Any

import httpx


class Mem0Client:
    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        self.api_url = (api_url or os.getenv("MEM0_API_URL", "http://localhost:8000")).rstrip("/")
        key = api_key if api_key is not None else os.getenv("MEM0_API_KEY", "")
        self.headers = {"Authorization": f"Bearer {key}"} if key else {}
        self.add_path = os.getenv("MEM0_ADD_PATH", "/add")
        self.search_path = os.getenv("MEM0_SEARCH_PATH", "/search")

    def search(
        self,
        query: str,
        *,
        tenants: tuple[str, ...],
        limit: int = 8,
        repo: str | None = None,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {"tenant": {"in": list(tenants)}}
        if repo:
            filters["repo"] = repo
        return self._post(
            self.search_path,
            {"query": query, "top_k": limit, "filters": filters},
        )

    def remember(self, memory: str, *, tenant: str, metadata: dict[str, Any]) -> dict[str, Any]:
        merged = dict(metadata)
        merged["tenant"] = tenant
        return self._post(
            self.add_path,
            {
                "messages": [{"role": "user", "content": memory}],
                "user_id": tenant,
                "agent_id": "mcp",
                "metadata": merged,
                "infer": False,
            },
        )

    def list_recent(
        self,
        *,
        tenants: tuple[str, ...],
        repo: str | None,
        limit: int = 10,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {"tenant": {"in": list(tenants)}}
        if repo:
            filters["repo"] = repo
        return self._post(
            self.search_path,
            {"query": repo or "project memories", "top_k": limit, "filters": filters},
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.api_url}{path}",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
