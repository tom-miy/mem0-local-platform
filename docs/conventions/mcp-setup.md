# MCP Setup

This guide shows how Codex, Claude, and other MCP clients connect to
mem0-local-platform.

The repository provides an MCP server. The installer does not rewrite existing
agent configuration files. It prints snippets that you review and merge into the
client configuration you use.

Keep secrets out of MCP client config when possible. Put local client settings
in `mem0.env`, and do not commit that file.

## Tools

- `search_memory`
- `related_repo_context`
- `recent_project_memories`

MCP is read-only. Search tools only read configured readable tenants. Register
new memory through GitHub Actions, `remember-to-mem0`, or Obsidian / Raycast
wrappers around the Python CLI.

## Connection Modes

There are two common modes:

- The client starts the MCP server locally over `stdio`.
- The client connects to the MCP service through Cloudflare Tunnel.

For Codex, use `scripts/run_mcp.sh`. The script loads `mem0.env` before starting
`uv run mem0-local-mcp`.

## Local Setup

Create local config files:

```bash
cp mem0.env.example mem0.env
cp mem0.policy.example.yml mem0.policy.yml
```

Set the mem0 API URL and Cloudflare Access service token values in `mem0.env`:

```text
MEM0_API_URL=https://mem0-api.example.com
MEM0_TENANT_POLICY_FILE=mem0.policy.yml
CLOUDFLARE_ACCESS_CLIENT_ID=...
CLOUDFLARE_ACCESS_CLIENT_SECRET=...
```

Set readable tenants in `mem0.policy.yml`:

```yaml
read:
  - secret-knowledge
```

Print a generic stdio MCP snippet:

```bash
./install.sh --target generic --transport stdio
```

Print a Codex snippet:

```bash
./install.sh --target codex
```

Codex example:

```toml
[mcp_servers.mem0-local-platform]
command = "/path/to/mem0-local-platform/scripts/run_mcp.sh"
args = []
```

If `mem0.env` lives somewhere else, pass `MEM0_ENV_FILE` from the Codex MCP
server environment.

## Cloudflare Tunnel Setup

Expose the MCP service through Cloudflare Tunnel:

```text
mem0-mcp.example.com -> http://mcp:8010
```

Print an SSE or HTTP remote MCP snippet:

```bash
./install.sh --target generic --transport sse
```

`CLOUDFLARE_TUNNEL_TOKEN` is not a client token. It belongs only to the
`cloudflared` service that keeps the tunnel open.

## Tailscale Setup

For private access from your own devices to a home server, point `MEM0_API_URL`
at the Tailscale device name:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
```

If you want to reach the MCP service over the tailnet, configure Tailscale Serve
on the server:

```bash
tailscale serve --bg --https=9443 localhost:8010
```

See [Tailscale Access](../security/tailscale-access.md).

## Verification

Install dependencies:

```bash
mise trust .
mise install
mise run setup
```

Start the local MCP server:

```bash
MEM0_API_URL=https://mem0-api.example.com \
MEM0_TENANT_POLICY_FILE=mem0.policy.yml \
CLOUDFLARE_ACCESS_CLIENT_ID=... \
CLOUDFLARE_ACCESS_CLIENT_SECRET=... \
uv run mem0-local-mcp
```

After registering the server in the client, verify that `search_memory` can
search the expected tenant.
