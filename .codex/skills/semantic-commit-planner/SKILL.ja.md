# semantic-commit-planner 日本語版

このファイルは [SKILL.md](SKILL.md) の日本語参照版です。
Codex の skill として使う正本は [SKILL.md](SKILL.md) です。

## 目的

大きな差分から、review しやすい semantic commit を作ります。

優先すること:

- semantic cohesion
- reviewability
- runtime concern の分離
- 理解しやすい git history

commit 数の最小化は優先しません。

---

# Core rules

- staged changes だけを commit する。
- unstaged files を commit に含めない。
- staged diff は人間が VSCode Source Control で review する。
- assistant が commit 順序を提案し、最初に commit すべき 1 単位を stage する。
- 後続 commit 用の変更は、人間が次に進むことを承認するまで unstaged のまま残す。
- commit は明示的な承認後にだけ実行する。

---

# Chunking rules

優先順位:

1. semantic cohesion
2. runtime isolation
3. reviewability
4. 管理しやすい diff size

file count と changed lines は soft heuristic として扱います。

soft limits:

```txt
soft_limit_files_per_commit = 7
hard_limit_files_per_commit = 12

soft_limit_changed_lines = 300
hard_limit_changed_lines = 700
```

---

# Hard isolation rules

明示的に上書きされない限り、次は専用の commit group に分けます。

```txt
wrangler.toml
wrangler.jsonc
.github/workflows/*
generated/*
openapi/*
*.gen.go
dist/*
coverage/*
```

これらを runtime business logic と自動でまとめません。

---

# Documentation rules

すべての documentation changes を自動で 1 commit にまとめません。

次のような semantic documentation group を優先します。

- ADR
- onboarding
- API docs
- architecture
- observability
- security
- deployment

---

# Conventional Commits

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

---

# Commit message output

常に次を提示します。

1. English Conventional Commit
2. Japanese translation

例:

```txt
[a]
docs: update ADR and onboarding documentation

和訳:
docs: ADR とオンボーディングドキュメントを更新
```

可能な場合は複数候補を提示します。

---

# Workflow

1. changed files を分析する
2. semantic commit chunks を提案する
3. ユーザーから別指示がない限り、最初に commit すべき chunk を選ぶ
4. その最初の chunk の files を stage する
5. staged diff に対する人間の review を待つ
6. staged contents のみから commit message を提案する
7. 承認を待つ
8. commit を実行する
9. working tree が clean になるまで繰り返す

---

# Repository rules

ユーザーに求められた場合:

- `.codex/AGENTS.md` を読み直す
- repository-specific rules を適用する
- 継続前に有効な rules を要約する
