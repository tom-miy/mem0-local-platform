"""FastMCP server exposing tenant-aware developer memory tools."""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP

from mem0_local_platform_mcp.mem0_client import Mem0Client
from mem0_local_platform_mcp.tenant_policy import TenantPolicy


mcp = FastMCP(name="mem0-local-platform")
policy = TenantPolicy.from_env()
client = Mem0Client()


@mcp.tool
def search_memory(query: str, tenants: list[str] | None = None, limit: int = 8) -> dict[str, Any]:
    """Search semantic memory inside configured readable tenant boundaries."""
    readable = policy.readable(tenants)
    return client.search(query, tenants=readable, limit=limit)


@mcp.tool
def remember(memory: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write a memory only to the configured write tenant."""
    return client.remember(memory, tenant=policy.write_tenant, metadata=metadata or {})


@mcp.tool
def related_repo_context(
    repo: str,
    query: str,
    tenants: list[str] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Search for context related to one repository without making repo a tenant."""
    readable = policy.readable(tenants)
    result = client.search(query, tenants=readable, limit=limit, repo=repo)
    result["repo_filter_note"] = f"Repository is metadata: repo={repo}"
    return result


@mcp.tool
def recent_project_memories(
    repo: str | None = None,
    tenants: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Fetch recent or project-scoped memories across readable tenants."""
    readable = policy.readable(tenants)
    return client.list_recent(tenants=readable, repo=repo, limit=limit)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8010"))

    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    main()

