# mem0-local-platform

このリポジトリは、Codex、Claude、ローカルエージェントが
開発作業中に必要な文脈を検索するための、ローカル運用前提の mem0 実行基盤です。
mem0、FalkorDB、Qdrant、Ollama を自分の Docker 環境で動かすため、
ローカルモデル構成では登録した知識を外部 AI SaaS に送らずに運用できます。

できること:

- GitHub に push された README、docs、ADR を自動で取り込む
- 手元の Markdown、Obsidian ノート、Raycast のメモを Python CLI 経由で登録する
- 登録した文脈を FalkorDB のグラフと Qdrant のベクトル検索インデックスに保存する
- Codex、Claude、ローカルエージェントから MCP 経由で検索する
- MCP 設定で、AI エージェントが参照してよい知識の範囲を指定する

嬉しいこと:

- AI エージェントが、過去の判断、設計メモ、調査結果を毎回聞き返さなくなる
- リポジトリをまたぐ知識を、作業中の文脈として引ける
- 関係性は FalkorDB、意味検索は Qdrant に分けて扱える
- 顧客や契約で隔離が必要な知識を、通常の mimr-tech 知識と混ぜずに扱える
- ローカルモデル構成なら、社内メモや判断パターンを外部 AI SaaS に預けずに済む
- mem0 側のデータを失っても、Git や Markdown から作り直せる

これはチャットボットや試作用 RAG ではありません。
複数リポジトリや Obsidian に散らばる開発知識を、AI エージェントが安全に再利用するための
AI エージェント向け知識基盤です。

Git リポジトリ、Markdown、ADR、Obsidian ノートを知識の保存場所として扱い、
mem0 はそこから作る検索インデックスとして扱います。
外部 LLM や外部 embedding provider を選ぶ場合は、その provider に送信される内容を
別途レビューしてください。

## 使用例

設計メモをリポジトリに残す:

1. `docs/e2e.md` や `adr/001-retry-policy.md` を更新します。
2. GitHub に push します。
3. 共通ワークフローが変更された Markdown だけを mem0 に反映します。
4. Codex や Claude が MCP 経由で、過去の設計判断を検索できます。

作業中の短いメモをすぐ登録する:

```bash
uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source obsidian \
  --type note \
  --tag debugging \
  --file "$HOME/Obsidian/Vault/ai-workflows/e2e-debugging.md"
```

AI エージェントから検索する:

```text
search_memory("E2E 失敗時に trace.zip をどう扱うか")
```

顧客案件の知識を分ける:

```yaml
read:
  - mimr-tech
  - client-acme
```

この設定では、AI エージェントは `mimr-tech` と `client-acme` を参照できます。
顧客案件の内容を新しく記録する場合は、GitHub Actions の `tenant` input または
Python CLI の `--tenant client-acme` で登録先を指定します。

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

- `mimr-tech`
- `client-*`

メタデータ例:

```json
{
  "tenant": "mimr-tech",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

リポジトリごとにテナントを作ると、テナントが増えすぎて運用と監査が難しくなります。
`mimr-tech` は mimr-tech が管理する知識全体の境界です。
国内ポートフォリオ用リポジトリ、公開可能な skill、非公開の判断パターン、
DevEx テンプレート、調査ツール、Upwork 関連メモもここに入れます。
公開可否、用途、リポジトリ種別はテナントではなくメタデータで扱います。
顧客や契約上の隔離が必要な場合だけ `client-*` を使います。
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
      tenant: mimr-tech
    secrets:
      MEM0_API_URL: ${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: ${{ secrets.MEM0_API_KEY }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_ID: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_ID }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET: ${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET }}
```

通常の push では `changed` を使います。
初回投入、除外ルール変更後、mem0 の状態を再構築した後は `full` を使います。

手動で全内容を取り込む場合は、対象リポジトリの GitHub 画面で
`Actions` から `Sync Repository Memory` を選び、`Run workflow` で
`sync_mode` に `full` を指定します。

詳細は [別リポジトリへの導入手順](docs/conventions/adopting-repository.jp.md)
を見てください。

薄い呼び出し側ワークフローとパス設定ファイルは、`install.sh` で生成できます。

```bash
./install.sh \
  --target github-actions \
  --target-dir /path/to/repository \
  --tenant mimr-tech
```

対象リポジトリの GitHub secret は GitHub CLI でも設定できます。

```bash
gh secret set MEM0_API_URL --repo tom-miy/target-repository --body "https://mem0-api.example.com"
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID --repo tom-miy/target-repository --body "..."
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET --repo tom-miy/target-repository --body "..."
```

Organization 配下で共有する場合は、アクセス可能なリポジトリを指定して
Organization secret として設定できます。

```bash
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID \
  --org tom-miy \
  --visibility selected \
  --repos target-repository,another-repository \
  --body "..."
```

Obsidian、Raycast、手元の Markdown から短いメモを入れる場合は
[ローカルツールからの取り込み](docs/conventions/local-tool-ingestion.jp.md)
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
- `sync_config_file`: パスルールを書いた設定ファイル

通常は各リポジトリに次のファイルを置きます。

```text
.mem0-sync.yml
```

共通ワークフローは、このファイルがあれば読み込みます。
なければ mem0-local-platform 側の `.mem0-sync.default.yml` を使います。
共通ワークフロー本体には include/exclude の実体を置きません。
YAML のキーは `include` と `exclude` です。
ローカル確認では `mise run sync-path-rules` で同じ変換を確認できます。

