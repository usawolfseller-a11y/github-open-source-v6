"""Candidate sources: GitHub Search, Hacker News and public Telegram web.

All network sources are synchronous and dependency-light. They return
plain dictionaries so state serialization remains trivial.
"""
from __future__ import annotations

import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests

from .http import USER_AGENT, HttpError, request_json

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_REPO_URL_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:[/?#\s\"'<>)]|$)",
    re.I,
)
_IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_IMAGE_HTML_RE = re.compile(r"<(?:img|source)[^>]+src=[\"']([^\"']+)[\"']", re.I)

BAD_MEDIA_MARKERS = (
    "shields.io",
    "badge",
    "codecov",
    "coveralls",
    "travis-ci",
    "circleci",
    "buy_me_a_coffee",
    "buymeacoffee",
    "ko-fi",
    "sponsor",
    "discord",
    "twitter",
    "github-sponsors",
    "actions/workflows",
)


def full_name_from_url(url: str) -> str:
    match = _REPO_URL_RE.search(str(url or ""))
    if not match:
        return ""
    owner, repo = match.group(1), match.group(2).removesuffix(".git")
    if owner.lower() in {"topics", "search", "features", "marketplace"}:
        return ""
    return f"{owner}/{repo}"


def repo_url(full_name: str) -> str:
    return f"https://github.com/{full_name}"


def map_repo(item: dict[str, Any], source: str) -> dict[str, Any]:
    full_name = str(item.get("full_name") or "")
    return {
        "repo_id": item.get("id"),
        "id": item.get("id"),
        "name": item.get("name") or full_name.split("/")[-1],
        "full_name": full_name,
        "url": item.get("html_url") or repo_url(full_name),
        "description": item.get("description") or "",
        "homepage": item.get("homepage") or "",
        "language": item.get("language") or "",
        "stars": item.get("stargazers_count") or 0,
        "stargazers_count": item.get("stargazers_count") or 0,
        "forks": item.get("forks_count") or 0,
        "forks_count": item.get("forks_count") or 0,
        "open_issues": item.get("open_issues_count") or 0,
        "open_issues_count": item.get("open_issues_count") or 0,
        "topics": list(item.get("topics") or []),
        "license": item.get("license") or {},
        "created_at": item.get("created_at") or "",
        "pushed_at": item.get("pushed_at") or "",
        "updated_at": item.get("updated_at") or "",
        "archived": bool(item.get("archived")),
        "fork": bool(item.get("fork")),
        "disabled": bool(item.get("disabled")),
        "default_branch": item.get("default_branch") or "main",
        "sources": [source],
        "source_name": source,
    }


class GitHubApi:
    def __init__(self, token: str = ""):
        self.token = token.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def get(self, path: str, *, params: dict[str, Any] | None = None, accept: str | None = None):
        headers = {}
        if accept:
            headers["Accept"] = accept
        response = self.session.get(GITHUB_API + path, params=params, headers=headers, timeout=30)
        return response

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> tuple[int, Any, Any]:
        response = self.get(path, params=params)
        try:
            parsed = response.json() if response.content else {}
        except ValueError:
            parsed = {}
        return response.status_code, parsed, response

    def search(self, query: str, *, sort: str = "stars", per_page: int = 25) -> list[dict[str, Any]]:
        status, data, _ = self.get_json(
            "/search/repositories",
            params={"q": query, "sort": sort, "order": "desc", "per_page": per_page},
        )
        if status != 200:
            logger.warning("GitHub search failed status=%s query=%r", status, query)
            return []
        return list(data.get("items") or [])

    def repo(self, full_name: str) -> dict[str, Any] | None:
        status, data, _ = self.get_json(f"/repos/{full_name}")
        if status != 200:
            logger.info("GitHub repo lookup failed %s status=%s", full_name, status)
            return None
        return data

    def contributors_count(self, full_name: str) -> int:
        status, data, response = self.get_json(
            f"/repos/{full_name}/contributors",
            params={"per_page": 1, "anon": "true"},
        )
        if status != 200 or not isinstance(data, list):
            return 0
        link = response.headers.get("Link", "") if response is not None else ""
        match = re.search(r"[?&]page=(\d+)>;\s*rel=\"last\"", link)
        if match:
            return int(match.group(1))
        return len(data)

    def readme(self, full_name: str) -> str:
        response = self.get(
            f"/repos/{full_name}/readme",
            accept="application/vnd.github.raw",
        )
        if response.status_code != 200:
            return ""
        response.encoding = "utf-8"
        return response.text[:80_000]


