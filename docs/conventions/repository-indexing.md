# Repository Indexing Conventions

Repository names are metadata. They are not tenants.

Use tenants for security boundaries and use `repo` metadata for project-level
retrieval.
When you need both shared knowledge and repository-specific knowledge, keep them
in the same tenant when the readable boundary is the same, and filter by `repo`,
`path`, `type`, and `tags`. Monorepo areas should also use `path` and `tags`.

## Retrieval Scopes

Use metadata to split retrieval scope inside the same tenant:

- `repo`: repository name from GitHub Actions or the CLI `--repo` argument
- `path`: repository-relative path, saved automatically per file
- `type`: broad file category inferred from `path`
- `tags`: optional classifications passed with CLI `--tag`

Registration example:

```bash
python scripts/ingest_repo.py \
  --root /path/to/backend-testing-patterns \
  --tenant secret-knowledge \
  --repo backend-testing-patterns \
  --tag backend \
  --tag testing \
  --since-ref origin/main
```

That produces chunk metadata such as:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["backend", "testing"]
}
```

MCP searches can pass the same metadata filters:

```text
search_memory(
  query="when should trace.zip be preserved",
  tenants=["secret-knowledge"],
  repo="backend-testing-patterns",
  type="doc",
  tags=["testing"]
)
```

Use `related_repo_context` when the repository is the main scope:

```text
related_repo_context(
  repo="backend-testing-patterns",
  query="E2E failure log retention policy",
  tenants=["secret-knowledge"]
)
```

`path` is an exact metadata filter for one file:

```text
search_memory(
  query="retry decision criteria",
  tenants=["secret-knowledge"],
  repo="backend-testing-patterns",
  path="docs/retry-policy.md"
)
```

For broad monorepo areas such as `apps/api/**`, combine `repo`, `type`, `tags`,
and the query text. Add tags such as `api` or `tool` at ingestion time when you
know you will need those scopes later.

## Indexed Repository Context

The default ingestion rules index:

- `README.md`
- `README*.md`
- `docs/**/*.md`
- `adr/**/*.md`
- `adrs/**/*.md`
- `**/*.go`
- `**/*.py`
- `**/*.ts`
- `**/*.tsx`
- `**/*.js`
- `**/*.jsx`
- `**/*.rs`
- `**/*.java`
- `**/*.kt`
- `**/*.sql`
- `**/*.sh`
- `api.yaml`
- `openapi.yaml`
- `**/*.yaml`
- `**/*.yml`
- `**/*.json`
- `**/*.toml`
- `**/*.proto`
- `Dockerfile`
- `compose.yml`
- `Makefile`

The CLI skips generated or dependency-heavy paths such as `node_modules`,
`dist`, `vendor`, `coverage`, and `build`.
Secret and runtime state paths such as `.env`, `secrets/**`, and `data/**` are
also excluded.
It also excludes binary and non-text formats such as PDF, Office documents,
images, archives, and media files. Those need file-type-specific extractors
before they should be indexed.

Repositories can keep path rules in a source-controlled YAML file:

```text
.mem0-sync.yml
```

The reusable workflow reads that file when it exists. If it is absent, it uses
`.mem0-sync.default.yml` from the platform repository. The workflow itself does
not carry path-rule defaults.
The YAML keys are `include` and `exclude`.

Exclusion is applied before inclusion.

## Sync Modes

The reusable workflow supports two file-list modes:

- `changed` indexes only files changed by the push diff.
- `full` indexes all tracked files that pass include/exclude rules.

Use `full` for first indexing, policy changes, and recovery after backend state
is rebuilt.

For changed sync, deleted files and renamed source paths are also passed to the
ingestion CLI. Existing chunks for the same `tenant + repo + path` are deleted
before a file is re-indexed, so removed headings and deleted files do not leave
stale chunks behind.

## Chunking

Markdown is split by headings. Heading hierarchy is stored as metadata so a
retrieved chunk can be traced back to its document context.
Code, API definitions, and config files are also indexed as repository context,
with path, document type, and repository metadata preserved.

`type` is inferred by the Python ingestion code from `path` at registration
time. Current values are:

```text
readme
adr
doc
code
config
markdown
```

`type` is a broad file category. Usage-level labels such as local tool Go code
versus main app Go code are both stored as `type=code`; retrieval should
interpret `repo` and `path` when it needs that distinction. Paths such as
`tools/**`, `scripts/**`, and `cmd/**` can mean different things per repository,
so they are not stored as fixed mem0 metadata.
