# Memory Model

mem0 is retrieval infrastructure, not the canonical datastore.

Canonical content lives in Git repositories, Markdown documents, ADRs, and
Obsidian notes. The platform indexes that content into mem0 so agents can
retrieve context during development.

## Chunk Identity

Chunks use stable upsert IDs derived from:

```text
repo:path:heading
```

The current implementation hashes that value with SHA-256. This keeps repeated
workflow runs idempotent while allowing content updates under the same heading to
replace prior indexed content.

## Metadata

Each chunk carries metadata like:

```json
{
  "tenant": "mimr-tech",
  "repo": "mem0-local-platform",
  "path": "docs/architecture/memory-model.md",
  "type": "doc",
  "tags": ["mem0", "mcp"]
}
```

`tenant` is used for isolation. `repo` and `path` are retrieval metadata.

## Backend Responsibilities

FalkorDB stores graph memory and relationship-oriented context.

Qdrant stores semantic vectors and supports similarity retrieval.

The source repository can rebuild both stores, so operational recovery starts
from Git rather than from mem0 exports.

The compose runtime uses the local API package in this repository to pass Qdrant
and FalkorDB settings into the mem0 OSS library.
