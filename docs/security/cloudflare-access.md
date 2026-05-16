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

## Human Login

Human OAuth login is optional. It can be enabled for debugging or manual
inspection, but the production target is non-interactive agent access.
