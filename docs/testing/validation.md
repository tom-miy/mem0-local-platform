# Validation

Local validation should prove the indexing path without requiring a live mem0
service.

Run syntax checks:

```bash
mise run compile
```

Run ingestion in dry-run mode:

```bash
mise run ingest-dry-run
```

When mem0 is running, remove `--dry-run` to upsert chunks.

The compose runtime exposes a health check inside the compose network:

```bash
docker compose -f compose.yml exec mem0 \
  uv run python -c "import httpx; print(httpx.get('http://localhost:8000/healthz').json())"
```

From outside the compose network, use the Cloudflare-protected mem0 hostname.

Run all local checks:

```bash
mise run check
```
