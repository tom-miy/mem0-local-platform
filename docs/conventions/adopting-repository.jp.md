# 別リポジトリへの mem0 同期導入

この手順は、既存リポジトリに mem0 同期を追加するためのものです。

リポジトリ側に取り込み処理をコピーしません。
各リポジトリには薄い呼び出し側ワークフローだけを置きます。

## 前提

mem0-local-platform が起動しており、GitHub Actions から Cloudflare 経由で
mem0 API に到達できる状態にします。

注意: GitHub Actions に Cloudflare Access のサービストークンを置くと、
そのシークレットを読めるワークフローは mem0 API へ到達できます。
現在の API では書き込み用と検索用のエンドポイントが同じ API ホストにあるため、
機密性の高いテナントや顧客リポジトリでは Actions 直結を標準にしないでください。
その場合は、ローカルクローンからの同期、Tailscale 経由の同期、プライベートネットワーク内の
self-hosted runner、または書き込み専用取り込みゲートウェイを使います。
詳細は [Cloudflare Access](../security/cloudflare-access.jp.md) を見てください。

GitHub リポジトリのシークレット:

- `MEM0_API_URL`
- `MEM0_CLOUDFLARE_ACCESS_CLIENT_ID`
- `MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET`

`MEM0_API_URL` は Cloudflare Access で保護されたホスト名を使います。
GitHub Actions からのリポジトリ同期では `https://` で始まる URL を必須にします。
Tailscale 経由で接続する場合も、HTTPS 終端されたホスト名を使います。
Compose 内部の `http://mem0:8000` は使いません。
平文の `http://` は、信頼境界の外へ出ないローカル実行や Docker Compose 内部通信だけに
限定してください。

`MEM0_API_URL`、`MEM0_CLOUDFLARE_ACCESS_CLIENT_ID`、または
`MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET` が未設定の場合、共通ワークフローは warning を出して
リポジトリ同期をスキップします。
公開リポジトリや導入直後の呼び出し側リポジトリで、接続シークレットを意図的に設定する前に
ワークフロー全体が失敗しないようにするためです。

`MEM0_API_KEY` は、mem0 API ランタイム側にも同じ値を設定した場合に
Bearer トークンとして検証されます。
ローカルだけの実験では未設定でも動きますが、Cloudflare Access 経由で外部公開する
実務運用では設定してください。
GitHub Actions には同じ値を `MEM0_API_KEY` シークレットとして渡します。

GitHub CLI で設定する例:

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

dotenv 形式のファイルからまとめて設定することもできます。

```bash
gh secret set --repo tom-miy/target-repository -f mem0.github-secrets.env
```

`mem0.github-secrets.env` の例:

```env
MEM0_API_URL=https://mem0-api.example.com
MEM0_API_KEY=...
MEM0_CLOUDFLARE_ACCESS_CLIENT_ID=...
MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

同じ mem0 接続先を Organization 配下の複数リポジトリで使う場合は、
Organization シークレットとして設定できます。
ただし、mem0 へ到達できるシークレットを広く配るほど漏えい時の影響が大きくなります。
実務ではまず `--visibility selected` で対象リポジトリを限定してください。

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

Organization 内の private リポジトリ全体に使わせる場合は `--visibility private`、
公開リポジトリにも使わせる場合だけ `--visibility all` を使います。
機密テナントへ接続できるサービストークンに `--visibility all` は使わないでください。
個人アカウントでは GitHub Actions のシークレットはリポジトリ単位です。
`gh secret set --user` は Codespaces 用であり、Actions 用ではありません。

GitHub Actions は Cloudflare Access のサービストークンを HTTP ヘッダーとして送り、
Tunnel の先へ接続します。`CLOUDFLARE_TUNNEL_TOKEN` は Actions には渡しません。
これはプラットフォーム側の `cloudflared` サービスが使うトークンです。

クライアント案件などで GitHub Actions から mem0 API へ接続できない場合は、
このワークフローを使わず、ローカルクローンから同期します。
手順は [ローカルツールからの取り込み](local-tool-ingestion.jp.md) の
「ローカルリポジトリ差分を同期する」を見てください。

接続できる場合でも、GitHub Actions に mem0 のサービストークンを置きたくない
機密リポジトリでは同じくローカル同期を使います。

## 追加するワークフロー

対象リポジトリに `.github/workflows/sync-memory.yml` を追加します。

`install.sh` で生成できます。

```bash
/path/to/mem0-local-platform/install.sh \
  --target github-actions \
  --target-dir /path/to/repository \
  --tenant secret-knowledge
```

このコマンドは次を作成します。

- `.github/workflows/sync-memory.yml`
- `.mem0-sync.yml`

既存ファイルがある場合は上書きしません。
内容を確認したうえで上書きしたい場合だけ `--force` を付けます。

手動で追加する場合の workflow は次です。

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
      tenant: secret-knowledge
    secrets:
      MEM0_API_URL: ${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: ${{ secrets.MEM0_API_KEY }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_ID }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

パス設定を手動で追加する場合は、`.mem0-sync.yml` も追加します。

このファイルがある場合、共通ワークフローはその内容を使います。
ファイルがない場合は、mem0-local-platform 側の `.mem0-sync.default.yml` を使います。

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
ルールに合うコード、API 定義、設定、Markdown を mem0 に送ります。
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

## パスルール

通常は、パスルールを `.mem0-sync.yml` としてリポジトリに置きます。

例:

```yaml
include:
  - README.md
  - README*.md
  - handbook/*.md
  - handbook/**/*.md
  - docs/*.md
  - docs/**/*.md
  - "**/*.go"
  - "**/*.py"
  - "**/*.ts"
  - "**/*.yaml"
  - "**/*.yml"
  - "**/*.json"
  - api.yaml
  - openapi.yaml

exclude:
  - .env
  - "**/.env"
  - secrets/**
  - "**/secrets/**"
  - data/**
  - generated/**
  - "**/generated/**"
  - node_modules/**
  - "**/node_modules/**"
```

YAML のキーは `include` と `exclude` です。
ファイルがない場合は、mem0-local-platform 側の `.mem0-sync.default.yml` を使います。

リポジトリ固有のコード、API 定義、設定、ドキュメントのパスがある場合は、
`.mem0-sync.yml` で上書きします。
PDF、Office 文書、画像、アーカイブ、音声や動画はデフォルトで除外します。
今の取り込みは UTF-8 テキストが前提だからです。

`exclude` は `include` より先に評価されます。

## リポジトリとテナント

リポジトリ名はメタデータです。
テナントではありません。

必要なら `repo` 入力を明示できます。

```yaml
with:
  tenant: secret-knowledge
  repo: backend-testing-patterns
```

同じテナントの中で `repo` メタデータを使って検索範囲を絞ります。

## 導入後の確認

1. `workflow_dispatch` で `full` を 1 回実行します。
2. 以降の push で `changed` が動くことを確認します。
3. MCP の `related_repo_context` で `repo` メタデータ検索を確認します。
