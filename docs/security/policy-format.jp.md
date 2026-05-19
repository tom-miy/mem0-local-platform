# mem0 ポリシー書式

既定では、ポリシーファイルを 2 つに分けます。

- `mem0.policy.yml`: MCP ツールが検索できるテナント
- `mem0.sanitizer.yml`: `/add` が mem0 に書き込む前に、サーバ側で匿名化を必須にするテナント

MCP サーバーには `MEM0_TENANT_POLICY_FILE` を指定します。
mem0-local-platform API には `MEM0_SANITIZER_POLICY_FILE` を指定します。
後方互換のため、`MEM0_SANITIZER_POLICY_FILE` が未指定の場合は API が
`MEM0_TENANT_POLICY_FILE` からも匿名化設定を読みます。
ただし、新しい構成ではファイルを分けます。

## 最小ポリシー

```yaml
read:
  - secret-knowledge
```

`read` は MCP ツール用の必須設定です。
検索できるテナントを列挙します。

## 匿名化ポリシー

mem0 に保存する前に匿名化が必要なテナントでは `mem0.sanitizer.yml` を使います。

```yaml
sanitization:
  sanitizer: mem0-local-platform
  tenants:
    secret-knowledge:
      mode: required
      profile: default
    public-notes:
      mode: disabled
  profiles:
    default:
      allow_terms:
        - mem0
        - Qdrant
      sensitive_terms:
        - name: client-name
          term: client-acme
          replacement: CUSTOMER_1
          aliases:
            - Acme client
        - name: internal-project-name
          term: internal-payment-risk-review
          replacement: PROJECT_1
      sensitive_patterns:
        - name: access-key-assignment
          pattern: '(?i)\b[A-Z0-9_]*(?:ACCESS|SECRET|API)_KEY\s*=\s*[^\s]+'
          replacement: REDACTED_SECRET_ASSIGNMENT
        - name: bearer-token
          pattern: '(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}'
          replacement: 'Bearer REDACTED_TOKEN'
```

## トップレベルのキー

`read`:
MCP ツールが検索できるテナントのリストです。

`write`:
過去互換のキーです。現在の MCP サーバーは書き込み制御に使いません。
書き込み許可の設定として依存しないでください。

## 匿名化ポリシーのトップレベルキー

`sanitization`:
`mem0.sanitizer.yml` に必要なキーです。
匿名化ポリシーを設定しない場合、`/add` に送られた本文がそのまま保存されます。

## sanitization のキー

`sanitizer`:
チャンクのメタデータの `sanitizer` に記録する名前です。
`mem0-local-platform` のような安定した値にします。

`tenants`:
テナント名から匿名化モードへの対応表です。

`profiles`:
プロファイル名から置換ルールへの対応表です。

## テナントモード

`mode: required`:
mem0-local-platform API が `memory.add` を呼ぶ前に、このテナントの本文を必ず匿名化します。
書き込み経路は引き続き `/add` です。
クライアントが自分で「匿名化済み」と申告して迂回する設計にはしません。

`mode: disabled`:
このテナントでは mem0-local-platform API が匿名化しません。

`/add` リクエストに `metadata.tenant` がある場合は、`user_id` と一致している必要があります。
一致しない場合は拒否します。

## プロファイルルール

`allow_terms`:
このプロファイルで公開名または許可語として扱う名前です。
現在の実装では、同じ語が機密語にも入っている事故を拒否するために使います。
正規表現パターンから除外する機能ではありません。

`sensitive_terms`:
大文字小文字を区別せずに置換する固定語と別名です。

フィールド:

- `name`: デバッグ用メタデータに入れる任意のルール名
- `term`: 必須の固定語
- `replacement`: 必須の置換後文字列
- `aliases`: 任意の追加表記

短い固定語が長い別名を先に壊さないように、長い表記から置換します。

`sensitive_patterns`:
アクセスキーの代入や Bearer トークンなど、形で検出するシークレット用の正規表現です。

フィールド:

- `name`: デバッグ用メタデータに入れる必須のルール名
- `pattern`: 必須の Python 正規表現
- `replacement`: 必須の置換後文字列
- `flags`: 任意のリスト。対応値は `ignorecase` と `multiline` です。

不正な正規表現がある場合は拒否側に倒します。ポリシーを直すまで API は書き込みを拒否します。

## 匿名化メタデータ

`mode: required` のテナントでは、API が mem0 に書き込む前にメタデータを付けます。

```json
{
  "sanitized": true,
  "sanitizer": "mem0-local-platform",
  "sanitization_profile": "default",
  "sanitization_policy_hash": "8b2e...",
  "sanitization_policy_hash_algorithm": "sha256",
  "sanitization_matches": [
    {"kind": "pattern", "rule": "access-key-assignment", "count": 1}
  ]
}
```

`sanitization_policy_hash` は、ポリシーファイル内の有効な `sanitization`
セクションから計算します。
ポリシーファイルのパス、一致した値、本文は含めません。
現在の匿名化ポリシーを通っていないチャンクを見つけるために使います。

`sanitization_matches` はローカルデバッグ用です。
ルール名と件数だけを記録します。
一致した値、生の本文、匿名化後本文、周辺文脈は入れません。

## 既存データへの適用

`mode: required` は、新しく `/add` へ送られる本文に効きます。
すでに mem0 に入っている本文を自動で書き換えるわけではありません。

棚卸しでは、保存済みメタデータを現在のポリシーと比較します。

- `sanitized != true`: サーバ側匿名化を通っていない過去データ
- `sanitization_policy_hash` がない: ポリシー指紋の導入前に匿名化された過去データ
- `sanitization_policy_hash` が現在値と違う: 古い匿名化ポリシーで処理されたデータ

この確認には、読み取り専用の棚卸しエンドポイントを使えます。

```bash
curl "$MEM0_API_URL/v1/sanitization/audit?tenant=secret-knowledge&repo=example-repo"
```

返すのは `repo` と `path` でまとめたメタデータだけです。
本文、一致した値、匿名化後本文は返しません。

検索時にも確認します。
`/search` の結果に匿名化必須テナントのデータが含まれ、そのデータの
`sanitization_policy_hash` がない、または現在値と違う場合、API は検索結果を返さず
`409 stale_sanitization_policy` を返します。

Git、Markdown、ADR、Obsidian など原本が残っているデータは、原本から再登録します。
リポジトリ同期では `full` 再同期を実行します。
取り込み CLI は同じ `tenant + repo + path` の既存チャンクを削除してから
`/add` へ再登録するため、サーバ側の匿名化が適用された本文に置き換わります。

```bash
MEM0_SYNC_MODE=full mise run sync-local-repo
```

GitHub Actions で同期しているリポジトリでは、`workflow_dispatch` から
`sync_mode=full` を選びます。

Obsidian や Raycast などの手元メモは、原本ファイルから `remember-to-mem0` で
再登録します。既存の生データを確実に消す必要がある場合は、対象テナント、`repo`、
`path` で `/v1/memories/` の削除を実行してから再登録します。

mem0 内の検索結果だけを読んで匿名化し直す取得後匿名化は、原本がない過去データや
信頼経路が混在する場合の予備手段です。標準手順にはしません。

## 運用メモ

ポリシーファイルを変更したら、API または MCP プロセスを再起動します。

匿名化を有効にしていても、テナント境界は緩めません。
匿名化は漏えい時の影響を下げる補助策であり、アクセス制御、テナント分離、
シークレット管理、取り込み対象レビューの代わりにはなりません。
