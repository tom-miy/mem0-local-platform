"""Write mem0 sync include/exclude path rules from YAML config."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_FILE = ".mem0-sync.yml"
PLATFORM_DEFAULT_CONFIG_FILE = ".mem0-sync.default.yml"


def main() -> int:
    args = parse_args()
    config_path = resolve_config_path(
        source_root=Path(args.source_root),
        platform_root=Path(args.platform_root),
        config_file=args.config_file,
    )
    config = load_sync_config(config_path)
    write_patterns(Path(args.include_output), config.include)
    write_patterns(Path(args.exclude_output), config.exclude)
    print(f"using mem0 sync config: {config_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--platform-root", required=True)
    parser.add_argument("--config-file", default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--include-output", required=True)
    parser.add_argument("--exclude-output", required=True)
    return parser.parse_args()


class SyncPathConfig:
    def __init__(self, *, include: tuple[str, ...], exclude: tuple[str, ...]) -> None:
        self.include = include
        self.exclude = exclude


def resolve_config_path(*, source_root: Path, platform_root: Path, config_file: str) -> Path:
    if not config_file.strip():
        raise ValueError("sync config file path must not be empty")

    source_config = safe_child_path(source_root, config_file)
    if source_config.exists():
        return source_config

    default_config = platform_root / PLATFORM_DEFAULT_CONFIG_FILE
    if default_config.exists():
        return default_config

    raise FileNotFoundError(
        f"mem0 sync config not found: {source_config} or {default_config}"
    )


def safe_child_path(root: Path, child: str) -> Path:
    root = root.resolve()
    path = (root / child).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"sync config path escapes source root: {child}") from exc
    return path


def load_sync_config(path: Path) -> SyncPathConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mem0 sync config must be a YAML object")

    return SyncPathConfig(
        include=read_pattern_list(data.get("include"), key="include"),
        exclude=read_pattern_list(data.get("exclude"), key="exclude"),
    )


def read_pattern_list(value: Any, *, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"mem0 sync config {key} must be a list")
    patterns = tuple(str(item).strip() for item in value if str(item).strip())
    if not patterns:
        raise ValueError(f"mem0 sync config {key} must not be empty")
    return patterns


def write_patterns(path: Path, patterns: tuple[str, ...]) -> None:
    path.write_text("".join(f"{pattern}\n" for pattern in patterns), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
