# ローカルツールからの取り込み

この手順は、Obsidian、Raycast、Alfred、シェルスクリプトなどから短いメモを
mem0 に登録するためのものです。

GitHub Actions の同期とは別経路です。
通常のリポジトリ同期では共通ワークフローを使います。
クライアント案件などで GitHub Actions から mem0 に接続できない場合は、
ローカル clone から差分同期または全体同期を実行できます。
その場で思いついたメモ、調査メモ、作業中の決定を登録する場合は
`remember-to-mem0` を使います。

## 接続先

ローカルツールから Compose 外の mem0 に接続する場合は、Cloudflare Access で
保護されたホスト名を使います。

```text
MEM0_API_URL=https://mem0-api.example.com
```

自分の Tailscale ネットワーク内の端末から自宅サーバへ接続する場合は、Tailscale の
デバイス名も使えます。

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
```

Compose 内のサービスから呼ぶ場合だけ、内部 URL を使います。

```text
MEM0_API_URL=http://mem0:8000
```

Raycast や通常のターミナルから Cloudflare Access 経由で使う場合は、
Cloudflare Access のサービストークンも設定します。値は `mem0.env` に置くか、
Raycast の環境変数として設定します。Tailscale 経由では Cloudflare Access の
サービストークンは不要です。

```text
CLOUDFLARE_ACCESS_CLIENT_ID=...
CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

`CLOUDFLARE_TUNNEL_TOKEN` は使いません。
これは実行基盤側の `cloudflared` サービスが使うトークンです。

`mem0.env` を使う場合:

```bash
cp mem0.env.example mem0.env
```

## ローカルリポジトリ差分を同期する

GitHub Actions を使えないリポジトリでは、手元の clone から mem0 に同期します。
対象リポジトリ側に `.mem0-sync.yml` があればそれを使い、なければ
mem0-local-platform 側の `.mem0-sync.default.yml` を使います。

作業ツリーと staged 差分だけを確認する例:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
mise run sync-local-repo-dry-run
```

実際に登録する例:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
mise run sync-local-repo
```

ブランチ全体を `origin/main` からの差分として同期する例:

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
MEM0_SINCE_REF=origin/main \
mise run sync-local-repo
```

初回投入や再構築では全体同期を使います。

```bash
MEM0_REPO_ROOT=/path/to/client-repository \
MEM0_DEFAULT_TENANT=client-acme \
MEM0_SYNC_MODE=full \
mise run sync-local-repo
```

未追跡ファイルも含める場合だけ、CLI を直接呼んで `--include-untracked` を付けます。

```bash
uv run sync-local-repo-to-mem0 \
  --root /path/to/client-repository \
  --tenant client-acme \
  --since-ref origin/main \
  --include-untracked
```

この経路でも、`tenant + repo + path` 単位で既存 chunk を消してから再登録します。
削除済みファイルやリネーム元 path も、差分に含まれていれば mem0 側から消します。

## 直接実行

テキストを引数で渡す例:

```bash
MEM0_API_URL=https://mem0-api.example.com \
CLOUDFLARE_ACCESS_CLIENT_ID=... \
CLOUDFLARE_ACCESS_CLIENT_SECRET=... \
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source raycast \
  --type note \
  --tag idea \
  --text "次回から E2E の失敗は trace.zip を先に確認する"
```

標準入力から渡す例:

```bash
pbpaste | uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source raycast \
  --type note \
  --tag clipboard
```

ファイルから渡す例:

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source local-file \
  --type note \
  --file /path/to/note.md
```

Python モジュールとして直接呼ぶこともできます。
動作は `remember-to-mem0` と同じです。

```bash
uv run python -m scripts.remember_text \
  --tenant secret-knowledge \
  --source local-file \
  --type note \
  --file /path/to/note.md
```

## Obsidian から登録する

