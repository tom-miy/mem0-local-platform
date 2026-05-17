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

## agent-privacy-guard との関係

`agent-privacy-guard` は、別の GitHub リポジトリで作っている
Claude Code、Cursor、Copilot、Codex 向けのプロンプト安全制御です。
ユーザーの依頼文やツール呼び出しに含まれる顧客名、リポジトリ名、API 名などを
匿名化し、MCP 呼び出しの信頼経路を分け、フックで危険な操作を止める役割を持ちます。
mem0-local-platform との連携では、検索語を先に匿名化する使い方を標準にはしません。
より安全な連携点は、mem0 に書き込む前に本文を匿名化する経路です。

現時点の問題は、mem0 に生の本文を保存している場合、検索前の匿名化で
mem0 検索の精度が落ちることです。
たとえば MCP 検索前に顧客名、リポジトリ名、API 名、ファイル名が置換されると、
匿名化後の検索語が取り込み済みの生の本文と一致しにくくなります。

TODO として、取り込み時匿名化、つまり `sanitize-on-ingest` を主な連携点として設計します。
取り込み経路は `memory.add` の前に必要に応じて `agent-privacy-guard` を呼び、
mem0 には匿名化済みチャンク本文だけを保存します。
チャンクには `sanitized=true`、`sanitizer=agent-privacy-guard`、
`sanitization_profile` のようなメタデータを付けます。
生の情報は Git、Markdown、ADR、Obsidian に残します。
取得後匿名化は、過去の生データや信頼経路が混在する場合のフォールバックに限定し、
標準設計にはしません。

GitHub Actions の同期ジョブには、通常この制御は効きません。
Actions は GitHub runner 上で直接実行されるため、ローカルのフックやゲートウェイを
通りません。Actions 側は Cloudflare Access のサービストークン、GitHub secrets、
取り込み対象パス、テナント指定で保護します。

## 人間のログイン

人間向けの OAuth ログインは任意です。
デバッグや手動確認のために有効化できますが、本番想定の対象は非対話の
エージェントアクセスです。
