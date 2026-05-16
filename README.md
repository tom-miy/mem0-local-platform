# mem0-local-platform

Developer Knowledge Infrastructure for local-first AI-assisted engineering.

Japanese documentation: [README.jp.md](README.jp.md)

This repository runs a self-hosted mem0 layer backed by FalkorDB and Qdrant,
exposes tenant-aware memory tools over MCP, and provides one reusable GitHub
Actions workflow for keeping repository knowledge in sync.

mem0 is not the source of truth. Git repositories, Markdown docs, ADRs, and
Obsidian notes remain canonical. mem0 is the retrieval cache and runtime context
layer that agents use while working.

## Architecture

```text
Git repository
  -> GitHub push
  -> reusable mem0 sync workflow
  -> ingest-to-mem0 CLI
  -> Cloudflare Tunnel
  -> mem0
     -> FalkorDB graph memory
     -> Qdrant vector retrieval
  -> MCP
  -> Codex / Claude / local agents
```

## Memory Flow

1. A repository changes through normal Git work.
2. GitHub push triggers `.github/workflows/reusable-sync.yml`.
3. The workflow selects changed files or all tracked files.
4. `scripts/ingest_repo.py` indexes Markdown-first content.
5. Chunks are upserted with stable IDs based on `repo + path + heading`.
6. Agents retrieve memory through MCP tools with tenant filters applied.

## Tenant Strategy

Tenant is a security boundary. It is not a repository name.

Use tenants for isolation scopes such as:

- `mimr-tech`
- `client-*`

Repository name is metadata:

```json
{
  "tenant": "mimr-tech",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

Use `mimr-tech` for knowledge controlled by mimr-tech: public portfolio
repositories, publishable skills, private judgment patterns, templates,
research tools, and Upwork-related notes. Use `client-*` only when a customer
or contract needs its own isolation boundary. Public/private status, topic, and
repository type should be metadata, not tenants.

## GitHub Sync Strategy

Workflow logic is centralized here:

```text
.github/workflows/reusable-sync.yml
```

That workflow is `workflow_call` only. It is the shared implementation.

Calling repositories should contain only a thin trigger workflow:

```yaml
name: Sync Repository Memory

on:
  push:
    branches:
      - main
  workflow_dispatch:
    inputs:
      sync_mode:
        description: changed indexes push diffs, full indexes all eligible files.
        required: true
        type: choice
        options:
          - changed
          - full
        default: full

jobs:
  sync:
    uses: tom-miy/mem0-local-platform/.github/workflows/reusable-sync.yml@main
    with:
      sync_mode: ${{ github.event.inputs.sync_mode || 'changed' }}
      tenant: mimr-tech
    secrets:
      MEM0_API_URL: ${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: ${{ secrets.MEM0_API_KEY }}
      CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.CLOUDFLARE_ACCESS_CLIENT_ID }}
      CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

You can generate that workflow and path-rule files in a target repository:

```bash
./install.sh \
  --target github-actions \
  --target-dir /path/to/repository \
  --tenant mimr-tech
```

The reusable workflow checks out the source repository, checks out this platform
repository for the ingestion CLI, sets up `uv`, creates the platform `.venv`,
and builds the file list from `sync_mode`.
For repository sync from GitHub Actions, `MEM0_API_URL` should be the
Cloudflare-protected mem0 API hostname, not the internal compose URL.
GitHub Actions authenticates to Cloudflare Access with
`CLOUDFLARE_ACCESS_CLIENT_ID` and `CLOUDFLARE_ACCESS_CLIENT_SECRET`.
`CLOUDFLARE_TUNNEL_TOKEN` is only used by the platform runtime's
`cloudflared` service.

Each repository can keep path rules in a source-controlled config file:

```text
.mem0-sync.yml
```

The reusable workflow reads that file when it exists. If it is absent, it uses
`.mem0-sync.default.yml` from this platform repository. The workflow itself does
not carry path-rule defaults.
The YAML keys are `include` and `exclude`.

`sync_mode` controls the file list:

- `changed` indexes files changed by the push diff.
- `full` indexes all tracked files that pass include/exclude rules.

Use `changed` for normal push sync. Use `full` for initial indexing, policy
changes, or recovery after rebuilding mem0 state.

