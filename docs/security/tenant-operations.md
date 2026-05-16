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
mimr-tech
client-*
```

Examples:

```text
mimr-tech
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
  "tenant": "mimr-tech",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

`tenant` is the isolation boundary. `repo` and `path` are retrieval metadata.

## Read And Registration Policy

MCP only configures readable tenants:

```yaml
read:
  - mimr-tech
```

For client work:

```yaml
read:
  - mimr-tech
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
