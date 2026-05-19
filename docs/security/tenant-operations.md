# Tenant Operations

Tenants are read boundaries in mem0-local-platform. Use them to define which
knowledge set an AI agent or developer may read.

Tenants are not repository categories. Repository names are stored as metadata.

## Basic Rules

- Use tenants for readable boundaries and registration destinations.
- Use `repo` metadata for repository-level retrieval.
- Use tenant names that match operational isolation decisions.
- Split tenants when allowed readers differ across customers, teams, developers,
  or AI agents.
- Split tenants when handling rules differ, such as NDA terms,
  external-sharing restrictions, or reuse restrictions.
- Split tenants when leak impact differs, such as sensitive architecture
  details, decision patterns, operating procedures, or vulnerability context.
- Do not split tenants when the same agent may read the same knowledge boundary.
Use `repo`, `path`, `type`, and `tags` for classifications that do not change the
read boundary.

## Recommended Tenants

Tenant names should describe the read boundary, not the repository name. Choose
names that make it clear who may read the knowledge and which owner or customer
boundary it belongs to.

Useful tenant names:

- Personal or company knowledge boundary: `secret-knowledge`, `studio-knowledge`, `mimr-internal`
- Team boundary: `team-platform`, `team-sales-tools`
- Customer or project boundary: `client-acme`, `client-upwork-18384728-acme`
- NDA or external-sharing boundary: `restricted-acme`, `nda-partner-x`

Naming rules:

- The allowed people or AI agents should be understandable from the name.
- Customer, project, team, or ownership boundaries should be visible.
- The name should still make sense if repositories are renamed.
- Do not name tenants only by public/private status, language, framework, or app name.

Base shapes:

- `secret-knowledge`
- `client-*`

`secret-knowledge` is an example boundary for your own judgment patterns and
internal knowledge that do not need a customer-specific tenant. It does not mean
that arbitrary secrets should be indexed there.

## Do Not Use Repository Names As Tenants By Default

Repository names, app names, tool names, and technical area names usually belong
in `repo`, `path`, `type`, or `tags` metadata instead.

If the name does not tell you who may read the knowledge, do not use it as a
tenant name. The following examples are repository names, app names, tool names,
or technical area names. They describe source or retrieval scope, not read
boundaries:

- `backend-testing-patterns`: repository name
- `frontend-app`: app name
- `infra-scripts`: tool or script area
- `platform-api`: app or API area
- `review-tools`: tool or purpose name
- `terraform-modules`: technical area or module group

Repository names are not the default tenant shape because they make shared
knowledge harder to retrieve across repositories, turn repository rename, split,
and merge work into access-control changes, do not model monorepo areas such as
`apps/api` or `tools/review`, and increase policy-review overhead.

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
Policy file format: [policy-format.md](policy-format.md)

## Operational Examples

For internal or shared knowledge, keep the readable tenant narrow:

```yaml
read:
  - secret-knowledge
```

This tenant can contain publishable skills, private judgment patterns, DevEx
templates, research tools, and sales or deal notes. Use metadata to narrow the
search scope.

```python
search_memory(
  query="FastAPI exception review criteria",
  tenants=["secret-knowledge"],
  repo="backend-review-patterns",
  type="doc",
  tags=["backend"]
)
```

Omit `repo` when you want shared knowledge across repositories:

```python
search_memory(
  query="when should flaky E2E behavior be suspected",
  tenants=["secret-knowledge"],
  tags=["testing"]
)
```

Use `repo` when the repository is the scope:

```python
related_repo_context(
  repo="backend-testing-patterns",
  query="trace.zip retention policy",
  tenants=["secret-knowledge"]
)
```

Use `path` for one exact file:

```python
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

```python
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

## Tenant Configuration Change Check

Use this when changing `mem0.policy.yml`, GitHub Actions `tenant` inputs, or
local sync `--tenant` values. The goal is to avoid exposing knowledge to agents
or developers that should not read it, and to avoid writing memory into the wrong
tenant.

- Is the new tenant really a read boundary?
- Are the allowed developers, teams, or AI agents actually different?
- Is a repository or project name being used as a tenant?
- Does `mem0.policy.yml` include unnecessary client or sensitive tenants in `read`?
- Does the GitHub Actions `tenant` input match the intended write destination?
- Does local sync or Python CLI `--tenant` match the current work target?
