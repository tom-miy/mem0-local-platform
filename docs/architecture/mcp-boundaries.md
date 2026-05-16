# MCP Boundaries

The MCP server is the policy enforcement layer for agent access.

Tools exposed by `mcp/server.py` apply readable tenant filters before querying
mem0. MCP does not register new memory.

## Tools

- `search_memory` searches readable tenants.
- `related_repo_context` searches with repository metadata in mind.
- `recent_project_memories` retrieves project-scoped context.

## Read Boundary

Configure readable tenants in `mem0.policy.yml`:

```yaml
read:
  - secret-knowledge
```

Register memory through GitHub Actions or the Python CLI. This avoids
persisting an AI agent's temporary guesses through MCP.
