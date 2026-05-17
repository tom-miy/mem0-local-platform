# Docker Resource Sizing

`compose.yml` does not hard-code memory limits because developer laptops and
home servers vary a lot.

Use `compose.resources.yml` when you want explicit memory limits:

```bash
mise run up-resources
```

Use it with the Tailscale localhost-bind override:

```bash
mise run up-tailscale-resources
```

## Starting Point

External LLM and external embedding provider:

```text
Host memory: 4GB to 6GB
```

Local Ollama with a small LLM and embedding model:

```text
Host memory: 12GB to 16GB
Example: qwen3.5:4b + bge-m3
```

Larger local models:

```text
Host memory: 24GB to 32GB+
Example: 8B+ models, multiple resident models, repeated ingestion of large repos
```

## Default Limits

Initial values in `compose.resources.yml`:

```text
falkordb:    1GB
qdrant:      2GB
ollama:      8GB
mem0:        1GB
mcp:       512MB
cloudflared: 256MB
```

These limits are meant to make behavior predictable on a small personal server.
They are not tuned for maximum throughput.

## What To Increase

Ollama usually uses the most memory. If you run the LLM locally, increase the
`ollama` limit first.

Qdrant grows with chunk count and embedding dimensions. Increase `qdrant` when
you index many repositories or long Markdown documents.

FalkorDB grows with relationships and history. Increase `falkordb` when you keep
more related memories and cross-repository context.

Increase `mem0` if the mem0 API process is OOM-killed. `mcp` and `cloudflared`
usually stay small.

## Inspect Usage

After startup, inspect actual usage:

```bash
docker stats
```

Docker Desktop has its own memory cap. If you run local Ollama through Docker
Desktop, start by allocating 12GB to 16GB in Docker Desktop Resources.

## Operating Rule

- Keep `compose.yml` as the shared default.
- Put memory limits in `compose.resources.yml`.
- Do not commit host-specific tuning; use a personal override file if needed.
- When OOM happens, check `docker stats` before increasing limits.
