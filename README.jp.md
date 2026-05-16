# mem0-local-platform

開発者向けのローカル AI メモリ基盤です。

このリポジトリは、自前で動かす mem0 環境、FalkorDB、Qdrant、
Cloudflare Tunnel、MCP、GitHub Actions による自動同期をまとめます。
試作用の RAG デモではなく、実際の AI 支援開発で使う知識基盤を目指します。

mem0 は正本ではありません。

正本は次です。

- Git リポジトリ
- Markdown ドキュメント
- ADR
- Obsidian ノート

mem0 は、意味検索用キャッシュ、AI メモリ索引、実行時コンテキスト層として扱います。

## アーキテクチャ

```text
Git repository
  -> GitHub push
  -> 再利用可能な mem0 同期ワークフロー
  -> mem0 取り込みコマンド
  -> Cloudflare Tunnel
  -> mem0
     -> FalkorDB グラフメモリ
     -> Qdrant 意味ベクトル検索
  -> MCP
  -> Codex / Claude / ローカルエージェント
```

## メモリ同期の流れ

1. Git リポジトリで Markdown や ADR を更新します。
2. GitHub push が薄い呼び出し側ワークフローを起動します。
3. 呼び出し側ワークフローは共通ワークフローを呼び出します。
4. 共通ワークフローが `changed` または `full` の対象ファイル一覧を作ります。
5. `scripts/ingest_repo.py` が Markdown を見出しごとに分割します。
6. 分割した内容は安定 ID で mem0 に更新または追加されます。
7. エージェントは MCP 経由でテナント絞り込み付きの検索を行います。

## テナント戦略

テナントはセキュリティ境界です。

リポジトリごとにテナントを作ってはいけません。リポジトリ名はメタデータとして
保存します。

推奨テナント:

- `vault`
- `work`
- `client-*`
- `agency-*`

メタデータ例:

```json
{
  "tenant": "work",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

リポジトリごとにテナントを作ると、テナントが増えすぎて運用と監査が難しくなります。
詳細は [テナント運用ルール](docs/security/tenant-operations.jp.md) を見てください。

## 別リポジトリへの追加

別リポジトリ側には、薄い呼び出し側ワークフローだけを追加します。

取り込みコマンド、差分判定、除外ルールを各リポジトリへコピーしません。

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
初回投入、除外ルール変更後、mem0 の状態を再構築した後は `full` を使います。

詳細は [別リポジトリへの導入手順](docs/conventions/adopting-repository.jp.md)
を見てください。

Raycast などローカルツールから短いメモを入れる場合は
[Raycast などローカルツールからの取り込み](docs/conventions/local-tool-ingestion.jp.md)
を見てください。

## 共通ワークフロー

共通ワークフローはここにあります。

```text
.github/workflows/reusable-sync.yml
```

これは `workflow_call` 専用です。

各リポジトリにワークフローの処理をコピーせず、`uses:` でこのワークフローを
呼び出します。

主な入力:

- `sync_mode`: `changed` または `full`
- `tenant`: 書き込み先テナント
- `repo`: メタデータとして保存するリポジトリ名
- `include_paths`: 索引対象パス
- `exclude_paths`: 除外パス

`exclude_paths` は `include_paths` より先に評価されます。

## Markdown の索引作成

デフォルトでは次を索引します。

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
- ロックファイル

取り込み内容は Markdown の見出しごとに分割されます。
安定 ID は次の値から SHA-256 で作ります。

```text
repo:path:heading
```

## MCP 連携

FastMCP サーバーは次のツールを提供します。

- `search_memory`
- `remember`
- `related_repo_context`
- `recent_project_memories`

読み取りと書き込みは分離します。

```yaml
read_tenants:
  - vault
  - work
write_tenant: work
```

`remember` は設定された書き込み先テナントにだけ書き込みます。
検索ツールは、設定された読み取り可能テナントの範囲だけを読みます。

## Cloudflare 設定

外部エージェントや GitHub Actions は、Cloudflare Tunnel と Cloudflare Access
のサービストークン経由でアクセスします。

Compose スタックには `cloudflared` サービスが含まれます。
外部公開は直接ポートではなく、Tunnel 経由を前提にします。

Tunnel ルーティング例:

```text
mem0-api.example.com -> http://mem0:8000
mem0-mcp.example.com -> http://mcp:8010
```

GitHub Actions の `MEM0_API_URL` には、Cloudflare Access で保護された
ホスト名を設定します。Compose 内部の `http://mem0:8000` は外部から使いません。

