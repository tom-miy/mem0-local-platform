# mem0-local-platform

開発者向けのローカル AI メモリ基盤です。

このリポジトリは、self-hosted mem0 runtime、FalkorDB、Qdrant、
Cloudflare Tunnel、MCP、GitHub Actions による自動同期をまとめます。
目的は toy RAG demo ではなく、実際の AI-assisted engineering workflow で
使える Developer Knowledge Infrastructure を作ることです。

mem0 は正本ではありません。

正本は次です。

- Git リポジトリ
- Markdown ドキュメント
- ADR
- Obsidian notes

mem0 は semantic retrieval cache、AI memory index、runtime context layer
として扱います。

## アーキテクチャ

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

## メモリ同期の流れ

1. Git リポジトリで Markdown や ADR を更新します。
2. GitHub push が thin caller workflow を起動します。
3. caller workflow は共通 workflow を呼び出します。
4. 共通 workflow が `changed` または `full` の file list を作ります。
5. `scripts/ingest_repo.py` が Markdown を heading ごとに chunk します。
6. chunk は stable ID で mem0 に upsert されます。
7. agent は MCP 経由で tenant filter 付きの検索を行います。

## tenant 戦略

tenant はセキュリティ境界です。

リポジトリごとに tenant を作ってはいけません。repo 名は metadata として
保存します。

推奨 tenant:

- `vault`
- `work`
- `client-*`
- `agency-*`

metadata 例:

```json
{
  "tenant": "work",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

repo ごとに tenant を作ると、tenant が増えすぎて運用と監査が難しくなります。
詳細は [tenant 運用ルール](docs/security/tenant-operations.jp.md) を見てください。

## 別リポジトリへの追加

別リポジトリ側には thin caller workflow だけを追加します。

取り込み CLI、差分判定、除外ルールを各リポジトリへコピーしません。

```yaml
name: Sync Repository Memory

on:
  push:
    branches:
      - main
  workflow_dispatch:
    inputs:
      sync_mode:
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
      tenant: work
    secrets:
      MEM0_API_URL: ${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: ${{ secrets.MEM0_API_KEY }}
      CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.CLOUDFLARE_ACCESS_CLIENT_ID }}
      CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

通常の push では `changed` を使います。
初回投入、除外ルール変更後、mem0 state の再構築後は `full` を使います。

詳細は [別リポジトリへの導入手順](docs/conventions/adopting-repository.jp.md)
を見てください。

## 共通 workflow

共通 workflow はここにあります。

```text
.github/workflows/reusable-sync.yml
```

これは `workflow_call` 専用です。

各リポジトリに workflow logic をコピーせず、`uses:` でこの workflow を
呼び出します。

主な inputs:

- `sync_mode`: `changed` または `full`
- `tenant`: 書き込み先 tenant
- `repo`: metadata として保存する repo 名
- `include_paths`: index 対象 path
- `exclude_paths`: 除外 path

`exclude_paths` は `include_paths` より先に評価されます。

## Markdown indexing

デフォルトでは次を index します。

- `README.md`
- `README*.md`
- `docs/**/*.md`
- `adr/**/*.md`
- `adrs/**/*.md`

デフォルトでは次を除外します。

- `node_modules/**`
- `dist/**`
- `vendor/**`
- `coverage/**`
- `build/**`
- `__pycache__/**`
- lock files

chunk は Markdown heading ごとに作られます。
stable ID は次の値から SHA-256 で作ります。

```text
repo:path:heading
```

## MCP integration

FastMCP server は次の tools を提供します。

- `search_memory`
- `remember`
- `related_repo_context`
- `recent_project_memories`

read/write は分離します。

```yaml
read_tenants:
  - vault
  - work
write_tenant: work
```

`remember` は configured write tenant にだけ書き込みます。
検索 tools は configured readable tenants の範囲だけを読みます。

## Cloudflare setup

外部 agent や GitHub Actions は Cloudflare Tunnel と Cloudflare Access
Service Token 経由でアクセスします。

compose stack には `cloudflared` service が含まれます。
外部公開は direct port ではなく Tunnel 経由を前提にします。

Tunnel routing 例:

```text
mem0-api.example.com -> http://mem0:8000
mem0-mcp.example.com -> http://mcp:8010
```

GitHub Actions の `MEM0_API_URL` には Cloudflare-protected hostname を
設定します。compose 内部の `http://mem0:8000` は外部から使いません。

GitHub Actions は Cloudflare Access Service Token で認証します。
caller workflow には `CLOUDFLARE_ACCESS_CLIENT_ID` と
`CLOUDFLARE_ACCESS_CLIENT_SECRET` を渡します。
`CLOUDFLARE_TUNNEL_TOKEN` は platform runtime の `cloudflared` service
だけが使います。

## backend の責務

FalkorDB は graph memory と関係性を扱います。

Qdrant は semantic vector retrieval を扱います。

このリポジトリの `mem0` API service は mem0 OSS library を呼び出し、
FalkorDB と Qdrant に接続します。

## local run

toolchain は mise で管理します。

```bash
mise trust .
mise install
mise run setup
```

`.env` を作成します。

```bash
cp .env.example .env
```

runtime を起動します。

```bash
mise run up
```

dry-run ingestion:

```bash
mise run ingest-dry-run
```

local validation:

```bash
mise run check
```

## backup

backend state は `data/` に bind mount します。
Docker named volume は使いません。

```text
data/falkordb/
data/qdrant/
data/mem0/
```

通常の filesystem backup tool で `data/` を backup できます。

詳細は [backup docs](docs/operations/backup.md) を見てください。

## security model

- tenant は isolation boundary です。
- repo 名は authorization boundary ではなく metadata です。
- Git / Markdown / ADR / Obsidian notes が正本です。
- mem0 は source から rebuild 可能な retrieval infrastructure です。
- MCP tools は tenant filters を自動注入します。
- write は configured write tenant に限定します。
- Service Token は Cloudflare Access で agent/tool 認証に使います。
- secrets や個人情報を log に出してはいけません。
