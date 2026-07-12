from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from minutes_agent.config import Settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
RAW_CONTENT_BASE = "https://raw.githubusercontent.com"
# GitHub API は User-Agent 無しのリクエストを 403 で拒否するため必ず付与する
# (minutes_agent/discord.py と同じ UA 文字列で揃える)
USER_AGENT = "MinutesAgent (https://github.com/hinapupil/minutes-agent, 0.1)"
REQUEST_TIMEOUT_SECONDS = 30

MAX_MARKDOWN_FILES = 15
MAX_MARKDOWN_TOTAL_BYTES = 300 * 1024
MAX_GLOSSARY_TERMS = 60

REPO_SLUG_PATTERN = re.compile(r"^[\w.-]+/[\w.-]+$")

GLOSSARY_PROMPT_TEMPLATE = """\
あなたは音声認識の誤変換を補正するための議事録用語集を作るエージェントです。
以下はある GitHub プロジェクトの情報です。固有名詞・プロダクト名・人名（コントリビューター）・
技術用語のうち、音声会議で登場しうる語を抽出してください。

制約:
- 出力は JSON 配列（文字列の配列）のみ
- 各要素は「用語（よみ・別表記があれば併記）」の形式（よみや別表記が不明なら用語のみでよい）
- 最大 {max_terms} 語
- 一般的すぎる単語（例:「実装」「テスト」）は含めない
- プロジェクト固有の名詞を優先する

リポジトリ: {repo}
説明: {description}

コントリビューター:
{contributors}

ファイル一覧（抜粋）:
{file_paths}

README / ドキュメント抜粋:
{markdown_bundle}
"""


def parse_repo_slug(repo: str) -> tuple[str, str]:
    if not REPO_SLUG_PATTERN.match(repo):
        raise ValueError(f"repo は owner/repo 形式で指定してください: {repo!r}")
    owner, name = repo.split("/", 1)
    return owner, name


def fetch_repo_glossary(settings: Settings, repo: str) -> list[str]:
    owner, name = parse_repo_slug(repo)
    repo_info = _get_repo_info(owner, name)
    default_branch = str(repo_info.get("default_branch") or "main")
    description = str(repo_info.get("description") or "")

    tree = _get_tree(owner, name, default_branch)
    file_paths = [
        str(entry.get("path"))
        for entry in tree
        if entry.get("type") == "blob" and entry.get("path")
    ]
    contributors = _get_contributors(owner, name)
    markdown_paths = _select_markdown_paths(tree)
    markdown_bundle = _fetch_markdown_bundle(owner, name, default_branch, markdown_paths)

    return _distill_glossary(
        settings,
        repo=repo,
        description=description,
        file_paths=file_paths,
        contributors=contributors,
        markdown_bundle=markdown_bundle,
    )


