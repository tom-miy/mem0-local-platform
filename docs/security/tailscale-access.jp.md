# Tailscale 接続

Tailscale は、自分の端末から自宅サーバ上の mem0-local-platform に入るための
プライベート接続経路として使います。

Cloudflare Tunnel は、GitHub Actions や外部エージェントが非対話で接続するための
公開ホスト名と Cloudflare Access 認証に使います。
ただし、GitHub Actions に mem0 の service token を置きたくない高機密リポジトリでは、
Tailscale 経由のローカル同期や private network 内の self-hosted runner を使います。
Tailscale は、自分の Tailscale アカウントまたは組織に参加している端末から
管理、検証、ローカル取り込みを行う経路です。

## 使い分け

- GitHub Actions からの通常同期: Cloudflare Tunnel + Cloudflare Access
- 高機密リポジトリの同期: Tailscale 経由のローカル同期、または private network 内の self-hosted runner
- 外部の自動化エージェント: Cloudflare Tunnel + Cloudflare Access
- 自分の端末から自宅サーバへ接続: Tailscale
- サーバ上の compose 内部通信: Docker DNS

## compose の起動

Tailscale 経由で使う場合は、通常の compose に Tailscale 用 override を重ねます。

```bash
mise run up-tailscale
```

自宅サーバで常駐させる場合:

```bash
mise run start-tailscale
```

メモリ上限も同時に有効にする場合:

```bash
mise run up-tailscale-resources
```

メモリ上限も有効にして常駐させる場合:

```bash
mise run start-tailscale-resources
```

`compose.tailscale.yml` は `mem0` と `mcp` をホストの `127.0.0.1` にだけ公開します。
LAN 全体へ直接ポートを開けません。

```text
127.0.0.1:8000 -> mem0:8000
127.0.0.1:8010 -> mcp:8010
```

通常の `mise run up` は `compose.yml` だけを使います。
Tailscale 用の localhost bind は `mise run up-tailscale` のときだけ有効です。

## Tailscale Serve

自宅サーバ上で Tailscale Serve を設定します。
Tailscale Serve は自分の Tailscale ネットワーク内向けに HTTPS で公開できます。
HTTPS 証明書は Tailscale 側で終端され、compose 側の `mem0` と `mcp` は
localhost の HTTP のままで構いません。

既定例ではポートで分けます。
API や MCP クライアントはルートパス前提のことがあるため、まずはこの形が安全です。

```bash
tailscale serve --bg --https=8443 localhost:8000
tailscale serve --bg --https=9443 localhost:8010
```

自分の Tailscale ネットワーク内の端末からは、MagicDNS 名を使って HTTPS で接続します。

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
MCP URL=https://home-server.tailnet-name.ts.net:9443
```

`home-server.tailnet-name.ts.net` は実際の Tailscale の MagicDNS 名に置き換えます。

Tailscale Serve の HTTPS を使うには、Tailscale 管理画面で
このアカウントまたは組織の HTTPS 証明書機能を有効にする必要があります。
未設定の場合、`tailscale serve` 実行時に有効化用の案内 URL が表示されます。
通常は `tailscale cert` で証明書ファイルを発行して compose 側へ渡す必要はありません。
この構成では Tailscale daemon が HTTPS を終端し、localhost の HTTP サービスへ転送します。

`--bg` を付けた Serve 設定はバックグラウンド設定として保存されます。
端末を閉じても残り、Tailscale daemon の再起動後も再開されます。
Docker コンテナ側の常駐は `mise run start-tailscale` または
`mise run start-tailscale-resources` で行います。

## パスで分ける構成

Tailscale Serve は `--set-path` で `/mem0` や `/mem0-mcp` のようなパスにも振り分けできます。
n8n などのサービスを後で増やす場合は、1 つの HTTPS ポートにまとめる選択肢になります。

例:

```bash
tailscale serve --bg --https=443 --set-path=/mem0 localhost:8000
tailscale serve --bg --https=443 --set-path=/mem0-mcp localhost:8010
tailscale serve --bg --https=443 --set-path=/n8n localhost:5678
```

接続例:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net/mem0
MCP URL=https://home-server.tailnet-name.ts.net/mem0-mcp
n8n URL=https://home-server.tailnet-name.ts.net/n8n
```

ただし、アプリやクライアントがサブパス配下で動けるかは別問題です。
リダイレクト、WebSocket、コールバック URL、静的ファイルのパスがルート前提の場合は、
アプリ側にも base URL や path prefix の設定が必要になります。

そのため、このリポジトリの既定は `8443` と `9443` のポート分離にしています。
n8n のような Web UI を追加するときは、アプリがサブパス対応か確認してから
`/n8n` に寄せるか、`10443` のようにポートを分けるかを決めます。

設定確認:

```bash
tailscale serve status
tailscale serve status --json
```

設定を消す場合:

```bash
tailscale serve reset
```

## Tailscale コンテナを入れない理由

この構成では Tailscale 用コンテナを追加しません。
自宅サーバ本体に Tailscale を入れ、ホスト上の `tailscale serve` で
`127.0.0.1` に公開された compose サービスへ転送します。

理由は次です。

- 既存の自宅サーバを Tailscale ネットワーク内の 1 台の端末として扱える
- Tailscale の認証状態やデバイス名を Docker 状態に閉じ込めない
- `compose.tailscale.yml` で LAN へ直接ポートを開けずに済む
- HTTPS 終端を Tailscale Serve に任せられる

Tailscale をコンテナ化する構成も可能ですが、その場合は auth key、状態ディレクトリ、
Serve 設定、ネットワーク権限の管理が増えます。
このリポジトリの既定は、ホストの Tailscale daemon を使う構成です。

## クライアント設定

自分の端末から Python CLI や MCP クライアントを使う場合は、`mem0.env` の
`MEM0_API_URL` を Tailscale 経由の URL にできます。

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
MEM0_TENANT_POLICY_FILE=mem0.policy.yml
```

Tailscale 経由では Cloudflare Access のサービストークンは不要です。
通常の GitHub-hosted runner は Tailscale ではなく Cloudflare Access 経由で接続します。
mem0 の service token を GitHub Actions に置きたくない場合は、GitHub-hosted runner からの
直接同期を使わず、ローカル同期または self-hosted runner を使います。

## 注意点

- Tailscale は自分の Tailscale ネットワーク内の private access 用です。
- Tailscale Funnel は使いません。公開インターネットへ出す用途ではありません。
- `compose.tailscale.yml` は localhost bind に限定します。
- HTTPS は Tailscale Serve で終端します。
- Tailscale ACL で、mem0 に接続できるユーザーや端末を制限します。
- 外部 LLM や外部 embedding provider を使う場合、検索結果や登録内容が provider に送られる可能性があります。
