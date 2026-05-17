"""Small HTTP adapter around the local mem0 runtime."""

from __future__ import annotations

import os
from typing import Any

import httpx

from scripts.ingest_repo import build_request_headers


class Mem0Client:
    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        self.api_url = (api_url or os.getenv("MEM0_API_URL", "http://localhost:8000")).rstrip("/")
        key = api_key if api_key is not None else os.getenv("MEM0_API_KEY", "")
        self.headers = build_request_headers(
            api_key=key,
            cloudflare_access_client_id=os.getenv("CLOUDFLARE_ACCESS_CLIENT_ID", ""),
            cloudflare_access_client_secret=os.getenv("CLOUDFLARE_ACCESS_CLIENT_SECRET", ""),
        )
        self.search_path = os.getenv("MEM0_SEARCH_PATH", "/search")

    def search(
        self,
        query: str,
        *,
        tenants: tuple[str, ...],
        limit: int = 8,
        repo: str | None = None,
        path: str | None = None,
        type: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        metadata_filters = _metadata_filters(repo=repo, path=path, type=type, tags=tags)
        return self._search_each_tenant(
            query,
            tenants=tenants,
            limit=limit,
            metadata_filters=metadata_filters,
        )

    def list_recent(
        self,
        *,
        tenants: tuple[str, ...],
        repo: str | None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return self._search_each_tenant(
            repo or "project memories",
            tenants=tenants,
            limit=limit,
            metadata_filters=_metadata_filters(repo=repo),
        )

    def _search_each_tenant(
        self,
        query: str,
        *,
        tenants: tuple[str, ...],
        limit: int,
        metadata_filters: dict[str, Any],
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for tenant in tenants:
            filters: dict[str, Any] = {"user_id": tenant, "tenant": tenant}
            filters.update(metadata_filters)
            response = self._post(
                self.search_path,
                {"query": query, "top_k": limit, "filters": filters},
            )
            results.extend(_extract_results(response))

        results.sort(key=_result_score, reverse=True)
        return {"results": results[:limit]}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.api_url}{path}",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def _extract_results(response: dict[str, Any]) -> list[dict[str, Any]]:
    results = response.get("results", response.get("memories", []))
    return results if isinstance(results, list) else []


def _result_score(result: dict[str, Any]) -> float:
    score = result.get("score", 0)
    return score if isinstance(score, (int, float)) else 0


def _metadata_filters(
    *,
    repo: str | None = None,
    path: str | None = None,
    type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if repo:
        filters["repo"] = repo
    if path:
        filters["path"] = path
    if type:
        filters["type"] = type
    if tags:
        filters["tags"] = tags
    return filters
