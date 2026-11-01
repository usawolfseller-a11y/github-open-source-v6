"""v6 — long-form Telegram project post formatter (free, no caption limit).

Why this exists
---------------
A photo caption in Telegram is hard-capped at 1,024 characters.
A text message allows 4,096.  v6 therefore publishes projects as
*text messages* with a large link preview shown above the text
(Bot API ``link_preview_options``), which gives ~4x more room than a
caption while keeping a big visual on top of the post — for free.

Expected project dict keys (superset of the current collector output):
    name, description, url, homepage, language, stars, forks,
    open_issues, contributors_count, topics, license (str | dict),
    last_commit_date | pushed_at | updated_at (ISO-8601),
    primary_use_case, key_features (list[str]), readme_summary,
and optionally (new Gemini schema fields, all optional):
    hook, who_for, why_now, quick_start, verdict, discussion_question

The formatter is pure: no I/O, no network, no templates on disk.
All untrusted strings are HTML-escaped; only https:// links survive.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

#: Telegram counts UTF-16 code units of the *visible* text after entity
#: parsing.  Keep a safety margin below the 4,096 hard limit.
MAX_VISIBLE_UTF16 = 4000

_CATEGORY_EMOJI = [
    (("ai", "llm", "machine-learning", "ml", "agent"), "🤖"),
    (("cli", "terminal", "tui", "shell"), "🖥"),
    (("security", "pentest", "vulnerability"), "🛡️"),
    (("web", "frontend", "react", "vue", "api", "backend"), "🌐"),
    (("data", "database", "analytics", "etl"), "📊"),
    (("game", "gamedev", "unity", "godot"), "🎮"),
    (("android", "ios", "mobile", "flutter"), "📱"),
    (("devops", "docker", "kubernetes", "self-hosted", "selfhosted"), "⚙️"),
]

_LANG_HASHTAG = {"c++": "cpp", "c#": "csharp", "f#": "fsharp", "objective-c": "objc"}


def _esc(value: Any) -> str:
    return html.escape(str(value or "").strip(), quote=False)


def _safe_url(value: Any) -> str:
    url = str(value or "").strip()
    return url if url.startswith("https://") else ""


def _fmt_num(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _license_name(project: dict[str, Any]) -> str:
    lic = project.get("license")
    if isinstance(lic, dict):
        return str(lic.get("spdx_id") or lic.get("name") or "").strip()
    return str(lic or "").strip()


def _activity(project: dict[str, Any]) -> str:
    raw = project.get("last_commit_date") or project.get("pushed_at") or project.get("updated_at")
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    days = max(0, (datetime.now(timezone.utc) - dt).days)
    if days == 0:
        return "🟢 commit today"
    if days == 1:
        return "🟢 commit yesterday"
    if days < 30:
        return f"🟢 commit {days}d ago"
    if days < 365:
        return f"🟡 commit {days // 30}mo ago"
    return f"🔴 commit {days // 365}y ago"


def _emoji(project: dict[str, Any]) -> str:
    haystack = " ".join(
        [str(project.get("name", "")), str(project.get("language", ""))]
        + [str(t) for t in project.get("topics") or []]
    ).lower()
    for keys, emoji in _CATEGORY_EMOJI:
        if any(k in haystack for k in keys):
            return emoji
    return "🚀"


def _hashtags(project: dict[str, Any], limit: int = 6) -> str:
    tags: list[str] = []
    lang = str(project.get("language") or "").strip().lower()
    if lang:
        tags.append(_LANG_HASHTAG.get(lang, re.sub(r"[^a-z0-9]+", "", lang)))
    for topic in project.get("topics") or []:
        tag = re.sub(r"[^a-zA-Z0-9_]+", "_", str(topic).strip().lower()).strip("_")
        if tag and tag not in tags:
            tags.append(tag)
    tags = [t for t in tags if t][:limit]
    tags.append("opensource") if "opensource" not in tags and "open-source" not in tags else None
    return " ".join(f"#{t}" for t in tags)


def visible_text(rendered_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", rendered_html)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(". ", 1)[0]
    return (cut + ".") if len(cut) > limit * 0.5 else text[: limit - 1].rstrip() + "…"


def format_project_post(
    project: dict[str, Any],
    *,
    telegraph_url: str = "",
    expandable_deep_dive: bool = True,
    max_visible: int = MAX_VISIBLE_UTF16,
) -> str:
    """Render one project as Telegram HTML text (<= ``max_visible`` visible chars)."""
    name = _esc(project.get("name") or "Unknown project")
    hook = _clip(str(project.get("hook") or project.get("description") or ""), 140)
    url = _safe_url(project.get("url") or project.get("html_url"))
    homepage = _safe_url(project.get("homepage"))
    telegraph_url = _safe_url(telegraph_url)

    stats_bits = [f"⭐ {_fmt_num(project.get('stars'))}", f"🍴 {_fmt_num(project.get('forks'))}"]
    lic = _license_name(project)
    if lic:
        stats_bits.append(f"📜 {_esc(lic)}")
    activity = _activity(project)
    if activity:
        stats_bits.append(activity)
    lang = str(project.get("language") or "").strip()
    if lang:
        stats_bits.append(f"💻 {_esc(lang)}")

    features = [_clip(str(f), 150) for f in (project.get("key_features") or []) if str(f).strip()][:6]
    summary = _clip(str(project.get("readme_summary") or project.get("primary_use_case") or ""), 650)

    deep_parts: list[str] = []
    if project.get("who_for"):
        deep_parts.append(f"<b>Who it's for:</b> {_esc(_clip(str(project['who_for']), 300))}")
    if project.get("why_now"):
        deep_parts.append(f"<b>Why now:</b> {_esc(_clip(str(project['why_now']), 300))}")
    if project.get("verdict"):
        deep_parts.append(f"<b>Verdict:</b> {_esc(_clip(str(project['verdict']), 280))}")
    if project.get("quick_start"):
        deep_parts.append(f"<b>Quick start:</b>\n<code>{_esc(str(project['quick_start']).strip()[:400])}</code>")

    links: list[str] = []
    if url:
        links.append(f'🔗 <a href="{html.escape(url, quote=True)}">View on GitHub</a>')
    if homepage and homepage != url:
        links.append(f'<a href="{html.escape(homepage, quote=True)}">Homepage</a>')
    if telegraph_url:
        links.append(f'📖 <a href="{html.escape(telegraph_url, quote=True)}">Full breakdown</a>')

    question = _clip(
        str(project.get("discussion_question") or "Would you use this in production? Tell us in the comments ↓"),
        160,
    )

    def render(feats: list[str], deep: list[str], summ: str) -> str:
        lines = [f"{_emoji(project)} <b>{name}</b>" + (f" — {_esc(hook)}" if hook else "")]
        lines.append(" · ".join(stats_bits))
        if project.get("is_dual_use"):
            lines.append("⚠️ <b>Dual-use security tool</b> — for security research & education.")
        if summ:
            lines += ["", _esc(summ)]
        if feats:
            lines += ["", "✨ <b>Key features:</b>"] + [f"• {_esc(f)}" for f in feats]
        if deep:
            tag = "<blockquote expandable>" if expandable_deep_dive else "<blockquote>"
            lines += ["", tag + "\n\n".join(deep) + "</blockquote>"]
        lines += ["", f"💬 <i>{_esc(question)}</i>"]
        if links:
            lines.append(" · ".join(links))
        lines.append("⭐ <i>Enjoy it? Star the repo to support the author.</i>")
        ht = _hashtags(project)
        if ht:
            lines.append(ht)
        return "\n".join(lines)

    out = render(features, deep_parts, summary)
    # Trim least-valuable material first; keep hook, stats, links intact.
    while utf16_len(visible_text(out)) > max_visible and len(features) > 3:
        features.pop()
        out = render(features, deep_parts, summary)
    while utf16_len(visible_text(out)) > max_visible and deep_parts:
        deep_parts.pop()
        out = render(features, deep_parts, summary)
    while utf16_len(visible_text(out)) > max_visible and summary:
        summary = _clip(summary, max(120, len(summary) - 150))
        out = render(features, deep_parts, summary)
    if utf16_len(visible_text(out)) > max_visible:  # pathological metadata; hard fallback
        out = render(features[:3], [], _clip(summary, 200))
    return out
