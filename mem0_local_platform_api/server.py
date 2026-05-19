"""Small REST API around the mem0 OSS library.

This exists so compose does not depend on an unverified external mem0 image.
"""

from __future__ import annotations

import json
import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
import yaml

from mem0_local_platform_api.sanitizer import SanitizationPolicy


def require_api_key(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("MEM0_API_KEY", "")
    if not expected:
        return
    actual = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not secrets.compare_digest(actual, expected):
        raise HTTPException(status_code=401, detail="invalid MEM0_API_KEY")


app = FastAPI(title="mem0-local-platform API", dependencies=[Depends(require_api_key)])


class AddRequest(BaseModel):
    messages: str | list[dict[str, str]]
    user_id: str
    agent_id: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    infer: bool = False


class SearchRequest(BaseModel):
    query: str
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = 8


@app.post("/add")
def add_memory(request: AddRequest) -> Any:
    tenant = _resolve_write_tenant(request.user_id, request.metadata)
    try:
        sanitized = get_sanitization_policy().sanitize(
            tenant=tenant,
            messages=request.messages,
            metadata=request.metadata,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    memory = get_memory()
    return memory.add(
        sanitized.messages,
        user_id=request.user_id,
        agent_id=request.agent_id,
        run_id=request.run_id,
        metadata=sanitized.metadata,
        infer=request.infer,
    )


@app.post("/search")
def search_memory(request: SearchRequest) -> Any:
    memory = get_memory()
    response = memory.search(request.query, filters=request.filters, top_k=request.top_k)
    try:
        _validate_search_sanitization(response, filters=request.filters)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return response


@app.delete("/v1/memories/")
def delete_memories(filters: str = Query(default="{}")) -> dict[str, Any]:
    try:
        parsed = json.loads(filters)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="filters must be valid JSON") from exc
    if not parsed:
        raise HTTPException(status_code=400, detail="filters are required")
    search_filters = _mem0_search_filters(parsed)

    memory = get_memory()
    deleted = 0

    while True:
        matches = memory.search("", filters=search_filters, top_k=100)
        results = _extract_results(matches)
        if not results:
            break

        deleted_in_batch = 0
        for result in results:
            memory_id = result.get("id") or result.get("memory_id")
            if not memory_id:
                continue
            delete = getattr(memory, "delete", None)
            if delete is None:
                raise HTTPException(status_code=501, detail="mem0 Memory.delete is unavailable")
            try:
                delete(memory_id=memory_id)
            except TypeError:
                delete(memory_id)
            deleted += 1
            deleted_in_batch += 1

        if deleted_in_batch == 0:
            raise HTTPException(status_code=500, detail="no deletable memory ids found")

    return {"status": "success", "deleted_count": deleted}


@app.get("/v1/sanitization/audit")
def audit_sanitization(
    tenant: str,
    repo: str | None = None,
    path: str | None = None,
    top_k: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    policy = get_sanitization_policy()
    current_hash = policy.policy_hash
    if not current_hash:
        raise HTTPException(status_code=400, detail="sanitization policy hash is unavailable")
    if tenant not in policy.tenant_profiles:
        raise HTTPException(status_code=400, detail="tenant does not require sanitization")

    filters: dict[str, Any] = {"tenant": tenant}
    if repo:
        filters["repo"] = repo
    if path:
        filters["path"] = path

    memory = get_memory()
    matches = memory.search("", filters=_mem0_search_filters(filters), top_k=top_k)
    results = _extract_results(matches)
    files = _audit_sanitization_results(results, current_hash=current_hash)

    return {
        "tenant": tenant,
        "repo": repo,
        "path": path,
        "current_sanitization_policy_hash": current_hash,
        "scanned_count": len(results),
        "issue_file_count": len(files),
        "files": files,
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@lru_cache(maxsize=1)
def get_memory() -> Any:
    os.environ.setdefault("MEM0_DIR", "/tmp/mem0-local-platform/mem0")

    from mem0 import Memory

    config_json = os.getenv("MEM0_CONFIG_JSON")
    config_file = os.getenv("MEM0_CONFIG_FILE")
    if config_json and config_file:
        raise ValueError("set only one of MEM0_CONFIG_JSON or MEM0_CONFIG_FILE")
    if config_json:
        return Memory.from_config(json.loads(config_json))
    if config_file:
        return Memory.from_config(_load_mem0_config_file(Path(config_file)))

    config = {
        "vector_store": {
            "provider": os.getenv("MEM0_VECTOR_STORE_PROVIDER", "qdrant"),
            "config": {
                "host": os.getenv("QDRANT_HOST", "qdrant"),
                "port": int(os.getenv("QDRANT_PORT", "6333")),
                "collection_name": os.getenv("QDRANT_COLLECTION", "developer_memories"),
                "embedding_model_dims": int(os.getenv("MEM0_EMBEDDING_DIMS", "1024")),
            },
        },
        "graph_store": {
            "provider": os.getenv("MEM0_GRAPH_STORE_PROVIDER", "falkordb"),
            "config": {
                "url": os.getenv("FALKORDB_URL", "redis://falkordb:6379"),
            },
        },
        "llm": {
            "provider": os.getenv("MEM0_LLM_PROVIDER", "ollama"),
            "config": {
                "model": os.getenv("MEM0_LLM_MODEL", "qwen3.5:4b"),
                "temperature": float(os.getenv("MEM0_LLM_TEMPERATURE", "0.1")),
                "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            },
        },
        "embedder": {
            "provider": os.getenv("MEM0_EMBEDDER_PROVIDER", "ollama"),
            "config": {
                "model": os.getenv("MEM0_EMBEDDER_MODEL", "bge-m3"),
                "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            },
        },
    }
    return Memory.from_config(config)


def _load_mem0_config_file(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        config = json.loads(content)
    elif suffix in {".yaml", ".yml"}:
        config = yaml.safe_load(content)
    else:
        raise ValueError("MEM0_CONFIG_FILE must end with .json, .yaml, or .yml")

    if not isinstance(config, dict):
        raise ValueError("MEM0_CONFIG_FILE must contain a mapping/object")
    return config


@lru_cache(maxsize=1)
def get_sanitization_policy() -> SanitizationPolicy:
    return SanitizationPolicy.from_env()


def _resolve_write_tenant(user_id: str, metadata: dict[str, Any]) -> str:
    metadata_tenant = metadata.get("tenant")
    if metadata_tenant is None:
        return user_id
    if not isinstance(metadata_tenant, str) or not metadata_tenant.strip():
        raise HTTPException(status_code=400, detail="metadata.tenant must be a non-empty string")
    if metadata_tenant != user_id:
        raise HTTPException(status_code=400, detail="metadata.tenant must match user_id")
    return metadata_tenant


def _extract_results(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        results = response.get("results", response.get("memories", []))
        return results if isinstance(results, list) else []
    if isinstance(response, list):
        return response
    return []


def _audit_sanitization_results(
    results: list[dict[str, Any]],
    *,
    current_hash: str,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for result in results:
        metadata = _result_metadata(result)
        reasons = _sanitization_issue_reasons(metadata, current_hash=current_hash)
        if not reasons:
            continue

        repo = _metadata_string(metadata, "repo") or "(unknown repo)"
        path = _metadata_string(metadata, "path") or "(unknown path)"
        key = (repo, path)
        entry = grouped.setdefault(
            key,
            {
                "repo": repo,
                "path": path,
                "count": 0,
                "reasons": [],
                "observed_hashes": [],
            },
        )
        entry["count"] += 1
        for reason in reasons:
            if reason not in entry["reasons"]:
                entry["reasons"].append(reason)
        observed_hash = metadata.get("sanitization_policy_hash")
        if isinstance(observed_hash, str) and observed_hash not in entry["observed_hashes"]:
            entry["observed_hashes"].append(observed_hash)

    return sorted(grouped.values(), key=lambda item: (item["repo"], item["path"]))


def _validate_search_sanitization(response: Any, *, filters: dict[str, Any]) -> None:
    policy = get_sanitization_policy()
    if not policy.policy_hash or not policy.tenant_profiles:
        return

    requested_required_tenant = _requested_required_tenant(filters, policy)
    results = _extract_results(response)
    stale_results: list[dict[str, Any]] = []
    for result in results:
        metadata = _result_metadata(result)
        result_tenant = _metadata_string(metadata, "tenant")
        if result_tenant:
            if result_tenant not in policy.tenant_profiles:
                continue
        elif not requested_required_tenant:
            continue

        if _sanitization_issue_reasons(metadata, current_hash=policy.policy_hash):
            stale_results.append(result)

    if stale_results:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "stale_sanitization_policy",
                "message": "search results include memories that were not sanitized with the current policy",
                "current_sanitization_policy_hash": policy.policy_hash,
                "files": _audit_sanitization_results(
                    stale_results,
                    current_hash=policy.policy_hash,
                ),
            },
        )


def _requested_required_tenant(
    filters: dict[str, Any],
    policy: SanitizationPolicy,
) -> bool:
    tenants = (filters.get("tenant"), filters.get("user_id"))
    return any(isinstance(tenant, str) and tenant in policy.tenant_profiles for tenant in tenants)


def _result_metadata(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return result


def _metadata_string(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return value if isinstance(value, str) else ""


def _sanitization_issue_reasons(
    metadata: dict[str, Any],
    *,
    current_hash: str,
) -> list[str]:
    reasons: list[str] = []
    if metadata.get("sanitized") is not True:
        reasons.append("not_sanitized")

    observed_hash = metadata.get("sanitization_policy_hash")
    if not isinstance(observed_hash, str) or not observed_hash:
        reasons.append("missing_policy_hash")
    elif observed_hash != current_hash:
        reasons.append("policy_hash_mismatch")
    return reasons


def _mem0_search_filters(filters: dict[str, Any]) -> dict[str, Any]:
    search_filters = dict(filters)
    tenant = search_filters.get("tenant")
    if "user_id" not in search_filters and isinstance(tenant, str) and tenant:
        search_filters["user_id"] = tenant
    if not any(key in search_filters for key in ("user_id", "agent_id", "run_id")):
        raise HTTPException(
            status_code=400,
            detail="filters must include tenant, user_id, agent_id, or run_id",
        )
    return search_filters


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mem0_local_platform_api.server:app",
        host=os.getenv("MEM0_API_HOST", "0.0.0.0"),
        port=int(os.getenv("MEM0_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
