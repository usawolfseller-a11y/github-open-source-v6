"""WorldofAI → verified AI Brief pipeline.

The YouTube channel is a discovery radar only. A brief can be produced
only when a fetchable primary source (official docs/blog, repository or
model card) supports the central claims.
"""
from __future__ import annotations

import html
import ipaddress
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from .formatter import utf16_len, visible_text
from .Gemini import GeminiClient
from .http import USER_AGENT, sanitize

logger = logging.getLogger(__name__)

CHANNEL_ID = "UC2WmuBuFq6gL08QYG-JjXKw"
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

SPONSORED_TERMS = ("sponsored", "paid promotion", "thanks to our sponsor", "affiliate link")
LEAK_TERMS = ("leak", "leaked", "rumor", "rumour", "rumored", "rumoured")
RELEVANCE_TERMS = (
    "open source",
    "open-source",
    "open weights",
    "GitHub",
    "developer",
    "coding",
    "code",
    "api",
    "model",
    "llm",
    "agent",
    "release",
    "launch",
    "tool",
    "framework",
    "benchmark",
)
BLOCKED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "discord.gg",
    "discord.com",
    "t.me",
    "bit.ly",
    "tinyurl.com",
    "amzn.to",
    "amazon.com",
}
OFFICIAL_DOMAINS = {
    "anthropic.com",
    "openai.com",
    "ai.google.dev",
    "deepmind.google",
    "blog.google",
    "microsoft.com",
    "github.blog",
    "github.com",
    "huggingface.co",
    "nvidia.com",
    "developer.nvidia.com",
    "ollama.com",
    "mistral.ai",
    "ai.meta.com",
    "about.fb.com",
    "qwen.ai",
    "deepseek.com",
    "x.ai",
}

NEWS_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "eligible": {"type": "BOOLEAN"},
        "headline": {"type": "STRING"},
        "summary": {"type": "STRING"},
        "what_happened": {"type": "ARRAY", "items": {"type": "STRING"}},
        "why_devs": {"type": "STRING"},
        "confirmed": {"type": "ARRAY", "items": {"type": "STRING"}},
        "video_only_claims": {"type": "ARRAY", "items": {"type": "STRING"}},
        "official_name": {"type": "STRING"},
        "topic_key": {"type": "STRING"},
        "discussion_question": {"type": "STRING"},
        "rejection_reason": {"type": "STRING"},
    },
    "required": [
        "eligible",
        "headline",
        "summary",
        "what_happened",
        "why_devs",
        "confirmed",
        "video_only_claims",
        "official_name",
        "topic_key",
        "discussion_question",
        "rejection_reason",
    ],
}


