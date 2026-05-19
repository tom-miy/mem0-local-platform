# Tailscale Access

Use Tailscale as a private path from your own devices to mem0-local-platform on a
home server.

Cloudflare Tunnel is still the default path for GitHub Actions and external
automation agents that need a public hostname protected by Cloudflare Access.
Tailscale is for management, verification, and local ingestion from devices in
your Tailscale account or organization network.
For sensitive repositories where you do not want a mem0 service token in GitHub
Actions, use Tailscale-based local sync or a self-hosted runner inside the
private network.

## When To Use It

- Normal GitHub Actions sync: Cloudflare Tunnel + Cloudflare Access
- Sensitive repository sync: Tailscale-based local sync or private-network self-hosted runner
- External automation agents: Cloudflare Tunnel + Cloudflare Access
- Your devices reaching a home server: Tailscale
- Compose-internal service calls: Docker DNS

## Compose Startup

Layer the Tailscale override on top of the normal Docker Compose file:

```bash
mise run up-tailscale
```

For a home server, start it in the background:

```bash
mise run start-tailscale
```

Enable Tailscale and memory limits together:

```bash
mise run up-tailscale-resources
```

Start in the background with Tailscale and memory limits:

```bash
mise run start-tailscale-resources
```

`compose.tailscale.yml` publishes `mem0` and `mcp` only on host localhost. It
does not open those ports to the whole LAN.

```text
127.0.0.1:8000 -> mem0:8000
127.0.0.1:8010 -> mcp:8010
```

The normal `mise run up` task uses only `compose.yml`. The localhost binds for
Tailscale are enabled only by `mise run up-tailscale`.

## Tailscale Serve

On the home server, configure Tailscale Serve:
Tailscale Serve can expose the service over HTTPS inside your Tailscale network. Tailscale
terminates HTTPS; the Docker Compose-side `mem0` and `mcp` services can stay on
localhost HTTP.

The default example separates services by port. This is the safer starting
point because API and MCP clients may assume they are mounted at the root path.

```bash
tailscale serve --bg --https=8443 localhost:8000
tailscale serve --bg --https=9443 localhost:8010
```

From devices in your Tailscale network, connect through the MagicDNS name over HTTPS:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
MCP URL=https://home-server.tailnet-name.ts.net:9443
```

Replace `home-server.tailnet-name.ts.net` with the actual Tailscale MagicDNS
name.

Tailscale Serve HTTPS requires enabling HTTPS certificates in the Tailscale
admin console for your account or organization network. If they are not enabled,
`tailscale serve` prints a URL that guides you through enabling them.
You normally do not need to run `tailscale cert` and mount certificate files
into Docker Compose for this setup. The Tailscale daemon terminates HTTPS and proxies
to the localhost HTTP service.

Serve configuration with `--bg` is saved as a background Serve configuration.
It remains after the terminal exits and resumes after the Tailscale daemon
restarts.
Keep the Docker containers resident with `mise run start-tailscale` or
`mise run start-tailscale-resources`.

## Path-Based Routing

Tailscale Serve can also route by path with `--set-path`, such as `/mem0` and
`/mem0-mcp`. This can be useful when you later add services like n8n and want one
HTTPS port.

Example:

```bash
tailscale serve --bg --https=443 --set-path=/mem0 localhost:8000
tailscale serve --bg --https=443 --set-path=/mem0-mcp localhost:8010
tailscale serve --bg --https=443 --set-path=/n8n localhost:5678
```

Client URLs:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net/mem0
MCP URL=https://home-server.tailnet-name.ts.net/mem0-mcp
n8n URL=https://home-server.tailnet-name.ts.net/n8n
```

Whether this works cleanly depends on the application and client. Redirects,
WebSockets, callback URLs, and static asset paths often need explicit base URL
or path prefix settings.

For that reason, this repository defaults to port separation with `8443` and
`9443`. When adding a web UI such as n8n, first check whether the app supports a
subpath. If not, use another port such as `10443`.

Inspect the current configuration:

```bash
tailscale serve status
tailscale serve status --json
```

Remove the Serve configuration:

```bash
tailscale serve reset
```

## Why There Is No Tailscale Container

This setup does not add a Tailscale container by default. Install Tailscale on
the home server and use host-level `tailscale serve` to forward to Docker Compose
services published on `127.0.0.1`.

Reasons:

- the home server stays one normal device in your Tailscale network
- Tailscale auth state and device identity are not hidden inside Docker state
- `compose.tailscale.yml` avoids opening ports directly to the LAN
- HTTPS termination stays in Tailscale Serve

A containerized Tailscale setup is possible, but it adds auth key, state
directory, Serve config, and network permission management. The default here is
the host Tailscale daemon.

## Client Config

For Python CLI or MCP clients on your own devices, `mem0.env` can point at the
Tailscale URL:

```text
MEM0_API_URL=https://home-server.tailnet-name.ts.net:8443
MEM0_TENANT_POLICY_FILE=mem0.policy.yml
```

Cloudflare Access service tokens are not needed on the Tailscale path. GitHub
hosted runners normally use the Cloudflare Access path, not Tailscale. If you do
not want a mem0 service token stored in GitHub Actions, do not use direct
GitHub-hosted runner sync; use local sync or a self-hosted runner instead.

## Notes

- Tailscale is for private access inside your Tailscale network.
- Do not use Tailscale Funnel for this default setup.
- Keep `compose.tailscale.yml` limited to localhost binds.
- Terminate HTTPS with Tailscale Serve.
- Use Tailscale ACLs to restrict which users and devices can reach mem0.
- If you configure an external LLM or embedding provider, retrieved or
  registered text may still be sent to that provider.