def build_search_queries(now: datetime | None = None) -> list[tuple[str, str]]:
    now = now or datetime.now(timezone.utc)
    pushed_45 = (now - timedelta(days=45)).date().isoformat()
    pushed_21 = (now - timedelta(days=21)).date().isoformat()
    created_240 = (now - timedelta(days=240)).date().isoformat()
    created_120 = (now - timedelta(days=120)).date().isoformat()
    languages_by_day = [
        ["Python", "TypeScript", "Rust"],
        ["Go", "JavaScript", "Java"],
        ["Python", "Kotlin", "PHP"],
        ["TypeScript", "Rust", "C++"],
        ["Python", "Go", "Ruby"],
        ["TypeScript", "Java", "Shell"],
        ["Rust", "Python", "Swift"],
    ]
    languages = languages_by_day[now.weekday() % len(languages_by_day)]
    queries: list[tuple[str, str]] = []
    for language in languages:
        queries.append(
            (
                f"stars:100..30000 pushed:>={pushed_45} archived:false fork:false language:{language}",
                "stars",
            )
        )
    queries.extend(
        [
            (f"stars:1000..100000 pushed:>={pushed_21} archived:false fork:false", "updated"),
            (f"stars:30..600 created:>={created_120} pushed:>={pushed_21} archived:false fork:false", "stars"),
            (f"created:>={created_240} stars:>=100 pushed:>={pushed_21} archived:false fork:false topic:developer-tools", "stars"),
            (f"stars:>=100 pushed:>={pushed_21} archived:false fork:false topic:self-hosted", "updated"),
            (f"stars:>=100 pushed:>={pushed_21} archived:false fork:false topic:ai", "updated"),
        ]
    )
    return queries


def merge_candidate(target: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> None:
    full_name = str(candidate.get("full_name") or full_name_from_url(str(candidate.get("url") or "")))
    if not full_name:
        return
    candidate["full_name"] = full_name
    key = full_name.lower()
    if key not in target:
        target[key] = candidate
        return
    existing = target[key]
    sources = list(existing.get("sources") or [])
    for source in candidate.get("sources") or []:
        if source not in sources:
            sources.append(source)
    existing["sources"] = sources
    if candidate.get("hn_points"):
        existing["hn_points"] = max(int(existing.get("hn_points") or 0), int(candidate["hn_points"]))
    for field in ("repo_id", "id", "name", "description", "homepage", "language", "license"):
        if not existing.get(field) and candidate.get(field):
            existing[field] = candidate[field]


def collect_GitHub_search(api: GitHubApi, merged: dict[str, dict[str, Any]]) -> None:
    for query, sort in build_search_queries():
        for item in api.search(query, sort=sort, per_page=25):
            merge_candidate(merged, map_repo(item, "github_search"))
        time.sleep(0.15)


def collect_hn(merged: dict[str, dict[str, Any]], *, days: int = 14) -> None:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    status, data, _ = request_json(
        "GET",
        "https://hn.algolia.com/api/v1/search_by_date",
        params={
            "query": "github.com",
            "tags": "story",
            "hitsPerPage": 100,
            "numericFilters": f"created_at_i>{since},points>=5",
        },
        retries=1,
    )
    if status != 200 or not isinstance(data, dict):
        logger.warning("HN Algolia failed status=%s", status)
        return
    for hit in data.get("hits") or []:
        text = " ".join(
            str(hit.get(key) or "") for key in ("url", "story_url", "story_text", "title")
        )
        full_name = full_name_from_url(text)
        if not full_name:
            continue
        merge_candidate(
            merged,
            {
                "full_name": full_name,
                "name": full_name.split("/")[-1],
                "url": repo_url(full_name),
                "sources": ["hacker_news"],
                "source_name": "hacker_news",
                "hn_points": int(hit.get("points") or 0),
                "hn_title": hit.get("title") or "",
            },
        )


def collect_telegram_web(merged: dict[str, dict[str, Any]], channels: tuple[str, ...]) -> None:
    for channel in channels:
        url = f"https://t.me/s/{channel}"
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25)
            if response.status_code != 200:
                logger.info("Telegram web source %s status=%s", channel, response.status_code)
                continue
            text = html.unescape(response.text)
        except requests.RequestException as exc:
            logger.warning("Telegram web source %s failed: %s", channel, type(exc).__name__)
            continue
        found: set[str] = set()
        for owner, repo in _REPO_URL_RE.findall(text):
            full_name = f"{owner}/{repo.removesuffix('.git')}"
            if full_name.lower() in found:
                continue
            found.add(full_name.lower())
            merge_candidate(
                merged,
                {
                    "full_name": full_name,
                    "name": full_name.split("/")[-1],
                    "url": repo_url(full_name),
                    "sources": [f"telegram:{channel}"],
                    "source_name": f"telegram:{channel}",
                },
            )


