# mem0-local-platform

AI Agent Knowledge Infrastructure for local-first engineering workflows.

Japanese documentation: [README.jp.md](README.jp.md)

This repository runs a self-hosted mem0 layer backed by FalkorDB and Qdrant,
exposes tenant-aware memory tools over MCP, and provides one reusable GitHub
Actions workflow for keeping repository knowledge in sync.
With the local Ollama configuration, indexed knowledge can stay inside your own
Docker runtime instead of being sent to an external AI SaaS.

It can:

- sync README, docs, ADRs, source code, API definitions, and config files from GitHub pushes
- sync repositories from a local clone when GitHub Actions cannot reach mem0
- remember local Markdown, Obsidian notes, and Raycast notes through a Python CLI
- store context in a FalkorDB graph and a Qdrant vector search index
- expose the indexed context to Codex, Claude, and local agents through MCP
- configure which knowledge boundaries agents may search through MCP

The benefit is that AI agents can reuse prior decisions, design notes, and
research findings without asking for the same context again. Git repositories,
source code, API definitions, config files, Markdown, ADRs, and Obsidian notes
remain the durable knowledge sources; mem0 is the rebuildable retrieval index
built from them.
FalkorDB handles relationship-oriented memory, while Qdrant handles semantic
similarity retrieval. If you configure an external LLM or embedding provider,
review what text is sent to that provider.

## Usage Examples

Keep design and implementation context in a repository:

1. Update `docs/e2e.md`, `adr/001-retry-policy.md`, `api/openapi.yaml`, or `cmd/server/main.go`.
2. Push to GitHub.
3. The reusable workflow syncs only changed eligible files into mem0.
4. Codex or Claude can retrieve prior design decisions, API contracts, and implementation details through MCP.

Register a short working note immediately:

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source obsidian \
  --type note \
  --tag debugging \
  --file "$HOME/Obsidian/Vault/ai-workflows/e2e-debugging.md"
```

Search from an AI agent:

```text
search_memory("How should trace.zip be handled when E2E fails?")
```

Separate customer-specific knowledge:

```yaml
read:
  - secret-knowledge
  - client-acme
```

With this policy, the agent can read both `secret-knowledge` and `client-acme`. Register
new customer-specific memory with the GitHub Actions `tenant` input or
`--tenant client-acme` in the Python CLI.

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
4. `scripts/ingest_repo.py` indexes repository context files.
5. Chunks are upserted with stable IDs based on `repo + path + heading`.
6. Agents retrieve memory through MCP tools with tenant filters applied.

## Tenant Strategy

Tenant is a security boundary. It is not a repository name.

Use tenants for isolation scopes such as:

- `secret-knowledge`
- `client-*`

Repository name is metadata:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

`secret-knowledge` is an example tenant for your own judgment patterns and
internal knowledge that do not need a customer-specific tenant. It does not mean
that arbitrary secrets should be stored there. Replace it with the tenant name
that represents your company, studio, team, or solo business boundary if needed.
Use that tenant for public repositories, publishable skills, private judgment
patterns, templates, research tools, and sales or deal notes. Use `client-*`
only when a customer or contract needs its own isolation boundary. Public/private
status, topic, and repository type should be metadata, not tenants.

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
      tenant: secret-knowledge
    secrets:
      MEM0_API_URL: ${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: ${{ secrets.MEM0_API_KEY }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_ID }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

You can generate that workflow and path-rule files in a target repository:

```bash
./install.sh \
  --target github-actions \
  --target-dir /path/to/repository \
  --tenant secret-knowledge
```

Set the target repository secrets with GitHub CLI:

```bash
gh secret set MEM0_API_URL --repo tom-miy/target-repository --body "https://mem0-api.example.com"
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID --repo tom-miy/target-repository --body "..."
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET --repo tom-miy/target-repository --body "..."
```

For organization-wide reuse, use organization secrets with selected repository
access:

```bash
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID \
  --org tom-miy \
  --visibility selected \
  --repos target-repository,another-repository \
  --body "..."
```

The reusable workflow checks out the source repository, checks out this platform
repository for the ingestion CLI, sets up `uv`, creates the platform `.venv`,
and builds the file list from `sync_mode`.
For repository sync from GitHub Actions, `MEM0_API_URL` should be the
Cloudflare-protected mem0 API hostname, not the internal compose URL.
GitHub Actions authenticates to Cloudflare Access with repository secrets named
`MEM0_CLOUDFLARE_ACCESS_CLIENT_ID` and `MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET`.
`MEM0_API_KEY` is optional and only needed when the mem0 endpoint or a custom
gateway requires a Bearer token.
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

For short notes from Obsidian, Raycast, or local Markdown files, use
[Local Tool Ingestion](docs/conventions/local-tool-ingestion.md).

For client repositories where GitHub Actions cannot reach mem0, sync from a
local clone:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
MEM0_SINCE_REF=origin/main \
mise run sync-local-repo
```

