# Repository Indexing Conventions

Repository names are metadata. They are not tenants.

Use tenants for security boundaries and use `repo` metadata for project-level
retrieval.

## Indexed Markdown

The default ingestion rules index:

- `README.md`
- `README*.md`
- `docs/**/*.md`
- `adr/**/*.md`
- `adrs/**/*.md`

The CLI skips generated or dependency-heavy paths such as `node_modules`,
`dist`, `vendor`, `coverage`, and `build`.
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

## Chunking

Markdown is split by headings. Heading hierarchy is stored as metadata so a
retrieved chunk can be traced back to its document context.
