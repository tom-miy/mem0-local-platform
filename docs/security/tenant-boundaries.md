# Tenant Boundaries

Tenant is the boundary for "which knowledge this agent or developer may read."
Use tenants to separate knowledge that must not be mixed, such as customer work,
NDA-covered work, external-sharing restrictions, or developer/team-specific
repository access.

Repository-level retrieval should use `repo` metadata, not tenants. If the same
agent is allowed to read a group of repositories, those repositories do not need
separate tenants.

Repository tenants are not the default because they:

- make cross-repository retrieval for shared knowledge harder
- do not model monorepo areas such as `apps/api`, `tools/review`, or `docs/adr`
- turn repository rename, split, and merge work into access-control changes
- increase tenant count and make MCP read policy review harder

Exception: if a repository itself is a customer, NDA, external-sharing, or
developer access boundary, using a dedicated tenant for that repository is
reasonable. The decision is not "one repository or many repositories." The
decision is "who may read this knowledge."

Recommended tenant examples:

- `secret-knowledge`
- `client-upwork-18384728-acme`
- `client-acme`

Repository and monorepo-area filtering should use metadata:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

For a monorepo:

```json
{
  "tenant": "secret-knowledge",
  "repo": "platform-monorepo",
  "path": "apps/api/internal/auth/session.go",
  "type": "code",
  "tags": ["api", "auth"]
}
```

The MCP server must reject requested read tenants that are outside the configured
read boundary.
