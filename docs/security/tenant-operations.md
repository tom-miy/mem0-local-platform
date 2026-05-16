# Tenant Operations

Tenants are security boundaries in mem0-local-platform.

Tenants are not repository categories. Repository names are stored as metadata.

## Basic Rules

- Use tenants for readable boundaries and registration destinations.
- Do not create one tenant per repository.
- Use tenant names that match operational isolation decisions.
- Split tenants when customer data or contract boundaries differ.
- Do not split tenants when the same agent may read the same knowledge boundary.

## Recommended Tenants

```text
secret-knowledge
client-*
```

`secret-knowledge` is an example boundary for your own judgment patterns and
internal knowledge that do not need a customer-specific tenant. It does not mean
that arbitrary secrets should be indexed there.

Examples:

```text
secret-knowledge
client-upwork-18384728-acme
client-acme
```

## Avoid Repository Tenants

Avoid tenants such as:

```text
backend-testing-patterns
frontend-app
infra-scripts
```

Those names are repositories or topics, not security boundaries.

## Metadata

Store repository context as metadata:

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

`tenant` decides which knowledge boundary an agent may read. An agent allowed to
read only `secret-knowledge` cannot search `client-acme`.

`repo` and `path` are not access-control boundaries. They identify where a chunk
came from, such as `backend-testing-patterns` and `docs/e2e.md`, so search
results can be filtered or shown with source context.

## Read And Registration Policy

MCP only configures readable tenants:

```yaml
read:
  - secret-knowledge
```

For client work:

```yaml
read:
  - secret-knowledge
  - client-18384728-acme
```

Multiple readable tenants are allowed. Register new memory through GitHub
Actions or the Python CLI, and set the destination tenant there.

## Review Checklist

When changing tenant settings, check:

- Is the tenant really a security boundary?
- Is a repository or project name being used as a tenant?
- Does the registration `tenant` match the current work target?
- Are unnecessary client tenants included in the read list?
- Does the GitHub Actions `tenant` input match the intended destination?
