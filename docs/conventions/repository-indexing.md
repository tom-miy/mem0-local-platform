# Repository Indexing Conventions

Repository names are metadata. They are not tenants.

Use tenants for security boundaries and use `repo` metadata for project-level
retrieval.

## Indexed Markdown

The default ingestion rules index:

- `README.md`
- `docs/**/*.md`
- `adr/**/*.md`
- `adrs/**/*.md`

The CLI skips generated or dependency-heavy paths such as `node_modules`,
`dist`, `vendor`, `coverage`, and `build`.

Repositories can override these rules through the reusable workflow inputs:

- `include_paths`
- `exclude_paths`

Exclusion is applied before inclusion. Use this when a repository keeps
Markdown under a project-specific docs directory or needs to skip generated
Markdown.

## Sync Modes

The reusable workflow supports two file-list modes:

- `changed` indexes only files changed by the push diff.
- `full` indexes all tracked files that pass include/exclude rules.

Use `full` for first indexing, policy changes, and recovery after backend state
is rebuilt.

## Chunking

Markdown is split by headings. Heading hierarchy is stored as metadata so a
retrieved chunk can be traced back to its document context.