`exclude` は `include` より先に評価されます。

同期モードの使い分け:

- `changed`: push された差分ファイルだけを取り込みます。
- `full`: Git 管理下の全ファイルから対象 Markdown を取り込みます。

`full` は自動 push ではなく、初回投入や復旧時に手動実行するためのモードです。

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
- `related_repo_context`
- `recent_project_memories`

MCP はデフォルトで読み取り専用です。
登録は GitHub Actions、Python CLI、Obsidian や Raycast からの Python CLI 呼び出しに限定します。

読み取り可能テナントは `mem0.policy.yml` に置きます。

```yaml
read:
  - mimr-tech
```

検索ツールは、設定された読み取り可能テナントの範囲だけを読みます。

クライアントへの設定方法は
[MCP の設定](docs/conventions/mcp-setup.jp.md) を見てください。
設定例を表示するには次を実行します。

```bash
./install.sh --target generic --transport stdio
```

Codex 用の設定例:

```bash
cp mem0.env.example mem0.env
cp mem0.policy.example.yml mem0.policy.yml
./install.sh --target codex
```

`mem0.env` は Codex、Claude、Raycast などローカルクライアント用の設定です。
Cloudflare Access の秘密値は MCP クライアント設定へ直接書かず、
`mem0.env` に置きます。
読み取り可能テナントは `mem0.policy.yml` に置きます。

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
呼び出し側ワークフローには GitHub secret 名として
`MEM0_CLOUDFLARE_ACCESS_CLIENT_ID` と
`MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET` を渡します。
`MEM0_API_KEY` は任意で、mem0 API または独自 gateway が Bearer token を
要求する場合だけ使います。
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
cp mem0.policy.example.yml mem0.policy.yml
```

Docker Compose でローカル環境を起動します。

```bash
mise run up
```

compose の `ollama` サービスへデフォルトモデルを取得します。

```bash
mise run ollama-pull
```

取り込みのドライラン:

```bash
mise run ingest-dry-run
```

Ollama、Ollama Cloud、OpenRouter、OpenAI 互換ルーターの設定例は
[モデルプロバイダ設定](docs/architecture/model-provider-settings.jp.md) を見てください。

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
data/ollama/
```

通常のファイルシステム用バックアップツールで `data/` をバックアップできます。

詳細は [バックアップ手順](docs/operations/backup.md) を見てください。

## セキュリティモデル

このリポジトリでは、メモリを次のルールで扱います。

- テナントは「読ませてよい範囲」を分ける単位です。
- リポジトリ名だけでアクセス制御をしません。
- リポジトリ名は検索用の情報として保存します。
- 長く残す知識は Git、Markdown、ADR、Obsidian ノートに置きます。
- mem0 は AI エージェントが検索しやすくするための索引として扱います。
- mem0 の内容は、必要になれば Git や Markdown から作り直します。
- MCP の検索ツールは、許可されたテナントだけを検索します。
- MCP は読み取り専用です。登録は GitHub Actions または Python CLI から行います。
- 外部からのアクセスは Cloudflare Access のサービストークンで認証します。
- 秘密情報や個人情報をログに出してはいけません。

ローカルの Claude Code、Cursor、Copilot、Codex から使う場合は、
`agent-privacy-guard` と組み合わせると、mem0 から取り出した文脈を
AI に渡す前に匿名化や trust routing をかけられます。
`agent-privacy-guard` は AI Agent Governance Gateway として、prompt 匿名化、
MCP trust routing、hook ベースの安全制御を提供します。
mem0-local-platform は記憶の保存と検索を担当し、`agent-privacy-guard` は
検索結果を含む prompt やツール呼び出しが AI クライアントや外部モデルへ渡る前段を
制御します。

ただし、GitHub Actions 上の同期ジョブには通常この制御は効きません。
GitHub Actions は GitHub runner 上で共通ワークフローを直接実行するためです。
Actions 側の保護は Cloudflare Access のサービストークン、GitHub secrets、
取り込み対象パスの include/exclude、テナント指定で行います。
GitHub Actions からも `agent-privacy-guard` を効かせたい場合は、ワークフロー自体を
gateway 経由にする追加設計が必要です。

つまり、mem0 に入っている情報だけを唯一の保存先にしません。
長く残す内容は Git や Obsidian に戻し、mem0 では
「誰がどのテナントを読めるか」と「どのテナントへ書けるか」を明確にします。

例:

```json
{
  "tenant": "mimr-tech",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

この場合、`mimr-tech` が読み取り境界です。
`backend-testing-patterns` は検索で絞り込むための情報であり、境界ではありません。

mimr-tech 管理下の作業例:

```yaml
read:
  - mimr-tech
```

この設定では、エージェントは `mimr-tech` だけを検索できます。
新しく記録する内容は GitHub Actions または Python CLI から `mimr-tech` に入れます。

顧客作業の例:

```yaml
read:
  - client-18384728-acme
```

この設定では、エージェントはその顧客用テナントだけを読みます。
別の顧客や `mimr-tech` には触れません。

GitHub Actions から同期する例:

```yaml
with:
  tenant: client-18384728-acme
  repo: backend-testing-patterns
```

このワークフローは、`backend-testing-patterns` の Markdown を
`client-18384728-acme` テナントへ記録します。
repo 名はメタデータとして残るため、後から repo 単位で検索できます。
