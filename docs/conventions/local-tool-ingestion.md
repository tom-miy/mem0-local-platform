# Local Tool Ingestion

This guide is for sending short notes to mem0 from Obsidian, Raycast, Alfred,
shell scripts, or similar local tools.

This path is separate from GitHub Actions repository sync. Use the reusable
workflow for normal repository sync. When a client repository cannot connect to
mem0 from GitHub Actions, sync a local clone with changed or full mode. Use
`remember-to-mem0` for a short working note, research note, or decision that has
not yet been written back to Git.

## Connection

From outside Docker Compose, use the Cloudflare Access protected API hostname:

```text
MEM0_API_URL=https://mem0-api.example.com
```

From your own devices in a tailnet, you can also use the Tailscale device name:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
```

Only services inside the compose network should use:

```text
MEM0_API_URL=http://mem0:8000
```

Local tools using the Cloudflare Access path also need the Cloudflare Access
service token values. Tailscale access does not need Cloudflare Access service
tokens.

```text
CLOUDFLARE_ACCESS_CLIENT_ID=...
CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

Do not use `CLOUDFLARE_TUNNEL_TOKEN` from local tools. That token is only for the
runtime `cloudflared` service.

## Local Repository Diff Sync

For repositories that cannot use GitHub Actions, sync from a local clone. The
command uses `.mem0-sync.yml` from the target repository when it exists, and
falls back to `.mem0-sync.default.yml` from mem0-local-platform.

Dry-run working tree and staged changes:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
mise run sync-local-repo-dry-run
```

Register those changes:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
mise run sync-local-repo
```

Sync the whole branch diff from `origin/main`:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
MEM0_SINCE_REF=origin/main \
mise run sync-local-repo
```

Use full sync for first indexing or rebuilds:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
MEM0_SYNC_MODE=full \
mise run sync-local-repo
```

To include untracked files, call the CLI directly:

```bash
uv run sync-local-repo-to-mem0 \
  --root /path/to/client-repository \
  --tenant client-acme \
  --since-ref origin/main \
  --include-untracked
```

This path also deletes existing chunks for the same `tenant + repo + path`
before re-indexing. Deleted files and renamed source paths remove stale chunks
from mem0 when they appear in the local diff.

## Direct Use

Pass text directly:

```bash
MEM0_API_URL=https://mem0-api.example.com \
CLOUDFLARE_ACCESS_CLIENT_ID=... \
CLOUDFLARE_ACCESS_CLIENT_SECRET=... \
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source raycast \
  --type note \
  --tag idea \
  --text "Check trace.zip first when E2E fails"
```

Read from standard input:

```bash
pbpaste | uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source raycast \
  --type note \
  --tag clipboard
```

Read from a file:

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source local-file \
  --type note \
  --file /path/to/note.md
```

You can also call the Python module directly. It behaves the same as the
`remember-to-mem0` script entrypoint.

```bash
uv run python -m scripts.remember_text \
  --tenant secret-knowledge \
  --source local-file \
  --type note \
  --file /path/to/note.md
```

## Obsidian

To register an Obsidian vault note, pass the note file path to `--file`:

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source obsidian \
  --type note \
  --path "obsidian/ai-workflows/e2e-debugging.md" \
  --tag obsidian \
  --tag debugging \
  --file "$HOME/Obsidian/Vault/ai-workflows/e2e-debugging.md"
```

`--path` is the relative search path stored in mem0 metadata. It does not need
to expose the real local filesystem path.

Use a separate tenant, such as `client-*`, only when customer work, NDA terms,
external-sharing restrictions, or developer-specific repository access requires
an isolation boundary. Use `--tag` and `--path` for public/private status,
repository type, and topic metadata.

If you call this from an Obsidian shell command plugin or shortcut, pass the
current file path to `--file`. Limit the source folders so notes containing
secrets are not sent to mem0.

## Raycast Script Command

Example Raycast script command:

```bash
#!/usr/bin/env bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Remember Clipboard to mem0
# @raycast.mode compact
#
# Optional parameters:
# @raycast.icon memory-stick
# @raycast.packageName mem0-local-platform
#
# Documentation:
# @raycast.description Send clipboard text to mem0 through Cloudflare Access.

set -euo pipefail

cd "$HOME/ghq/personal/github.com/tom-miy/mem0-local-platform"

pbpaste | \
  MEM0_API_URL="https://mem0-api.example.com" \
  CLOUDFLARE_ACCESS_CLIENT_ID="$CLOUDFLARE_ACCESS_CLIENT_ID" \
  CLOUDFLARE_ACCESS_CLIENT_SECRET="$CLOUDFLARE_ACCESS_CLIENT_SECRET" \
  uv run remember-to-mem0 \
    --tenant secret-knowledge \
    --source raycast \
    --type note \
    --tag clipboard
```

Important long-lived knowledge should still be moved back into Git, Markdown,
Obsidian, or an ADR. mem0 is the retrieval index used by agents, not the only
place that information should live.
