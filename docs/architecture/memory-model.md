# Memory Model

mem0 is retrieval infrastructure, not the canonical datastore.

Canonical content lives in Git repositories, Markdown documents, ADRs, and
Obsidian notes. The platform indexes that content into mem0 so agents can
retrieve context during development.

## Chunk Identity

Chunks use stable upsert IDs derived from `repo:path:heading[:occurrence]`.

The occurrence suffix is used only when the same heading appears more than once
in the same file. The current implementation hashes that value with SHA-256.
This keeps repeated workflow runs idempotent while allowing content updates
under the same heading to replace prior indexed content.

## Metadata

Each chunk carries metadata like:

```json
{
  "tenant": "secret-knowledge",
  "repo": "mem0-local-platform",
  "path": "docs/architecture/memory-model.md",
  "type": "doc",
  "tags": ["mem0", "mcp"]
}
```

`tenant` decides which knowledge boundary an agent may read. For example, an
agent allowed to read only `secret-knowledge` cannot search `client-acme`.

`repo` and `path` are not access-control boundaries. They tell the retrieval
layer which repository and file a chunk came from, so results can be filtered or
shown with source context.

`type` is a broad file category inferred by the ingestion CLI from `path`.
For example, `docs/**` becomes `doc`, `adr/**` becomes `adr`, `.go` and `.py`
become `code`, and `.yaml` or `Dockerfile` become `config`.
Usage-level roles are not stored in `type`. Local tool Go code and main app Go
code are both stored as `code`; retrieval should interpret `repo` and `path`
when it needs that distinction.

## Backend Responsibilities

FalkorDB stores graph memory and relationship-oriented context.

Qdrant stores semantic vectors and supports similarity retrieval.

The source repository can rebuild both stores, so operational recovery starts
from Git rather than from mem0 exports.

The compose runtime uses the local API package in this repository to pass Qdrant
and FalkorDB settings into the mem0 OSS library.
