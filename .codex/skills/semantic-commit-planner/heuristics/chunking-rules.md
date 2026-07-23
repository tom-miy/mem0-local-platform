# Cloudflare Config Isolation

The following files should usually be isolated into dedicated commits:

- wrangler.toml
- wrangler.jsonc
- .dev.vars
- worker-configuration.d.ts

Reasons:

- deployment risk
- infrastructure reviewability
- rollback safety
- operational auditability

These files should not usually be grouped with:

- provider runtime changes
- parser logic
- webhook handlers
- generated files