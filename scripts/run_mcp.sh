#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
env_file="${MEM0_ENV_FILE:-$repo_root/mem0.env}"

if [ -f "$env_file" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
else
  echo "mem0 env file not found: $env_file" >&2
  echo "copy mem0.env.example to mem0.env and fill in the values" >&2
  exit 2
fi

cd "$repo_root"

if [ -n "${MEM0_TENANT_POLICY_FILE:-}" ] && [ ! -f "$MEM0_TENANT_POLICY_FILE" ]; then
  echo "tenant policy file not found: $MEM0_TENANT_POLICY_FILE" >&2
  echo "copy mem0.policy.example.yml to mem0.policy.yml and set readable tenants" >&2
  exit 2
fi

exec uv run mem0-local-mcp
