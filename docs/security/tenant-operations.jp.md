# テナント運用ルール

テナントは mem0-local-platform における読み取り境界です。
「この AI エージェントや開発者に読ませてよい知識の集合」を分けるために使います。

テナントはリポジトリの分類名ではありません。
リポジトリ名はメタデータとして保存します。

## 基本ルール

- テナントは読み取り境界と登録先の分離境界を表します。
- リポジトリごとの検索範囲は `repo` メタデータで絞ります。
- テナント名は人間が運用判断できる粒度にします。
- 顧客案件、NDA、社外共有禁止、開発者ごとの閲覧権限差がある場合はテナントを分けます。
- 同じ管理境界の知識で、読ませてよい範囲が同じならテナントを分けません。

## 推奨テナント

```text
secret-knowledge
client-*
```

`secret-knowledge` は、顧客テナントへ分けない自分側の判断パターンや
社内ナレッジを置く境界名の例です。
秘密情報そのものを無条件に登録してよい、という意味ではありません。

例:

```text
secret-knowledge
client-upwork-18384728-acme
client-acme
```

## 避けるテナント

リポジトリごとのテナント:

```text
backend-testing-patterns
frontend-app
infra-scripts
```

これは標準にはしません。

理由:

- 全体知識と個別リポジトリ知識を横断して検索しにくくなる
- 読み取りと登録先の方針が複雑になる
- リポジトリ名変更、分割、統合がアクセス制御の変更になってしまう
- モノレポ内の `apps/api`、`tools/review`、`docs/adr` のような領域を表しにくい

例外として、リポジトリそのものが顧客案件、NDA、社外共有禁止、開発者ごとの
閲覧権限差の境界である場合は、
専用テナントに登録して構いません。
判断基準は「リポジトリ単位か」ではなく「読ませてよい相手が違うか」です。

## メタデータ

リポジトリはメタデータに入れます。

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

`tenant` は、AI エージェントが読んでよい知識の範囲を決めます。
`secret-knowledge` だけを許可したエージェントは、`client-acme` の知識を検索できません。

`repo` と `path` はアクセス制御ではありません。
「backend-testing-patterns の docs/e2e.md から来た文脈」のように、
検索結果の出所を絞ったり表示したりするための情報です。
モノレポ内のアプリ、ツール、ドキュメント領域を分けたい場合も、
`path`、`type`、`tags` を使います。

## 読み取りと登録の方針

MCP サーバーでは、読み取り可能テナントだけを設定します。

```yaml
read:
  - secret-knowledge
```

読み取り可能テナントは検索できる範囲です。
登録は GitHub Actions または Python CLI から行います。
これにより、エージェントの一時的な推測を MCP 経由で永続化する事故を避けます。

## テナントを増やす基準

テナントを増やしてよい場合:

- 顧客が違う
- NDA、社外共有禁止、再利用禁止などの条件が違う
- 社内ナレッジやチーム共通の知識と顧客情報を分けたい
- エージェントや開発者に読ませてよい範囲が明確に違う
- 開発者ごとに見てよいリポジトリが違う
- リポジトリそのものが顧客案件、NDA、社外共有禁止、閲覧権限差の境界になっている

テナントを増やさない場合:

- リポジトリが違うだけ
- モノレポ内のアプリやツールが違うだけ
- ドキュメントの種類が違うだけ
- 言語やフレームワークが違うだけ
- 同じ人や同じエージェントが読んでよい作業領域で使うだけ

## 運用例

社内ナレッジやチーム共通の知識だけを扱う作業では、読み取りテナントを
`secret-knowledge` にします。

```yaml
read:
  - secret-knowledge
```

この中に、公開可能な skill、非公開の判断パターン、DevEx テンプレート、
調査ツール、営業や案件獲得メモを登録できます。
検索時は `repo`、`path`、`type`、`tags` で範囲を絞ります。

```text
search_memory(
  query="FastAPI の例外設計レビュー観点",
  tenants=["secret-knowledge"],
  repo="backend-review-patterns",
  type="doc",
  tags=["backend"]
)
```

全体知識を横断して探す場合は、`repo` を指定しません。

```text
search_memory(
  query="E2E テストで flaky を疑う条件",
  tenants=["secret-knowledge"],
  tags=["testing"]
)
```

特定リポジトリの文脈だけを探す場合は、`repo` を指定します。

```text
related_repo_context(
  repo="backend-testing-patterns",
  query="trace.zip の保存方針",
  tenants=["secret-knowledge"]
)
```

特定ファイルだけを探す場合は、`path` を指定します。

```text
search_memory(
  query="リトライしてよい条件",
  tenants=["secret-knowledge"],
  repo="backend-testing-patterns",
  path="docs/retry-policy.md"
)
```

モノレポでは、アプリやツールごとにテナントを分けません。
登録時にタグを付け、検索時に `repo`、`type`、`tags`、検索語を組み合わせます。

```bash
python scripts/ingest_repo.py \
  --root /path/to/platform-monorepo \
  --tenant secret-knowledge \
  --repo platform-monorepo \
  --tag api \
  --tag auth \
  --changed-files apps/api/internal/auth/session.go
```

```text
search_memory(
  query="session refresh の失敗時の扱い",
  tenants=["secret-knowledge"],
  repo="platform-monorepo",
  type="code",
  tags=["api", "auth"]
)
```

顧客作業では、読み取りテナントに自分側の知識と顧客テナントを入れます。

```yaml
read:
  - secret-knowledge
  - client-18384728-acme
```

顧客テナントへ登録する内容は、GitHub Actions の `tenant` input または
Python CLI の `--tenant` で指定します。
作業用テナントへ顧客情報を書かないためです。

開発者ごとに見てよいリポジトリが違う場合は、その閲覧権限差をテナントで表します。

```yaml
read:
  - secret-knowledge
  - team-platform
```

```yaml
read:
  - secret-knowledge
  - team-sales-tools
```

この場合、`team-platform` と `team-sales-tools` はリポジトリ名ではなく、
読める人やエージェントが違う知識集合の名前です。
同じテナントの中では、引き続き `repo`、`path`、`type`、`tags` で検索範囲を絞ります。

## レビュー観点

テナント設定を変えるときは次を確認します。

- そのテナントは本当にセキュリティ境界か
- 読める開発者やエージェントが本当に違うか
- リポジトリ名やプロジェクト名をテナントにしていないか
- 登録時の `tenant` が現在の作業対象と一致しているか
- 読み取り可能テナントに不要な顧客テナントが入っていないか
- GitHub Actions の `tenant` input が正しいか
