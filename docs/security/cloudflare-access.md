# Cloudflare Access

Cloudflare Tunnel is part of the default runtime. The compose stack runs
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

Those service names are compose service names. They are reachable from the
`cloudflared` container on the default compose network.

## Service Token Headers

Agents call the protected endpoint with:

```text
CF-Access-Client-Id: <client id>
CF-Access-Client-Secret: <client secret>
```

Store those values in the agent runtime or CI secret store. Do not commit them
to this repository.

The MCP and ingestion clients should call the Cloudflare-protected hostnames
from outside the compose network. Inside the compose network, services call
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

The current API exposes `/add`, `/search`, and `/v1/memories/` on the same API
host. If an Actions service token leaks, the holder may be able to reach search
endpoints, not just ingestion. Do not treat direct GitHub Actions access as the
default for highly sensitive customer data, private judgment patterns, or
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
token should not be accepted by `mem0-mcp.example.com`. The current compose stack
does not yet include a write-only ingestion gateway. Until it exists, use local
sync or a self-hosted runner for sensitive data instead of direct Actions sync.

## Relationship With agent-privacy-guard

`agent-privacy-guard` is a separate GitHub repository for Claude Code, Cursor,
Copilot, and Codex prompt safety. It anonymizes prompts, routes MCP calls by
trust level, and applies hook-based controls before data leaves the local client
path. For mem0-local-platform, the recommended direction is not pre-search query
anonymization. The intended integration point is anonymizing content before it is
written into mem0.

Anonymization does not make sensitive information safe by itself. It only reduces
impact if data leaks. It is not a replacement for access control, tenant
isolation, secret handling, or review of what is ingested. Even when customer
names or personal names are removed, architecture details, decision patterns,
operational procedures, vulnerability context, and non-shareable know-how can
still be sensitive. Treat that content as sensitive after anonymization.

Current limitation: pre-search anonymization can make mem0 search worse when
mem0 contains raw indexed text. For example, if `agent-privacy-guard` replaces a
customer, repository, API, or file name before an MCP search call, the sanitized
query may no longer match the raw text stored by the repository ingester.

TODO: design sanitize-on-ingest as the primary integration point. The ingestion
path should optionally call `agent-privacy-guard` before `memory.add`, store only
sanitized chunk text in mem0, and mark chunks with metadata such as
`sanitized=true`, `sanitizer=agent-privacy-guard`, and `sanitization_profile`.
Raw source should remain in Git, Markdown, ADRs, or Obsidian. Sanitized mem0
content must not be treated as low-risk by default. Post-retrieval sanitization
should stay a compatibility fallback for legacy raw memory or mixed trust routes,
not the default design.

That control does not normally apply to GitHub Actions sync jobs. Actions run
directly on GitHub runners and do not pass through local hooks or a local gateway.
Protect Actions sync with Cloudflare Access service tokens, GitHub secrets,
ingestion path rules, and tenant inputs.

## Human Login

Human OAuth login is optional. It can be enabled for debugging or manual
inspection, but the production target is non-interactive agent access.
