from __future__ import annotations

import json
import unittest
import urllib.parse
import urllib.request
from typing import Any
from unittest.mock import patch

from minutes_agent.config import Settings
from minutes_agent.github_glossary import (
    USER_AGENT,
    _fetch_markdown_bundle,
    _get_json,
    _get_raw_text,
    _normalize_glossary,
    _select_markdown_paths,
    fetch_repo_glossary,
    parse_repo_slug,
)


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers: dict[str, str] = {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class ParseRepoSlugTest(unittest.TestCase):
    def test_valid_slug_splits_owner_and_name(self) -> None:
        self.assertEqual(parse_repo_slug("octocat/Hello-World"), ("octocat", "Hello-World"))

    def test_invalid_slug_raises_value_error(self) -> None:
        for invalid in ["not-a-repo", "owner/repo/extra", "", "owner/"]:
            with self.assertRaises(ValueError):
                parse_repo_slug(invalid)


class SelectMarkdownPathsTest(unittest.TestCase):
    def test_filters_to_root_and_docs_markdown_and_prioritizes_readme(self) -> None:
        tree = [
            {"type": "blob", "path": "docs/guide.md"},
            {"type": "blob", "path": "README.md"},
            {"type": "blob", "path": "src/app.py"},
            {"type": "blob", "path": "notes/other.md"},  # not root, not docs/ -> excluded
            {"type": "blob", "path": "CONTRIBUTING.md"},
        ]

        selected = _select_markdown_paths(tree)

        self.assertEqual(selected[0], "README.md")
        self.assertIn("docs/guide.md", selected)
        self.assertIn("CONTRIBUTING.md", selected)
        self.assertNotIn("notes/other.md", selected)
        self.assertNotIn("src/app.py", selected)

    def test_caps_at_max_15_files(self) -> None:
        tree = [{"type": "blob", "path": f"docs/page{i}.md"} for i in range(30)]

        selected = _select_markdown_paths(tree)

        self.assertEqual(len(selected), 15)


class FetchMarkdownBundleTest(unittest.TestCase):
    def test_respects_300kb_total_cap(self) -> None:
        big_chunk = "a" * (200 * 1024)
        with patch(
            "minutes_agent.github_glossary._get_raw_text",
            side_effect=[big_chunk, big_chunk, big_chunk],
        ):
            bundle = _fetch_markdown_bundle(
                "owner", "repo", "main", ["one.md", "two.md", "three.md"]
            )

        self.assertLessEqual(len(bundle.encode("utf-8")), 300 * 1024 + 200)  # ヘッダ分の余裕


class HttpHeaderTest(unittest.TestCase):
    def test_get_json_sends_expected_user_agent(self) -> None:
        captured: dict[str, urllib.request.Request] = {}

        def fake_urlopen(request: urllib.request.Request, timeout: int = 30) -> _FakeResponse:
            captured["request"] = request
            return _FakeResponse(json.dumps({"ok": True}).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _get_json("https://api.github.com/repos/owner/name")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["request"].get_header("User-agent"), USER_AGENT)

    def test_get_raw_text_sends_expected_user_agent(self) -> None:
        captured: dict[str, urllib.request.Request] = {}

        def fake_urlopen(request: urllib.request.Request, timeout: int = 30) -> _FakeResponse:
            captured["request"] = request
            return _FakeResponse(b"hello")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _get_raw_text("https://raw.githubusercontent.com/owner/name/main/README.md")

        self.assertEqual(result, "hello")
        self.assertEqual(captured["request"].get_header("User-agent"), USER_AGENT)


class NormalizeGlossaryTest(unittest.TestCase):
    def test_dedupes_and_caps_at_60_terms(self) -> None:
        payload = [f"term{i}" for i in range(70)] + ["term0"]

        terms = _normalize_glossary(payload)

        self.assertEqual(len(terms), 60)
        self.assertEqual(terms.count("term0"), 1)

    def test_rejects_non_list_payload(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_glossary({"not": "a list"})


class _FakeGenaiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeGenaiModels:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, *, model: str, contents: str, config: Any) -> _FakeGenaiResponse:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return _FakeGenaiResponse(self._text)


class _FakeGenaiClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.models = _FakeGenaiModels(json.dumps(["MiyaIF", "Proto Pedia"]))


class FetchRepoGlossaryEndToEndTest(unittest.TestCase):
    def test_fetch_repo_glossary_orchestrates_fetch_and_distillation(self) -> None:
        repo_info = {"default_branch": "main", "description": "テストリポジトリ"}
        tree_response = {
            "tree": [
                {"type": "blob", "path": "README.md"},
                {"type": "blob", "path": "src/app.py"},
            ]
        }
        contributors_response = [{"login": "hinapupil"}, {"login": "someone"}]

        def fake_urlopen(request: urllib.request.Request, timeout: int = 30) -> _FakeResponse:
            url = request.full_url
            host = urllib.parse.urlparse(url).hostname
            if url.endswith("/repos/hinapupil/minutes-agent"):
                return _FakeResponse(json.dumps(repo_info).encode("utf-8"))
            if "git/trees/main" in url:
                return _FakeResponse(json.dumps(tree_response).encode("utf-8"))
            if "contributors" in url:
                return _FakeResponse(json.dumps(contributors_response).encode("utf-8"))
            if host == "raw.githubusercontent.com":
                return _FakeResponse(b"# README\nMiyaIF is a contributor.")
            raise AssertionError(f"unexpected url: {url}")

        settings = Settings(google_cloud_project="proj")
        with (
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
            patch("google.genai.Client", _FakeGenaiClient),
        ):
            glossary = fetch_repo_glossary(settings, "hinapupil/minutes-agent")

        self.assertEqual(glossary, ["MiyaIF", "Proto Pedia"])


if __name__ == "__main__":
    unittest.main()


class ParseJsonLenientlyTest(unittest.TestCase):
    def test_plain_json_array(self) -> None:
        from minutes_agent.github_glossary import _parse_json_leniently

        self.assertEqual(_parse_json_leniently('["a", "b"]'), ["a", "b"])

    def test_trailing_extra_data_is_ignored(self) -> None:
        from minutes_agent.github_glossary import _parse_json_leniently

        # 実測エラー "Extra data: line N column 1" の再現形: JSON 値の後ろに続きがある
        self.assertEqual(
            _parse_json_leniently('["a", "b"]\n["c"]'),
            ["a", "b"],
        )
        self.assertEqual(
            _parse_json_leniently('["a"]\n以上が用語集です。'),
            ["a"],
        )

    def test_code_fenced_json(self) -> None:
        from minutes_agent.github_glossary import _parse_json_leniently

        self.assertEqual(_parse_json_leniently('```json\n["a", "b"]\n```'), ["a", "b"])
