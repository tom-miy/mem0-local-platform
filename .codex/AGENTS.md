# AGENTS.md

## Repository Philosophy

This repository prioritizes:

- reviewability
- semantic commits
- small meaningful diffs
- human-reviewed staging
- AI-assisted workflows
- explicit architecture documentation

Do not optimize for maximum automation.

---

## Commit Workflow

Use the semantic-commit-planner skill before creating commits.

Requirements:

- commits should represent a single semantic concern
- avoid mixing docs, runtime logic, and CI changes
- generated files should usually be isolated
- prefer smaller reviewable commits

---

## Staging Rules

Assume staged changes were reviewed by a human in VSCode Source Control.

Never commit unstaged changes.

Always generate commit messages from staged contents only.

When `/smart-commit` is requested, the assistant is responsible for:

- analyzing all current changes
- proposing the semantic commit order
- staging only the first recommended commit unit
- leaving unrelated or later commit units unstaged
- waiting for the human to judge whether the staged diff is appropriate

Do not require the human to choose and stage the first commit unit manually.

---

## Conventional Commits

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

```txt id="jlwm6ag"
feat(auth): add refresh token rotation
```

When presenting commit message candidates, put each exact commit message in a
plain fenced text block so it can be copied directly. After each text block,
add a separate Japanese translation or explanation of that commit message.

---

## Documentation Rules

Do not group all documentation changes into a single commit automatically.

Prefer semantic documentation boundaries:

- ADR
- onboarding
- architecture
- API docs
- observability
- security

---

## Reviewability Rules

Optimize for:

- semantic isolation
- understandable history
- reviewable PRs
- maintainable git history

Do not optimize for minimum commit count.

---

## Generated Files

Prefer separate commits for:

- *.gen.go
- mocks/*
- dist/*
- coverage/*
- openapi generated code

---

## Important

The human operator is responsible for reviewing staged diffs before commit execution.

## Edge Social Relay Rules

Prefer separating commits by provider and infrastructure concern.

Examples:

- Cloudflare Worker runtime
- GitHub Actions
- provider integrations
- generated types
- deployment configuration
- documentation

Avoid mixing:
- runtime logic
- deployment config
- CI
- generated files

---

## Cloudflare Rules

Prefer isolated commits for:

- wrangler.toml
- wrangler.jsonc
- bindings
- secrets configuration
- routes
- worker compatibility flags

---

## Provider Rules

Prefer provider-specific commits:

- x/twitter
- raindrop
- rss
- webhook
- parser
- scheduler

Avoid cross-provider commits unless changes are strongly related.

## Slash Command Aliases

The following slash commands should invoke `.codex/skills/semantic-commit-planner/SKILL.md`:

- /smart-commit
