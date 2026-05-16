# Cloudflare Access

Cloudflare Tunnel はデフォルトの実行環境に含まれます。
Compose スタックは `cloudflared` を起動し、直接 inbound port を開けずに
Docker DNS 経由で内部サービスを公開します。

公開ホスト名は Cloudflare Access で保護します。
デフォルトの対象は、サービストークンを使うエージェントやツールの認証です。

## Tunnel ルーティング

Cloudflare Tunnel に公開ホスト名を作成します。

```text
mem0-api.example.com -> http://mem0:8000
mem0-mcp.example.com -> http://mcp:8010
```

これらのサービス名は compose のサービス名です。
`cloudflared` コンテナから、デフォルトの compose ネットワーク上で到達できます。

## サービストークンヘッダー

エージェントは、保護されたエンドポイントへ次のヘッダーを付けて呼び出します。

```text
CF-Access-Client-Id: <client id>
CF-Access-Client-Secret: <client secret>
```

これらの値はエージェント実行環境か CI の secret store に保存します。
このリポジトリへコミットしてはいけません。

MCP クライアントや取り込みクライアントは、compose ネットワークの外からは
Cloudflare で保護されたホスト名を呼び出します。
compose ネットワーク内では、サービスは `http://mem0:8000` を呼び出します。

`CLOUDFLARE_TUNNEL_TOKEN` は、Tunnel を維持する `cloudflared` サービス専用です。
GitHub Actions などのクライアントは Tunnel token を使いません。
上記の Access service token ヘッダーを使います。

## 人間のログイン

人間向けの OAuth ログインは任意です。
デバッグや手動確認のために有効化できますが、本番想定の対象は非対話の
エージェントアクセスです。
