# semantic-commit-planner

## Purpose

Create reviewable semantic commits from large diffs.

Optimize for:

- semantic cohesion
- reviewability
- isolated runtime concerns
- understandable git history

Do NOT optimize for minimum commit count.

---

# Core Rules

- Only commit staged changes.
- Never include unstaged files in commits.
- The user reviews staged diffs in VSCode Source Control.
- The assistant must propose the commit order and stage the first recommended commit unit.
- Leave later commit units unstaged until the human approves moving to the next commit.
- Commit only after explicit approval.

---

# Chunking Rules

Prioritize:

1. semantic cohesion
2. runtime isolation
3. reviewability
4. manageable diff size

Use file count and changed lines only as soft heuristics.

Soft limits:

```txt
soft_limit_files_per_commit = 7
hard_limit_files_per_commit = 12

soft_limit_changed_lines = 300
hard_limit_changed_lines = 700
```

---

# Hard Isolation Rules

Always isolate these into dedicated commit groups unless explicitly overridden:

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

Do not automatically group them with runtime business logic.

---

# Documentation Rules

Do NOT group all documentation changes into one commit automatically.

Prefer semantic documentation groups:

- ADR
- onboarding
- API docs
- architecture
- observability
- security
- deployment

---

# Conventional Commits

Use:

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

Prefer scoped commits when appropriate.

Example:

```txt
feat(auth): add refresh token rotation
```

---

# Commit Message Output

Always provide:

1. English Conventional Commit
2. Japanese translation

Example:

```txt
[a]
docs: update ADR and onboarding documentation

和訳:
docs: ADR とオンボーディングドキュメントを更新
```

Provide multiple candidates whenever possible.

---

# Workflow

1. Analyze changed files
2. Propose semantic commit chunks
3. Select the first recommended chunk unless the user instructs otherwise
4. Stage files for that first chunk
5. Wait for human review of the staged diff
6. Propose commit messages from staged contents only
7. Wait for approval
8. Execute commit
9. Repeat until working tree is clean

---

# Repository Rules

When requested by the user:

- re-read `.codex/AGENTS.md`
- apply repository-specific rules
- summarize active rules before continuing
