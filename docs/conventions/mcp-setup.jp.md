# MCP の設定

この手順は、Codex、Claude、その他の MCP 対応クライアントから
mem0-local-platform のメモリ検索ツールを使うためのものです。

このリポジトリは MCP サーバーを提供します。
既存のエージェント設定ファイルを自動で書き換えることはしません。
`install.sh` は設定例を表示するだけです。表示内容を確認してから、
使っているクライアントの設定へ追加してください。

秘密情報は MCP クライアントの設定へ直接書かず、`mem0.env` に置きます。
`mem0.env` は Git にコミットしません。

## 提供する MCP ツール

- `search_memory`
- `remember`
- `related_repo_context`
- `recent_project_memories`

`search_memory` と `related_repo_context` は、設定された読み取り可能テナントだけを検索します。
`remember` は、設定された書き込み先テナントにだけ書き込みます。

## 接続方式

使い方は 2 つあります。

1. クライアントがローカルで MCP サーバーを起動する
2. Cloudflare Tunnel 経由で compose 内の MCP サーバーに接続する

ローカル起動では `stdio` を使います。
クライアントが `uv run mem0-local-mcp` を起動します。
Codex では `scripts/run_mcp.sh` を起動し、このスクリプトが `mem0.env` を読みます。

Cloudflare Tunnel 経由では、compose の `mcp` サービスに接続します。
外部からの接続には Cloudflare Access のサービストークンが必要です。

## ローカル起動の設定例

まず `mem0.env` を作ります。

```bash
cp mem0.env.example mem0.env
cp mem0.policy.example.yml mem0.policy.yml
```

`mem0.env` には、MCP クライアントや Raycast などローカルツールから使う
接続情報を書きます。

```text
MEM0_API_URL=https://mem0-api.example.com
MEM0_TENANT_POLICY_FILE=mem0.policy.yml
CLOUDFLARE_ACCESS_CLIENT_ID=...
CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

読み取り可能テナントと書き込み先テナントは `mem0.policy.yml` に書きます。

```yaml
read:
  - mimr-tech

write:
  - mimr-tech
```

`mem0.env` は `.env` とは用途が違います。

- `.env` は Docker Compose の実行環境用です。
- `mem0.env` は Codex、Claude、Raycast などローカルクライアント用です。

設定例を表示します。

```bash
./install.sh --target generic --transport stdio
```

Claude Desktop 用の説明付きで表示する場合:

```bash
./install.sh --target claude-desktop --transport stdio
```

## Codex の設定

Codex には `stdio` の MCP サーバーとして登録します。

設定例を表示します。

```bash
./install.sh --target codex
```

出力例:

```toml
[mcp_servers.mem0-local-platform]
command = "/path/to/mem0-local-platform/scripts/run_mcp.sh"
args = []
```

`scripts/run_mcp.sh` は `mem0.env` を読み込んでから `uv run mem0-local-mcp`
を起動します。

Codex 側の設定ファイルには Cloudflare Access の秘密値を直接書きません。
秘密値は `mem0.env` にだけ置きます。

`mem0.env` の場所を変えたい場合は、Codex の MCP 設定で `MEM0_ENV_FILE`
を環境変数として渡せます。

```toml
[mcp_servers.mem0-local-platform]
command = "/path/to/mem0-local-platform/scripts/run_mcp.sh"
args = []

[mcp_servers.mem0-local-platform.env]
MEM0_ENV_FILE = "/path/to/private/mem0.env"
```

## Claude Desktop の設定

Claude Desktop など JSON 形式の MCP 設定では、次のように登録します。

出力例:

```json
{
  "mcpServers": {
    "mem0-local-platform": {
      "command": "uv",
      "args": ["run", "mem0-local-mcp"],
      "cwd": "/path/to/mem0-local-platform",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "MEM0_API_URL": "${MEM0_API_URL}",
        "MEM0_TENANT_POLICY_FILE": "${MEM0_TENANT_POLICY_FILE}",
        "CLOUDFLARE_ACCESS_CLIENT_ID": "${CLOUDFLARE_ACCESS_CLIENT_ID}",
        "CLOUDFLARE_ACCESS_CLIENT_SECRET": "${CLOUDFLARE_ACCESS_CLIENT_SECRET}"
      }
    }
  }
}
```

Claude Desktop でも秘密値を設定ファイルへ直接書きたくない場合は、
`scripts/run_mcp.sh` を command に指定する形を使えます。

```json
{
  "mcpServers": {
    "mem0-local-platform": {
      "command": "/path/to/mem0-local-platform/scripts/run_mcp.sh",
      "args": []
    }
  }
}
```

`MEM0_API_URL` は接続先に合わせます。

Cloudflare Access 経由で mem0 API に接続する場合:

```text
MEM0_API_URL=https://mem0-api.example.com
```

compose 内から mem0 API に接続する場合:

```text
MEM0_API_URL=http://mem0:8000
```

通常のデスクトップクライアントから使う場合は、Cloudflare Access で保護された
ホスト名を使います。

## Cloudflare Tunnel 経由の設定例

compose の `mcp` サービスを Cloudflare Tunnel で公開する場合は、MCP の
ホスト名を Cloudflare に設定します。

```text
mem0-mcp.example.com -> http://mcp:8010
```

設定例を表示します。

```bash
./install.sh --target generic --transport sse
```

出力例:

```json
{
  "mcpServers": {
    "mem0-local-platform": {
      "url": "${CLOUDFLARE_MCP_HOSTNAME}/sse",
      "headers": {
        "CF-Access-Client-Id": "${CLOUDFLARE_ACCESS_CLIENT_ID}",
        "CF-Access-Client-Secret": "${CLOUDFLARE_ACCESS_CLIENT_SECRET}"
      }
    }
  }
}
```

`CLOUDFLARE_TUNNEL_TOKEN` はクライアントには渡しません。
これは実行基盤側の `cloudflared` サービスが Tunnel を維持するための
トークンです。

## 必要な環境変数

ローカル MCP サーバーを起動する側に設定します。
通常は `mem0.env` に書きます。

```text
MEM0_API_URL=https://mem0-api.example.com
MEM0_TENANT_POLICY_FILE=mem0.policy.yml
CLOUDFLARE_ACCESS_CLIENT_ID=...
CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

読み取り可能テナントと書き込み先テナントは用途に合わせて変えます。

mimr-tech 管理下の作業:

```yaml
read:
  - mimr-tech

write:
  - mimr-tech
```

顧客作業:

```yaml
read:
  - client-18384728-acme

write:
  - client-18384728-acme
```

## 動作確認

まず依存関係を入れます。

```bash
mise trust .
mise install
mise run setup
```

MCP サーバーをローカルで起動する場合:

```bash
MEM0_API_URL=https://mem0-api.example.com \
MEM0_TENANT_POLICY_FILE=mem0.policy.yml \
CLOUDFLARE_ACCESS_CLIENT_ID=... \
CLOUDFLARE_ACCESS_CLIENT_SECRET=... \
uv run mem0-local-mcp
```

クライアントに登録した後、`search_memory` で検索できることを確認します。

## 注意点

- `install.sh` は設定ファイルを変更しません。
- 既存の MCP 設定がある場合は、`mcpServers` の中へ手動で統合します。
- `CLOUDFLARE_TUNNEL_TOKEN` をクライアントに渡しません。
- 読み取り可能テナントを広げる前に、顧客情報や個人情報の境界を確認します。
- 書き込み先テナントは 1 つに固定します。
