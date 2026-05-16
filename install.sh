#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./install.sh [--target generic|codex|claude-desktop|raycast|github-actions] [--transport stdio|sse|http]

Print setup snippets for mem0-local-platform or install repository sync files.

This script does not edit your agent configuration files.
For GitHub Actions, it writes new files into the target repository and refuses
to overwrite existing files unless --force is provided.

Examples:
  ./install.sh --target generic --transport stdio
  ./install.sh --target codex
  ./install.sh --target claude-desktop --transport stdio
  ./install.sh --target generic --transport sse
  ./install.sh --target raycast
  ./install.sh --target github-actions --target-dir /path/to/repo --tenant mimr-tech

GitHub Actions options:
  --target-dir PATH             repository to install into (default: current directory)
  --tenant NAME                 tenant written by the sync workflow (default: mimr-tech)
  --platform-repository OWNER/REPO
                                reusable workflow repository (default: tom-miy/mem0-local-platform)
  --platform-ref REF            reusable workflow ref (default: main)
  --force                       overwrite generated workflow/path-rule files
USAGE
}

target="generic"
transport="stdio"
target_dir="."
tenant="mimr-tech"
platform_repository="tom-miy/mem0-local-platform"
platform_ref="main"
force="false"

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
    --target-dir)
      target_dir="${2:-}"
      shift 2
      ;;
    --tenant)
      tenant="${2:-}"
      shift 2
      ;;
    --platform-repository)
      platform_repository="${2:-}"
      shift 2
      ;;
    --platform-ref)
      platform_ref="${2:-}"
      shift 2
      ;;
    --force)
      force="true"
      shift
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
  generic|codex|claude-desktop|raycast|github-actions) ;;
  *)
    echo "target must be generic, codex, claude-desktop, raycast, or github-actions: $target" >&2
    exit 2
    ;;
esac

if [ -z "$tenant" ]; then
  echo "tenant must not be empty" >&2
  exit 2
fi

if [ -z "$platform_repository" ]; then
  echo "platform repository must not be empty" >&2
  exit 2
fi

if [ -z "$platform_ref" ]; then
  echo "platform ref must not be empty" >&2
  exit 2
fi

case "$transport" in
  stdio|sse|http) ;;
  *)
    echo "transport must be stdio, sse, or http: $transport" >&2
    exit 2
    ;;
esac

repo_root="$(cd "$(dirname "$0")" && pwd)"

write_file() {
  local path="$1"
  if [ -e "$path" ] && [ "$force" != "true" ]; then
    echo "refusing to overwrite existing file: $path" >&2
    echo "rerun with --force after reviewing the existing file" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$path")"
  cat > "$path"
}

install_github_actions() {
  local dest
  dest="$(cd "$target_dir" && pwd)"

  write_file "$dest/.github/workflows/sync-memory.yml" <<YAML
name: Sync Repository Memory

on:
  push:
    branches:
      - main
  workflow_dispatch:
    inputs:
      sync_mode:
        description: changed は差分同期、full は全体同期
        required: true
        type: choice
        options:
          - changed
          - full
        default: full

jobs:
  sync:
    uses: $platform_repository/.github/workflows/reusable-sync.yml@$platform_ref
    with:
      sync_mode: \${{ github.event.inputs.sync_mode || 'changed' }}
      tenant: $tenant
    secrets:
      MEM0_API_URL: \${{ secrets.MEM0_API_URL }}
      MEM0_API_KEY: \${{ secrets.MEM0_API_KEY }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_ID: \${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_ID }}
      MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET: \${{ secrets.MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET }}
YAML

  write_file "$dest/.mem0-sync.yml" <<'EOF'
include:
  - README.md
  - README*.md
  - docs/*.md
  - docs/**/*.md
  - adr/*.md
  - adr/**/*.md
  - adrs/*.md
  - adrs/**/*.md

exclude:
  - .git/**
  - .venv/**
  - .cache/**
  - data/**
  - node_modules/**
  - "**/node_modules/**"
  - dist/**
  - "**/dist/**"
  - vendor/**
  - "**/vendor/**"
  - coverage/**
  - "**/coverage/**"
  - build/**
  - "**/build/**"
  - __pycache__/**
  - "**/__pycache__/**"
  - "*.pyc"
  - "**/*.pyc"
  - "*.lock"
  - "**/*.lock"
  - package-lock.json
  - "**/package-lock.json"
  - pnpm-lock.yaml
  - "**/pnpm-lock.yaml"
  - yarn.lock
  - "**/yarn.lock"
  - "**/*.pdf"
  - "**/*.xls"
  - "**/*.xlsx"
  - "**/*.doc"
  - "**/*.docx"
  - "**/*.ppt"
  - "**/*.pptx"
  - "**/*.png"
  - "**/*.jpg"
  - "**/*.jpeg"
  - "**/*.gif"
  - "**/*.webp"
  - "**/*.svg"
  - "**/*.ico"
  - "**/*.zip"
  - "**/*.tar"
  - "**/*.tar.gz"
  - "**/*.tgz"
  - "**/*.7z"
  - "**/*.rar"
  - "**/*.mp3"
  - "**/*.mp4"
  - "**/*.mov"
  - "**/*.wav"
EOF

  cat <<EOF
Installed GitHub Actions mem0 sync files into:
  $dest

Created:
  .github/workflows/sync-memory.yml
  .mem0-sync.yml

Next steps:
  1. Review the tenant in .github/workflows/sync-memory.yml.
  2. Adjust .mem0-sync.yml.
  3. Configure these repository secrets:
     MEM0_API_URL
     MEM0_CLOUDFLARE_ACCESS_CLIENT_ID
     MEM0_CLOUDFLARE_ACCESS_CLIENT_SECRET
     MEM0_API_KEY only if the mem0 endpoint requires a Bearer token
  4. Commit the generated files.
EOF
}

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

if [ "$target" = "github-actions" ]; then
  install_github_actions
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
