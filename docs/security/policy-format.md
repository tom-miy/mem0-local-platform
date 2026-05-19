# mem0 Policy Format

Use two policy files by default:

- `mem0.policy.yml`: tenants MCP tools may read
- `mem0.sanitizer.yml`: tenants that require server-side sanitize-on-add before `/add` writes to mem0

Set `MEM0_TENANT_POLICY_FILE` for the MCP server and
`MEM0_SANITIZER_POLICY_FILE` for the mem0-local-platform API runtime.
For backward compatibility, the API still falls back to
`MEM0_TENANT_POLICY_FILE` when `MEM0_SANITIZER_POLICY_FILE` is omitted, but new
setups should keep the files separate.

## Minimal Policy

```yaml
read:
  - secret-knowledge
```

`read` is required for MCP tools. It lists the tenants that an MCP client may
search.

## Sanitizer Policy

Use `mem0.sanitizer.yml` when a tenant must be anonymized before mem0 stores it.

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

## Top-Level Keys

`read`:
List of tenants that MCP tools may search.

`write`:
Legacy compatibility key. The current MCP server does not use it for writes.
Do not rely on it for write authorization.

## Sanitizer Top-Level Keys

`sanitization`:
Required in `mem0.sanitizer.yml`. When no sanitizer policy is configured, `/add`
stores the text sent by the client.

## Sanitization Keys

`sanitizer`:
Name recorded in chunk metadata as `sanitizer`. Use a stable value such as
`mem0-local-platform`.

`tenants`:
Map from tenant name to sanitizer mode.

`profiles`:
Map from profile name to replacement rules.

## Tenant Modes

`mode: required`:
The mem0-local-platform API must sanitize content for this tenant before calling `memory.add`.
The request still goes through `/add`; the client cannot mark itself as already
trusted.

`mode: disabled`:
The mem0-local-platform API does not sanitize content for this tenant.

When `metadata.tenant` is present on an `/add` request, it must match `user_id`.
Mismatched tenants are rejected.

## Profile Rules

`allow_terms`:
Names that should be treated as public or allowed terms for this profile. The
current implementation uses this to reject accidental conflicts where the same
term is also listed as sensitive. It does not exempt text from regex patterns.

`sensitive_terms`:
Literal terms and aliases to replace case-insensitively.

Fields:

- `name`: optional rule name for debugging metadata
- `term`: required literal term
- `replacement`: required replacement text
- `aliases`: optional list of additional literal forms

Longer aliases are replaced before shorter terms so `client-acme` is not partly
changed by a shorter `client` rule first.

`sensitive_patterns`:
Regular expressions for shape-based secrets such as access key assignments or
bearer tokens.

Fields:

- `name`: required rule name for debugging metadata
- `pattern`: required Python regular expression
- `replacement`: required replacement text
- `flags`: optional list. Supported values are `ignorecase` and `multiline`.

Invalid regex patterns fail closed. The API rejects writes until the policy is
fixed.

## Sanitization Metadata

When a tenant uses `mode: required`, the API adds metadata before writing to
mem0:

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

`sanitization_policy_hash` is calculated from the effective `sanitization`
section of the policy file. It does not include the policy file path, raw
matched values, or source text. Use it to find chunks that were not processed by
the current sanitizer policy.

`sanitization_matches` is for local debugging. It records rule names and counts
only. It must not include matched values, original text, sanitized text, or
surrounding context.

## Applying Sanitization to Existing Data

`mode: required` applies to new content sent to `/add`. It does not rewrite text
that is already stored in mem0.

For inventory, compare stored metadata against the current policy:

- `sanitized != true`: legacy data that did not pass server-side sanitization
- missing `sanitization_policy_hash`: legacy sanitized data before policy
  fingerprinting was enabled
- `sanitization_policy_hash` differs from the current hash: data sanitized with
  an older sanitizer policy

The API exposes a read-only inventory endpoint for this check:

```bash
curl "$MEM0_API_URL/v1/sanitization/audit?tenant=secret-knowledge&repo=example-repo"
```

It returns only metadata grouped by `repo` and `path`. It does not return memory
text, matched values, or sanitized text.

Search is also guarded. When `/search` results include memories for a
sanitize-required tenant that are missing the current `sanitization_policy_hash`
or have a different hash, the API returns `409 stale_sanitization_policy`
instead of returning the search results.

For data that still has a source of truth in Git, Markdown, ADRs, or Obsidian,
re-register it from that source. For repository sync, run a `full` sync. The
ingestion CLI deletes existing chunks for the same `tenant + repo + path` before
posting to `/add`, so the server-side sanitizer replaces the stored text.

```bash
MEM0_SYNC_MODE=full mise run sync-local-repo
```

For repositories synced through GitHub Actions, run `workflow_dispatch` and
choose `sync_mode=full`.

For local notes from Obsidian or Raycast, re-register from the source file with
`remember-to-mem0`. If existing raw data must be removed first, delete by
tenant, `repo`, and `path` through `/v1/memories/`, then re-register.

Post-retrieval sanitization of existing mem0 results is a compatibility fallback
for legacy raw data or mixed trust routes. It is not the standard migration
path.

## Operational Notes

Restart the API or MCP process after changing the policy file.

Keep tenant boundaries strict even when sanitization is enabled. Anonymization
reduces leak impact, but it does not replace access control, tenant isolation,
secret handling, or review of what is ingested.
