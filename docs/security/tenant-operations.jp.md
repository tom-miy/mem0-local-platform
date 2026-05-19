# テナント運用ルール

テナントは mem0-local-platform における読み取り境界です。
読み取りを許可する AI エージェントや開発者ごとに、
見せてよい知識の範囲を分けるために使います。

テナントはプロジェクトやリポジトリの分類名ではありません。
プロジェクト名やリポジトリ名はメタデータとして保存します。

## 基本ルール

- テナントは読み取り境界と登録先の分離境界を表します。
- プロジェクトや作業領域ごとの検索範囲は `repo`、`path`、`type`、`tags` のメタデータで絞ります。
- テナント名は人間が運用判断できる粒度にします。
- 顧客案件、NDA、社外共有禁止、開発者ごとの閲覧権限差がある場合はテナントを分けます。
- 同じ管理境界の知識で、読ませてよい範囲が同じならテナントを分けません。

## 推奨テナント

テナント名は、プロジェクト名やリポジトリ名ではなく読み取り境界を表す名前にします。
名前を見たときに「誰が読んでよい知識か」「どの管理主体の知識か」が分かるものを選びます。

使いやすいテナント名:

- 自分または自社の知識境界: `secret-knowledge`、`studio-knowledge`、`mimr-internal`
- チーム単位の境界: `team-platform`、`team-sales-tools`
- 顧客や案件単位の境界: `client-acme`、`client-upwork-18384728-acme`
- NDA や社外共有禁止の境界: `restricted-acme`、`nda-partner-x`

命名の基準:

- 読める人や AI エージェントの範囲が分かる
- 顧客、案件、チーム、管理主体の違いが分かる
- 将来プロジェクト名やリポジトリ名が変わっても意味が変わらない
- public/private、言語、フレームワーク、アプリ名だけで名前を決めない

基本形:

- `secret-knowledge`
- `client-*`

`secret-knowledge` は、顧客テナントへ分けない自分側の判断パターンや
社内ナレッジを置く境界名の例です。
秘密情報そのものを無条件に登録してよい、という意味ではありません。

## プロジェクト名やリポジトリ名をそのままテナントにしない

プロジェクト名、リポジトリ名、アプリ名、ツール名、技術領域名は、通常はテナントではなく
`repo`、`path`、`type`、`tags` のメタデータに入れます。

名前だけでは「誰が読んでよいか」を判断できないものは、テナント名にしません。
次の例は、プロジェクト名、リポジトリ名、アプリ名、ツール名、技術領域名です。
これらは読み取り境界ではなく、検索範囲や出所を表す名前です。

- `backend-testing-patterns`: リポジトリ名
- `portfolio-site`: プロジェクト名
- `frontend-app`: アプリ名
- `infra-scripts`: ツール群やスクリプト置き場
- `platform-api`: アプリ領域や API 領域
- `review-tools`: ツール名や用途名
- `terraform-modules`: 技術領域やモジュール群

プロジェクト名やリポジトリ名をそのままテナントにしない理由:

- 全体知識と個別プロジェクト知識を横断して検索しにくくなる
- プロジェクト名やリポジトリ名の変更、分割、統合がアクセス制御の変更になってしまう
- モノレポ内の `apps/api` や `tools/review` のような領域を表しにくい
- テナントが増え、読み取り設定やポリシーレビューが複雑になる

ただし、プロジェクトやリポジトリそのものが顧客案件、NDA、社外共有禁止、開発者ごとの
閲覧権限差の境界である場合は、専用テナントに登録して構いません。
判断基準は「プロジェクト単位か」ではなく「読ませてよい相手が違うか」です。

## メタデータ

プロジェクトやリポジトリはメタデータに入れます。

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
プロジェクト、リポジトリ、ファイルパスによる出所を絞ったり表示したりするための情報です。
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
ポリシーファイルの書式: [policy-format.jp.md](policy-format.jp.md)

## テナントを増やす基準

テナントを増やす基準は、プロジェクト数やリポジトリ数ではなく読み取り境界です。
次のどれかが変わる場合は、テナントを分けます。

- 読める相手が違う: 顧客、チーム、開発者、AI エージェントごとに閲覧範囲が違う
- 利用条件が違う: NDA、社外共有禁止、再利用禁止などの扱いが違う
- 漏えい時の影響が違う: 仕組み、判断パターン、運用手順、脆弱性の文脈が機密である

たとえば、開発者ごとに見てよいプロジェクトやリポジトリが違う場合や、
プロジェクトそのものが顧客案件の境界になっている場合は、テナントを分けます。
匿名化していても、仕組みや判断パターン自体が機密なら同じ扱いです。

この基準に当てはまらない分類は、テナントではなく `repo`、`path`、`type`、`tags`
で扱います。

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

```python
search_memory(
  query="FastAPI の例外設計レビュー観点",
  tenants=["secret-knowledge"],
  repo="backend-review-patterns",
  type="doc",
  tags=["backend"]
)
```

全体知識を横断して探す場合は、`repo` を指定しません。

```python
search_memory(
  query="E2E テストで flaky を疑う条件",
  tenants=["secret-knowledge"],
  tags=["testing"]
)
```

特定リポジトリの文脈だけを探す場合は、`repo` を指定します。

```python
related_repo_context(
  repo="backend-testing-patterns",
  query="trace.zip の保存方針",
  tenants=["secret-knowledge"]
)
```

特定ファイルだけを探す場合は、`path` を指定します。

```python
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

```python
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

顧客テナントへ登録する内容は、GitHub Actions の `tenant` 入力または
Python CLI の `--tenant` で指定します。
作業用テナントへ顧客情報を書かないためです。

開発者ごとに見てよいプロジェクトやリポジトリが違う場合は、その閲覧権限差をテナントで表します。

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

## テナント設定変更時の確認

`mem0.policy.yml`、GitHub Actions の `tenant` 入力、ローカル同期の `--tenant` を
変えるときに確認します。
目的は、読ませてはいけない知識を AI エージェントや開発者に見せないことと、
登録先テナントを間違えないことです。

- 新しいテナントは本当に読み取り境界か
- 読める開発者、チーム、AI エージェントが本当に違うか
- プロジェクト名やリポジトリ名だけをテナントにしていないか
- `mem0.policy.yml` の `read` に不要な顧客テナントや機密テナントが入っていないか
- GitHub Actions の `tenant` 入力が登録先として正しいか
- ローカル同期や Python CLI の `--tenant` が現在の作業対象と一致しているか
