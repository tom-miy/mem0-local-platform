from pathlib import Path
import json
import os
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import yaml

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
from mem0_local_platform_api.sanitizer import (
    SanitizationPolicy,
    SanitizationProfile,
    SensitiveTerm,
)
from mem0_local_platform_api.server import (
    AddRequest,
    SearchRequest,
    _mem0_search_filters,
    add_memory,
    audit_sanitization,
    delete_memories,
    get_memory,
    require_api_key,
    search_memory,
)


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

    def test_audit_sanitization_groups_stale_files_without_returning_memory_text(self) -> None:
        class FakeMemory:
            search_filters: dict[str, object] | None = None

            def search(
                self,
                _query: str,
                *,
                filters: dict[str, object],
                top_k: int,
            ) -> dict[str, object]:
                self.search_filters = filters
                self.top_k = top_k
                return {
                    "results": [
                        {
                            "id": "old-hash",
                            "memory": "raw text must not be returned",
                            "metadata": {
                                "tenant": "secret-knowledge",
                                "repo": "repo",
                                "path": "docs/a.md",
                                "sanitized": True,
                                "sanitization_policy_hash": "old-policy-hash",
                            },
                        },
                        {
                            "id": "missing-hash",
                            "metadata": {
                                "tenant": "secret-knowledge",
                                "repo": "repo",
                                "path": "docs/a.md",
                                "sanitized": True,
                            },
                        },
                        {
                            "id": "not-sanitized",
                            "metadata": {
                                "tenant": "secret-knowledge",
                                "repo": "repo",
                                "path": "docs/b.md",
                            },
                        },
                        {
                            "id": "current",
                            "metadata": {
                                "tenant": "secret-knowledge",
                                "repo": "repo",
                                "path": "docs/c.md",
                                "sanitized": True,
                                "sanitization_policy_hash": "current-policy-hash",
                            },
                        },
                    ]
                }

        memory = FakeMemory()
        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            profiles={"default": SanitizationProfile(name="default", sensitive_terms=())},
            policy_hash="current-policy-hash",
        )

        with (
            patch("mem0_local_platform_api.server.get_memory", return_value=memory),
            patch("mem0_local_platform_api.server.get_sanitization_policy", return_value=policy),
        ):
            result = audit_sanitization(tenant="secret-knowledge", repo="repo", top_k=50)

        self.assertEqual(memory.search_filters["tenant"], "secret-knowledge")  # type: ignore[index]
        self.assertEqual(memory.search_filters["user_id"], "secret-knowledge")  # type: ignore[index]
        self.assertEqual(memory.search_filters["repo"], "repo")  # type: ignore[index]
        self.assertEqual(memory.top_k, 50)  # type: ignore[attr-defined]
        self.assertEqual(result["scanned_count"], 4)
        self.assertEqual(result["issue_file_count"], 2)
        self.assertEqual(
            result["files"],
            [
                {
                    "repo": "repo",
                    "path": "docs/a.md",
                    "count": 2,
                    "reasons": ["policy_hash_mismatch", "missing_policy_hash"],
                    "observed_hashes": ["old-policy-hash"],
                },
                {
                    "repo": "repo",
                    "path": "docs/b.md",
                    "count": 1,
                    "reasons": ["not_sanitized", "missing_policy_hash"],
                    "observed_hashes": [],
                },
            ],
        )
        self.assertNotIn("raw text", json.dumps(result))

    def test_audit_sanitization_rejects_tenant_without_required_sanitization(self) -> None:
        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            profiles={"default": SanitizationProfile(name="default", sensitive_terms=())},
            policy_hash="current-policy-hash",
        )

        with patch("mem0_local_platform_api.server.get_sanitization_policy", return_value=policy):
            with self.assertRaises(HTTPException):
                audit_sanitization(tenant="public-notes")

    def test_search_memory_rejects_stale_sanitization_hash_for_required_tenant(self) -> None:
        class FakeMemory:
            def search(
                self,
                _query: str,
                *,
                filters: dict[str, object],
                top_k: int,
            ) -> dict[str, object]:
                return {
                    "results": [
                        {
                            "id": "stale",
                            "memory": "raw text must not be returned",
                            "metadata": {
                                "tenant": "secret-knowledge",
                                "repo": "repo",
                                "path": "docs/a.md",
                                "sanitized": True,
                                "sanitization_policy_hash": "old-policy-hash",
                            },
                        }
                    ]
                }

        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            profiles={"default": SanitizationProfile(name="default", sensitive_terms=())},
            policy_hash="current-policy-hash",
        )

        with (
            patch("mem0_local_platform_api.server.get_memory", return_value=FakeMemory()),
            patch("mem0_local_platform_api.server.get_sanitization_policy", return_value=policy),
            self.assertRaises(HTTPException) as raised,
        ):
            search_memory(
                SearchRequest(
                    query="query",
                    filters={"tenant": "secret-knowledge", "user_id": "secret-knowledge"},
                )
            )

        self.assertEqual(raised.exception.status_code, 409)
        detail = raised.exception.detail
        self.assertEqual(detail["error"], "stale_sanitization_policy")
        self.assertEqual(
            detail["files"],
            [
                {
                    "repo": "repo",
                    "path": "docs/a.md",
                    "count": 1,
                    "reasons": ["policy_hash_mismatch"],
                    "observed_hashes": ["old-policy-hash"],
                }
            ],
        )
        self.assertNotIn("raw text", json.dumps(detail))

    def test_search_memory_allows_current_sanitization_hash_for_required_tenant(self) -> None:
        class FakeMemory:
            def search(
                self,
                _query: str,
                *,
                filters: dict[str, object],
                top_k: int,
            ) -> dict[str, object]:
                return {
                    "results": [
                        {
                            "id": "current",
                            "metadata": {
                                "tenant": "secret-knowledge",
                                "repo": "repo",
                                "path": "docs/a.md",
                                "sanitized": True,
                                "sanitization_policy_hash": "current-policy-hash",
                            },
                        }
                    ]
                }

        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            profiles={"default": SanitizationProfile(name="default", sensitive_terms=())},
            policy_hash="current-policy-hash",
        )

        with (
            patch("mem0_local_platform_api.server.get_memory", return_value=FakeMemory()),
            patch("mem0_local_platform_api.server.get_sanitization_policy", return_value=policy),
        ):
            result = search_memory(
                SearchRequest(
                    query="query",
                    filters={"tenant": "secret-knowledge", "user_id": "secret-knowledge"},
                )
            )

        self.assertEqual(len(result["results"]), 1)

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

    def test_api_key_is_optional_when_not_configured(self) -> None:
        with patch.dict(os.environ, {"MEM0_API_KEY": ""}, clear=False):
            self.assertIsNone(require_api_key())

    def test_api_key_rejects_wrong_bearer_token_when_configured(self) -> None:
        with patch.dict(os.environ, {"MEM0_API_KEY": "expected"}, clear=False):
            with self.assertRaises(HTTPException):
                require_api_key("Bearer wrong")

    def test_api_key_accepts_matching_bearer_token_when_configured(self) -> None:
        with patch.dict(os.environ, {"MEM0_API_KEY": "expected"}, clear=False):
            self.assertIsNone(require_api_key("Bearer expected"))

    def test_sanitization_policy_replaces_sensitive_terms_for_required_tenant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "read:\n"
                "  - secret-knowledge\n"
                "sanitization:\n"
                "  sanitizer: mem0-local-platform\n"
                "  tenants:\n"
                "    secret-knowledge:\n"
                "      mode: required\n"
                "      profile: default\n"
                "  profiles:\n"
                "    default:\n"
                "      sensitive_terms:\n"
                "        - term: client-acme\n"
                "          replacement: CUSTOMER_1\n"
                "          aliases:\n"
                "            - Acme client\n",
                encoding="utf-8",
            )

            policy = SanitizationPolicy.from_file(policy_path)

        result = policy.sanitize(
            tenant="secret-knowledge",
            messages=[{"role": "user", "content": "client-acme and Acme client"}],
            metadata={"tenant": "secret-knowledge"},
        )

        self.assertEqual(
            result.messages,
            [{"role": "user", "content": "CUSTOMER_1 and CUSTOMER_1"}],
        )
        self.assertEqual(result.metadata["sanitized"], True)
        self.assertEqual(result.metadata["sanitizer"], "mem0-local-platform")
        self.assertEqual(result.metadata["sanitization_profile"], "default")
        self.assertEqual(result.metadata["sanitization_policy_hash_algorithm"], "sha256")
        self.assertRegex(result.metadata["sanitization_policy_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            result.metadata["sanitization_matches"],
            [{"kind": "term", "rule": "term:CUSTOMER_1", "count": 2}],
        )

    def test_sanitization_policy_hash_changes_when_sanitization_section_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_path = Path(tmp) / "first.yml"
            second_path = Path(tmp) / "second.yml"
            first_path.write_text(
                "read:\n"
                "  - secret-knowledge\n"
                "sanitization:\n"
                "  tenants:\n"
                "    secret-knowledge:\n"
                "      mode: required\n"
                "      profile: default\n"
                "  profiles:\n"
                "    default:\n"
                "      sensitive_terms:\n"
                "        - term: client-acme\n"
                "          replacement: CUSTOMER_1\n",
                encoding="utf-8",
            )
            second_path.write_text(
                "read:\n"
                "  - another-tenant\n"
                "sanitization:\n"
                "  tenants:\n"
                "    secret-knowledge:\n"
                "      mode: required\n"
                "      profile: default\n"
                "  profiles:\n"
                "    default:\n"
                "      sensitive_terms:\n"
                "        - term: client-acme\n"
                "          replacement: CUSTOMER_2\n",
                encoding="utf-8",
            )

            first_policy = SanitizationPolicy.from_file(first_path)
            second_policy = SanitizationPolicy.from_file(second_path)

        self.assertNotEqual(first_policy.policy_hash, second_policy.policy_hash)

    def test_sanitization_policy_replaces_longer_aliases_first(self) -> None:
        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            policy_hash="test-policy-hash",
            profiles={
                "default": SanitizationProfile(
                    name="default",
                    sensitive_terms=(
                        SensitiveTerm(
                            term="client",
                            replacement="CUSTOMER",
                            aliases=("client-acme",),
                        ),
                    ),
                )
            },
        )

        result = policy.sanitize(
            tenant="secret-knowledge",
            messages="client-acme and client",
            metadata={"tenant": "secret-knowledge"},
        )

        self.assertEqual(result.messages, "CUSTOMER and CUSTOMER")

    def test_sanitization_policy_replaces_sensitive_regex_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "sanitization:\n"
                "  tenants:\n"
                "    secret-knowledge:\n"
                "      mode: required\n"
                "      profile: default\n"
                "  profiles:\n"
                "    default:\n"
                "      sensitive_terms: []\n"
                "      sensitive_patterns:\n"
                "        - name: access-key-assignment\n"
                "          pattern: '(?i)\\b[A-Z0-9_]*(?:ACCESS|SECRET|API)_KEY\\s*=\\s*[^\\s]+'\n"
                "          replacement: REDACTED_SECRET_ASSIGNMENT\n",
                encoding="utf-8",
            )

            policy = SanitizationPolicy.from_file(policy_path)

        result = policy.sanitize(
            tenant="secret-knowledge",
            messages="AWS_ACCESS_KEY=abc123 should not be stored",
            metadata={"tenant": "secret-knowledge"},
        )

        self.assertEqual(result.messages, "REDACTED_SECRET_ASSIGNMENT should not be stored")
        self.assertEqual(
            result.metadata["sanitization_matches"],
            [{"kind": "pattern", "rule": "access-key-assignment", "count": 1}],
        )

    def test_sanitization_policy_rejects_invalid_regex_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "sanitization:\n"
                "  tenants:\n"
                "    secret-knowledge:\n"
                "      mode: required\n"
                "      profile: default\n"
                "  profiles:\n"
                "    default:\n"
                "      sensitive_terms: []\n"
                "      sensitive_patterns:\n"
                "        - name: broken\n"
                "          pattern: '('\n"
                "          replacement: REDACTED\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                SanitizationPolicy.from_file(policy_path)

    def test_sanitization_policy_rejects_allowed_sensitive_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "mem0.policy.yml"
            policy_path.write_text(
                "sanitization:\n"
                "  tenants:\n"
                "    secret-knowledge:\n"
                "      mode: required\n"
                "      profile: default\n"
                "  profiles:\n"
                "    default:\n"
                "      allow_terms:\n"
                "        - mem0\n"
                "      sensitive_terms:\n"
                "        - term: mem0\n"
                "          replacement: PRODUCT_1\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                SanitizationPolicy.from_file(policy_path)

    def test_sanitization_policy_leaves_unconfigured_tenant_unchanged(self) -> None:
        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            profiles={},
        )

        result = policy.sanitize(
            tenant="public-notes",
            messages="client-acme",
            metadata={"tenant": "public-notes"},
        )

        self.assertEqual(result.messages, "client-acme")
        self.assertEqual(result.metadata, {"tenant": "public-notes"})

    def test_add_memory_sanitizes_before_calling_mem0(self) -> None:
        class FakeMemory:
            def __init__(self) -> None:
                self.add_payload: dict[str, object] | None = None

            def add(
                self,
                messages: object,
                *,
                user_id: str,
                agent_id: str | None,
                run_id: str | None,
                metadata: dict[str, object],
                infer: bool,
            ) -> dict[str, str]:
                self.add_payload = {
                    "messages": messages,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "run_id": run_id,
                    "metadata": metadata,
                    "infer": infer,
                }
                return {"status": "ok"}

        memory = FakeMemory()
        policy = SanitizationPolicy(
            tenant_profiles={"secret-knowledge": "default"},
            policy_hash="test-policy-hash",
            profiles={
                "default": SanitizationProfile(
                    name="default",
                    sensitive_terms=(
                        SensitiveTerm(term="client-acme", replacement="CUSTOMER_1"),
                    ),
                )
            },
        )

        with (
            patch("mem0_local_platform_api.server.get_memory", return_value=memory),
            patch("mem0_local_platform_api.server.get_sanitization_policy", return_value=policy),
        ):
            add_memory(
                AddRequest(
                    messages=[{"role": "user", "content": "client-acme incident note"}],
                    user_id="secret-knowledge",
                    metadata={"tenant": "secret-knowledge", "repo": "repo"},
                    infer=False,
                )
            )

        self.assertIsNotNone(memory.add_payload)
        self.assertEqual(
            memory.add_payload["messages"],  # type: ignore[index]
            [{"role": "user", "content": "CUSTOMER_1 incident note"}],
        )
        metadata = memory.add_payload["metadata"]  # type: ignore[index]
        self.assertEqual(metadata["sanitized"], True)  # type: ignore[index]
        self.assertEqual(metadata["sanitization_profile"], "default")  # type: ignore[index]
        self.assertEqual(metadata["sanitization_policy_hash"], "test-policy-hash")  # type: ignore[index]
        self.assertEqual(metadata["sanitization_policy_hash_algorithm"], "sha256")  # type: ignore[index]
        self.assertEqual(
            metadata["sanitization_matches"],  # type: ignore[index]
            [{"kind": "term", "rule": "term:CUSTOMER_1", "count": 1}],
        )

    def test_add_memory_rejects_mismatched_user_id_and_metadata_tenant(self) -> None:
        with self.assertRaises(HTTPException):
            add_memory(
                AddRequest(
                    messages="note",
                    user_id="secret-knowledge",
                    metadata={"tenant": "client-acme"},
                )
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
            path="docs/e2e.md",
            type="doc",
            tags=["testing", "e2e"],
            limit=5,
        )

        self.assertEqual(len(client.calls), 2)
        first_filters = client.calls[0]["filters"]  # type: ignore[index]
        second_filters = client.calls[1]["filters"]  # type: ignore[index]
        self.assertEqual(first_filters["user_id"], "secret-knowledge")  # type: ignore[index]
        self.assertEqual(first_filters["tenant"], "secret-knowledge")  # type: ignore[index]
        self.assertEqual(first_filters["repo"], "repo")  # type: ignore[index]
        self.assertEqual(first_filters["path"], "docs/e2e.md")  # type: ignore[index]
        self.assertEqual(first_filters["type"], "doc")  # type: ignore[index]
        self.assertEqual(first_filters["tags"], ["testing", "e2e"])  # type: ignore[index]
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

    def test_get_memory_reads_yaml_config_file(self) -> None:
        class FakeMemory:
            config: dict[str, object] | None = None

            @classmethod
            def from_config(cls, config: dict[str, object]) -> dict[str, object]:
                cls.config = config
                return config

        fake_mem0 = types.SimpleNamespace(Memory=FakeMemory)

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mem0.config.yml"
            config_path.write_text(
                "\n".join(
                    (
                        "vector_store:",
                        "  provider: qdrant",
                        "  config:",
                        "    host: qdrant",
                        "    port: 6333",
                        "    collection_name: developer_memories",
                        "    embedding_model_dims: 1024",
                        "graph_store:",
                        "  provider: falkordb",
                        "  config:",
                        "    url: redis://falkordb:6379",
                        "llm:",
                        "  provider: ollama",
                        "  config:",
                        "    model: qwen3.5:4b",
                        "embedder:",
                        "  provider: ollama",
                        "  config:",
                        "    model: bge-m3",
                    )
                ),
                encoding="utf-8",
            )

            get_memory.cache_clear()
            with (
                patch.dict("os.environ", {"MEM0_CONFIG_FILE": str(config_path)}, clear=True),
                patch.dict(sys.modules, {"mem0": fake_mem0}),
            ):
                memory = get_memory()

            get_memory.cache_clear()

        self.assertEqual(memory["vector_store"]["config"]["host"], "qdrant")  # type: ignore[index]
        self.assertEqual(FakeMemory.config, memory)

    def test_get_memory_rejects_config_json_and_file_together(self) -> None:
        fake_mem0 = types.SimpleNamespace(Memory=object)

        get_memory.cache_clear()
        with (
            patch.dict(
                "os.environ",
                {"MEM0_CONFIG_JSON": "{}", "MEM0_CONFIG_FILE": "/tmp/mem0.config.yml"},
                clear=True,
            ),
            patch.dict(sys.modules, {"mem0": fake_mem0}),
            self.assertRaises(ValueError),
        ):
            get_memory()
        get_memory.cache_clear()

    def test_model_provider_docs_config_file_examples_are_valid(self) -> None:
        docs = (
            Path("docs/architecture/model-provider-settings.md"),
            Path("docs/architecture/model-provider-settings.jp.md"),
        )

        examples: list[dict[str, object]] = []
        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            matches = re.findall(r"```yaml\n(.*?)\n```", text, flags=re.DOTALL)
            config_examples = [
                yaml.safe_load(match) for match in matches if "vector_store:" in match
            ]
            self.assertGreaterEqual(len(config_examples), 3, f"expected config file examples in {doc}")
            examples.extend(config_examples)

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
