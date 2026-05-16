"""Ingest changed repository context files into mem0."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

from scripts.chunk_markdown import MarkdownChunk, chunk_markdown


DEFAULT_INCLUDE_PATTERNS = (
    "README.md",
    "README*.md",
    "docs/*.md",
    "docs/**/*.md",
    "adr/*.md",
    "adr/**/*.md",
    "adrs/*.md",
    "adrs/**/*.md",
    "api.yaml",
    "api.yml",
    "openapi.yaml",
    "openapi.yml",
    "**/api.yaml",
    "**/api.yml",
    "**/openapi.yaml",
    "**/openapi.yml",
    "**/*.go",
    "**/*.py",
    "**/*.ts",
    "**/*.tsx",
    "**/*.js",
    "**/*.jsx",
    "**/*.rs",
    "**/*.java",
    "**/*.kt",
    "**/*.sql",
    "**/*.sh",
    "**/*.yaml",
    "**/*.yml",
    "**/*.json",
    "**/*.toml",
    "**/*.ini",
    "**/*.proto",
    "**/*.graphql",
    "Dockerfile",
    "**/Dockerfile",
    "compose.yml",
    "compose.yaml",
    "**/compose.yml",
    "**/compose.yaml",
    "Makefile",
    "**/Makefile",
)
DEFAULT_EXCLUDE_PATTERNS = (
    ".git/**",
    ".venv/**",
    ".cache/**",
    "data/**",
    "secrets/**",
    "**/secrets/**",
    ".env",
    "**/.env",
    ".env.local",
    "**/.env.local",
    "node_modules/**",
    "**/node_modules/**",
    "dist/**",
    "**/dist/**",
    "vendor/**",
    "**/vendor/**",
    "coverage/**",
    "**/coverage/**",
    "build/**",
    "**/build/**",
    "__pycache__/**",
    "**/__pycache__/**",
    "*.pyc",
    "**/*.pyc",
    "*.lock",
    "**/*.lock",
    "package-lock.json",
    "**/package-lock.json",
    "pnpm-lock.yaml",
    "**/pnpm-lock.yaml",
    "yarn.lock",
    "**/yarn.lock",
)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    repo = args.repo or detect_repo_name(root)
    files = list(resolve_changed_files(root, args))
    include_patterns = load_patterns(args.include, args.include_from, DEFAULT_INCLUDE_PATTERNS)
    exclude_patterns = load_patterns(args.exclude, args.exclude_from, DEFAULT_EXCLUDE_PATTERNS)

    chunks: list[MarkdownChunk] = []
    indexed_files = 0
    path_deletes = 0
    delete_only_paths = 0
    client = None if args.dry_run else build_mem0_client(args)
    for rel_path in files:
        normalized = normalize_repo_path(rel_path)
        if normalized is None or not should_index(
            normalized,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        ):
            continue

        source = safe_source_path(root, normalized)
        if source is None or not source.exists():
            delete_only_paths += 1
            if not args.dry_run:
                assert client is not None
                client.delete_path_memories(
                    tenant=args.tenant,
                    repo=repo,
                    path=normalized.as_posix(),
                )
                path_deletes += 1
            continue
        indexed_files += 1
        text = source.read_text(encoding="utf-8")
        if not args.dry_run:
            assert client is not None
            client.delete_path_memories(
                tenant=args.tenant,
                repo=repo,
                path=normalized.as_posix(),
            )
            path_deletes += 1
        chunks.extend(
            chunk_markdown(
                text,
                tenant=args.tenant,
                repo=repo,
                path=normalized.as_posix(),
                tags=tuple(args.tag),
            )
        )

    payloads = [chunk_to_payload(chunk) for chunk in chunks]
    if args.json:
        print(json.dumps(payloads, indent=2, ensure_ascii=False))

    if args.dry_run:
        print(
            f"dry-run: {len(files)} candidate files, {indexed_files} indexed files, "
            f"{delete_only_paths} delete-only paths, {len(chunks)} chunks",
            file=sys.stderr,
        )
        return 0

    assert client is not None
    for chunk in chunks:
        client.upsert(chunk)

    print(
        f"ingested: {len(files)} candidate files, {indexed_files} indexed files, "
        f"{path_deletes} path deletes, {delete_only_paths} delete-only paths, "
        f"{len(chunks)} chunks",
        file=sys.stderr,
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root to inspect")
    parser.add_argument("--repo", help="repository metadata name; defaults to git directory name")
    parser.add_argument("--tenant", default=os.getenv("MEM0_DEFAULT_TENANT", "secret-knowledge"))
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--changed-files", nargs="*", help="explicit changed file list")
    parser.add_argument("--changed-files-file", help="newline-delimited changed file list")
    parser.add_argument("--since-ref", help="git ref used to compute changed files")
    parser.add_argument("--include", action="append", default=[], help="glob path to index")
    parser.add_argument("--include-from", help="newline-delimited include glob file")
    parser.add_argument("--exclude", action="append", default=[], help="glob path to ignore")
    parser.add_argument("--exclude-from", help="newline-delimited exclude glob file")
    parser.add_argument("--mem0-url", default=os.getenv("MEM0_API_URL", "http://localhost:8000"))
    parser.add_argument("--mem0-api-key", default=os.getenv("MEM0_API_KEY", ""))
    parser.add_argument(
        "--cloudflare-access-client-id",
        default=os.getenv("CLOUDFLARE_ACCESS_CLIENT_ID", ""),
    )
    parser.add_argument(
        "--cloudflare-access-client-secret",
        default=os.getenv("CLOUDFLARE_ACCESS_CLIENT_SECRET", ""),
    )
    parser.add_argument("--agent-id", default=os.getenv("MEM0_AGENT_ID", "github-repo-indexer"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def resolve_changed_files(root: Path, args: argparse.Namespace) -> Iterable[Path]:
    if args.changed_files_file:
        return [
            Path(line)
            for line in Path(args.changed_files_file).read_text(encoding="utf-8").splitlines()
            if line
        ]

    if args.changed_files is not None:
        return [Path(path) for path in args.changed_files if path]

    if args.since_ref:
        result = subprocess.run(
            ["git", "diff", "--name-status", "--diff-filter=ACMRD", args.since_ref, "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return parse_git_name_status(result.stdout)

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def should_index(
    path: Path,
    *,
    include_patterns: tuple[str, ...] = DEFAULT_INCLUDE_PATTERNS,
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS,
) -> bool:
    normalized = path.as_posix()
    if matches_any(normalized, exclude_patterns):
        return False
    return matches_any(normalized, include_patterns)


def load_patterns(
    cli_patterns: list[str],
    patterns_file: str | None,
    defaults: tuple[str, ...],
) -> tuple[str, ...]:
    patterns: list[str] = []
    if patterns_file:
        patterns.extend(read_pattern_file(Path(patterns_file)))
    patterns.extend(cli_patterns)
    return tuple(patterns or defaults)


def read_pattern_file(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(matches_pattern(path, pattern) for pattern in patterns)


def matches_pattern(path: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(path, pattern):
        return True
    if pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern.removeprefix("**/")):
        return True
    return False


def parse_git_name_status(output: str) -> list[Path]:
    paths: list[Path] = []
    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            paths.append(Path(parts[1]))
            paths.append(Path(parts[2]))
        elif len(parts) >= 2:
            paths.append(Path(parts[1]))
    return paths


def normalize_repo_path(path: Path) -> Path | None:
    normalized = Path(path.as_posix().lstrip("/"))
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    return normalized


def safe_source_path(root: Path, rel_path: Path) -> Path | None:
    source = (root / rel_path).resolve()
    try:
        source.relative_to(root)
    except ValueError:
        return None
    return source


def detect_repo_name(root: Path) -> str:
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    remote = result.stdout.strip()
    if remote:
        return remote.removesuffix(".git").split("/")[-1]
    return root.name


def chunk_to_payload(chunk: MarkdownChunk) -> dict[str, object]:
    return {
        "id": chunk.stable_id,
        "memory": chunk.content,
        "metadata": chunk.metadata,
    }


class Mem0HttpClient:
    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        cloudflare_access_client_id: str,
        cloudflare_access_client_secret: str,
        agent_id: str,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.headers = build_request_headers(
            api_key=api_key,
            cloudflare_access_client_id=cloudflare_access_client_id,
            cloudflare_access_client_secret=cloudflare_access_client_secret,
        )
        self.agent_id = agent_id
        self.add_path = os.getenv("MEM0_ADD_PATH", "/add")
        self.delete_path = os.getenv("MEM0_DELETE_PATH", "/v1/memories/")

    def upsert(self, chunk: MarkdownChunk) -> None:
        import httpx

        metadata = dict(chunk.metadata)
        metadata["stable_id"] = chunk.stable_id

        with httpx.Client(headers=self.headers, timeout=30) as client:
            response = client.post(
                f"{self.api_url}{self.add_path}",
                json={
                    "messages": [{"role": "user", "content": chunk.content}],
                    "user_id": metadata["tenant"],
                    "agent_id": self.agent_id,
                    "metadata": metadata,
                    "infer": False,
                },
            )
            response.raise_for_status()

    def delete_path_memories(self, *, tenant: str, repo: str, path: str) -> None:
        import httpx

        with httpx.Client(headers=self.headers, timeout=30) as client:
            self.delete_existing(
                client,
                filters={
                    "tenant": tenant,
                    "repo": repo,
                    "path": path,
                },
            )

    def delete_existing(self, client: Any, *, filters: dict[str, Any]) -> None:
        response = client.delete(
            f"{self.api_url}{self.delete_path}",
            params={"filters": json.dumps(filters)},
        )
        if response.status_code == 404:
            return
        response.raise_for_status()


def build_request_headers(
    *,
    api_key: str,
    cloudflare_access_client_id: str,
    cloudflare_access_client_secret: str,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if cloudflare_access_client_id or cloudflare_access_client_secret:
        if not cloudflare_access_client_id or not cloudflare_access_client_secret:
            raise ValueError(
                "both CLOUDFLARE_ACCESS_CLIENT_ID and "
                "CLOUDFLARE_ACCESS_CLIENT_SECRET are required"
            )
        headers["CF-Access-Client-Id"] = cloudflare_access_client_id
        headers["CF-Access-Client-Secret"] = cloudflare_access_client_secret
    return headers


def build_mem0_client(args: argparse.Namespace) -> Mem0HttpClient:
    return Mem0HttpClient(
        api_url=args.mem0_url,
        api_key=args.mem0_api_key,
        cloudflare_access_client_id=args.cloudflare_access_client_id,
        cloudflare_access_client_secret=args.cloudflare_access_client_secret,
        agent_id=args.agent_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
