# Tenant Boundaries

Tenant is the isolation boundary for memory access.

Do not create one tenant per repository. That creates unnecessary operational
sprawl and makes policy review harder.

Recommended tenant examples:

- `vault`
- `work`
- `upwork-18384728-acme`
- `agency-991-example`

Repository filtering should use metadata:

```json
{
  "tenant": "work",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

The MCP server must reject requested read tenants that are outside the configured
read boundary.

