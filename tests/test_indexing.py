from pathlib import Path
import json
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts.chunk_markdown import chunk_markdown, infer_document_type, stable_chunk_id
from scripts.cleanup_text import cleanup_text
from scripts.ingest_repo import (
    Mem0HttpClient,
    build_request_headers,
    load_patterns,
    normalize_repo_path,
    parse_git_name_status,
    should_index,
)
from scripts.sync_path_rules import load_sync_config
from scripts.sync_local_repo import unique_paths
from mem0_local_platform_mcp.mem0_client import Mem0Client
from mem0_local_platform_mcp.tenant_policy import TenantPolicy
from mem0_local_platform_api.server import _mem0_search_filters, delete_memories


class IndexingTests(unittest.TestCase):
    def test_cleanup_removes_transcript_noise(self) -> None:
        text = """
This transcript may contain mentions of ChatGPT...
# Title
Useful content.
Subscribe to the channel
"""
        self.assertEqual(cleanup_text(text), "# Title\nUseful content.\n")

    def test_chunk_markdown_preserves_heading_metadata(self) -> None:
        chunks = chunk_markdown(
            "# Title\nIntro\n\n## Details\nBody",
            tenant="secret-knowledge",
            repo="example",
            path="docs/example.md",
            tags=("mem0",),
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[1].metadata["heading"], "Title > Details")
        self.assertEqual(chunks[1].metadata["tenant"], "secret-knowledge")
        self.assertEqual(chunks[1].metadata["repo"], "example")
        self.assertEqual(chunks[1].metadata["type"], "doc")
        self.assertEqual(chunks[1].metadata["tags"], ["mem0"])

    def test_stable_chunk_id_uses_repo_path_heading(self) -> None:
        self.assertEqual(
            stable_chunk_id(repo="repo", path="README.md", heading="Document"),
            stable_chunk_id(repo="repo", path="README.md", heading="Document"),
        )
        self.assertNotEqual(
            stable_chunk_id(repo="repo-a", path="README.md", heading="Document"),
            stable_chunk_id(repo="repo-b", path="README.md", heading="Document"),
        )

    def test_duplicate_headings_get_distinct_stable_ids(self) -> None:
        chunks = chunk_markdown(
            "# Notes\nFirst\n\n# Notes\nSecond",
            tenant="secret-knowledge",
            repo="example",
            path="docs/notes.md",
        )

        self.assertEqual(len(chunks), 2)
        self.assertNotEqual(chunks[0].stable_id, chunks[1].stable_id)
        self.assertEqual(chunks[0].metadata["heading_occurrence"], 1)
        self.assertEqual(chunks[1].metadata["heading_occurrence"], 2)

    def test_infer_document_type_matches_indexed_path_rules(self) -> None:
        self.assertEqual(infer_document_type("README.md"), "readme")
        self.assertEqual(infer_document_type("README.jp.md"), "readme")
        self.assertEqual(infer_document_type("adr/0001-record.md"), "adr")
        self.assertEqual(infer_document_type("adrs/0001-record.md"), "adr")
        self.assertEqual(infer_document_type("cmd/server/main.go"), "code")
        self.assertEqual(infer_document_type("api/openapi.yaml"), "config")

    def test_should_index_repository_context_paths(self) -> None:
        self.assertTrue(should_index(Path("README.md")))
        self.assertTrue(should_index(Path("README.jp.md")))
        self.assertTrue(should_index(Path("docs/e2e.md")))
        self.assertTrue(should_index(Path("docs/nested/e2e.md")))
        self.assertTrue(should_index(Path("adr/0001-record.md")))
        self.assertTrue(should_index(Path("main.go")))
        self.assertTrue(should_index(Path("server.py")))
        self.assertTrue(should_index(Path("package.json")))
        self.assertTrue(should_index(Path("cmd/server/main.go")))
        self.assertTrue(should_index(Path("api/openapi.yaml")))
        self.assertTrue(should_index(Path("compose.yml")))
        self.assertFalse(should_index(Path("node_modules/pkg/README.md")))
        self.assertFalse(should_index(Path("secrets/api.yaml")))
        self.assertFalse(should_index(Path(".env")))

    def test_should_index_accepts_workflow_path_rules(self) -> None:
        self.assertTrue(
            should_index(
                Path("notes/project.md"),
                include_patterns=("notes/**/*.md", "notes/*.md"),
                exclude_patterns=("notes/private/**",),
            )
        )
        self.assertFalse(
            should_index(
                Path("notes/private/project.md"),
                include_patterns=("notes/**/*.md", "notes/*.md"),
                exclude_patterns=("notes/private/**",),
            )
        )

    def test_load_patterns_prefers_supplied_rules(self) -> None:
        self.assertEqual(load_patterns(["README.md"], None, ("docs/**/*.md",)), ("README.md",))

    def test_repo_sync_path_files_index_local_mcp_docs(self) -> None:
        config = load_sync_config(Path(".mem0-sync.yml"))

        self.assertTrue(
            should_index(
                Path("mcp/tools/README.jp.md"),
                include_patterns=config.include,
                exclude_patterns=config.exclude,
            )
        )
        self.assertFalse(
            should_index(
                Path("data/qdrant/storage.md"),
                include_patterns=config.include,
                exclude_patterns=config.exclude,
            )
        )
        self.assertFalse(
            should_index(
                Path("docs/spec.pdf"),
                include_patterns=config.include,
                exclude_patterns=config.exclude,
            )
        )
        self.assertFalse(
            should_index(
                Path("docs/diagram.png"),
                include_patterns=config.include,
                exclude_patterns=config.exclude,
            )
        )

    def test_normalize_repo_path_rejects_traversal(self) -> None:
        self.assertEqual(normalize_repo_path(Path("/docs/e2e.md")), Path("docs/e2e.md"))
        self.assertIsNone(normalize_repo_path(Path("../README.md")))

    def test_parse_git_name_status_preserves_deleted_and_renamed_paths(self) -> None:
        self.assertEqual(
            parse_git_name_status(
                "M\tdocs/changed.md\n"
                "D\tdocs/deleted.md\n"
                "R100\tdocs/old.md\tdocs/new.md\n"
            ),
            [
                Path("docs/changed.md"),
                Path("docs/deleted.md"),
                Path("docs/old.md"),
                Path("docs/new.md"),
            ],
        )

    def test_unique_paths_preserves_order(self) -> None:
        self.assertEqual(
            unique_paths([Path("docs/a.md"), Path("docs/b.md"), Path("docs/a.md")]),
            [Path("docs/a.md"), Path("docs/b.md")],
        )

    def test_delete_path_memories_filters_by_tenant_repo_and_path(self) -> None:
        class FakeResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        class FakeClient:
            def __init__(self) -> None:
                self.params: dict[str, str] | None = None

            def delete(self, _url: str, *, params: dict[str, str]) -> FakeResponse:
                self.params = params
                return FakeResponse()

        fake = FakeClient()
        client = Mem0HttpClient(
            api_url="http://mem0",
            api_key="",
            cloudflare_access_client_id="",
            cloudflare_access_client_secret="",
            agent_id="test",
        )

        client.delete_existing(
            fake,
            filters={
                "tenant": "secret-knowledge",
                "repo": "repo",
                "path": "docs/example.md",
            },
        )

        self.assertIsNotNone(fake.params)
        self.assertEqual(
            json.loads(fake.params["filters"]),  # type: ignore[index]
            {
                "tenant": "secret-knowledge",
                "repo": "repo",
                "path": "docs/example.md",
            },
        )

    def test_delete_memories_deletes_more_than_one_search_page(self) -> None:
        class FakeMemory:
            def __init__(self) -> None:
                self.ids = [f"memory-{index}" for index in range(105)]
                self.deleted: list[str] = []
                self.search_filters: list[dict[str, object]] = []

            def search(
                self,
                _query: str,
                *,
                filters: dict[str, object],
                top_k: int,
            ) -> dict[str, object]:
                self.search_filters.append(filters)
                remaining = [memory_id for memory_id in self.ids if memory_id not in self.deleted]
                return {"results": [{"id": memory_id} for memory_id in remaining[:top_k]]}

            def delete(self, *, memory_id: str) -> None:
                self.deleted.append(memory_id)

        memory = FakeMemory()

        with patch("mem0_local_platform_api.server.get_memory", return_value=memory):
            result = delete_memories(filters='{"tenant": "secret-knowledge", "repo": "repo"}')

        self.assertEqual(result["deleted_count"], 105)
        self.assertEqual(len(memory.deleted), 105)
        self.assertEqual(memory.search_filters[0]["user_id"], "secret-knowledge")
        self.assertEqual(memory.search_filters[0]["tenant"], "secret-knowledge")

    def test_mem0_search_filters_map_tenant_to_user_id(self) -> None:
        self.assertEqual(
            _mem0_search_filters(
                {"tenant": "secret-knowledge", "repo": "repo", "path": "docs/example.md"}
            ),
            {
                "tenant": "secret-knowledge",
                "user_id": "secret-knowledge",
                "repo": "repo",
                "path": "docs/example.md",
            },
        )

    def test_mcp_client_searches_each_tenant_with_user_id_filter(self) -> None:
        class FakeClient(Mem0Client):
            def __init__(self) -> None:
                self.search_path = "/search"
                self.calls: list[dict[str, object]] = []

            def _post(self, _path: str, payload: dict[str, object]) -> dict[str, object]:
                self.calls.append(payload)
                filters = payload["filters"]  # type: ignore[index]
                tenant = filters["user_id"]  # type: ignore[index]
                return {"results": [{"memory": tenant, "score": 1}]}

        client = FakeClient()
        result = client.search(
            "query",
            tenants=("secret-knowledge", "client-acme"),
            repo="repo",
            limit=5,
        )

        self.assertEqual(len(client.calls), 2)
        first_filters = client.calls[0]["filters"]  # type: ignore[index]
        second_filters = client.calls[1]["filters"]  # type: ignore[index]
        self.assertEqual(first_filters["user_id"], "secret-knowledge")  # type: ignore[index]
        self.assertEqual(first_filters["tenant"], "secret-knowledge")  # type: ignore[index]
        self.assertEqual(first_filters["repo"], "repo")  # type: ignore[index]
        self.assertEqual(second_filters["user_id"], "client-acme")  # type: ignore[index]
        self.assertEqual(
            [item["memory"] for item in result["results"]],
            ["secret-knowledge", "client-acme"],
        )

    def test_tenant_policy_rejects_out_of_boundary_reads(self) -> None:
        policy = TenantPolicy(read_tenants=("secret-knowledge",))

        self.assertEqual(policy.readable(["secret-knowledge"]), ("secret-knowledge",))
        with self.assertRaises(ValueError):
            policy.readable(["client-secret"])

    def test_tenant_policy_loads_read_only_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n  - secret-knowledge\n  - client-tenant\n",
                encoding="utf-8",
            )

            policy = TenantPolicy.from_file(policy_path)

        self.assertEqual(policy.read_tenants, ("secret-knowledge", "client-tenant"))

    def test_tenant_policy_accepts_legacy_single_write_tenant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n  - secret-knowledge\nwrite:\n  - client-tenant\n",
                encoding="utf-8",
            )

            policy = TenantPolicy.from_file(policy_path)

        self.assertEqual(policy.read_tenants, ("secret-knowledge",))

    def test_tenant_policy_rejects_legacy_multiple_write_tenants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n  - secret-knowledge\nwrite:\n  - secret-knowledge\n  - client-tenant\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                TenantPolicy.from_file(policy_path)

    def test_tenant_policy_from_env_prefers_policy_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n  - secret-knowledge\n  - client-tenant\n",
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "MEM0_TENANT_POLICY_FILE": str(policy_path),
                    "MEM0_READ_TENANTS": "secret-knowledge",
                    "MEM0_WRITE_TENANT": "secret-knowledge",
                },
                clear=True,
            ):
                policy = TenantPolicy.from_env()

        self.assertEqual(policy.read_tenants, ("secret-knowledge", "client-tenant"))

    def test_tenant_policy_from_env_uses_read_tenants_only(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MEM0_READ_TENANTS": "secret-knowledge",
                "MEM0_WRITE_TENANT": "client-tenant",
            },
            clear=True,
        ):
            policy = TenantPolicy.from_env()

        self.assertEqual(policy.read_tenants, ("secret-knowledge",))

    def test_build_request_headers_includes_cloudflare_access(self) -> None:
        headers = build_request_headers(
            api_key="",
            cloudflare_access_client_id="client-id",
            cloudflare_access_client_secret="client-secret",
        )

        self.assertEqual(headers["CF-Access-Client-Id"], "client-id")
        self.assertEqual(headers["CF-Access-Client-Secret"], "client-secret")

    def test_build_request_headers_requires_complete_cloudflare_pair(self) -> None:
        with self.assertRaises(ValueError):
            build_request_headers(
                api_key="",
                cloudflare_access_client_id="client-id",
                cloudflare_access_client_secret="",
            )

    def test_mcp_client_includes_cloudflare_access_headers(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MEM0_API_URL": "https://mem0-api.example.com",
                "MEM0_API_KEY": "",
                "CLOUDFLARE_ACCESS_CLIENT_ID": "client-id",
                "CLOUDFLARE_ACCESS_CLIENT_SECRET": "client-secret",
            },
            clear=True,
        ):
            client = Mem0Client()

        self.assertEqual(client.headers["CF-Access-Client-Id"], "client-id")
        self.assertEqual(client.headers["CF-Access-Client-Secret"], "client-secret")

    def test_model_provider_docs_config_json_examples_are_valid(self) -> None:
        docs = (
            Path("docs/architecture/model-provider-settings.md"),
            Path("docs/architecture/model-provider-settings.jp.md"),
        )

        examples: list[dict[str, object]] = []
        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            matches = re.findall(r"MEM0_CONFIG_JSON='(\{.*?\})'", text, flags=re.DOTALL)
            self.assertGreaterEqual(len(matches), 3, f"expected MEM0_CONFIG_JSON examples in {doc}")
            examples.extend(json.loads(match) for match in matches)

        for example in examples:
            self.assertIn("vector_store", example)
            self.assertIn("graph_store", example)
            self.assertIn("llm", example)
            self.assertIn("embedder", example)

            vector_store = example["vector_store"]
            self.assertIsInstance(vector_store, dict)
            vector_config = vector_store["config"]  # type: ignore[index]
            self.assertEqual(vector_config["host"], "qdrant")  # type: ignore[index]
            self.assertEqual(vector_config["embedding_model_dims"], 1024)  # type: ignore[index]

    def test_markdown_docs_have_japanese_counterparts(self) -> None:
        markdown_files = [
            path
            for path in Path(".").rglob("*.md")
            if ".venv" not in path.parts
            and ".git" not in path.parts
            and path.name != "AGENTS.md"
            and not path.name.endswith(".jp.md")
        ]

        missing = [path.as_posix() for path in markdown_files if not japanese_counterpart(path).exists()]

        self.assertEqual(missing, [])

    def test_japanese_docs_have_english_sources(self) -> None:
        japanese_files = [
            path
            for path in Path(".").rglob("*.jp.md")
            if ".venv" not in path.parts and ".git" not in path.parts
        ]

        missing = [path.as_posix() for path in japanese_files if not english_counterpart(path).exists()]

        self.assertEqual(missing, [])


def japanese_counterpart(path: Path) -> Path:
    return path.with_name(f"{path.stem}.jp.md")


def english_counterpart(path: Path) -> Path:
    if not path.name.endswith(".jp.md"):
        raise ValueError(f"not a Japanese Markdown file: {path}")
    return path.with_name(path.name.removesuffix(".jp.md") + ".md")


if __name__ == "__main__":
    unittest.main()
