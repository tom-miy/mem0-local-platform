"""Remember ad-hoc text from local tools such as Raycast."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

import httpx

from scripts.ingest_repo import build_request_headers


def main() -> int:
    args = parse_args()
    text = read_text(args)
    if not text.strip():
        print("no input text", file=sys.stderr)
        return 2

    metadata = {
        "tenant": args.tenant,
        "source": args.source,
        "type": args.type,
        "repo": args.repo,
        "path": args.path,
        "tags": args.tag,
    }
    metadata = {key: value for key, value in metadata.items() if value not in ("", [], None)}

    client = AdHocMemoryClient(
        api_url=args.mem0_url,
        api_key=args.mem0_api_key,
        cloudflare_access_client_id=args.cloudflare_access_client_id,
        cloudflare_access_client_secret=args.cloudflare_access_client_secret,
        agent_id=args.agent_id,
    )
    client.remember(text.strip(), tenant=args.tenant, metadata=metadata)
    print("remembered", file=sys.stderr)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="text to remember")
    parser.add_argument("--file", help="file to remember; stdin is used when omitted")
    parser.add_argument("--tenant", default=os.getenv("MEM0_DEFAULT_TENANT", "mimr-tech"))
    parser.add_argument("--source", default="local-tool")
    parser.add_argument("--type", default="note")
    parser.add_argument("--repo", default="")
    parser.add_argument("--path", default="")
    parser.add_argument("--tag", action="append", default=[])
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
    parser.add_argument("--agent-id", default=os.getenv("MEM0_AGENT_ID", "local-tool"))
    return parser.parse_args()


def read_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return sys.stdin.read()


class AdHocMemoryClient:
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

    def remember(self, text: str, *, tenant: str, metadata: dict[str, Any]) -> None:
        response = httpx.post(
            f"{self.api_url}{self.add_path}",
            headers=self.headers,
            json={
                "messages": [{"role": "user", "content": text}],
                "user_id": tenant,
                "agent_id": self.agent_id,
                "metadata": metadata,
                "infer": False,
            },
            timeout=30,
        )
        response.raise_for_status()


if __name__ == "__main__":
    raise SystemExit(main())
