"""Sync a local Git repository into mem0 without GitHub Actions."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from scripts.ingest_repo import detect_repo_name, parse_git_name_status
from scripts.sync_path_rules import (
    DEFAULT_CONFIG_FILE,
    load_sync_config,
    resolve_config_path,
)


def main() -> int:
    args = parse_args()
    source_root = Path(args.root).resolve()
    platform_root = Path(args.platform_root).resolve()
    repo = args.repo or detect_repo_name(source_root)
    config_path = resolve_config_path(
        source_root=source_root,
        platform_root=platform_root,
        config_file=args.sync_config_file,
    )
    config = load_sync_config(config_path)
    files = resolve_sync_files(
        source_root=source_root,
        mode=args.sync_mode,
        since_ref=args.since_ref,
        include_untracked=args.include_untracked,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        changed_files = tmp_path / "sync-files.txt"
        include_file = tmp_path / "include-paths.txt"
        exclude_file = tmp_path / "exclude-paths.txt"
        write_lines(changed_files, [path.as_posix() for path in files])
        write_lines(include_file, config.include)
        write_lines(exclude_file, config.exclude)

        command = [
            sys.executable,
            "-m",
            "scripts.ingest_repo",
            "--root",
            str(source_root),
            "--tenant",
            args.tenant,
            "--repo",
            repo,
            "--changed-files-file",
            str(changed_files),
            "--include-from",
            str(include_file),
            "--exclude-from",
            str(exclude_file),
        ]
        if args.dry_run:
            command.append("--dry-run")
        if args.json:
            command.append("--json")

        print(
            f"local-sync: {len(files)} candidate files, repo={repo}, "
            f"tenant={args.tenant}, config={config_path}",
            file=sys.stderr,
        )
        subprocess.run(command, cwd=platform_root, check=True)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="local Git repository to sync")
    parser.add_argument("--platform-root", default=".", help="mem0-local-platform repository root")
    parser.add_argument("--repo", help="repository metadata name; defaults to git remote basename")
    parser.add_argument("--tenant", default=os.getenv("MEM0_DEFAULT_TENANT", "secret-knowledge"))
    parser.add_argument(
        "--sync-mode",
        choices=("changed", "full"),
        default="changed",
        help="changed syncs local diffs; full syncs all tracked files",
    )
    parser.add_argument(
        "--since-ref",
        default="HEAD",
        help="base ref for changed mode; use origin/main for branch-wide local sync",
    )
    parser.add_argument(
        "--sync-config-file",
        default=DEFAULT_CONFIG_FILE,
        help="path-rule YAML in the source repository",
    )
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="also include untracked files that pass include/exclude rules",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_sync_files(
    *,
    source_root: Path,
    mode: str,
    since_ref: str,
    include_untracked: bool,
) -> list[Path]:
    if mode == "full":
        return git_lines(source_root, ["ls-files"])
    if mode != "changed":
        raise ValueError(f"unsupported sync mode: {mode}")

    paths: list[Path] = []
    if since_ref:
        paths.extend(
            parse_git_name_status(
                git_output(
                    source_root,
                    ["diff", "--name-status", "--diff-filter=ACMRD", since_ref, "HEAD"],
                )
            )
        )
    paths.extend(
        parse_git_name_status(
            git_output(source_root, ["diff", "--name-status", "--diff-filter=ACMRD"])
        )
    )
    paths.extend(
        parse_git_name_status(
            git_output(source_root, ["diff", "--cached", "--name-status", "--diff-filter=ACMRD"])
        )
    )
    if include_untracked:
        paths.extend(git_lines(source_root, ["ls-files", "--others", "--exclude-standard"]))
    return unique_paths(paths)


def git_output(root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def git_lines(root: Path, args: list[str]) -> list[Path]:
    return [Path(line) for line in git_output(root, args).splitlines() if line]


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def write_lines(path: Path, lines: tuple[str, ...] | list[str]) -> None:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
