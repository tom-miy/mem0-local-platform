"""Server-side sanitization before writing memories to mem0."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

import yaml


@dataclass(frozen=True)
class SensitiveTerm:
    term: str
    replacement: str
    name: str = ""
    aliases: tuple[str, ...] = ()

    def sources(self) -> tuple[str, ...]:
        return tuple(sorted((self.term, *self.aliases), key=len, reverse=True))


@dataclass(frozen=True)
class SensitivePattern:
    name: str
    pattern: str
    replacement: str
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SanitizationProfile:
    name: str
    sensitive_terms: tuple[SensitiveTerm, ...]
    sensitive_patterns: tuple[SensitivePattern, ...] = ()
    allow_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class SanitizedPayload:
    messages: str | list[dict[str, str]]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SanitizationMatch:
    kind: str
    rule: str
    count: int


@dataclass(frozen=True)
class SanitizationPolicy:
    tenant_profiles: dict[str, str]
    profiles: dict[str, SanitizationProfile]
    sanitizer_name: str = "mem0-local-platform"
    policy_hash: str = ""
    policy_hash_algorithm: str = "sha256"

    @classmethod
    def disabled(cls) -> "SanitizationPolicy":
        return cls(tenant_profiles={}, profiles={})

    @classmethod
    def from_env(cls) -> "SanitizationPolicy":
        policy_file = os.getenv("MEM0_SANITIZER_POLICY_FILE", "").strip()
        if not policy_file:
            policy_file = os.getenv("MEM0_TENANT_POLICY_FILE", "").strip()
        if not policy_file:
            return cls.disabled()
        return cls.from_file(Path(policy_file))

    @classmethod
    def from_file(cls, path: Path) -> "SanitizationPolicy":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data is None:
            return cls.disabled()
        if not isinstance(data, dict):
            raise ValueError("sanitization policy must be a YAML object")

        section = data.get("sanitization")
        if section is None:
            return cls.disabled()
        if not isinstance(section, dict):
            raise ValueError("sanitization must be a YAML object")

        profiles = _load_profiles(section.get("profiles", {}))
        tenant_profiles = _load_tenants(section.get("tenants", {}))
        sanitizer_name = str(section.get("sanitizer", "mem0-local-platform")).strip()
        if not sanitizer_name:
            raise ValueError("sanitization sanitizer must not be empty")

        for tenant, profile_name in tenant_profiles.items():
            if profile_name not in profiles:
                raise ValueError(
                    f"sanitization tenant {tenant} references unknown profile {profile_name}"
                )

        return cls(
            tenant_profiles=tenant_profiles,
            profiles=profiles,
            sanitizer_name=sanitizer_name,
            policy_hash=_hash_sanitization_section(section),
        )

    def sanitize(
        self,
        *,
        tenant: str,
        messages: str | list[dict[str, str]],
        metadata: dict[str, Any],
    ) -> SanitizedPayload:
        profile_name = self.tenant_profiles.get(tenant)
        if profile_name is None:
            return SanitizedPayload(messages=messages, metadata=metadata)

        profile = self.profiles[profile_name]
        sanitized_messages, matches = _sanitize_messages(messages, profile)
        sanitized_metadata = dict(metadata)
        sanitized_metadata.update(
            {
                "sanitized": True,
                "sanitizer": self.sanitizer_name,
                "sanitization_profile": profile_name,
            }
        )
        if self.policy_hash:
            sanitized_metadata.update(
                {
                    "sanitization_policy_hash": self.policy_hash,
                    "sanitization_policy_hash_algorithm": self.policy_hash_algorithm,
                }
            )
        if matches:
            sanitized_metadata["sanitization_matches"] = [
                {"kind": match.kind, "rule": match.rule, "count": match.count}
                for match in matches
            ]
        return SanitizedPayload(messages=sanitized_messages, metadata=sanitized_metadata)


def _load_profiles(value: object) -> dict[str, SanitizationProfile]:
    if not isinstance(value, dict):
        raise ValueError("sanitization profiles must be a YAML object")

    profiles: dict[str, SanitizationProfile] = {}
    for name, raw_profile in value.items():
        profile_name = str(name).strip()
        if not profile_name:
            raise ValueError("sanitization profile name must not be empty")
        if not isinstance(raw_profile, dict):
            raise ValueError(f"sanitization profile {profile_name} must be a YAML object")

        sensitive_terms = _load_sensitive_terms(
            raw_profile.get("sensitive_terms", ()),
            profile_name=profile_name,
        )
        sensitive_patterns = _load_sensitive_patterns(
            raw_profile.get("sensitive_patterns", ()),
            profile_name=profile_name,
        )
        allow_terms = _load_string_list(
            raw_profile.get("allow_terms", ()),
            key=f"sanitization profile {profile_name} allow_terms",
        )
        _reject_allow_conflicts(
            sensitive_terms,
            allow_terms,
            profile_name=profile_name,
        )
        profiles[profile_name] = SanitizationProfile(
            name=profile_name,
            sensitive_terms=sensitive_terms,
            sensitive_patterns=sensitive_patterns,
            allow_terms=allow_terms,
        )
    return profiles


def _hash_sanitization_section(section: dict[str, Any]) -> str:
    canonical = json.dumps(
        section,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_tenants(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("sanitization tenants must be a YAML object")

    tenant_profiles: dict[str, str] = {}
    for tenant_name, raw_config in value.items():
        tenant = str(tenant_name).strip()
        if not tenant:
            raise ValueError("sanitization tenant name must not be empty")
        if not isinstance(raw_config, dict):
            raise ValueError(f"sanitization tenant {tenant} must be a YAML object")

        mode = str(raw_config.get("mode", "required")).strip()
        if mode not in ("required", "disabled"):
            raise ValueError(f"sanitization tenant {tenant} mode must be required or disabled")
        if mode == "disabled":
            continue

        profile_name = str(raw_config.get("profile", "")).strip()
        if not profile_name:
            raise ValueError(f"sanitization tenant {tenant} profile must not be empty")
        tenant_profiles[tenant] = profile_name
    return tenant_profiles


def _load_sensitive_terms(value: object, *, profile_name: str) -> tuple[SensitiveTerm, ...]:
    if not isinstance(value, list):
        raise ValueError(f"sanitization profile {profile_name} sensitive_terms must be a list")

    terms: list[SensitiveTerm] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_terms[{index}] must be an object"
            )

        term = str(item.get("term", "")).strip()
        replacement = str(item.get("replacement", "")).strip()
        if not term:
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_terms[{index}].term is required"
            )
        if not replacement:
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_terms[{index}].replacement "
                "is required"
            )
        name = str(item.get("name", "")).strip()
        aliases = _load_string_list(
            item.get("aliases", ()),
            key=f"sanitization profile {profile_name} sensitive_terms[{index}].aliases",
        )
        terms.append(
            SensitiveTerm(
                term=term,
                replacement=replacement,
                name=name,
                aliases=aliases,
            )
        )
    return tuple(terms)


def _load_sensitive_patterns(value: object, *, profile_name: str) -> tuple[SensitivePattern, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise ValueError(f"sanitization profile {profile_name} sensitive_patterns must be a list")

    patterns: list[SensitivePattern] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_patterns[{index}] "
                "must be an object"
            )

        name = str(item.get("name", "")).strip()
        pattern = str(item.get("pattern", "")).strip()
        replacement = str(item.get("replacement", "")).strip()
        if not name:
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_patterns[{index}].name "
                "is required"
            )
        if not pattern:
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_patterns[{index}].pattern "
                "is required"
            )
        if not replacement:
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_patterns[{index}].replacement "
                "is required"
            )
        flags = _load_string_list(
            item.get("flags", ()),
            key=f"sanitization profile {profile_name} sensitive_patterns[{index}].flags",
        )
        try:
            re.compile(pattern, _regex_flags(flags))
        except re.error as exc:
            raise ValueError(
                f"sanitization profile {profile_name} sensitive_patterns[{index}] "
                f"has invalid regex"
            ) from exc
        patterns.append(
            SensitivePattern(
                name=name,
                pattern=pattern,
                replacement=replacement,
                flags=flags,
            )
        )
    return tuple(patterns)


def _load_string_list(value: object, *, key: str) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _regex_flags(flags: tuple[str, ...]) -> int:
    parsed = 0
    for flag in flags:
        if flag == "ignorecase":
            parsed |= re.IGNORECASE
        elif flag == "multiline":
            parsed |= re.MULTILINE
        else:
            raise ValueError(f"unsupported regex flag: {flag}")
    return parsed


def _reject_allow_conflicts(
    sensitive_terms: tuple[SensitiveTerm, ...],
    allow_terms: tuple[str, ...],
    *,
    profile_name: str,
) -> None:
    allowed = {term.casefold() for term in allow_terms}
    for sensitive_term in sensitive_terms:
        for source in sensitive_term.sources():
            if source.casefold() in allowed:
                raise ValueError(
                    f"sanitization profile {profile_name} marks {source} as both "
                    "sensitive and allowed"
                )


def _sanitize_messages(
    messages: str | list[dict[str, str]],
    profile: SanitizationProfile,
) -> tuple[str | list[dict[str, str]], tuple[SanitizationMatch, ...]]:
    if isinstance(messages, str):
        return _sanitize_text(messages, profile)

    sanitized: list[dict[str, str]] = []
    match_counts: dict[tuple[str, str], int] = {}
    for message in messages:
        sanitized_message = dict(message)
        content = sanitized_message.get("content")
        if isinstance(content, str):
            sanitized_content, matches = _sanitize_text(content, profile)
            sanitized_message["content"] = sanitized_content
            _merge_matches(match_counts, matches)
        sanitized.append(sanitized_message)
    return sanitized, _matches_from_counts(match_counts)


def _sanitize_text(text: str, profile: SanitizationProfile) -> tuple[str, tuple[SanitizationMatch, ...]]:
    sanitized = text
    match_counts: dict[tuple[str, str], int] = {}
    for sensitive_term in profile.sensitive_terms:
        for source in sensitive_term.sources():
            pattern = re.compile(re.escape(source), flags=re.IGNORECASE)
            count = len(pattern.findall(sanitized))
            if count == 0:
                continue
            sanitized = re.sub(
                re.escape(source),
                lambda _match: sensitive_term.replacement,
                sanitized,
                flags=re.IGNORECASE,
            )
            rule_name = sensitive_term.name or f"term:{sensitive_term.replacement}"
            match_counts[("term", rule_name)] = match_counts.get(("term", rule_name), 0) + count
    for sensitive_pattern in profile.sensitive_patterns:
        flags = _regex_flags(sensitive_pattern.flags)
        pattern = re.compile(sensitive_pattern.pattern, flags)
        count = len(pattern.findall(sanitized))
        if count == 0:
            continue
        sanitized = re.sub(
            sensitive_pattern.pattern,
            lambda _match: sensitive_pattern.replacement,
            sanitized,
            flags=flags,
        )
        match_counts[("pattern", sensitive_pattern.name)] = (
            match_counts.get(("pattern", sensitive_pattern.name), 0) + count
        )
    return sanitized, _matches_from_counts(match_counts)


def _merge_matches(
    match_counts: dict[tuple[str, str], int],
    matches: tuple[SanitizationMatch, ...],
) -> None:
    for match in matches:
        key = (match.kind, match.rule)
        match_counts[key] = match_counts.get(key, 0) + match.count


def _matches_from_counts(match_counts: dict[tuple[str, str], int]) -> tuple[SanitizationMatch, ...]:
    return tuple(
        SanitizationMatch(kind=kind, rule=rule, count=count)
        for (kind, rule), count in sorted(match_counts.items())
    )
