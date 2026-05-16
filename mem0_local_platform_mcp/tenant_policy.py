"""Tenant boundary helpers for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class TenantPolicy:
    read_tenants: tuple[str, ...]
    write_tenant: str

    @classmethod
    def from_env(cls) -> "TenantPolicy":
        read_tenants = _csv(os.getenv("MEM0_READ_TENANTS", "work"))
        write_tenant = os.getenv("MEM0_WRITE_TENANT", "work").strip()
        if not write_tenant:
            raise ValueError("MEM0_WRITE_TENANT must not be empty")
        if write_tenant not in read_tenants:
            read_tenants = (*read_tenants, write_tenant)
        return cls(read_tenants=read_tenants, write_tenant=write_tenant)

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