GitHub Actions は Cloudflare Access のサービストークンで認証します。
呼び出し側ワークフローには `CLOUDFLARE_ACCESS_CLIENT_ID` と
`CLOUDFLARE_ACCESS_CLIENT_SECRET` を渡します。
`CLOUDFLARE_TUNNEL_TOKEN` は、プラットフォーム側の `cloudflared` サービスだけが使います。

## バックエンドの責務

FalkorDB はグラフメモリと関係性を扱います。

Qdrant は意味ベクトル検索を扱います。

このリポジトリの `mem0` API サービスは mem0 OSS ライブラリを呼び出し、
FalkorDB と Qdrant に接続します。

## ローカル実行

ツールチェーンは mise で管理します。

```bash
mise trust .
mise install
mise run setup
```

`.env` を作成します。

```bash
cp .env.example .env
```

Docker Compose でローカル環境を起動します。

```bash
mise run up
```

取り込みのドライラン:

```bash
mise run ingest-dry-run
```

ローカル検証:

```bash
mise run check
```

検証で作られたキャッシュを消す場合:

```bash
mise run clean
```

Docker Compose や結合テストで作られた `data/` も消す場合:

```bash
mise run clean-data
```

Python 仮想環境も作り直したい場合:

```bash
mise run distclean
```

全部まとめて消す場合:

```bash
mise run clean-all
```

`clean` と `distclean` は `data/` を削除しません。
FalkorDB、Qdrant、mem0 の状態を消す場合は `clean-data` を明示して実行します。

## バックアップ

バックエンド状態は `data/` にバインドマウントします。
Docker 名前付きボリュームは使いません。

```text
data/falkordb/
data/qdrant/
data/mem0/
```

通常のファイルシステム用バックアップツールで `data/` をバックアップできます。

詳細は [バックアップ手順](docs/operations/backup.md) を見てください。

## セキュリティモデル

このリポジトリでは、メモリを次のルールで扱います。

- テナントは「読ませてよい範囲」を分ける単位です。
- リポジトリ名だけでアクセス制御をしません。
- リポジトリ名は検索用の情報として保存します。
- Git、Markdown、ADR、Obsidian ノートを正本にします。
- mem0 は検索を速くするための索引として扱います。
- mem0 の内容は、必要になれば正本から作り直します。
- MCP の検索ツールは、許可されたテナントだけを検索します。
- MCP の書き込みツールは、設定された 1 つのテナントにだけ書き込みます。
- 外部からのアクセスは Cloudflare Access のサービストークンで認証します。
- 秘密情報や個人情報をログに出してはいけません。

つまり、mem0 に入っている情報そのものを正本として守るのではなく、
「誰がどのテナントを読めるか」と「どのテナントへ書けるか」を明確にします。

例:

```json
{
  "tenant": "work",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

この場合、`work` が読み取りや書き込みの境界です。
`backend-testing-patterns` は検索で絞り込むための情報であり、境界ではありません。

個人作業の例:

```text
MEM0_READ_TENANTS=vault,work
MEM0_WRITE_TENANT=work
```

この設定では、エージェントは `vault` と `work` を検索できます。
新しく記録する内容は `work` にだけ入ります。

顧客作業の例:

```text
MEM0_READ_TENANTS=client-18384728-acme
MEM0_WRITE_TENANT=client-18384728-acme
```

この設定では、エージェントはその顧客用テナントだけを読み書きします。
別の顧客や通常作業用の `work` には触れません。

GitHub Actions から同期する例:

```yaml
with:
  tenant: client-18384728-acme
  repo: backend-testing-patterns
```

このワークフローは、`backend-testing-patterns` の Markdown を
`client-18384728-acme` テナントへ記録します。
repo 名はメタデータとして残るため、後から repo 単位で検索できます。
