"""Platform-native content adapters.

Gemini produces one canonical, fact-checked content object.  This
module turns that object into native copy for each surface instead of
copy/pasting the same paragraph everywhere:

* Bluesky: one sharp idea + repo link, hard 300-character budget.
* Mastodon: scannable 500-character community post with CamelCase tags.
* Facebook: plain-language Page post with context and a question.
* dev.to: searchable article wrapper with TL;DR and discussion CTA.

The voice is intentionally stable across surfaces: a curious senior
developer-editor.  No fake first-person testing, no inherited hype,
benefit first, proof points second, details progressively disclosed.
"""
from __future__ import annotations

import re
from typing import Any

BLUESKY_LIMIT = 300
MASTODON_LIMIT = 500
FACEBOOK_TARGET = 1800

_LANG_TAG = {
    "c++": "cpp",
    "c#": "csharp",
    "f#": "fsharp",
    "objective-c": "objc",
    "jupyter notebook": "jupyter",
}

_DEVTO_TAG_ALIASES = {
    "developer-tools": "devtools",
    "developertools": "devtools",
    "machine-learning": "machinelearning",
    "open-source": "opensource",
}

_GENERIC_TOPICS = {"GitHub", "awesome", "awesome-list", "open-source", "opensource"}


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clip_text(value: Any, limit: int) -> str:
    text = clean_text(value)
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= 1:
        return "…"[:limit]
    cut = text[: limit - 1].rstrip()
    if ". " in cut:
        sentence = cut.rsplit(". ", 1)[0]
        if len(sentence) >= max(35, int(limit * 0.55)):
            return sentence.rstrip(".") + "."
    word = cut.rsplit(" ", 1)[0]
    return (word or cut).rstrip(" ,;:") + "…"


def _sentences(value: Any, limit: int) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for part in parts:
        candidate = f"{out} {part}".strip()
        if len(candidate) > limit:
            break
        out = candidate
    return out or clip_text(text, limit)