Indexed paths:

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

Ignored paths include `node_modules`, `dist`, `vendor`, `coverage`, and build
artifacts. Secret and runtime state paths such as `.env`, `secrets/**`, and
`data/**` are also excluded.

Exclusion applies before inclusion.

## Repository Context Indexing

Markdown is chunked by heading. Code, API definitions, and config files are
indexed as repository context chunks. Each chunk preserves:

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
- `related_repo_context`
- `recent_project_memories`

MCP is read-only by default. Registration is limited to GitHub Actions and the
Python CLI, including Obsidian or Raycast wrappers.

Readable tenants are configured in `mem0.policy.yml`:

```yaml
read:
  - secret-knowledge
```

Search tools only read from configured readable tenants, even when a caller
requests a narrower set.

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

## Tailscale Access

Use Tailscale when your own devices need to reach mem0-local-platform on a home
server. Keep GitHub Actions and external automation on the Cloudflare Access
path; use Tailscale for private access, management, and local ingestion from
devices in your Tailscale account or organization network.

```bash
mise run up-tailscale
tailscale serve --bg --https=8443 localhost:8000
tailscale serve --bg --https=9443 localhost:8010
```

Devices in your Tailscale network can point `mem0.env` at the Tailscale device name:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
```

Tailscale Serve terminates HTTPS. You normally do not need to mount certificate
files into compose. Serve configuration created with `--bg` is saved by the
Tailscale daemon.
Path-based routing such as `/mem0` and `/mem0-mcp` is possible, but API and MCP
clients must work under a subpath. The default example uses port separation with
`8443` and `9443`.

See [Tailscale Access](docs/security/tailscale-access.md).

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

For a home server, start it in the background. Every service in `compose.yml`
uses `restart: unless-stopped`, so containers restart when the Docker daemon
starts.

```bash
mise run start
```

Start with explicit memory limits:

```bash
mise run up-resources
```

Start in the background with memory limits:

```bash
mise run start-resources
```

Pull the default Ollama models into the compose `ollama` service:

```bash
mise run ollama-pull
```

The `mem0` service is built from this repository. It wraps the mem0 OSS Python
library instead of depending on an unverified external image.

Persistent backend data is stored under `data/` with bind mounts:

```text
data/falkordb/
data/qdrant/
data/mem0/
data/ollama/
```

Back up `data/` with normal filesystem backup tools. The compose file does not
use Docker named volumes for state.

Docker memory sizing guide:
[docs/operations/resource-sizing.md](docs/operations/resource-sizing.md)

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
- MCP is read-only; writes go through GitHub Actions or the Python CLI.
- Service tokens are used for agent authentication through Cloudflare Access.
- Secrets and personal data must not be emitted in logs.

For local Claude Code, Cursor, Copilot, or Codex usage, pair this repository with
`agent-privacy-guard` so retrieved mem0 context can be anonymized and routed
before it is sent to an AI client or external model. `agent-privacy-guard` acts
as an AI Agent Governance Gateway for prompt anonymization, MCP trust routing,
and hook-based safety controls. mem0-local-platform stores and retrieves memory;
`agent-privacy-guard` controls prompts and tool calls, including retrieved
memory context, before they leave the local client path.

That control does not normally apply to GitHub Actions sync jobs. GitHub Actions
runs the reusable workflow directly on a GitHub runner. Protect Actions sync with
Cloudflare Access service tokens, GitHub secrets, include/exclude path rules, and
the intended tenant input. To apply `agent-privacy-guard` to GitHub Actions, the
workflow itself would need to be explicitly routed through that gateway.

## Repository Indexing Lifecycle

1. Author updates code, API definitions, config, or Markdown in Git.
2. Pull request review happens in the source repository.
3. Merge or push triggers the reusable sync workflow.
4. Changed eligible files are cleaned and chunked.
5. Existing chunks for the same `tenant + repo + path` are deleted before re-indexing.
6. Deleted and renamed source paths remove stale chunks from mem0.
7. Agents retrieve current context through MCP.

See `docs/architecture/` and `docs/security/` for design notes.
