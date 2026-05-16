# Raycast などローカルツールからの取り込み

この手順は、Raycast、Alfred、シェルスクリプトなどから短いメモを mem0 に
登録するためのものです。

GitHub Actions の同期とは別経路です。
リポジトリの Markdown を同期する場合は共通ワークフローを使います。
その場で思いついたメモ、調査メモ、作業中の決定を登録する場合は
`remember-to-mem0` を使います。

## 接続先

ローカルツールから Compose 外の mem0 に接続する場合は、Cloudflare Access で
保護されたホスト名を使います。

```text
MEM0_API_URL=https://mem0-api.example.com
```

Compose 内のサービスから呼ぶ場合だけ、内部 URL を使います。

```text
MEM0_API_URL=http://mem0:8000
```

Raycast や通常のターミナルから使う場合は、Cloudflare Access の
サービストークンも設定します。値は `mem0.env` に置くか、Raycast の
環境変数として設定します。

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

## 直接実行

テキストを引数で渡す例:

```bash
MEM0_API_URL=https://mem0-api.example.com \
CLOUDFLARE_ACCESS_CLIENT_ID=... \
CLOUDFLARE_ACCESS_CLIENT_SECRET=... \
uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source raycast \
  --type note \
  --tag idea \
  --text "次回から E2E の失敗は trace.zip を先に確認する"
```

標準入力から渡す例:

```bash
pbpaste | uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source raycast \
  --type note \
  --tag clipboard
```

ファイルから渡す例:

```bash
uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source local-file \
  --type note \
  --file /path/to/note.md
```

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
    --tenant mimr-tech \
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
  "tenant": "mimr-tech",
  "source": "raycast",
  "type": "note",
  "tags": ["clipboard"]
}
```

必要なら `repo` と `path` も付けられます。

```bash
uv run remember-to-mem0 \
  --tenant mimr-tech \
  --source raycast \
  --type decision \
  --repo backend-testing-patterns \
  --path docs/e2e.md \
  --tag testing \
  --text "E2E では trace を artifact として必ず残す"
```

`repo` は検索用メタデータです。
テナントではありません。

## 使い分け

GitHub Actions の共通ワークフロー:

- README、docs、ADR を Git から同期する
- 初回投入や復旧時に `full` を使う
- 通常 push で `changed` を使う

`remember-to-mem0`:

- Raycast などから一時メモを入れる
- 作業中の判断や調査メモをすぐ登録する
- Git にまだ書いていない短い文脈を入れる

重要な決定や長く残す知識は、後で Git / Markdown / ADR に戻してください。
mem0 は正本ではありません。
