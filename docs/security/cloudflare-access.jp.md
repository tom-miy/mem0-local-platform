# Cloudflare Access

Cloudflare Tunnel はデフォルトの実行環境に含まれます。
Compose スタックは `cloudflared` を起動し、外部から直接入るポートを開けずに
Docker DNS 経由で内部サービスを公開します。

公開ホスト名は Cloudflare Access で保護します。
デフォルトの対象は、サービストークンを使うエージェントやツールの認証です。

## Tunnel ルーティング

Cloudflare Tunnel に公開ホスト名を作成します。

```text
mem0-api.example.com -> http://mem0:8000
mem0-mcp.example.com -> http://mcp:8010
```

これらのサービス名は Docker Compose のサービス名です。
`cloudflared` コンテナから、デフォルトの Docker Compose ネットワーク上で到達できます。

## サービストークンヘッダー

エージェントは、保護されたエンドポイントへ次のヘッダーを付けて呼び出します。

```text
CF-Access-Client-Id: <client id>
CF-Access-Client-Secret: <client secret>
```

これらの値はエージェント実行環境か CI のシークレットストアに保存します。
このリポジトリへコミットしてはいけません。

MCP クライアントや取り込みクライアントは、Docker Compose ネットワークの外からは
Cloudflare で保護されたホスト名を呼び出します。
Docker Compose ネットワーク内では、サービスは `http://mem0:8000` を呼び出します。

`CLOUDFLARE_TUNNEL_TOKEN` は、Tunnel を維持する `cloudflared` サービス専用です。
GitHub Actions などのクライアントは Tunnel トークンを使いません。
上記の Access サービストークンヘッダーを使います。

Cloudflare Access に加えて、mem0 API 側でも `MEM0_API_KEY` を設定できます。
設定した場合、API は `Authorization: Bearer <MEM0_API_KEY>` を検証します。
本番運用では、Cloudflare Access のサービストークンだけに依存しないでください。

## GitHub Actions から使う場合のリスク

GitHub Actions に Cloudflare Access のサービストークンを置くと、そのシークレットを
読めるワークフローは Cloudflare で保護された mem0 API へ到達できます。
Cloudflare Access は到達制御であり、mem0 内のテナント、リポジトリ、パス単位の
細かい認可ではありません。

現在の API は `/add`、`/search`、`/v1/memories/`、
`/v1/sanitization/audit` を同じ API ホストで公開します。
そのため、Actions 用のサービストークンが漏えいした場合、書き込みだけでなく
検索や棚卸しのエンドポイントにも到達できる可能性があります。
`MEM0_API_KEY` を有効にしていれば、Cloudflare のサービストークンだけでは API を
呼び出せません。
ただし、GitHub Actions 側には `MEM0_API_KEY` も渡すため、GitHub シークレットの
漏えいリスク自体は残ります。
mem0 に機密性の高い顧客情報、非公開の判断パターン、社外共有禁止の内容を入れる場合は、
GitHub Actions から直接 mem0 API へ接続する設計を標準にしないでください。

実務での推奨:

- 低〜中リスクの公開可能なリポジトリ同期だけ GitHub Actions から行う
- 機密テナントや顧客テナントは、ローカルクローンからの同期、Tailscale 経由の同期、
  またはプライベートネットワーク内の self-hosted runner で同期する
- GitHub Actions に渡すサービストークンはリポジトリごと、または用途ごとに分ける
- Organization シークレットを使う場合も `--visibility selected` で対象リポジトリを限定する
- 公開リポジトリやフォークのプルリクエストに mem0 接続用シークレットを渡さない
- Cloudflare Access 側で Actions 用ホスト名と MCP/検索用ホスト名を分ける
- Actions 用ホスト名は、将来的に書き込み専用ゲートウェイだけへ向ける

安全側の構成例:

```text
mem0-ingest.example.com -> 書き込み専用取り込みゲートウェイ
mem0-mcp.example.com    -> MCP/検索サービス
```

GitHub Actions は `mem0-ingest.example.com` だけを呼びます。
MCP や検索用の `mem0-mcp.example.com` には Actions 用サービストークンを許可しません。
現時点の Docker Compose スタックには書き込み専用取り込みゲートウェイは未実装です。
機密データを扱う場合は、このゲートウェイを追加するまで GitHub Actions からの
直接同期ではなく、ローカル同期または self-hosted runner を使うのが安全です。

## agent-privacy-guard との関係

`agent-privacy-guard` は、別の GitHub リポジトリで作っている
Claude Code、Cursor、Copilot、Codex 向けのプロンプト安全制御です。
ユーザーの依頼文やツール呼び出しに含まれる顧客名、リポジトリ名、API 名などを
匿名化し、MCP 呼び出しの信頼経路を分け、フックで危険な操作を止める役割を持ちます。
mem0-local-platform は記憶の保存と検索を担当します。

匿名化には 2 つの運用モードがあります。

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
生の情報は Git、Markdown、ADR、Obsidian に残します。
`sanitized != true`、ポリシーハッシュなし、または現在の匿名化ポリシーと違う
ハッシュを使って、過去データや古いポリシーで処理されたデータを見つけます。
既存の mem0 データへ匿名化を適用する場合は、サーバ側の匿名化を有効にした後、
原本から `full` 再同期または再登録を行います。
ローカルデバッグ用に、API は `sanitization_matches` メタデータも付けます。
ここにはルール名と件数だけを入れ、生の一致文字列は入れません。

ただし、匿名化すれば機密情報を安全に扱える、という意味ではありません。
匿名化は漏えい時の影響を下げる補助策です。
アクセス制御、テナント分離、シークレット管理、取り込み対象のレビューの代わりにはなりません。
顧客名や個人名を伏せても、設計の仕組み、判断パターン、運用手順、脆弱性の文脈、
社外共有禁止のノウハウそのものが機密である場合があります。
そのような情報は、匿名化後でも機密テナントとして扱います。
別 TODO として、`agent-privacy-guard` が匿名化に使う対象データの連携方法を設計します。
対象データには、テナントごとの機密語、別名、公開名として許可する語、
置換マッピングなどを含みます。
取得後匿名化は、過去の生データや信頼経路が混在する場合の予備手段に限定し、
標準設計にはしません。
ポリシーファイルの書式: [policy-format.jp.md](policy-format.jp.md)

## 人間のログイン

人間向けの OAuth ログインは任意です。
デバッグや手動確認のために有効化できますが、本番想定の対象は非対話の
エージェントアクセスです。
