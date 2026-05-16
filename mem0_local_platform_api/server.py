"""Small REST API around the mem0 OSS library.

This exists so compose does not depend on an unverified external mem0 image.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


app = FastAPI(title="mem0-local-platform API")


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
    memory = get_memory()
    return memory.add(
        request.messages,
        user_id=request.user_id,
        agent_id=request.agent_id,
        run_id=request.run_id,
        metadata=request.metadata,
        infer=request.infer,
    )


@app.post("/search")
def search_memory(request: SearchRequest) -> Any:
    memory = get_memory()
    return memory.search(request.query, filters=request.filters, top_k=request.top_k)


@app.delete("/v1/memories/")
def delete_memories(filters: str = Query(default="{}")) -> dict[str, Any]:
    try:
        parsed = json.loads(filters)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="filters must be valid JSON") from exc
    if not parsed:
        raise HTTPException(status_code=400, detail="filters are required")

    memory = get_memory()
    deleted = 0

    while True:
        matches = memory.search("", filters=parsed, top_k=100)
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


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@lru_cache(maxsize=1)
def get_memory() -> Any:
    os.environ.setdefault("MEM0_DIR", "/tmp/mem0-local-platform/mem0")

    from mem0 import Memory

    config_json = os.getenv("MEM0_CONFIG_JSON")
    if config_json:
        return Memory.from_config(json.loads(config_json))

    config = {
        "vector_store": {
            "provider": os.getenv("MEM0_VECTOR_STORE_PROVIDER", "qdrant"),
            "config": {
                "host": os.getenv("QDRANT_HOST", "qdrant"),
                "port": int(os.getenv("QDRANT_PORT", "6333")),
                "collection_name": os.getenv("QDRANT_COLLECTION", "developer_memories"),
                "embedding_model_dims": int(os.getenv("MEM0_EMBEDDING_DIMS", "768")),
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
                "model": os.getenv("MEM0_LLM_MODEL", "llama3.1:latest"),
                "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            },
        },
        "embedder": {
            "provider": os.getenv("MEM0_EMBEDDER_PROVIDER", "ollama"),
            "config": {
                "model": os.getenv("MEM0_EMBEDDER_MODEL", "nomic-embed-text:latest"),
                "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            },
        },
    }
    return Memory.from_config(config)


def _extract_results(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        results = response.get("results", response.get("memories", []))
        return results if isinstance(results, list) else []
    if isinstance(response, list):
        return response
    return []


def main() -> None:
    import uvicorn

    uvicorn.run(
        "mem0_local_platform_api.server:app",
        host=os.getenv("MEM0_API_HOST", "0.0.0.0"),
        port=int(os.getenv("MEM0_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
