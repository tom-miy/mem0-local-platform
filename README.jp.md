# mem0-local-platform

このリポジトリは、Codex、Claude、ローカルエージェントが
開発作業中に必要な文脈を検索するための、ローカル運用前提の mem0 実行基盤です。
mem0、FalkorDB、Qdrant、Ollama を自分の Docker 環境で動かすため、
ローカルモデル構成では、取り込みと検索処理(LLM と埋め込み)を
外部 AI SaaS に送らずに運用できます。
ただし、Codex や Claude のようなクラウド上のエージェントが MCP 経由で検索した場合、
ヒットした本文はそのエージェントのサービスへ渡ります。
外部エージェントに読ませてよい範囲は `mem0.policy.yml` の読み取りテナントで制御します。

できること:

- GitHub にプッシュされた README、docs、ADR、コード、API 定義、設定ファイルを自動で取り込む
- GitHub Actions を使えないリポジトリをローカルクローンから差分同期する
- 手元の Markdown、Obsidian ノート、Raycast のメモを Python CLI 経由で登録する
- 登録した文脈を FalkorDB のグラフと Qdrant のベクトル検索インデックスに保存する
- Codex、Claude、ローカルエージェントから MCP 経由で検索する
- MCP 設定で、AI エージェントが参照してよい知識の範囲を指定する

嬉しいこと:

- AI エージェントが、過去の判断、設計メモ、調査結果を毎回聞き返さなくなる
- リポジトリをまたぐ知識を、作業中の文脈として引ける
- 関係性は FalkorDB、意味検索は Qdrant に分けて扱える
- 顧客案件、NDA、社外共有禁止、開発者ごとの閲覧権限差がある知識を分けて扱える
- ローカルモデル構成なら、社内メモや判断パターンを外部 AI SaaS に預けずに済む
- mem0 側のデータを失っても、Git や Markdown から作り直せる

このリポジトリが管理するのは、ドキュメントそのものだけではありません。
Docker Compose で mem0、FalkorDB、Qdrant、Ollama、Cloudflare Tunnel を起動し、
GitHub Actions や Python CLI から知識を取り込み、MCP 経由で AI エージェントへ
検索可能な文脈として返すところまでを扱います。

Git や Obsidian は知識を書く場所です。
このリポジトリは、その知識を自宅サーバやローカル環境で動く検索基盤へ同期し、
Codex、Claude、ローカルエージェントが作業中に使える状態にします。

Git リポジトリ、ソースコード、API 定義、設定ファイル、Markdown、ADR、Obsidian ノートを
知識の保存場所として扱い、
mem0 はそこから作る検索インデックスとして扱います。
外部 LLM や外部埋め込みプロバイダを選ぶ場合は、そのプロバイダに送信される内容を
別途レビューしてください。

## 使用例

設計と実装の文脈をリポジトリに残す:

1. `docs/e2e.md`、`adr/001-retry-policy.md`、`api/openapi.yaml`、`cmd/server/main.go` などを更新します。
2. GitHub にプッシュします。
3. 共通ワークフローが変更された対象ファイルを mem0 に反映します。
4. Codex や Claude が MCP 経由で、過去の設計判断、API 契約、実装内容を検索できます。

作業中の短いメモをすぐ登録する:

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source obsidian \
  --type note \
  --tag debugging \
  --file "$HOME/Obsidian/Vault/ai-workflows/e2e-debugging.md"
```

AI エージェントから検索する:

```python
search_memory("E2E 失敗時に trace.zip をどう扱うか")
```

顧客案件の知識を分ける:

```yaml
read:
  - secret-knowledge
  - client-acme
```

この設定では、AI エージェントは `secret-knowledge` と `client-acme` を参照できます。
顧客案件の内容を新しく記録する場合は、GitHub Actions の `tenant` 入力または
Python CLI の `--tenant client-acme` で登録先を指定します。

## アーキテクチャ

```text
書き込み(取り込み):
Git リポジトリ -> GitHub へのプッシュ -> 再利用可能な mem0 同期ワークフロー
  -> mem0 取り込みコマンド
