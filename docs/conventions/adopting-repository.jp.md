# 別リポジトリへの mem0 同期導入

この手順は、既存リポジトリに mem0 同期を追加するためのものです。

リポジトリ側に取り込み処理をコピーしません。
各リポジトリには薄い呼び出し側ワークフローだけを置きます。

## 前提

mem0-local-platform が起動しており、GitHub Actions から Cloudflare 経由で
mem0 API に到達できる状態にします。

GitHub リポジトリのシークレット:

- `MEM0_API_URL`
- `MEM0_API_KEY`
- `CLOUDFLARE_ACCESS_CLIENT_ID`
- `CLOUDFLARE_ACCESS_CLIENT_SECRET`

`MEM0_API_URL` は Cloudflare Access で保護されたホスト名を使います。
Compose 内部の `http://mem0:8000` は使いません。

GitHub Actions は Cloudflare Access のサービストークンを HTTP ヘッダーとして送り、
Tunnel の先へ接続します。`CLOUDFLARE_TUNNEL_TOKEN` は Actions には渡しません。
これはプラットフォーム側の `cloudflared` サービスが使うトークンです。

## 追加するワークフロー

対象リポジトリに次を追加します。

```text
.github/workflows/sync-memory.yml
```

```yaml
name: Sync Repository Memory

on:
  push:
    branches:
      - main
  workflow_dispatch:
    inputs:
      sync_mode:
        description: changed は差分同期、full は全体同期
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
      tenant: work
    secrets:
      MEM0_API_URL: ${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: ${{ secrets.MEM0_API_KEY }}
      CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.CLOUDFLARE_ACCESS_CLIENT_ID }}
      CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

## 同期モード

`changed` は push 差分の対象ファイルだけを取り込みます。
通常運用ではこれを使います。

`full` は Git 管理下のファイル全体から include/exclude ルールに合うものを取り込みます。

`full` を使う場面:

- 初回の索引作成
- include/exclude ルールを変えた後
- mem0、Qdrant、FalkorDB の状態を再構築した後
- 取り込み漏れを修復したいとき

## 手動で全内容を取り込む

できます。

対象リポジトリ側に上の `workflow_dispatch` が入っていれば、GitHub 画面から
全内容取り込みを実行できます。

手順:

1. 対象リポジトリの GitHub 画面を開きます。
2. `Actions` を開きます。
3. `Sync Repository Memory` を選びます。
4. `Run workflow` を押します。
5. `sync_mode` で `full` を選びます。
6. 対象ブランチを確認して実行します。

この実行では、Git 管理下のファイル一覧を作り、その中から include/exclude
ルールに合う Markdown だけを mem0 に送ります。
`node_modules`、`dist`、`coverage` などの除外パスは取り込みません。

GitHub CLI を使う場合:

```bash
gh workflow run "Sync Repository Memory" \
  --ref main \
  -f sync_mode=full
```

通常の push では `sync_mode` が指定されないため、呼び出し側ワークフローの
式で `changed` になります。つまり、push は差分同期、手動実行は選択した
`sync_mode` で同期します。

## include/exclude ルール

デフォルトの include:

```text
README.md
README*.md
docs/*.md
docs/**/*.md
adr/*.md
adr/**/*.md
adrs/*.md
adrs/**/*.md
```

デフォルトの exclude:

```text
.git/**
.venv/**
node_modules/**
**/node_modules/**
dist/**
**/dist/**
vendor/**
**/vendor/**
coverage/**
**/coverage/**
build/**
**/build/**
__pycache__/**
**/__pycache__/**
*.pyc
**/*.pyc
*.lock
**/*.lock
package-lock.json
**/package-lock.json
pnpm-lock.yaml
**/pnpm-lock.yaml
yarn.lock
**/yarn.lock
```

リポジトリ固有の docs パスがある場合は、呼び出し側ワークフローで上書きします。

```yaml
jobs:
  sync:
    uses: tom-miy/mem0-local-platform/.github/workflows/reusable-sync.yml@main
    with:
      sync_mode: ${{ github.event.inputs.sync_mode || 'changed' }}
      tenant: work
      include_paths: |
        README.md
        handbook/*.md
        handbook/**/*.md
        docs/**/*.md
      exclude_paths: |
        generated/**
        **/generated/**
        node_modules/**
        **/node_modules/**
```

exclude は include より先に評価されます。

## リポジトリとテナント

リポジトリ名はメタデータです。
テナントではありません。

必要なら `repo` input を明示できます。

```yaml
with:
  tenant: work
  repo: backend-testing-patterns
```

同じテナントの中で repo メタデータを使って検索範囲を絞ります。

## 導入後の確認

1. `workflow_dispatch` で `full` を 1 回実行します。
2. 以降の push で `changed` が動くことを確認します。
3. MCP の `related_repo_context` で repo メタデータ検索を確認します。
