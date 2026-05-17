# Tenant Operations

Tenants are read boundaries in mem0-local-platform. Use them to define which
knowledge set an AI agent or developer may read.

Tenants are not repository categories. Repository names are stored as metadata.

## Basic Rules

- Use tenants for readable boundaries and registration destinations.
- Use `repo` metadata for repository-level retrieval.
- Use tenant names that match operational isolation decisions.
- Split tenants when customer work, NDA terms, external-sharing restrictions, or
  developer-specific repository access differs.
- Do not split tenants when the same agent may read the same knowledge boundary.

## Recommended Tenants

```text
secret-knowledge
client-*
```

`secret-knowledge` is an example boundary for your own judgment patterns and
internal knowledge that do not need a customer-specific tenant. It does not mean
that arbitrary secrets should be indexed there.

Examples:

```text
secret-knowledge
client-upwork-18384728-acme
client-acme
```

## Avoid Repository Tenants

Do not make repository-per-tenant the default:

```text
backend-testing-patterns
frontend-app
infra-scripts
```

Those names are repositories or topics, not security boundaries.

Repository tenants are not the default because they make shared knowledge harder
to retrieve across repositories, turn repository rename/split/merge work into
access-control changes, and do not model monorepo areas such as `apps/api`,
`tools/review`, or `docs/adr`.

Exception: if a repository itself is a customer, NDA, external-sharing, or
developer access boundary, using a dedicated tenant for that repository is
reasonable. The decision is "who may read this knowledge," not "one repository
or many repositories."

## Metadata

Store repository context as metadata:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

`tenant` decides which knowledge boundary an agent may read. An agent allowed to
read only `secret-knowledge` cannot search `client-acme`.

`repo` and `path` are not access-control boundaries. They identify where a chunk
came from, such as `backend-testing-patterns` and `docs/e2e.md`, so search
results can be filtered or shown with source context.
For monorepo areas, use `path`, `type`, and `tags`.

## Read And Registration Policy

MCP only configures readable tenants:

```yaml
read:
  - secret-knowledge
```

For client work:

```yaml
read:
  - secret-knowledge
  - client-18384728-acme
```

Multiple readable tenants are allowed. Register new memory through GitHub
Actions or the Python CLI, and set the destination tenant there.

## Operational Examples

For internal or shared knowledge, keep the readable tenant narrow:

```yaml
read:
  - secret-knowledge
```

This tenant can contain publishable skills, private judgment patterns, DevEx
templates, research tools, and sales or deal notes. Use metadata to narrow the
search scope.

```text
search_memory(
  query="FastAPI exception review criteria",
  tenants=["secret-knowledge"],
  repo="backend-review-patterns",
  type="doc",
  tags=["backend"]
)
```

Omit `repo` when you want shared knowledge across repositories:

```text
search_memory(
  query="when should flaky E2E behavior be suspected",
  tenants=["secret-knowledge"],
  tags=["testing"]
)
```

Use `repo` when the repository is the scope:

```text
related_repo_context(
  repo="backend-testing-patterns",
  query="trace.zip retention policy",
  tenants=["secret-knowledge"]
)
```

Use `path` for one exact file:

```text
search_memory(
  query="when is retry allowed",
  tenants=["secret-knowledge"],
  repo="backend-testing-patterns",
  path="docs/retry-policy.md"
)
```

For a monorepo, do not split tenants by app or tool. Add tags during ingestion
and combine `repo`, `type`, `tags`, and the query text during retrieval.

```bash
python scripts/ingest_repo.py \
  --root /path/to/platform-monorepo \
  --tenant secret-knowledge \
  --repo platform-monorepo \
  --tag api \
  --tag auth \
  --changed-files apps/api/internal/auth/session.go
```

```text
search_memory(
  query="session refresh failure handling",
  tenants=["secret-knowledge"],
  repo="platform-monorepo",
  type="code",
  tags=["api", "auth"]
)
```

When developers may read different repositories, model that access difference as
tenants:

```yaml
read:
  - secret-knowledge
  - team-platform
```

```yaml
read:
  - secret-knowledge
  - team-sales-tools
```

Here, `team-platform` and `team-sales-tools` are not repository names. They are
knowledge sets with different allowed readers. Inside each tenant, still use
`repo`, `path`, `type`, and `tags` for retrieval scope.

## Review Checklist

When changing tenant settings, check:

- Is the tenant really a security boundary?
- Are the allowed developers or agents actually different?
- Is a repository or project name being used as a tenant?
- Does the registration `tenant` match the current work target?
- Are unnecessary client tenants included in the read list?
- Does the GitHub Actions `tenant` input match the intended destination?
