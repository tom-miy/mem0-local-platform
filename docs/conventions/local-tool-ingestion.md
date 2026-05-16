# Local Tool Ingestion

This guide is for sending short notes to mem0 from Raycast, Alfred, shell
scripts, or similar local tools.

This path is separate from GitHub Actions repository sync. Use the reusable
workflow for repository Markdown. Use `remember-to-mem0` for a short working
note, research note, or decision that has not yet been written back to Git.

## Connection

From outside Docker Compose, use the Cloudflare Access protected API hostname:

```text
MEM0_API_URL=https://mem0-api.example.com
```

Only services inside the compose network should use:

```text
MEM0_API_URL=http://mem0:8000
```

Local tools also need the Cloudflare Access service token values:

```text
CLOUDFLARE_ACCESS_CLIENT_ID=...
CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

Do not use `CLOUDFLARE_TUNNEL_TOKEN` from local tools. That token is only for the
runtime `cloudflared` service.

## Direct Use

Pass text directly:

```bash
MEM0_API_URL=https://mem0-api.example.com \
CLOUDFLARE_ACCESS_CLIENT_ID=... \
CLOUDFLARE_ACCESS_CLIENT_SECRET=... \
uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source raycast \
  --type note \
  --tag idea \
  --text "Check trace.zip first when E2E fails"
```

Read from standard input:

```bash
pbpaste | uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source raycast \
  --type note \
  --tag clipboard
```

Read from a file:

```bash
uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source local-file \
  --type note \
  --file /path/to/note.md
```

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
    --tenant mimr-tech \
    --source raycast \
    --type note \
    --tag clipboard
```

Important long-lived knowledge should still be moved back into Git, Markdown, or
an ADR. mem0 is retrieval infrastructure, not the source of truth.
