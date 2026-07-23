# AGENTS.md 日本語版

このファイルは [.codex/AGENTS.md](AGENTS.md) の日本語参照版です。
Codex の実行時ルールとして使う正本は [.codex/AGENTS.md](AGENTS.md) です。

## リポジトリ方針

このリポジトリでは次を優先します。

- reviewability
- semantic commit
- 小さく意味のある差分
- 人間による staging review
- AI-assisted workflow
- 明示的な architecture documentation

最大限の自動化を優先しません。

---

## Commit workflow

commit を作る前に `semantic-commit-planner` skill を使います。

要件:

- commit は単一の意味的関心ごとを表す
- docs、runtime logic、CI を不用意に混ぜない
- 生成物は通常、別 commit に分ける
- 小さく review しやすい commit を優先する

---

## Staging rules

staged changes は、人間が VSCode Source Control で review 済みとみなします。

unstaged changes は commit しません。

commit message は staged contents のみから作ります。

`/smart-commit` が要求された場合、assistant は次を行います。

- 現在の変更全体を分析する
- semantic commit の順序を提案する
- 最初に commit すべき 1 単位だけを stage する
- 後続 commit 用の変更や無関係な変更は unstaged のまま残す
- staged diff が妥当かどうかの判断を人間に待つ

最初の commit 単位の選択と staging を人間に任せません。

---

## Conventional Commits

使用する type:

- feat
- fix
- docs
- refactor
- test
- ci
- chore
- perf
- build
- security

必要に応じて scope を付けます。

例:

```txt
feat(auth): add refresh token rotation
```

commit message 候補を提示するときは、コピーしやすいように exact message を plain fenced text block に入れます。
その後に、日本語訳または説明を付けます。

---

## Documentation rules

すべての docs 変更を自動で 1 commit にまとめません。

次のような意味単位で分けることを優先します。

- ADR
- onboarding
- architecture
- API docs
- observability
- security

---

## Reviewability rules

次を優先します。

- semantic isolation
- 理解しやすい履歴
- review しやすい PR
- 保守しやすい git history

commit 数の最小化は優先しません。

---

## 生成物

次は別 commit に分けることを優先します。

- `*.gen.go`
- `mocks/*`
- `dist/*`
- `coverage/*`
- OpenAPI generated code

---

## 重要事項

staged diff を review してから commit 実行を判断する責任は人間の operator にあります。

## Edge Social Relay rules

provider と infrastructure の関心ごとで commit を分けます。

例:

- Cloudflare Worker runtime
- GitHub Actions
- provider integrations
- generated types
- deployment configuration
- documentation

次を混ぜないようにします。

- runtime logic
- deployment config
- CI
- generated files

---

## Cloudflare rules

次は独立した commit にすることを優先します。

- `wrangler.toml`
- `wrangler.jsonc`
- bindings
- secrets configuration
- routes
- worker compatibility flags

---

## Provider rules

provider ごとに commit を分けます。

- x/twitter
- raindrop
- rss
- webhook
- parser
- scheduler

強く関連している場合を除き、provider をまたぐ commit は避けます。

## Slash command aliases

次の slash command は [.codex/skills/semantic-commit-planner/SKILL.md](skills/semantic-commit-planner/SKILL.md) を呼びます。

- `/smart-commit`