def collect_candidates(config: Any) -> list[dict[str, Any]]:
    api = GitHubApi(config.GitHub_token)
    merged: dict[str, dict[str, Any]] = {}
    collect_GitHub_search(api, merged)
    collect_hn(merged)
    if config.telegram_source_channels:
        collect_telegram_web(merged, config.telegram_source_channels)
    return list(merged.values())


def resolve_media_url(raw: str, full_name: str, default_branch: str) -> str:
    value = html.unescape(str(raw or "").strip().strip("<>"))
    if not value or value.startswith("data:"):
        return ""
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith("http://"):
        value = "https://" + value[len("http://"):]
    if value.startswith("https://github.com/") and "/blob/" in value:
        value = value.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
    if value.startswith("https://"):
        return value
    value = unquote(value)
    while value.startswith("./"):
        value = value[2:]
    value = value.lstrip("/")
    return f"https://raw.githubusercontent.com/{full_name}/{default_branch}/{value}"


def extract_media_urls(readme: str, full_name: str, default_branch: str = "main") -> list[str]:
    raw_urls: list[str] = []
    raw_urls.extend(_IMAGE_MD_RE.findall(readme or ""))
    raw_urls.extend(_IMAGE_HTML_RE.findall(readme or ""))
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_urls):
        url = resolve_media_url(raw, full_name, default_branch)
        if not url or url in seen:
            continue
        seen.add(url)
        lower = url.lower()
        if any(marker in lower for marker in BAD_MEDIA_MARKERS):
            continue
        parsed = urlparse(url)
        path = parsed.path.lower()
        if not (
            path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
            or "user-images.githubusercontent.com" in parsed.netloc
            or "githubusercontent.com" in parsed.netloc
        ):
            continue
        score = 0
        if path.endswith(".gif"):
            score += 40
        for word in ("demo", "screenshot", "screen", "preview", "banner", "hero", "cover"):
            if word in lower:
                score += 15
        if any(word in lower for word in ("logo", "icon", "avatar")):
            score -= 30
        scored.append((score, -index, url))
    scored.sort(reverse=True)
    return [url for _, _, url in scored[:8]]


def enrich_candidate(api: GitHubApi, candidate: dict[str, Any]) -> dict[str, Any]:
    full_name = str(candidate.get("full_name") or full_name_from_url(str(candidate.get("url") or "")))
    if not full_name:
        return candidate
    candidate["full_name"] = full_name
    if not candidate.get("repo_id") or not candidate.get("license"):
        raw_repo = api.repo(full_name)
        if raw_repo:
            mapped = map_repo(raw_repo, str((candidate.get("sources") or ["unknown"])[0]))
            sources = candidate.get("sources") or []
            hn_points = candidate.get("hn_points")
            candidate.update(mapped)
            candidate["sources"] = sources or mapped.get("sources") or []
            if hn_points is not None:
                candidate["hn_points"] = hn_points
    candidate["contributors_count"] = api.contributors_count(full_name)
    readme = api.readme(full_name)
    candidate["has_readme"] = bool(readme.strip())
    candidate["readme"] = readme
    candidate["readme_excerpt"] = readme[:6000]
    candidate["media_urls"] = extract_media_urls(
        readme,
        full_name,
        str(candidate.get("default_branch") or "main"),
    )
    return candidate


def enrich_candidates(
    api: GitHubApi,
    candidates: list[dict[str, Any]],
    *,
    max_enrich: int = 90,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for candidate in candidates[:max_enrich]:
        try:
            enriched.append(enrich_candidate(api, candidate))
        except (requests.RequestException, HttpError) as exc:
            logger.warning("Enrichment failed for %s: %s", candidate.get("full_name"), type(exc).__name__)
    return enriched
