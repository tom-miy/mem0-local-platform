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

## Relationship With agent-privacy-guard

`agent-privacy-guard` is a separate GitHub repository for Claude Code, Cursor,
Copilot, and Codex prompt safety. It anonymizes prompts, routes MCP calls by
trust level, and applies hook-based controls before data leaves the local client
path. For mem0-local-platform, the recommended direction is not pre-search query
anonymization. The safer integration point is anonymizing content before it is
written into mem0.

Current limitation: pre-search anonymization can make mem0 search worse when
mem0 contains raw indexed text. For example, if `agent-privacy-guard` replaces a
customer, repository, API, or file name before an MCP search call, the sanitized
query may no longer match the raw text stored by the repository ingester.

TODO: design sanitize-on-ingest as the primary integration point. The ingestion
path should optionally call `agent-privacy-guard` before `memory.add`, store only
sanitized chunk text in mem0, and mark chunks with metadata such as
`sanitized=true`, `sanitizer=agent-privacy-guard`, and `sanitization_profile`.
Raw source should remain in Git, Markdown, ADRs, or Obsidian. Post-retrieval
sanitization should stay a compatibility fallback for legacy raw memory or mixed
trust routes, not the default design.

That control does not normally apply to GitHub Actions sync jobs. Actions run
directly on GitHub runners and do not pass through local hooks or a local gateway.
Protect Actions sync with Cloudflare Access service tokens, GitHub secrets,
ingestion path rules, and tenant inputs.

## Human Login

Human OAuth login is optional. It can be enabled for debugging or manual
inspection, but the production target is non-interactive agent access.
