"""Tenant boundary helpers for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TenantPolicy:
    read_tenants: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "TenantPolicy":
        policy_file = os.getenv("MEM0_TENANT_POLICY_FILE", "").strip()
        if policy_file:
            return cls.from_file(Path(policy_file))

        read_tenants = _csv(os.getenv("MEM0_READ_TENANTS", "secret-knowledge"))
        return cls(read_tenants=read_tenants)

    @classmethod
    def from_file(cls, path: Path) -> "TenantPolicy":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("tenant policy must be a YAML object")

        read_tenants = _list(data.get("read"), key="read")
        write_value = data.get("write")
        if write_value is not None:
            write_tenants = _list(write_value, key="write")
            if len(write_tenants) != 1:
                raise ValueError("tenant policy write must contain at most one tenant")
        return cls(read_tenants=read_tenants)

    def readable(self, requested: list[str] | None) -> tuple[str, ...]:
        if not requested:
            return self.read_tenants
        requested_set = {tenant.strip() for tenant in requested if tenant.strip()}
        allowed = tuple(tenant for tenant in self.read_tenants if tenant in requested_set)
        if not allowed:
            raise ValueError("requested tenants are outside the configured read boundary")
        return allowed


def _csv(value: str) -> tuple[str, ...]:
    entries = tuple(item.strip() for item in value.split(",") if item.strip())
    if not entries:
        raise ValueError("tenant list must not be empty")
    return entries


def _list(value: object, *, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"tenant policy {key} must be a list")
    entries = tuple(str(item).strip() for item in value if str(item).strip())
    if not entries:
        raise ValueError(f"tenant policy {key} must not be empty")
    return entries