ローカルクローン / Markdown / Obsidian / Raycast -> Python 取り込み CLI
  -> Cloudflare Tunnel(GitHub Actions などの外部経路のみ)
  -> mem0 API
     -> FalkorDB グラフメモリ
     -> Qdrant 意味ベクトル検索

読み取り(検索):
Codex / Claude / ローカルエージェント
  -> MCP サーバー(外部エージェントは Cloudflare Tunnel 経由)
  -> mem0 API
```

## メモリ同期の流れ

1. Git リポジトリでコード、API 定義、設定、Markdown、ADR を更新します。
2. GitHub へのプッシュが薄い呼び出し側ワークフローを起動します。
3. 呼び出し側ワークフローは共通ワークフローを呼び出します。
4. 共通ワークフローが `changed` または `full` の対象ファイル一覧を作ります。
5. `scripts/ingest_repo.py` が対象ファイルを検索用チャンクに分割します。
6. 同じ `tenant + repo + path` の既存チャンクを消してから再登録します。
7. 削除されたファイルやリネーム元のパスは、mem0 側の古いチャンクも消します。
8. エージェントは MCP 経由でテナント絞り込み付きの検索を行います。

## テナント戦略

テナントは、読み取りを許可する AI エージェントや開発者ごとに、
見せてよい知識の範囲を分ける境界です。
顧客案件、NDA、社外共有禁止、チームや開発者ごとの閲覧権限差のように、
混ぜてはいけない知識を分けるときに使います。

プロジェクトや作業領域ごとの検索範囲は、テナントではなく `repo`、`path`、`type`、`tags`
のメタデータで絞ります。
同じ開発者や AI エージェントが読んでよいプロジェクト群なら、プロジェクトごとにテナントを
分ける必要はありません。

推奨テナント:

- `secret-knowledge`
- `client-*`

メタデータ例:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

プロジェクトごとのテナントを標準にしない理由は、全体知識と個別プロジェクト知識を
横断して検索しにくくなり、プロジェクト名やリポジトリ名の変更、分割統合がアクセス制御の変更に
なってしまうためです。
モノレポでも、`apps/api`、`tools/review`、`docs/adr` のような領域は
`path`、`type`、`tags` で絞ります。
例外として、プロジェクトやリポジトリそのものが顧客案件、NDA、社外共有禁止、開発者ごとの
閲覧権限差の境界である場合は、
専用テナントに登録して構いません。

検索例:

```python
search_memory(
  query="E2E 失敗時に trace.zip を保存する条件",
  tenants=["secret-knowledge"],
  repo="backend-testing-patterns",
  type="doc",
  tags=["testing"]
)
```

全体知識を横断したい場合は `repo` を外します。
特定ファイルだけを見たい場合は `path` を指定します。

`secret-knowledge` は、顧客テナントへ分けない自分側の判断パターンや
社内ナレッジをまとめる境界名の例です。
秘密情報そのものを無条件に入れる場所という意味ではありません。
実運用では、会社、屋号、チーム、個人事業など、自分の管理境界を表す
テナント名に置き換えても構いません。
公開用リポジトリ、公開可能な skill、非公開の判断パターン、
DevEx テンプレート、調査ツール、営業や案件獲得に関するメモもここに入れます。
公開可否、用途、リポジトリ種別はテナントではなくメタデータで扱います。
顧客案件、NDA、社外共有禁止、閲覧権限差による隔離が必要な場合だけ
`client-*` などの専用テナントを使います。
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
      tenant: secret-knowledge
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
GitHub Actions の `MEM0_API_URL` は `https://` で始まる URL にしてください。
接続先ホスト名の選び方とサービストークンの扱いは
[Cloudflare 設定](#cloudflare-設定) を見てください。
`MEM0_API_URL`、`MEM0_CLOUDFLARE_ACCESS_CLIENT_ID`、または
`MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET` のシークレット値が空の場合、
共通ワークフローは warning を出し、リポジトリ同期をスキップします。
呼び出し側ワークフローの `secrets:` ブロックでこの 3 つを渡すこと自体は必須で、
渡さない場合はワークフロー呼び出し自体がエラーになります。

薄い呼び出し側ワークフローとパス設定ファイルは、`install.sh` で生成できます。

```bash
./install.sh \
  --target github-actions \
  --target-dir /path/to/repository \
  --tenant secret-knowledge
```

対象リポジトリの GitHub シークレットは GitHub CLI でも設定できます。

```bash
gh secret set MEM0_API_URL --repo tom-miy/target-repository --body "https://mem0-api.example.com"
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_ID --repo tom-miy/target-repository --body "..."
gh secret set MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET --repo tom-miy/target-repository --body "..."
```

Organization 配下で共有する場合は、アクセス可能なリポジトリを指定して
Organization シークレットとして設定できます。

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

GitHub Actions から mem0 に接続できないクライアントリポジトリは、ローカルクローンから
同期できます。

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
MEM0_SINCE_REF=origin/main \
mise run sync-local-repo
```

## 共通ワークフロー

共通ワークフローは `.github/workflows/reusable-sync.yml` にあります。

これは `workflow_call` 専用です。

各リポジトリにワークフローの処理をコピーせず、`uses:` でこのワークフローを
呼び出します。

主な入力:

- `sync_mode`: `changed` または `full`
- `tenant`: 書き込み先テナント
- `repo`: メタデータとして保存するリポジトリ名
- `sync_config_file`: パスルールを書いた設定ファイル

通常は各リポジトリに `.mem0-sync.yml` を置きます。

共通ワークフローは、このファイルがあれば読み込みます。
なければ mem0-local-platform 側の `.mem0-sync.default.yml` を使います。
共通ワークフロー本体には include/exclude の実体を置きません。
YAML のキーは `include` と `exclude` です。
ローカル確認では `mise run sync-path-rules` で同じ変換を確認できます。

`exclude` は `include` より先に評価されます。

同期モードの使い分け:

- `changed`: push された差分ファイルだけを取り込みます。
- `full`: Git 管理下の全ファイルから include/exclude ルールを通った対象ファイルを取り込みます。

`full` は自動 push ではなく、初回投入や復旧時に手動実行するためのモードです。

## リポジトリ文脈の索引作成

デフォルトの索引対象は主に次です。完全な定義は
[.mem0-sync.default.yml](.mem0-sync.default.yml) を見てください。

- `README*.md`、`docs/**/*.md`、`adr/**/*.md`、`adrs/**/*.md`
- ソースコード: `**/*.go`、`**/*.py`、`**/*.ts`、`**/*.tsx`、`**/*.js`、
  `**/*.jsx`、`**/*.rs`、`**/*.java`、`**/*.kt`、`**/*.sql`、`**/*.sh`
- API 定義と設定: `**/api.yaml`、`**/openapi.yaml`(それぞれ `.yml` 版も)、
  `**/*.yaml`、`**/*.yml`、`**/*.json`、`**/*.toml`、`**/*.ini`、
  `**/*.proto`、`**/*.graphql`
- `**/Dockerfile`、`**/compose.yml`、`**/compose.yaml`、`**/Makefile`

デフォルトの除外は主に次です。

- `.git/**`、`.venv/**`、`.cache/**`、`data/**`、`secrets/**`
- `.env`、`.env.local`
- `node_modules/**`、`dist/**`、`vendor/**`、`coverage/**`、`build/**`、
  `__pycache__/**`、`*.pyc`
- ロックファイル(`*.lock`、`package-lock.json`、`pnpm-lock.yaml`、`yarn.lock`)
- 画像、音声、動画、アーカイブ、Office 文書、PDF などのバイナリ形式

Markdown は見出しごとに分割します。
コードや API 定義、設定ファイルはファイルパス、種別、リポジトリ名をメタデータに持つ
検索用チャンクとして扱います。
安定 ID は `repo:path:heading[:occurrence]` から SHA-256 で作ります。

同じファイル内で同じ見出しが複数回出る場合だけ、末尾に occurrence を付けます。

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
  - secret-knowledge
```

検索ツールは、設定された読み取り可能テナントの範囲だけを読みます。
ポリシーファイルの書式: [docs/security/policy-format.jp.md](docs/security/policy-format.jp.md)

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
ホスト名、または Tailscale 経由で HTTPS 終端できるホスト名を設定します。
GitHub Actions からの同期では `https://` を必須にします。
Compose 内部の `http://mem0:8000` は外部から使いません。

GitHub Actions は Cloudflare Access のサービストークンで認証します。
呼び出し側ワークフローには GitHub シークレット名として
`MEM0_CLOUDFLARE_ACCESS_CLIENT_ID` と
`MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET` を渡します。
このサービストークンは mem0 API へ到達できる鍵です。
漏えい時の影響を抑えるため、対象リポジトリを限定し、公開リポジトリやフォークのプルリクエストに
渡さないでください。
機密テナントや顧客リポジトリでは、GitHub Actions に mem0 のサービストークンを
置くこと自体がリスクになります。
その場合は Actions 直結ではなく、ローカルクローンからの同期、Tailscale 経由の同期、
プライベートネットワーク内の self-hosted runner、または書き込み専用取り込みゲートウェイを
使います。
`MEM0_API_KEY` は、mem0 API ランタイム側にも同じ値を設定した場合に
Bearer トークンとして検証されます。
ローカルだけの実験では空でも動きますが、Cloudflare などで外部公開する実務運用では
設定してください。
`CLOUDFLARE_TUNNEL_TOKEN` は、プラットフォーム側の `cloudflared` サービスだけが使います。

## Tailscale 接続

自分の端末から自宅サーバ上の mem0-local-platform に入る場合は、Tailscale を使えます。
GitHub Actions や外部エージェントは Cloudflare Access 経由、自分の Tailscale
アカウントまたは組織に参加している端末からの管理やローカル取り込みは
Tailscale 経由、という使い分けです。

```bash
mise run up-tailscale
tailscale serve --bg --https=8443 localhost:8000
tailscale serve --bg --https=9443 localhost:8010
```

自分の Tailscale ネットワーク内の端末では `mem0.env` に Tailscale のデバイス名を指定できます。

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
```

HTTPS は Tailscale Serve が終端します。
通常は Docker Compose 側へ証明書ファイルを渡す必要はありません。
`--bg` の Serve 設定は Tailscale daemon 側に保存されます。
`/mem0` や `/mem0-mcp` のようなパス分離もできますが、API や MCP クライアントが
サブパス対応している必要があります。
既定例は安全側に倒して `8443` と `9443` のポート分離にしています。

詳細は [Tailscale 接続](docs/security/tailscale-access.jp.md) を見てください。

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
cp mem0.sanitizer.example.yml mem0.sanitizer.yml
```

Docker Compose でローカル環境を起動します。

```bash
mise run up
```

自宅サーバで常駐させる場合は、バックグラウンド起動を使います。
`compose.yml` の全サービスには `restart: unless-stopped` が入っているため、
Docker daemon が起動すればコンテナも再起動されます。

```bash
mise run start
```

メモリ上限を明示して起動する場合:

```bash
mise run up-resources
```

メモリ上限つきで常駐させる場合:

```bash
mise run start-resources
```

Docker Compose の `ollama` サービスへデフォルトモデルを取得します。

```bash
mise run ollama-pull
```

ローカルモデルの標準の役割分担は次です。

- `qwen3.5:4b`: 推論、抽出、メタデータ生成、要約、MCP/tool 層
- `bge-m3`: 取得と意味検索の層

`qwen3.5:4b` を埋め込みモデルとして使ってはいけません。

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

- `data/falkordb/`
- `data/qdrant/`
- `data/mem0/`
- `data/ollama/`

通常のファイルシステム用バックアップツールで `data/` をバックアップできます。

詳細は [バックアップ手順](docs/operations/backup.jp.md) を見てください。
Docker のメモリ目安は
[Docker リソース目安](docs/operations/resource-sizing.jp.md) を見てください。

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

`agent-privacy-guard` は、別の GitHub リポジトリで作っている
Claude Code、Cursor、Copilot、Codex 向けの安全制御です。
ユーザーの依頼文やツール呼び出しに含まれる顧客名、リポジトリ名、API 名などを
匿名化し、MCP 呼び出しの信頼経路を分け、フックで危険な操作を止める役割を持ちます。
mem0-local-platform は記憶の保存と検索を担当します。

匿名化の運用は、サーバ側の匿名化を有効にするかどうかで 2 つに分かれます。

サーバ側の匿名化を有効にしない場合、または過去に生の本文で取り込んだデータが
残っている場合、検索前にユーザーの検索語を匿名化する使い方は標準にしません。
MCP 検索前に顧客名、リポジトリ名、API 名、ファイル名を置換すると、
匿名化後の検索語が取り込み済み本文と一致しにくくなります。

サーバ側の匿名化を有効にする場合、mem0-local-platform API が強制点になります。
`mem0.sanitizer.yml` で `sanitization.tenants.<tenant>.mode: required` にした
テナントでは、`/add` が `memory.add` を呼ぶ前に、設定済みの機密語と別名を
置換します。`ACCESS_KEY=...` のような代入形は正規表現ルールでも置換できます。
`sanitized=true`、`sanitizer`、`sanitization_profile`、
`sanitization_policy_hash` のようなメタデータはクライアントではなく API 側が付けます。
GitHub Actions、Python 取り込み CLI、ローカルツールのどれでも、
mem0-local-platform API 経由で書き込む限り同じ制御が効きます。
このモードでは mem0 には匿名化済み本文だけを保存し、生の情報は Git、
Markdown、ADR、Obsidian に残します。
`mode: required` のテナントでは、API が読み取り時にもこのポリシーを強制します。
検索結果に `sanitized != true`、ポリシーハッシュなし、または現在の匿名化ポリシーと
違うハッシュのメモリが混ざると、API は `409 stale_sanitization_policy` を返し、
該当ファイルの一覧とともに検索を失敗させます。
既存の mem0 データへ匿名化を適用する場合は、サーバ側の匿名化を有効にした後、
原本から `full` 再同期または再登録を行います。
再同期が終わるまで、該当テナントの検索は復旧しません。
ローカルデバッグ用に、API は `sanitization_matches` メタデータも付けます。
ここにはルール名と件数だけを入れ、生の一致文字列は入れません。

ただし、匿名化はアクセス制御やテナント分離の代わりではありません。
設計の仕組み、判断パターン、運用手順そのものが機密になる場合があるため、
匿名化済み本文でも機密テナントとして扱う場合があります。

別 TODO として、`agent-privacy-guard` が匿名化に使う対象データの連携方法を設計します。
対象データには、テナントごとの機密語、別名、公開名として許可する語、
置換マッピングなどを含みます。
取得後匿名化は、過去の生データや信頼経路が混在する場合の予備手段に限定し、
主な連携方法にはしません。
ポリシーファイルの書式: [docs/security/policy-format.jp.md](docs/security/policy-format.jp.md)

つまり、mem0 に入っている情報だけを唯一の保存先にしません。
長く残す内容は Git や Obsidian に戻し、mem0 では
「誰がどのテナントを読めるか」と「どのテナントへ書けるか」を明確にします。

例:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

この場合、`secret-knowledge` が読み取り境界です。
`backend-testing-patterns` は検索で絞り込むための情報であり、境界ではありません。

社内ナレッジやチーム共通の知識だけを扱う作業例:

```yaml
read:
  - secret-knowledge
```

この設定では、エージェントは `secret-knowledge` だけを検索できます。
新しく記録する内容は GitHub Actions または Python CLI から `secret-knowledge` に入れます。

顧客作業の例:

```yaml
read:
  - client-18384728-acme
```

この設定では、エージェントはその顧客用テナントだけを読みます。
別の顧客や `secret-knowledge` には触れません。

GitHub Actions から同期する例:

```yaml
with:
  tenant: client-18384728-acme
  repo: backend-testing-patterns
```

このワークフローは、`backend-testing-patterns` の対象ファイルを
`client-18384728-acme` テナントへ記録します。
`repo` 名はメタデータとして残るため、後から `repo` 単位で検索できます。
