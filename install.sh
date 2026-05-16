#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh [--target generic|codex|claude-desktop|raycast] [--transport stdio|sse|http]

Print setup snippets for mem0-local-platform.

This script does not edit your agent configuration files.
It prints the exact configuration to review and paste.

Examples:
  ./install.sh --target generic --transport stdio
  ./install.sh --target codex
  ./install.sh --target claude-desktop --transport stdio
  ./install.sh --target generic --transport sse
  ./install.sh --target raycast
USAGE
}

target="generic"
transport="stdio"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      target="${2:-}"
      shift 2
      ;;
    --transport)
      transport="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$target" in
  generic|codex|claude-desktop|raycast) ;;
  *)
    echo "target must be generic, codex, claude-desktop, or raycast: $target" >&2
    exit 2
    ;;
esac

case "$transport" in
  stdio|sse|http) ;;
  *)
    echo "transport must be stdio, sse, or http: $transport" >&2
    exit 2
    ;;
esac

repo_root="$(cd "$(dirname "$0")" && pwd)"

print_stdio_json() {
  cat <<JSON
{
  "mcpServers": {
    "mem0-local-platform": {
      "command": "uv",
      "args": ["run", "mem0-local-mcp"],
      "cwd": "$repo_root",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "MEM0_API_URL": "\${MEM0_API_URL}",
        "MEM0_TENANT_POLICY_FILE": "\${MEM0_TENANT_POLICY_FILE}",
        "CLOUDFLARE_ACCESS_CLIENT_ID": "\${CLOUDFLARE_ACCESS_CLIENT_ID}",
        "CLOUDFLARE_ACCESS_CLIENT_SECRET": "\${CLOUDFLARE_ACCESS_CLIENT_SECRET}"
      }
    }
  }
}
JSON
}

print_codex_toml() {
  cat <<TOML
[mcp_servers.mem0-local-platform]
command = "$repo_root/scripts/run_mcp.sh"
args = []
TOML
}

print_remote_json() {
  local url_var
  if [ "$transport" = "http" ]; then
    url_var="\${CLOUDFLARE_MCP_HOSTNAME}"
  else
    url_var="\${CLOUDFLARE_MCP_HOSTNAME}/sse"
  fi

  cat <<JSON
{
  "mcpServers": {
    "mem0-local-platform": {
      "url": "$url_var",
      "headers": {
        "CF-Access-Client-Id": "\${CLOUDFLARE_ACCESS_CLIENT_ID}",
        "CF-Access-Client-Secret": "\${CLOUDFLARE_ACCESS_CLIENT_SECRET}"
      }
    }
  }
}
JSON
}

print_raycast() {
  cat <<'SCRIPT'
#!/usr/bin/env bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Remember Clipboard to mem0
# @raycast.mode compact
#
# Optional parameters:
# @raycast.icon memory-stick
# @raycast.packageName mem0-local-platform
#
# Documentation:
# @raycast.description クリップボードの内容を Cloudflare Access 経由で mem0 に送ります。

set -euo pipefail

cd "$HOME/ghq/personal/github.com/tom-miy/mem0-local-platform"

pbpaste | \
  MEM0_API_URL="${MEM0_API_URL}" \
  CLOUDFLARE_ACCESS_CLIENT_ID="${CLOUDFLARE_ACCESS_CLIENT_ID}" \
  CLOUDFLARE_ACCESS_CLIENT_SECRET="${CLOUDFLARE_ACCESS_CLIENT_SECRET}" \
  uv run remember-to-mem0 \
    --tenant mimr-tech \
    --source raycast \
    --type note \
    --tag clipboard
SCRIPT
}

if [ "$target" = "raycast" ]; then
  print_raycast
  exit 0
fi

if [ "$target" = "codex" ]; then
  cat <<EOF
# Codex MCP setup
#
# 1. Copy local examples and fill in Cloudflare Access values:
#    cp mem0.env.example mem0.env
#    cp mem0.policy.example.yml mem0.policy.yml
#
# 2. Add this snippet to your Codex config.
#    Review existing MCP server entries first and merge by key.
#
EOF
  print_codex_toml
  exit 0
fi

cat <<EOF
# mem0-local-platform setup
#
# 1. Prepare the local toolchain:
#    mise trust .
#    mise install
#    mise run setup
#
# 2. Copy and review the tenant policy:
#    cp mem0.policy.example.yml mem0.policy.yml
#
# 3. Set these environment variables in your agent runtime:
#    MEM0_API_URL
#    MEM0_TENANT_POLICY_FILE
#    CLOUDFLARE_ACCESS_CLIENT_ID
#    CLOUDFLARE_ACCESS_CLIENT_SECRET
#
# 4. Add this MCP server configuration to your MCP client.
#
EOF

if [ "$transport" = "stdio" ]; then
  print_stdio_json
else
  print_remote_json
fi

if [ "$target" = "claude-desktop" ]; then
  cat <<'EOF'

# Claude Desktop note:
# Add the JSON under the top-level "mcpServers" object in Claude Desktop's
# config file. Review existing entries first and merge by key.
EOF
fi
