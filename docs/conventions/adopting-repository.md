# Add mem0 Sync to Another Repository

This guide shows how to add repository memory sync to an existing repository.

Do not copy ingestion logic into target repositories. Each repository should only
contain a thin caller workflow and optional path rules.

## Prerequisites

mem0-local-platform must be running, and GitHub Actions must be able to reach the
mem0 API through Cloudflare Access.

Set these GitHub repository secrets:

- `MEM0_API_URL`
- `MEM0_CLOUDFLARE_ACCESS_CLIENT_ID`
- `MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET`

`MEM0_API_URL` should be the Cloudflare-protected hostname. Do not use the
internal compose URL from GitHub Actions.

`MEM0_API_KEY` is optional. Leave it unset for the default self-hosted runtime
protected by Cloudflare Access. Set it only when the mem0 endpoint itself, a SaaS
mem0 API, or a custom gateway requires a Bearer token.

Set them with GitHub CLI:

```bash
gh secret set MEM0_API_URL \
  --repo tom-miy/target-repository \
  --body "https://mem0-api.example.com"

gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID \
  --repo tom-miy/target-repository \
  --body "..."

gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET \
  --repo tom-miy/target-repository \
  --body "..."
```

Or load them from a dotenv-formatted file:

```bash
gh secret set --repo tom-miy/target-repository -f mem0.github-secrets.env
```

Example `mem0.github-secrets.env`:

```env
MEM0_API_URL=https://mem0-api.example.com
MEM0_CLOUDFLARE_ACCESS_CLIENT_ID=...
MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

If many repositories under the same organization use the same mem0 endpoint,
store the secrets at the organization level instead:

```bash
gh secret set MEM0_API_URL \
  --org tom-miy \
  --visibility selected \
  --repos target-repository,another-repository \
  --body "https://mem0-api.example.com"

gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID \
  --org tom-miy \
  --visibility selected \
  --repos target-repository,another-repository \
  --body "..."

gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET \
  --org tom-miy \
  --visibility selected \
  --repos target-repository,another-repository \
  --body "..."
```

Use `--visibility private` for all private repositories in the organization, or
`--visibility all` only when public repositories should also receive the secret.
For personal accounts, GitHub Actions secrets are repository-level; user-level
`gh secret set --user` is for Codespaces, not Actions.

## Install

Generate the caller workflow and path-rule file:

```bash
/path/to/mem0-local-platform/install.sh \
  --target github-actions \
  --target-dir /path/to/repository \
  --tenant mimr-tech
```

This creates:

```text
.github/workflows/sync-memory.yml
.mem0-sync.yml
```

Existing files are not overwritten unless `--force` is provided.

## Manual Workflow

If you add the workflow manually, use:

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
      MEM0_CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_ID }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

## Full Sync

Use `changed` for normal push sync. Use `full` for first indexing, path-rule
changes, backend rebuilds, and repair runs.

To run a full sync from GitHub, open the target repository, go to `Actions`,
select `Sync Repository Memory`, run the workflow, and choose `sync_mode=full`.

GitHub CLI example:

```bash
gh workflow run "Sync Repository Memory" \
  --ref main \
  -f sync_mode=full
```