def _get_repo_info(owner: str, name: str) -> dict[str, Any]:
    try:
        data = _get_json(f"{GITHUB_API_BASE}/repos/{owner}/{name}")
    except _NotFoundError as exc:
        raise ValueError(
            f"リポジトリ {owner}/{name} が見つかりません（public か確認してください）"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected GitHub response for repos/{owner}/{name}")
    return data


def _get_tree(owner: str, name: str, branch: str) -> list[dict[str, Any]]:
    try:
        data = _get_json(f"{GITHUB_API_BASE}/repos/{owner}/{name}/git/trees/{branch}?recursive=1")
    except (_NotFoundError, RuntimeError) as exc:
        logger.warning("failed to fetch tree for %s/%s@%s: %s", owner, name, branch, exc)
        return []
    if not isinstance(data, dict):
        return []
    tree = data.get("tree")
    if not isinstance(tree, list):
        return []
    return [entry for entry in tree if isinstance(entry, dict)]


def _get_contributors(owner: str, name: str) -> list[str]:
    try:
        data = _get_json(f"{GITHUB_API_BASE}/repos/{owner}/{name}/contributors?per_page=30")
    except (_NotFoundError, RuntimeError) as exc:
        logger.warning("failed to fetch contributors for %s/%s: %s", owner, name, exc)
        return []
    if not isinstance(data, list):
        return []
    logins: list[str] = []
    for entry in data:
        if isinstance(entry, dict):
            login = entry.get("login")
            if isinstance(login, str) and login:
                logins.append(login)
    return logins


def _select_markdown_paths(tree: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "")
        if not path.lower().endswith(".md"):
            continue
        is_root_markdown = "/" not in path
        is_docs_markdown = path.startswith("docs/")
        if is_root_markdown or is_docs_markdown:
            candidates.append(path)

    def sort_key(path: str) -> tuple[int, str]:
        # README を最優先で読む
        is_readme = path.upper() in {"README.MD"}
        return (0 if is_readme else 1, path)

    candidates.sort(key=sort_key)
    return candidates[:MAX_MARKDOWN_FILES]


def _fetch_markdown_bundle(owner: str, name: str, branch: str, paths: list[str]) -> str:
    collected: list[str] = []
    total_bytes = 0
    for path in paths:
        if total_bytes >= MAX_MARKDOWN_TOTAL_BYTES:
            break
        url = f"{RAW_CONTENT_BASE}/{owner}/{name}/{branch}/{path}"
        try:
            content = _get_raw_text(url)
        except RuntimeError as exc:
            logger.warning("failed to fetch raw content %s: %s", path, exc)
            continue
        if content is None:
            continue
        remaining = MAX_MARKDOWN_TOTAL_BYTES - total_bytes
        encoded = content.encode("utf-8")
        if len(encoded) > remaining:
            content = encoded[:remaining].decode("utf-8", errors="ignore")
        total_bytes += len(content.encode("utf-8"))
        collected.append(f"## {path}\n{content}")
    return "\n\n".join(collected)


class _NotFoundError(RuntimeError):
    pass


def _get_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise _NotFoundError(f"GitHub リソースが見つかりません: {url}") from exc
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {url}") from exc
    return json.loads(body)


def _get_raw_text(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            text: str = response.read().decode("utf-8", errors="ignore")
            return text
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"GitHub raw content returned HTTP {exc.code}: {url}") from exc


def _distill_glossary(
    settings: Settings,
    *,
    repo: str,
    description: str,
    file_paths: list[str],
    contributors: list[str],
    markdown_bundle: str,
) -> list[str]:
    from google import genai
    from google.genai import types

    if settings.gemini_api_key:
        client = genai.Client(api_key=settings.gemini_api_key)
    else:
        settings.require("google_cloud_project")
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

    prompt = GLOSSARY_PROMPT_TEMPLATE.format(
        max_terms=MAX_GLOSSARY_TERMS,
        repo=repo,
        description=description.strip() or "（説明なし）",
        contributors="\n".join(f"- {login}" for login in contributors) or "（情報なし）",
        file_paths="\n".join(f"- {path}" for path in file_paths[:200]) or "（情報なし）",
        markdown_bundle=markdown_bundle.strip() or "（本文なし）",
    )
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini response did not contain text")
    payload = _parse_json_leniently(text)
    return _normalize_glossary(payload)


def _parse_json_leniently(text: str) -> Any:
    # response_mime_type="application/json" 指定でも、モデルは JSON 値の後ろに
    # 余分なテキストや2つ目の JSON を続けることがある（実測: "Extra data" エラー）。
    # コードフェンスを剥がし、先頭の JSON 値だけを採用する
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        value, _index = json.JSONDecoder().raw_decode(cleaned)
        return value


def _normalize_glossary(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        raise ValueError(f"用語集の応答が配列ではありません: {type(payload).__name__}")
    terms: list[str] = []
    seen: set[str] = set()
    for item in payload:
        term = str(item).strip()
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= MAX_GLOSSARY_TERMS:
            break
    return terms