Obsidian の保管庫にあるノートを登録する場合は、対象ノートのファイルパスを
`--file` に渡します。

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source obsidian \
  --type note \
  --path "obsidian/ai-workflows/e2e-debugging.md" \
  --tag obsidian \
  --tag debugging \
  --file "$HOME/Obsidian/Vault/ai-workflows/e2e-debugging.md"
```

`--path` は mem0 側に保存する検索用の相対パスです。
手元の実ファイルパスをそのまま保存する必要はありません。

顧客や契約で隔離が必要なノートは `--tenant client-...` に分けます。
公開可否やリポジトリ種別だけでテナントを増やさず、必要なら `--tag` や `--path`
で検索しやすくします。

Obsidian の Shell Commands プラグインやショートカットから呼ぶ場合も、選択中ファイルの
パスを `--file` に渡します。秘密情報を含むノートを送らないよう、登録対象の
フォルダを限定してください。

## Raycast スクリプトコマンド

Raycast のスクリプトコマンドとして使う例です。

```bash
#!/usr/bin/env bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Remember Clipboard to mem0
# @raycast.mode compact
#
# Optional parameters:
# @raycast.icon memory-stick
# @raycast.packageName mem0-local-platform
#
# Documentation:
# @raycast.description クリップボードの内容を Cloudflare Access 経由で mem0 に送ります。

set -euo pipefail

cd "$HOME/ghq/personal/github.com/tom-miy/mem0-local-platform"

pbpaste | \
  MEM0_API_URL="https://mem0-api.example.com" \
  CLOUDFLARE_ACCESS_CLIENT_ID="$CLOUDFLARE_ACCESS_CLIENT_ID" \
  CLOUDFLARE_ACCESS_CLIENT_SECRET="$CLOUDFLARE_ACCESS_CLIENT_SECRET" \
  uv run remember-to-mem0 \
    --tenant secret-knowledge \
    --source raycast \
    --type note \
    --tag clipboard
```

Raycast 側には次の環境変数を設定します。

```text
CLOUDFLARE_ACCESS_CLIENT_ID
CLOUDFLARE_ACCESS_CLIENT_SECRET
```

`MEM0_API_URL` はスクリプトに直接書かず、Raycast の環境変数として渡しても構いません。

## メタデータ

`remember-to-mem0` は次のメタデータを付けて登録します。

```json
{
  "tenant": "secret-knowledge",
  "source": "raycast",
  "type": "note",
  "tags": ["clipboard"]
}
```

必要なら `repo` と `path` も付けられます。

```bash
uv run remember-to-mem0 \
  --tenant secret-knowledge \
  --source raycast \
  --type decision \
  --repo backend-testing-patterns \
  --path docs/e2e.md \
  --tag testing \
  --text "E2E では trace を artifact として必ず残す"
```

`repo` はアクセス制御ではありません。
「どのリポジトリ由来のメモか」で検索結果を絞るための情報です。
読める範囲を分ける場合は `tenant` を分けます。

## 使い分け

GitHub Actions の共通ワークフロー:

- コード、API 定義、設定、README、docs、ADR を Git から同期する
- 初回投入や復旧時に `full` を使う
- 通常 push で `changed` を使う

`sync-local-repo-to-mem0`:

- GitHub Actions から mem0 へ接続できないリポジトリをローカル clone から同期する
- クライアント案件の private リポジトリを Cloudflare/Tailscale 経由で手元から登録する
- `HEAD` からの作業ツリー差分、または `origin/main` など任意 ref からの差分を同期する
- 初回投入や再構築時に `--sync-mode full` を使う

`remember-to-mem0`:

- Obsidian のノートを手動で入れる
- Raycast などから一時メモを入れる
- 作業中の判断や調査メモをすぐ登録する
- Git にまだ書いていない短い文脈を入れる

重要な決定や長く残す知識は、後で Git / Markdown / ADR に戻してください。
mem0 は唯一の保存先ではなく、AI エージェントが検索するための索引です。
