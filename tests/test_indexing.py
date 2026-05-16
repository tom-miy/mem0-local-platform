from pathlib import Path
import json
import re
import tempfile
import unittest
from unittest.mock import patch

from scripts.chunk_markdown import chunk_markdown, stable_chunk_id
from scripts.cleanup_text import cleanup_text
from scripts.ingest_repo import build_request_headers, load_patterns, normalize_repo_path, should_index
from mem0_local_platform_mcp.tenant_policy import TenantPolicy


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
            tenant="work",
            repo="example",
            path="docs/example.md",
            tags=("mem0",),
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[1].metadata["heading"], "Title > Details")
        self.assertEqual(chunks[1].metadata["tenant"], "work")
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

    def test_should_index_markdown_first_paths(self) -> None:
        self.assertTrue(should_index(Path("README.md")))
        self.assertTrue(should_index(Path("README.jp.md")))
        self.assertTrue(should_index(Path("docs/e2e.md")))
        self.assertTrue(should_index(Path("docs/nested/e2e.md")))
        self.assertTrue(should_index(Path("adr/0001-record.md")))
        self.assertFalse(should_index(Path("node_modules/pkg/README.md")))
        self.assertFalse(should_index(Path("src/main.py")))

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

    def test_normalize_repo_path_rejects_traversal(self) -> None:
        self.assertEqual(normalize_repo_path(Path("/docs/e2e.md")), Path("docs/e2e.md"))
        self.assertIsNone(normalize_repo_path(Path("../README.md")))

    def test_tenant_policy_rejects_out_of_boundary_reads(self) -> None:
        policy = TenantPolicy(read_tenants=("vault", "work"), write_tenant="work")

        self.assertEqual(policy.readable(["work"]), ("work",))
        with self.assertRaises(ValueError):
            policy.readable(["client-secret"])

    def test_tenant_policy_loads_read_write_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n  - vault\n  - client-tenant\nwrite:\n  - client-tenant\n",
                encoding="utf-8",
            )

            policy = TenantPolicy.from_file(policy_path)

        self.assertEqual(policy.read_tenants, ("vault", "client-tenant"))
        self.assertEqual(policy.write_tenant, "client-tenant")

    def test_tenant_policy_rejects_multiple_write_tenants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text("read:\n  - work\nwrite:\n  - work\n  - vault\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                TenantPolicy.from_file(policy_path)

    def test_tenant_policy_from_env_prefers_policy_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n  - vault\n  - client-tenant\nwrite:\n  - client-tenant\n",
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "MEM0_TENANT_POLICY_FILE": str(policy_path),
                    "MEM0_READ_TENANTS": "work",
                    "MEM0_WRITE_TENANT": "work",
                },
                clear=True,
            ):
                policy = TenantPolicy.from_env()

        self.assertEqual(policy.read_tenants, ("vault", "client-tenant"))
        self.assertEqual(policy.write_tenant, "client-tenant")

    def test_tenant_policy_from_env_fallback_adds_write_tenant_to_readable(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MEM0_READ_TENANTS": "vault",
                "MEM0_WRITE_TENANT": "work",
            },
            clear=True,
        ):
            policy = TenantPolicy.from_env()

        self.assertEqual(policy.read_tenants, ("vault", "work"))
        self.assertEqual(policy.write_tenant, "work")

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
            self.assertEqual(vector_config["embedding_model_dims"], 768)  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
