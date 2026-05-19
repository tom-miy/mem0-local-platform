# Backup

State is stored in repository-local bind mounts under `data/`.

- `data/falkordb/`
- `data/qdrant/`
- `data/mem0/`
- `data/ollama/`

The Docker Compose `compose.yml` file intentionally avoids Docker named volumes for backend state.
This keeps backups visible to standard filesystem tooling and avoids hidden
Docker volume paths.

## Backup Scope

Back up the whole `data/` directory when the stack is stopped.

If hot backups are required, use backend-specific backup commands for Qdrant and
FalkorDB before copying files.

## Restore

1. Stop the compose stack.
2. Restore `data/` from backup.
3. Start the compose stack.
4. Run a dry repository sync before allowing writes.

Git and Markdown remain the canonical source. If backend state is lost, the
semantic index can be rebuilt from repositories.
