# Cloudflare Access

Cloudflare Tunnel is part of the default runtime. The Docker Compose stack runs
`cloudflared` and exposes internal services through Docker DNS instead of
requiring direct inbound ports.

Cloudflare Access should protect the exposed hostname. The default target is
agent and tool authentication with service tokens.

## Tunnel Routing

Create public hostnames in Cloudflare Tunnel:

```text
mem0-api.example.com -> http://mem0:8000
mem0-mcp.example.com -> http://mcp:8010
```

Those service names are Docker Compose service names. They are reachable from the
`cloudflared` container on the default Docker Compose network.

## Service Token Headers

Agents call the protected endpoint with:

```text
CF-Access-Client-Id: <client id>
CF-Access-Client-Secret: <client secret>
```

Store those values in the agent runtime or CI secret store. Do not commit them
to this repository.

The MCP and ingestion clients should call the Cloudflare-protected hostnames
from outside the Docker Compose network. Inside the Docker Compose network, services call
`http://mem0:8000`.

`CLOUDFLARE_TUNNEL_TOKEN` is only for the `cloudflared` service that maintains
the tunnel. Clients such as GitHub Actions do not use the tunnel token. They use
the Access service token headers above.

Add API-level protection as well by setting `MEM0_API_KEY` on the mem0 API
runtime. When set, the API requires `Authorization: Bearer <MEM0_API_KEY>`.
For production, do not rely on the Cloudflare Access service token alone.

## GitHub Actions Risk

Putting a Cloudflare Access service token in GitHub Actions lets any workflow
that can read that secret reach the Cloudflare-protected mem0 API. Cloudflare
Access is network access control; it is not fine-grained authorization for mem0
tenants, repositories, or paths.

The current API exposes `/add`, `/search`, `/v1/memories/`, and
`/v1/sanitization/audit` on the same API host. If an Actions service token
leaks, the holder may be able to reach search and inventory endpoints, not just
ingestion. Do not treat direct GitHub Actions access as the default for highly
sensitive customer data, private judgment patterns, or
external-sharing-restricted content.
If `MEM0_API_KEY` is enabled, the Cloudflare service token alone is not enough
to call the API. GitHub Actions still needs the API key as a secret, so GitHub
secret leakage remains part of the threat model.

Production guidance:

- Use GitHub Actions sync only for low-to-medium-risk repository knowledge.
- For sensitive tenants, use local clone sync, Tailscale-based sync, or a
  self-hosted runner inside the private network.
- Use separate service tokens per repository or per automation purpose.
- If using organization secrets, keep `--visibility selected` and limit the
  repository set.
- Do not expose mem0 connection secrets to public repositories or fork pull
  requests.
- Separate the Actions hostname from the MCP/search hostname in Cloudflare
  Access.
- Point the Actions hostname to a write-only ingestion gateway when available.

Safer target shape:

```text
mem0-ingest.example.com -> write-only ingestion gateway
mem0-mcp.example.com    -> MCP/search service
```

GitHub Actions should call only `mem0-ingest.example.com`. The Actions service
token should not be accepted by `mem0-mcp.example.com`. The current Docker Compose stack
does not yet include a write-only ingestion gateway. Until it exists, use local
sync or a self-hosted runner for sensitive data instead of direct Actions sync.

## Relationship With agent-privacy-guard

`agent-privacy-guard` is a separate GitHub repository for Claude Code, Cursor,
Copilot, and Codex prompt safety. It anonymizes prompts, routes MCP calls by
trust level, and applies hook-based controls before data leaves the local client
path. mem0-local-platform stores and retrieves memory.

Anonymization has two operating modes.

When server-side sanitization is disabled, or when previously ingested raw text
still exists, do not make pre-search query anonymization the default. If a
client replaces a customer, repository, API, or file name before MCP search, the
sanitized query may no longer match the already indexed text.

When server-side sanitization is enabled, the mem0-local-platform API is the
enforcement point. If `mem0.sanitizer.yml` marks a tenant as
`sanitization.tenants.<tenant>.mode: required`, `/add` replaces configured
sensitive terms, aliases, and regex patterns such as access-key assignments
before calling `memory.add`. The API, not the client, marks chunks with metadata
such as `sanitized=true`, `sanitizer`, `sanitization_profile`, and
`sanitization_policy_hash`. This applies to GitHub Actions, the Python
ingestion CLI, and local tools as long as they write through the
mem0-local-platform API. Raw source should remain in Git, Markdown, ADRs, or
Obsidian.
Use `sanitized != true`, a missing policy hash, or a hash that differs from the
current sanitizer policy to identify legacy or stale mem0 data.
To apply sanitization to existing mem0 data, enable server-side sanitization and
then run a `full` sync or re-register from the source of truth.
For local debugging, the API also records `sanitization_matches` metadata with
the rule name and match count. It does not include the raw matched value.

Anonymization does not make sensitive information safe by itself. It only
reduces impact if data leaks. It is not a replacement for access control,
tenant isolation, secret handling, or review of what is ingested. Even when
customer names or personal names are removed, architecture details, decision
patterns, operational procedures, vulnerability context, and non-shareable
know-how can still be sensitive. Treat that content as sensitive after
anonymization.

TODO: separately design how `agent-privacy-guard` receives the target data it
needs for anonymization, such as tenant-specific sensitive terms, aliases,
allowed public names, and replacement mappings. Post-retrieval sanitization
should stay a compatibility fallback for legacy raw memory or mixed trust
routes, not the default design.
Policy file format: [policy-format.md](policy-format.md)

## Human Login

Human OAuth login is optional. It can be enabled for debugging or manual
inspection, but the production target is non-interactive agent access.
