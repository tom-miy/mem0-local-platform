# Docker リソース目安

`compose.yml` 本体にはメモリ上限を固定していません。
動かす端末やサーバの性能差が大きいためです。

メモリ上限を明示したい環境では、`compose.resources.yml` を重ねて起動します。

```bash
mise run up-resources
```

Tailscale 用の localhost bind と同時に使う場合:

```bash
mise run up-tailscale-resources
```

## まずの目安

外部 LLM と外部の埋め込みモデル提供元を使う場合:

```text
ホストメモリ: 4GB から 6GB
```

ローカル Ollama で軽量モデルと埋め込みモデルを動かす場合:

```text
ホストメモリ: 12GB から 16GB
例: qwen3:4b + nomic-embed-text
```

大きめのローカルモデルを使う場合:

```text
ホストメモリ: 24GB から 32GB 以上
例: 8B 以上のモデル、複数モデル常駐、大きいリポジトリの連続取り込み
```

## デフォルトの上限

`compose.resources.yml` の初期値:

```text
falkordb:    1GB
qdrant:      2GB
ollama:      8GB
mem0:        1GB
mcp:       512MB
cloudflared: 256MB
```

この値は「小さめの個人サーバで落ち方を予測しやすくする」ための上限です。
性能を最大化する設定ではありません。

## どこを増やすか

Ollama が一番メモリを使います。
LLM をローカルで動かすなら、まず `ollama` の上限を増やします。

Qdrant はチャンク数と埋め込み次元数で増えます。
大量のリポジトリや長い Markdown を取り込むなら、`qdrant` を増やします。

FalkorDB は関係性や履歴の量で増えます。
関連メモリやリポジトリ間の文脈を多く保持する場合は、`falkordb` を増やします。

mem0 API がメモリ不足で停止する場合は、`mem0` を増やします。
MCP と cloudflared は通常小さくて足ります。

## 確認コマンド

起動後に実使用量を見ます。

```bash
docker stats
```

Docker Desktop を使う場合は、Docker Desktop 側にもメモリ上限があります。
ローカル Ollama を使うなら、Docker Desktop の Resources で 12GB から 16GB 程度を
割り当てるところから始めます。

## 運用ルール

- `compose.yml` は共通の既定構成として保ちます。
- メモリ上限は `compose.resources.yml` で上書きします。
- ホストごとの調整はコミットせず、必要なら個人用の上書きファイルにします。
- メモリ不足で停止したら、まず `docker stats` で実使用量を見てから増やします。
