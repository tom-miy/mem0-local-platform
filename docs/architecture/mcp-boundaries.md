# MCP Boundaries

The MCP server is the policy enforcement layer for agent access.

Tools exposed by `mcp/server.py` apply readable tenant filters before querying
mem0. Write operations use one configured write tenant.

## Tools

- `search_memory` searches readable tenants.
- `remember` writes to the configured write tenant.
- `related_repo_context` searches with repository metadata in mind.
- `recent_project_memories` retrieves project-scoped context.

## Read And Write Separation

Configure read tenants and the write tenant in `mem0.policy.yml`:

```yaml
read:
  - vault
  - work

write:
  - work
```

The write tenant is automatically included in readable tenants so newly written
context can be found by the same agent boundary.