To run a full sync manually, open the target repository in GitHub, go to
`Actions`, choose `Sync Repository Memory`, run the workflow, and select
`sync_mode=full`.

Indexed paths:

- `README.md`
- `README*.md`
- `docs/**/*.md`
- `adr/**/*.md`
- `adrs/**/*.md`

Ignored paths include `node_modules`, `dist`, `vendor`, `coverage`, and build
artifacts.

Exclusion applies before inclusion.

## Markdown Indexing

Markdown is chunked by heading. Each chunk preserves:

- tenant
- repository metadata
- relative path
- inferred document type
- heading hierarchy
- tags

Stable IDs are SHA-256 hashes of:

```text
repo:path:heading
```

## MCP Integration

The FastMCP server exposes:

- `search_memory`
- `remember`
- `related_repo_context`
- `recent_project_memories`

Read and write boundaries are separated:

```yaml
read:
  - mimr-tech
write:
  - mimr-tech
```

`remember` always writes to the configured write tenant. Search tools only read
from configured readable tenants, even when a caller requests a narrower set.

## Cloudflare Setup

Primary access is through Cloudflare Tunnel, Cloudflare Access, and Service
Token authentication. The compose stack includes `cloudflared`; agent traffic
should enter through Cloudflare and reach internal services by Docker DNS.

Human OAuth login can be added, but it is not required for the default target.

Required environment variables are listed in `.env.example`:

- `CLOUDFLARE_TUNNEL_TOKEN`
- `CLOUDFLARE_ACCESS_CLIENT_ID`
- `CLOUDFLARE_ACCESS_CLIENT_SECRET`

Configure Tunnel routing in Cloudflare:

```text
mem0-api.example.com -> http://mem0:8000
mem0-mcp.example.com -> http://mcp:8010
```

Do not log service tokens or copy them into Markdown docs.

## Backend Responsibilities

FalkorDB stores graph-oriented memory relationships.

Qdrant stores semantic vectors for retrieval.

The local `mem0` API service coordinates memory writes, graph updates, and
vector search through the mem0 OSS library. This repository keeps source content
outside mem0 and treats mem0 as rebuildable infrastructure.

## Local Run

Trust and install the local toolchain:

```bash
mise trust .
mise install
mise run setup
```

Create a local env file:

```bash
cp .env.example .env
cp mem0.policy.example.yml mem0.policy.yml
```

Start the runtime:

```bash
mise run up
```

The `mem0` service is built from this repository. It wraps the mem0 OSS Python
library instead of depending on an unverified external image.

Persistent backend data is stored under `data/` with bind mounts:

```text
data/falkordb/
data/qdrant/
data/mem0/
```

Back up `data/` with normal filesystem backup tools. The compose file does not
use Docker named volumes for state.

Run a dry ingestion against this repository:

```bash
mise run ingest-dry-run
```

Run the MCP server locally:

```bash
uv run mem0-local-mcp
```

Print MCP client setup snippets:

```bash
./install.sh --target generic --transport stdio
```

Print Codex MCP setup:

```bash
cp mem0.env.example mem0.env
./install.sh --target codex
```

Japanese MCP setup guide: [docs/conventions/mcp-setup.jp.md](docs/conventions/mcp-setup.jp.md)

Model provider examples:
[docs/architecture/model-provider-settings.md](docs/architecture/model-provider-settings.md)

Run local validation:

```bash
mise run check
```

## Security Model

- Tenant boundaries are isolation boundaries.
- Repository names are metadata, not authorization boundaries.
- Git and Markdown remain the canonical source.
- mem0 can be rebuilt from source content.
- MCP tools inject tenant filters automatically.
- Write access is limited to one configured write tenant.
- Service tokens are used for agent authentication through Cloudflare Access.
- Secrets and personal data must not be emitted in logs.

## Repository Indexing Lifecycle

1. Author updates Markdown in Git.
2. Pull request review happens in the source repository.
3. Merge or push triggers the reusable sync workflow.
4. Changed Markdown files are cleaned and chunked.
5. Chunks are upserted into mem0 with stable IDs.
6. Agents retrieve current context through MCP.

See `docs/architecture/` and `docs/security/` for design notes.