def _fmt_num(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def license_name(record: dict[str, Any]) -> str:
    lic = record.get("license")
    if isinstance(lic, dict):
        return clean_text(lic.get("spdx_id") or lic.get("name") or "")
    return clean_text(lic)


def record_name(record: dict[str, Any]) -> str:
    return clean_text(record.get("name") or record.get("full_name") or "Open-source project")


def repo_url(record: dict[str, Any]) -> str:
    url = clean_text(record.get("url") or record.get("html_url") or "")
    if url.startswith("https://"):
        return url
    full_name = clean_text(record.get("full_name") or "")
    return f"https://github.com/{full_name}" if "/" in full_name else ""


def public_telegram_link(record: dict[str, Any]) -> str:
    link = clean_text(record.get("telegram_link") or "")
    if not link.startswith("https://t.me/"):
        return ""
    if "/c/" in link or "/+" in link or "joinchat" in link:
        return ""
    return link


def breakdown_url(record: dict[str, Any]) -> str:
    telegraph = clean_text(record.get("telegraph_url") or "")
    if telegraph.startswith("https://"):
        return telegraph
    return public_telegram_link(record)


def Facebook_link_url(record: dict[str, Any]) -> str:
    return breakdown_url(record) or repo_url(record)


def _generated(record: dict[str, Any], generated: dict[str, Any] | None) -> dict[str, Any]:
    if generated is not None:
        return generated
    value = record.get("generated")
    return value if isinstance(value, dict) else {}


def _hook(record: dict[str, Any], generated: dict[str, Any]) -> str:
    return clip_text(
        generated.get("hook") or generated.get("social_text") or record.get("description") or "",
        160,
    )


def _summary(record: dict[str, Any], generated: dict[str, Any]) -> str:
    return clean_text(generated.get("summary") or record.get("description") or "")


def _features(generated: dict[str, Any]) -> list[str]:
    features: list[str] = []
    for item in generated.get("key_features") or []:
        value = clip_text(item, 120)
        if value and value not in features:
            features.append(value)
    return features


def _lead(record: dict[str, Any], generated: dict[str, Any]) -> str:
    name = record_name(record)
    hook = _hook(record, generated).rstrip(".")
    if not hook:
        return name
    if hook.lower().startswith(name.lower()):
        return hook
    return f"{name} — {hook[0].lower() + hook[1:] if len(hook) > 1 else hook.lower()}"


def _detail(record: dict[str, Any], generated: dict[str, Any]) -> str:
    summary = _sentences(_summary(record, generated), 220)
    hook = _hook(record, generated)
    if summary and summary.lower() not in hook.lower() and hook.lower() not in summary.lower():
        return summary
    for key in ("why_now", "verdict", "who_for"):
        value = clip_text(generated.get(key), 190)
        if value:
            return value
    features = _features(generated)
    return features[0] if features else summary


def _tag_words(value: Any) -> list[str]:
    raw = clean_text(value).lower()
    raw = _LANG_TAG.get(raw, raw)
    return [word for word in re.split(r"[^a-z0-9]+", raw) if word]


def _camel_tag(value: Any) -> str:
    words = _tag_words(value)
    if not words:
        return ""
    if words == ["opensource"] or words == ["open", "source"]:
        return "OpenSource"
    return "".join(word[:1].upper() + word[1:] for word in words)


def _lower_tag(value: Any) -> str:
    raw = clean_text(value).lower()
    raw = _LANG_TAG.get(raw, raw)
    return re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")


def _raw_tag_values(record: dict[str, Any], generated: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for value in (
        record.get("language"),
        generated.get("category") or record.get("category"),
        *(record.get("topics") or []),
    ):
        text = clean_text(value)
        if text and text.lower() not in _GENERIC_TOPICS and text not in values:
            values.append(text)
    return values


def hashtags(
    record: dict[str, Any],
    generated: dict[str, Any] | None = None,
    *,
    limit: int = 4,
    camel: bool = True,
) -> str:
    generated = _generated(record, generated)
    formatter = _camel_tag if camel else _lower_tag
    tags: list[str] = []
    seen: set[str] = set()
    for value in ["open source", *_raw_tag_values(record, generated)]:
        tag = formatter(value)
        key = tag.lower()
        if tag and key not in seen:
            tags.append(tag)
            seen.add(key)
        if len(tags) >= limit:
            break
    return " ".join(f"#{tag}" for tag in tags[:limit])


def devto_tags(record: dict[str, Any], generated: dict[str, Any] | None = None) -> list[str]:
    generated = _generated(record, generated)
    tags: list[str] = []

    def add(value: Any) -> None:
        raw = clean_text(value).lower()
        raw = _DEVTO_TAG_ALIASES.get(raw, raw)
        tag = re.sub(r"[^a-z0-9]+", "", _LANG_TAG.get(raw, raw))[:30]
        if tag and tag not in tags:
            tags.append(tag)

    add("opensource")
    add(record.get("language"))
    add(generated.get("category") or record.get("category"))
    for topic in record.get("topics") or []:
        add(topic)
        if len(tags) >= 4:
            break
    if len(tags) < 4:
        add("GitHub")
    return tags[:4]


def image_alt_text(record: dict[str, Any], generated: dict[str, Any] | None = None) -> str:
    generated = _generated(record, generated)
    name = clean_text(record.get("full_name") or record_name(record))
    hook = clip_text(_hook(record, generated) or _summary(record, generated), 180)
    facts = [
        clean_text(record.get("language") or ""),
        license_name(record),
        f"⭐ {_fmt_num(record.get('stars'))}" if record.get("stars") is not None else "",
    ]
    fact_text = ", ".join(part for part in facts if part)
    kind = clean_text(record.get("visual_kind") or "")
    if kind == "readme":
        prefix = f"Demo or screenshot from the README of {name}."
    elif kind == "card":
        prefix = f"Branded cover card for {name}."
    elif kind == "opengraph":
        prefix = f"GitHub preview image for {name}."
    else:
        prefix = f"Cover image for {name}."
    return clip_text(" ".join(part for part in [prefix, hook, fact_text] if part), 420)


def _fit_parts(parts: list[str], limit: int) -> str:
    text = "\n\n".join(part for part in parts if part).strip()
    if len(text) <= limit:
        return text
    # Preserve the final link/tag block.  Shorten everything before it.
    if len(parts) < 2:
        return clip_text(text, limit)
    suffix = parts[-1]
    body = "\n\n".join(parts[:-1])
    budget = max(0, limit - len(suffix) - 2)
    return (clip_text(body, budget) + "\n\n" + suffix).strip()[:limit].rstrip()


def build_bluesky_text(record: dict[str, Any], generated: dict[str, Any] | None = None) -> str:
    generated = _generated(record, generated)
    url = repo_url(record) or breakdown_url(record)
    tags = hashtags(record, generated, limit=2, camel=True)
    suffix = " ".join(part for part in [url, tags] if part)
    lead = _lead(record, generated)
    body_budget = max(60, BLUESKY_LIMIT - len(suffix) - 2)
    lead = clip_text(lead, min(150, body_budget))
    remaining = body_budget - len(lead) - 2
    parts = [lead]
    if remaining >= 45:
        # Prefer a complete concrete detail over an ellipsized summary.
        candidates = [
            *(_features(generated)[:2]),
            clip_text(generated.get("verdict"), 180),
            clip_text(generated.get("social_text"), 180),
            clip_text(generated.get("why_now"), 190),
            _detail(record, generated),
        ]
        detail = ""
        for candidate in candidates:
            candidate = clean_text(candidate)
            if candidate and candidate.lower() not in lead.lower() and len(candidate) <= remaining:
                detail = candidate
                break
        if not detail:
            detail = clip_text(_detail(record, generated), remaining)
        if detail:
            parts.append(detail)
    if suffix:
        parts.append(suffix)
    return _fit_parts(parts, BLUESKY_LIMIT)


def build_mastodon_text(record: dict[str, Any], generated: dict[str, Any] | None = None) -> str:
    generated = _generated(record, generated)
    lead = clip_text(_lead(record, generated), 190)
    bullets = [f"• {feature}" for feature in _features(generated)[:2]]
    if not bullets:
        detail = clip_text(_detail(record, generated), 180)
        bullets = [detail] if detail else []
    links: list[str] = []
    url = repo_url(record)
    if url:
        links.append(f"Repo: {url}")
    breakdown = breakdown_url(record)
    if breakdown and breakdown != url:
        links.append(f"Breakdown: {breakdown}")
    tags = hashtags(record, generated, limit=4, camel=True)
    parts = [lead, "\n".join(bullets), "\n".join(links), tags]
    text = _fit_parts([part for part in parts if part], MASTODON_LIMIT)
    if len(text) > MASTODON_LIMIT and breakdown:
        parts = [lead, "\n".join(bullets), f"Repo: {url}" if url else "", tags]
        text = _fit_parts([part for part in parts if part], MASTODON_LIMIT)
    return text


def build_Facebook_text(record: dict[str, Any], generated: dict[str, Any] | None = None) -> str:
    generated = _generated(record, generated)
    name = record_name(record)
    hook = _hook(record, generated)
    title = f"🚀 {name} — {hook}" if hook and not hook.lower().startswith(name.lower()) else f"🚀 {hook or name}"
    proof_bits = [
        f"⭐ {_fmt_num(record.get('stars'))} stars" if record.get("stars") is not None else "",
        clean_text(record.get("language") or ""),
        license_name(record),
    ]
    proof = " · ".join(bit for bit in proof_bits if bit)
    summary = _sentences(_summary(record, generated), 460)
    why = clip_text(generated.get("why_now") or generated.get("verdict"), 280)
    who = clip_text(generated.get("who_for"), 240)
    quick = str(generated.get("quick_start") or "").strip()
    quick_lines = "\n".join(line.rstrip() for line in quick.splitlines()[:5])[:360]
    question = clip_text(
        generated.get("discussion_question") or "Would you try this in a real project? Why?",
        180,
    )
    features = _features(generated)[:3]
    parts = [title]
    if proof:
        parts.append(proof)
    if record.get("is_dual_use") or generated.get("safety") == "dual_use":
        parts.append("⚠️ Dual-use security tool — shared for security research and education.")
    if summary:
        parts.append(summary)
    if features:
        parts.append("What stands out:\n" + "\n".join(f"• {feature}" for feature in features))
    if why:
        parts.append(f"Why it matters: {why}")
    if who:
        parts.append(f"Good fit for: {who}")
    if quick_lines:
        parts.append("Quick start:\n" + quick_lines)
    parts.append(question)
    links: list[str] = []
    url = repo_url(record)
    if url:
        links.append(f"GitHub: {url}")
    breakdown = breakdown_url(record)
    if breakdown and breakdown != url:
        links.append(f"Full breakdown: {breakdown}")
    if links:
        parts.append("\n".join(links))
    parts.append(hashtags(record, generated, limit=3, camel=True))
    text = "\n\n".join(part for part in parts if part).strip()
    if len(text) <= FACEBOOK_TARGET:
        return text
    # Facebook can carry more, but the editorial target keeps it readable.
    shorter = [title, proof, summary, f"Why it matters: {why}" if why else "", question, "\n".join(links), hashtags(record, generated, limit=3, camel=True)]
    return clip_text("\n\n".join(part for part in shorter if part), FACEBOOK_TARGET)


def build_crosspost_text(
    platform: str,
    record: dict[str, Any],
    generated: dict[str, Any] | None = None,
) -> str:
    key = clean_text(platform).lower()
    if key == "bluesky":
        return build_bluesky_text(record, generated)
    if key == "mastodon":
        return build_mastodon_text(record, generated)
    if key == "Facebook":
        return build_Facebook_text(record, generated)
    return clip_text(_lead(record, _generated(record, generated)), 500)


def build_devto_title(record: dict[str, Any], generated: dict[str, Any] | None = None) -> str:
    generated = _generated(record, generated)
    name = record_name(record)
    hook = _hook(record, generated).rstrip(".")
    generated_title = clean_text(generated.get("article_title") or "")
    generic = "what it does and why" in generated_title.lower()
    if hook and not hook.lower().startswith(name.lower()):
        candidate = f"{name}: {hook[0].upper() + hook[1:] if len(hook) > 1 else hook.upper()}"
        if len(candidate) <= 125:
            return candidate
    if generated_title and not generic:
        return clip_text(generated_title, 125)
    return clip_text(f"{name}: a practical open-source breakdown", 125)


def _strip_leading_h1(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def build_devto_body(record: dict[str, Any], generated: dict[str, Any] | None = None) -> str:
    generated = _generated(record, generated)
    markdown = _strip_leading_h1(str(generated.get("article_markdown") or ""))
    summary = _sentences(_summary(record, generated), 330)
    who = clip_text(generated.get("who_for"), 220)
    proof_bits = [
        f"⭐ {_fmt_num(record.get('stars'))} stars" if record.get("stars") is not None else "",
        f"🍴 {_fmt_num(record.get('forks'))} forks" if record.get("forks") is not None else "",
        clean_text(record.get("language") or ""),
        license_name(record),
    ]
    proof = " · ".join(bit for bit in proof_bits if bit)
    intro_lines = []
    if summary:
        intro_lines.append(f"> **TL;DR:** {summary}")
    if who:
        intro_lines.append(f"> **Best for:** {who}")
    if proof:
        intro_lines.append(f"> **Repository snapshot:** {proof}")
    links = []
    url = repo_url(record)
    if url:
        links.append(f"- [GitHub repository]({url})")
    breakdown = breakdown_url(record)
    if breakdown and breakdown != url:
        links.append(f"- [Full breakdown]({breakdown})")
    links.append("- [More open-source finds on Telegram](https://t.me/GitHub_Open_Source)")
    question = clip_text(
        generated.get("discussion_question") or "Would you use this in production? Why?",
        190,
    )
    footer = (
        "\n\n---\n\n## Discuss\n\n"
        f"{question}\n\n"
        + "\n".join(links)
        + "\n\n*Curated from the repository README and metadata. "
        "No hands-on test is claimed; evaluate it in a sandbox before production use.*\n"
    )
    intro = "\n".join(intro_lines).strip()
    return (intro + "\n\n" if intro else "") + markdown + footer
