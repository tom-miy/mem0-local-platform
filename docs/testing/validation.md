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

Render repository sync path rules:

```bash
mise run sync-path-rules
```

When mem0 is running, remove `--dry-run` to upsert chunks.

The Docker Compose runtime exposes a health check inside the Docker Compose network:

```bash
docker compose -f compose.yml exec mem0 \
  uv run python -c "import httpx; print(httpx.get('http://localhost:8000/healthz').json())"
```

From outside the Docker Compose network, use the Cloudflare-protected mem0 hostname.

Run all local checks:

```bash
mise run check
```

Remove local validation artifacts except `data/`:

```bash
mise run clean
```

`clean` removes `.cache` and Python `__pycache__` directories. It does not
remove `data/`.

Remove Docker Compose or integration-test data:

```bash
mise run clean-data
```

Remove all local generated state, including `.venv` and `data/`:

```bash
mise run clean-all
```