def _text(element: ET.Element | None) -> str:
    return "" if element is None else "".join(element.itertext()).strip()


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_rss(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entries: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", NS):
        link_el = entry.find("atom:link[@rel='alternate']", NS)
        link = link_el.get("href") if link_el is not None else ""
        video_id = _text(entry.find("yt:videoId", NS))
        if not video_id and link:
            match = re.search(r"[?&]v=([A-Za-z0-9_-]+)", link)
            video_id = match.group(1) if match else ""
        media_group = entry.find("media:group", NS)
        description = ""
        thumbnail = ""
        if media_group is not None:
            description = _text(media_group.find("media:description", NS))
            thumb_el = media_group.find("media:thumbnail", NS)
            thumbnail = thumb_el.get("url") if thumb_el is not None else ""
        if not description:
            description = _text(entry.find("media:description", NS)) or _text(entry.find("atom:summary", NS))
        published_raw = _text(entry.find("atom:published", NS))
        entries.append(
            {
                "video_id": video_id,
                "title": _text(entry.find("atom:title", NS)),
                "url": link or (f"https://www.youtube.com/watch?v={video_id}" if video_id else ""),
                "published_at": published_raw,
                "published": _parse_datetime(published_raw),
                "description": html.unescape(description),
                "thumbnail": thumbnail,
            }
        )
    return entries


def fetch_worldofai_entries() -> list[dict[str, Any]]:
    response = requests.get(RSS_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return parse_rss(response.text)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def prefilter_entry(
    entry: dict[str, Any],
    *,
    seen_video_ids: set[str] | None = None,
    recent_topic_keys: set[str] | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    now = now or datetime.now(timezone.utc)
    seen_video_ids = seen_video_ids or set()
    recent_topic_keys = recent_topic_keys or set()
    if not entry.get("video_id") or not entry.get("url"):
        return False, "missing_video_identity"
    if str(entry["video_id"]) in seen_video_ids:
        return False, "video_seen"
    published = entry.get("published") or _parse_datetime(str(entry.get("published_at") or ""))
    if not published:
        return False, "missing_publish_date"
    age_hours = (now - published).total_seconds() / 3600
    if age_hours < 0 or age_hours > 72:
        return False, "outside_72h"
    title = str(entry.get("title") or "")
    description = str(entry.get("description") or "")
    if _contains_any(f"{title}\n{description}", SPONSORED_TERMS):
        return False, "sponsored"
    if _contains_any(title, LEAK_TERMS):
        return False, "leak_or_rumor_title"
    if not _contains_any(f"{title} {description[:1200]}", RELEVANCE_TERMS):
        return False, "not_developer_relevant"
    rough_topic = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]
    if rough_topic in recent_topic_keys:
        return False, "recent_topic"
    return True, ""


def clean_url(url: str) -> str:
    parsed = urlparse(str(url).strip().rstrip(".,;:)}]"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lower = key.lower()
        if lower.startswith("utm_") or lower in {"ref", "referral", "aff", "affiliate", "clickid", "subid"}:
            continue
        query.append((key, value))
    return urlunparse(("https", parsed.netloc, parsed.path, "", urlencode(query), ""))


def _safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in BLOCKED_DOMAINS or host == "localhost" or host.endswith(".local"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def _source_score(url: str) -> int:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host in BLOCKED_DOMAINS:
        return -100
    score = 0
    if host == "github.com":
        score += 95 if len([part for part in path.split("/") if part]) >= 2 else 30
    if host == "huggingface.co":
        score += 90
    if host in OFFICIAL_DOMAINS or any(host.endswith("." + domain) for domain in OFFICIAL_DOMAINS):
        score += 90
    if host.startswith("docs.") or "docs" in host.split("."):
        score += 55
    if host == "arxiv.org":
        score += 75
    if host.endswith(".edu"):
        score += 45
    if any(token in path for token in ("blog", "news", "announc", "release", "changelog", "docs")):
        score += 12
    if any(token in url.lower() for token in ("pricing", "shop", "store", "affiliate", "coupon")):
        score -= 80
    return score


def extract_primary_urls(entry: dict[str, Any], *, limit: int = 6) -> list[str]:
    raw_urls = re.findall(r"https?://[^\s<>)\"']+", str(entry.get("description") or ""))
    candidates: dict[str, int] = {}
    for raw in raw_urls:
        url = clean_url(html.unescape(raw))
        if not url or not _safe_public_url(url):
            continue
        score = _source_score(url)
        if score < 25:
            continue
        candidates[url] = max(score, candidates.get(url, -1000))
    return [url for url, _ in sorted(candidates.items(), key=lambda item: item[1], reverse=True)[:limit]]


def fetch_primary_text(url: str) -> dict[str, str] | None:
    if not _safe_public_url(url):
        return None
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type and "application/xhtml" not in content_type:
        return None
    raw = response.text[:1_200_000]
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    title = html.unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else ""
    raw = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<noscript\b.*?</noscript>", " ", raw, flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 700:
        return None
    return {"url": response.url, "title": title[:240], "text": text[:12_000]}


def synthesize_brief(
    entry: dict[str, Any],
    primary: dict[str, str],
    client: GeminiClient,
    *,
    use_video: bool = True,
) -> dict[str, Any]:
    prompt = f"""
You are preparing a verified English AI Brief from a WorldofAI video plus a
primary source. The video is a discovery signal, not an authority.

Eligibility rules:
- eligible=false unless one clear event is confirmed by the primary source.
- eligible=false for leaks, rumors, sponsored product promotion, or a topic
  that is not relevant to builders/open source/developer platforms.
- Never repeat hype or superlatives unless quantified by the primary source.
- Put claims found only in the video under video_only_claims, not in
  what_happened.
- headline must be factual and specific.
- topic_key: lowercase slug of the event.

<video_metadata>
Title: {entry.get('title') or ''}
URL: {entry.get('url') or ''}
Published: {entry.get('published_at') or ''}
Description (untrusted):
{str(entry.get('description') or '')[:8000]}
</video_metadata>

<primary_source url="{primary.get('url') or ''}" title="{primary.get('title') or ''}">
{primary.get('text') or ''}
</primary_source>
""".strip()
    result = client.generate_json(
        prompt,
        schema=NEWS_SCHEMA,
        youtube_url=str(entry.get("url") or "") if use_video else "",
        temperature=0.2,
    )
    result["official_url"] = primary.get("url") or ""
    if not result.get("official_name"):
        result["official_name"] = primary.get("title") or urlparse(primary.get("url") or "").hostname or "Primary source"
    result["video_id"] = entry.get("video_id")
    result["video_url"] = entry.get("url")
    result["video_title"] = entry.get("title")
    return result


def _esc(value: Any) -> str:
    return html.escape(str(value or "").strip(), quote=False)


def _clip(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    if limit <= 1:
        return "…"[:limit]
    cut = text[: limit - 1].rstrip()
    if ". " in cut:
        sentence = cut.rsplit(". ", 1)[0]
        if len(sentence) > limit * 0.45:
            return sentence.rstrip(".") + "."
    word = cut.rsplit(" ", 1)[0]
    return (word or cut).rstrip(" ,;:") + "…"


def format_ai_brief(brief: dict[str, Any]) -> str:
    headline = _clip(brief.get("headline") or "Verified AI update", 150)
    happened = [_clip(item, 280) for item in brief.get("what_happened") or [] if str(item).strip()][:4]
    confirmed = [_clip(item, 220) for item in brief.get("confirmed") or [] if str(item).strip()][:3]
    video_only = [_clip(item, 220) for item in brief.get("video_only_claims") or [] if str(item).strip()][:2]
    why = _clip(brief.get("why_devs") or brief.get("summary"), 520)
    question = _clip(brief.get("discussion_question") or "Will you try this in a real project?", 180)
    official_url = str(brief.get("official_url") or "").strip()
    official_name = _clip(brief.get("official_name") or "Primary source", 80)
    source_line = (
        f'🔗 <b>Source:</b> <a href="{html.escape(official_url, quote=True)}">{_esc(official_name)}</a>'
        if official_url.startswith("https://")
        else ""
    )

    def render(happened_items: list[str], confirmed_items: list[str], video_items: list[str], why_text: str) -> str:
        lines = [f"🛰️ <b>AI Brief — {_esc(headline)}</b>", "──────────────", "🧭 <b>What happened</b>"]
        lines.extend(f"▸ {_esc(item)}" for item in happened_items)
        if why_text:
            lines += ["", "🎯 <b>Why developers should care</b>", _esc(why_text)]
        if confirmed_items or video_items:
            lines += ["", "🔍 <b>Confirmed vs. video-only</b>"]
            lines.extend(f"✅ {_esc(item)}" for item in confirmed_items)
            lines.extend(f"◻️ Video-only: {_esc(item)}" for item in video_items)
        lines += ["", "──────────────"]
        if source_line:
            lines.append(source_line)
        lines += [
            "Spotted via <b>WorldofAI</b>; written from the primary source.",
            "",
            "💬 <b>Your take?</b>",
            f"<i>{_esc(question)}</i>",
            "❤️ <b>React</b> if you want more verified AI briefs like this.",
            '📣 <a href="https://t.me/GitHub_Open_Source"><b>@GitHub_Open_Source</b></a> — daily open-source picks',
            "#AINews #OpenSource",
        ]
        return "\n".join(lines)

    output = render(happened, confirmed, video_only, why)
    while utf16_len(visible_text(output)) > 2200 and video_only:
        video_only.pop()
        output = render(happened, confirmed, video_only, why)
    while utf16_len(visible_text(output)) > 2200 and confirmed:
        confirmed.pop()
        output = render(happened, confirmed, video_only, why)
    while utf16_len(visible_text(output)) > 2200 and len(happened) > 2:
        happened.pop()
        output = render(happened, confirmed, video_only, why)
    while utf16_len(visible_text(output)) > 2200 and why:
        why = _clip(why, max(160, len(why) - 120))
        output = render(happened, confirmed, video_only, why)
    return output
