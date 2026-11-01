"""End-to-end autonomous publishing pipeline."""
from __future__ import annotations

import html
import logging
import re
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .cards import render_ai_brief_card, render_digest_card
from .config import Config, telegram_message_link
from .content_adapters import build_crosspost_text, Facebook_link_url, image_alt_text
from .formatter import format_project_post
from .gate import GateConfig, evaluate
from .Gemini import GeminiClient, generate_project_content
from .http import download_bytes, sanitize
from .media import choose_visual
from .news import (
    extract_primary_urls,
    fetch_primary_text,
    fetch_worldofai_entries,
    format_ai_brief,
    prefilter_entry,
    synthesize_brief,
)
from .platforms import BlueskyClient, DevToClient, FacebookClient, MastodonClient
from .rank import rank_candidates, select_candidate
from .sources import GitHubApi, collect_candidates, enrich_candidate, enrich_candidates
from .state import StateStore, iso_now
from .telegram import TelegramClient
from .telegraph import TelegraphClient

logger = logging.getLogger(__name__)


def _parse_iso(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _today_records(store: StateStore, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    result = []
    for record in store.published_records():
        published = _parse_iso(record.get("published_at"))
        if published and published.date() == now.date():
            result.append(record)
    return result


def _recent_records(store: StateStore, days: int = 7) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = []
    for record in store.published_records():
        published = _parse_iso(record.get("published_at"))
        if published and published >= cutoff:
            records.append(record)
    return sorted(records, key=lambda item: str(item.get("published_at") or ""), reverse=True)


def alert_owner(config: Config, title: str, details: str = "") -> None:
    if not config.telegram_bot_token or not config.telegram_owner_chat_id:
        return
    try:
        text = f"<b>{html.escape(title)}</b>"
        if details:
            text += f"\n{html.escape(sanitize(details)[:1200])}"
        TelegramClient(config.telegram_bot_token).send_owner(config.telegram_owner_chat_id, text)
    except Exception:  # noqa: BLE001 - alerting must not mask the original failure
        logger.exception("Owner alert failed")


def collect_command(config: Config, store: StateStore) -> dict[str, Any]:
    started = iso_now()
    candidates = collect_candidates(config)
    candidates = [candidate for candidate in candidates if not store.is_published(candidate)]
    candidates = rank_candidates(candidates)
    api = GitHubApi(config.GitHub_token)
    enriched = enrich_candidates(api, candidates, max_enrich=90)

    gate_cfg = GateConfig()
    passing: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    for candidate in enriched:
        # Keep the committed queue reasonably small; Gemini gets enough
        # README context without storing whole repositories in git.
        readme = str(candidate.get("readme") or "")
        candidate["readme"] = readme[:14_000]
        candidate["readme_excerpt"] = readme[:6_000]
        decision = evaluate(candidate, gate_cfg)
        candidate["is_hidden_gem"] = decision.is_hidden_gem
        candidate["is_dual_use"] = decision.is_dual_use
        if decision.ok:
            passing.append(candidate)
            store.mark_seen(candidate, "queued")
        else:
            reason = ",".join(decision.reasons) or "unknown"
            rejection_counts.update(decision.reasons or ["unknown"])
            store.mark_seen(candidate, f"rejected:{reason}")

    passing = rank_candidates(passing)
    queue = passing[:35]
    store.set_queue(queue)
    store.data.setdefault("last_runs", {})["collect"] = {
        "started_at": started,
        "finished_at": iso_now(),
        "discovered": len(candidates),
        "enriched": len(enriched),
        "passed_gate": len(passing),
        "queued": len(queue),
        "rejections": dict(rejection_counts),
    }
    store.event(
        "collect_completed",
        discovered=len(candidates),
        enriched=len(enriched),
        passed_gate=len(passing),
        queued=len(queue),
        rejections=dict(rejection_counts),
    )
    store.save()
    return {
        "ok": True,
        "discovered": len(candidates),
        "enriched": len(enriched),
        "passed_gate": len(passing),
        "queued": len(queue),
        "top": [candidate.get("full_name") for candidate in queue[:5]],
        "rejections": dict(rejection_counts),
    }


def _public_record_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "repo_id",
        "id",
        "name",
        "full_name",
        "url",
        "description",
        "homepage",
        "language",
        "stars",
        "forks",
        "open_issues",
        "contributors_count",
        "topics",
        "license",
        "created_at",
        "pushed_at",
        "updated_at",
        "sources",
        "hn_points",
        "score",
        "is_hidden_gem",
        "is_dual_use",
        "media_urls",
    )
    return {key: candidate.get(key) for key in keep if key in candidate}


def _article_markdown(record_candidate: dict[str, Any], generated: dict[str, Any]) -> str:
    """Telegraph wrapper: standfirst + snapshot, then the long breakdown."""
    markdown = str(generated.get("article_markdown") or "").strip()
    lines = markdown.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        markdown = "\n".join(lines[1:]).strip()
    hook = str(generated.get("hook") or record_candidate.get("description") or "").strip()
    lic = record_candidate.get("license")
    license_name = ""
    if isinstance(lic, dict):
        license_name = str(lic.get("spdx_id") or lic.get("name") or "")
    elif lic:
        license_name = str(lic)
    snapshot_bits = []
    if record_candidate.get("full_name"):
        snapshot_bits.append(f"Repository: {record_candidate['full_name']}")
    if record_candidate.get("language"):
        snapshot_bits.append(f"Language: {record_candidate['language']}")
    if license_name:
        snapshot_bits.append(f"License: {license_name}")
    try:
        snapshot_bits.append(f"Stars: {int(record_candidate.get('stars') or 0):,}".replace(",", " "))
    except (TypeError, ValueError):
        pass
    intro = ""
    if hook:
        intro += hook + "\n\n"
    if snapshot_bits:
        intro += "*" + " · ".join(snapshot_bits) + "*\n\n"
    links = [
        f"- [GitHub repository]({record_candidate.get('url')})",
    ]
    if record_candidate.get("homepage"):
        links.append(f"- [Project homepage]({record_candidate['homepage']})")
    links.append("- [GitHub Open Source on Telegram](https://t.me/GitHub_Open_Source)")
    return (
        intro
        + markdown
        + "\n\n## Links\n\n"
        + "\n".join(links)
        + "\n\n*Curated from the repository README and metadata. "
        "No hands-on test is claimed; evaluate it in a sandbox before production use.*\n"
    )

def publish_slot(config: Config, store: StateStore, slot: str = "manual") -> dict[str, Any]:
    config.require("TELEGRAM_BOT_TOKEN")
    chat_id = config.telegram_chat_id
    if not store.data.get("queue"):
        collect_command(config, store)

    telegram = TelegramClient(config.telegram_bot_token)
    Gemini = GeminiClient(config.Gemini_api_key, config.Gemini_model)
    api = GitHubApi(config.GitHub_token)
    gate_cfg = GateConfig()
    attempts = 0

    while attempts < 10:
        attempts += 1
        published_today = _today_records(store)
        candidate = select_candidate(list(store.data.get("queue") or []), published_today)
        if candidate is None:
            store.event("publish_skipped", slot=slot, reason="no_candidate")
            store.save()
            return {"ok": True, "published": False, "reason": "no_candidate", "slot": slot}

        key = store.repo_key(candidate)
        try:
            candidate = enrich_candidate(api, dict(candidate))
            candidate["readme"] = str(candidate.get("readme") or "")[:20_000]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Selected candidate refresh failed for %s: %s", key, type(exc).__name__)

        pre_decision = evaluate(candidate, gate_cfg)
        if not pre_decision.ok:
            store.pop_queue_candidate(key)
            store.mark_seen(candidate, "rejected:" + ",".join(pre_decision.reasons))
            store.event("publish_candidate_rejected", repo=key, reasons=pre_decision.reasons, stage="pre_llm")
            store.save()
            continue
        candidate["is_hidden_gem"] = pre_decision.is_hidden_gem
        candidate["is_dual_use"] = pre_decision.is_dual_use

        generated = generate_project_content(Gemini, candidate)
        candidate["safety"] = generated.get("safety")
        post_decision = evaluate(candidate, gate_cfg)
        candidate["is_dual_use"] = bool(
            post_decision.is_dual_use or generated.get("safety") == "dual_use"
        )
        candidate["is_hidden_gem"] = post_decision.is_hidden_gem
        if not post_decision.ok:
            store.pop_queue_candidate(key)
            store.mark_seen(candidate, "rejected:" + ",".join(post_decision.reasons))
            store.event(
                "publish_candidate_rejected",
                repo=key,
                reasons=post_decision.reasons,
                stage="post_llm",
                safety_reason=generated.get("safety_reason") or "",
            )
            store.save()
            continue

        issue_number = len(store.published_records()) + 1
        visual = choose_visual(candidate, generated, issue_number=issue_number)
        telegraph = TelegraphClient(config.telegraph_access_token)
        image_url = visual.url
        if visual.kind == "card" and visual.data:
            try:
                image_url = telegraph.upload_image(
                    visual.data,
                    filename=(visual.local_path.name if visual.local_path else "cover.png"),
                    content_type=visual.content_type,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Card image upload failed: %s", type(exc).__name__)
                image_url = f"https://opengraph.githubassets.com/1/{candidate.get('full_name')}"

        telegraph_url = ""
        article_markdown = _article_markdown(candidate, generated)
        if config.feature_telegraph and telegraph.configured:
            try:
                page = telegraph.create_page(
                    title=str(generated.get("article_title") or candidate.get("name") or "Project breakdown"),
                    markdown=article_markdown,
                    image_url=image_url,
                    image_caption=str(candidate.get("full_name") or ""),
                )
                telegraph_url = str(page.get("url") or "")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Telegraph publish failed; continuing: %s", sanitize(str(exc))[:250])
                store.event("telegraph_failed", repo=key, error=sanitize(str(exc))[:250])

        format_input = dict(candidate)
        format_input.update(
            {
                "hook": generated.get("hook"),
                "readme_summary": generated.get("summary"),
                "primary_use_case": generated.get("summary"),
                "key_features": generated.get("key_features"),
                "who_for": generated.get("who_for"),
                "why_now": generated.get("why_now"),
                "verdict": generated.get("verdict"),
                "quick_start": generated.get("quick_start"),
                "discussion_question": generated.get("discussion_question"),
                "is_dual_use": candidate.get("is_dual_use"),
            }
        )
        text_html = format_project_post(format_input, telegraph_url=telegraph_url)
        preview_url = telegraph_url or image_url or str(candidate.get("url") or "")
        sent = telegram.send_project(
            chat_id,
            text_html,
            preview_url=preview_url,
            github_url=str(candidate.get("url") or ""),
            telegraph_url=telegraph_url,
            homepage_url=str(candidate.get("homepage") or ""),
        )
        message_id = int(sent.get("message_id") or 0)
        due = datetime.now(timezone.utc) + timedelta(minutes=30)
        record = _public_record_candidate(candidate)
        record.update(
            {
                "generated": generated,
                "category": generated.get("category") or "",
                "published_at": iso_now(),
                "slot": slot,
                "telegram_chat_id": chat_id,
                "telegram_message_id": message_id,
                "telegram_link": telegram_message_link(
                    chat_id,
                    message_id,
                    main=config.is_main_target,
                ),
                "telegraph_url": telegraph_url,
                "image_url": image_url,
                "visual_kind": visual.kind,
                "card_style": visual.card_style,
                "crossposts": {
                    "bluesky": {"status": "pending" if config.feature_bluesky else "disabled", "due_at": due.isoformat(), "attempts": 0},
                    "mastodon": {"status": "pending" if config.feature_mastodon else "disabled", "due_at": due.isoformat(), "attempts": 0},
                    "Facebook": {"status": "pending" if config.feature_Facebook else "disabled", "due_at": due.isoformat(), "attempts": 0},
                },
                "articles": {},
            }
        )
        store.record_published(record)
        store.mark_seen(record, "published")
        store.data.setdefault("last_runs", {})[f"publish:{slot}"] = {
            "finished_at": iso_now(),
            "repo": key,
            "telegram_message_id": message_id,
        }
        store.save()
        return {
            "ok": True,
            "published": True,
            "repo": key,
            "telegram_message_id": message_id,
            "telegram_link": record["telegram_link"],
            "telegraph_url": telegraph_url,
            "visual": visual.kind,
            "llm_used": bool(generated.get("llm_used")),
            "slot": slot,
        }

    store.event("publish_skipped", slot=slot, reason="all_candidates_rejected")
    store.save()
    return {"ok": True, "published": False, "reason": "all_candidates_rejected", "slot": slot}


def _download_record_image(record: dict[str, Any]) -> tuple[bytes, str]:
    image_url = str(record.get("image_url") or "")
    if not image_url.startswith("https://"):
        return b"", "image/png"
    try:
        data = download_bytes(image_url, max_bytes=5_000_000)
    except Exception:
        return b"", "image/png"
    lower = image_url.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return data, "image/jpeg"
    if lower.endswith(".gif"):
        return data, "image/gif"
    if lower.endswith(".webp"):
        return data, "image/webp"
    return data, "image/png"


def process_crossposts(config: Config, store: StateStore) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    summary = {"ok": True, "processed": 0, "published": 0, "failed": 0, "dead": 0}
    clients: dict[str, Any] = {}

    def client_for(platform: str):
        if platform not in clients:
            if platform == "bluesky":
                clients[platform] = BlueskyClient(config.bluesky_handle, config.bluesky_app_password)
            elif platform == "mastodon":
                clients[platform] = MastodonClient(config.mastodon_instance_url, config.mastodon_access_token)
            elif platform == "Facebook":
                clients[platform] = FacebookClient(config.Facebook_page_id, config.Facebook_page_access_token)
        return clients.get(platform)

    enabled = {
        "bluesky": config.feature_bluesky,
        "mastodon": config.feature_mastodon,
        "Facebook": config.feature_Facebook,
    }
    for key, record in list(store.data.get("published", {}).items()):
        generated = record.get("generated") or {}
        image_data, content_type = _download_record_image(record)
        for platform, status_info in list((record.get("crossposts") or {}).items()):
            if platform not in enabled:
                continue
            if not enabled[platform]:
                if status_info.get("status") == "pending":
                    status_info["status"] = "disabled"
                continue
            if status_info.get("status") not in {"pending", "failed"}:
                continue
            due = _parse_iso(status_info.get("due_at"))
            if due and due > now:
                continue
            summary["processed"] += 1
            try:
                client = client_for(platform)
                # Native copy per surface: limits, link placement, tags
                # and tone differ deliberately.  Private test-channel
                # t.me/c links are never used in public social copy.
                text = build_crosspost_text(platform, record, generated)
                if platform == "Facebook":
                    result = client.post(text, url=Facebook_link_url(record))
                    result_url = f"https://www.facebook.com/{result.get('id')}" if result.get("id") else ""
                else:
                    result = client.post(
                        text,
                        url="",
                        image_data=image_data,
                        content_type=content_type,
                        image_alt=image_alt_text(record, generated),
                    )
                    result_url = str(result.get("url") or "")
                status_info.update(
                    {"status": "published", "published_at": iso_now(), "url": result_url, "error": ""}
                )
                store.event("crosspost_published", repo=key, platform=platform, url=result_url)
                summary["published"] += 1
            except Exception as exc:  # noqa: BLE001
                attempts = int(status_info.get("attempts") or 0) + 1
                error = sanitize(str(exc))[:400]
                status_info["attempts"] = attempts
                status_info["error"] = error
                if attempts >= 3:
                    status_info["status"] = "dead"
                    store.add_dead_letter(
                        {
                            "repo": key,
                            "platform": platform,
                            "attempts": attempts,
                            "error": error,
                            "created_at": iso_now(),
                        }
                    )
                    summary["dead"] += 1
                else:
                    status_info["status"] = "failed"
                    delay = [30, 120, 360][min(attempts - 1, 2)]
                    status_info["due_at"] = (now + timedelta(minutes=delay)).isoformat()
                store.event("crosspost_failed", repo=key, platform=platform, attempts=attempts, error=error)
                summary["failed"] += 1
    store.save()
    return summary


def article_of_day(config: Config, store: StateStore) -> dict[str, Any]:
    today = sorted(_today_records(store), key=lambda item: float(item.get("score") or 0), reverse=True)
    if not today:
        return {"ok": True, "published": False, "reason": "no_projects_today"}
    for record in today:
        if (record.get("articles") or {}).get("devto"):
            continue
        key = store.repo_key(record)
        if not config.feature_devto:
            store.event("article_skipped", repo=key, reason="feature_devto_disabled")
            store.save()
            return {"ok": True, "published": False, "reason": "feature_devto_disabled", "repo": key}
        client = DevToClient(config.dev_api_key)
        result = client.publish_article(record, record.get("generated") or {})
        record.setdefault("articles", {})["devto"] = {
            "id": result.get("id"),
            "url": result.get("url") or "",
            "published_at": iso_now(),
        }
        store.event("article_published", repo=key, platform="devto", url=result.get("url") or "")
        store.save()
        return {"ok": True, "published": True, "repo": key, "url": result.get("url") or ""}
    return {"ok": True, "published": False, "reason": "already_published"}


def news_command(config: Config, store: StateStore, *, force: bool = False) -> dict[str, Any]:
    if not config.feature_ai_brief and not force:
        return {"ok": True, "published": False, "reason": "feature_ai_brief_disabled"}
    config.require("TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY")
    chat_id = config.telegram_chat_id
    client = GeminiClient(config.Gemini_api_key, config.Gemini_model)
    telegram = TelegramClient(config.telegram_bot_token)
    entries = fetch_worldofai_entries()

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    seen_video_ids: set[str] = set()
    recent_topics: set[str] = set()
    for item in store.data.get("news_topics") or []:
        if item.get("video_id"):
            seen_video_ids.add(str(item["video_id"]))
        published = _parse_iso(item.get("published_at"))
        if published and published >= cutoff and item.get("topic_key"):
            recent_topics.add(str(item["topic_key"]))

    rejected: Counter[str] = Counter()
    for entry in entries:
        allowed, reason = prefilter_entry(
            entry,
            seen_video_ids=seen_video_ids,
            recent_topic_keys=recent_topics,
        )
        if not allowed:
            rejected[reason] += 1
            continue
        primary = None
        for url in extract_primary_urls(entry):
            primary = fetch_primary_text(url)
            if primary:
                break
        if not primary:
            rejected["no_fetchable_primary_source"] += 1
            continue
        try:
            brief = synthesize_brief(entry, primary, client, use_video=True)
            video_input = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini YouTube input failed; retrying text-only: %s", type(exc).__name__)
            brief = synthesize_brief(entry, primary, client, use_video=False)
            video_input = False
        if not brief.get("eligible"):
            rejected[str(brief.get("rejection_reason") or "llm_ineligible")[:80]] += 1
            continue
        topic_key = re.sub(r"[^a-z0-9]+", "-", str(brief.get("topic_key") or "").lower()).strip("-")
        if topic_key and topic_key in recent_topics:
            rejected["recent_topic"] += 1
            continue
        buttons = []
        row = []
        if brief.get("official_url"):
            row.append({"text": "Official source", "url": str(brief["official_url"])})
        if entry.get("url"):
            row.append({"text": "Watch on WorldofAI", "url": str(entry["url"])})
        if row:
            buttons.append(row)
        preview_url = str(entry.get("url") or "")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                standfirst_items = brief.get("what_happened") or []
                standfirst = str(standfirst_items[0] if standfirst_items else brief.get("why_devs") or "")
                card_path = render_ai_brief_card(
                    str(brief.get("headline") or "Verified AI update"),
                    standfirst,
                    str(brief.get("official_name") or "Primary source"),
                    Path(tmp) / "ai-brief.png",
                )
                if config.telegraph_access_token:
                    uploaded = TelegraphClient(config.telegraph_access_token).upload_image_path(card_path)
                    if uploaded:
                        preview_url = uploaded
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI Brief Glass Aurora card failed; using video preview: %s", type(exc).__name__)
        sent = telegram.send_text(
            chat_id,
            format_ai_brief(brief),
            preview_url=preview_url,
            buttons=buttons,
        )
        record = {
            "video_id": entry.get("video_id"),
            "topic_key": topic_key,
            "headline": brief.get("headline") or "",
            "official_url": brief.get("official_url") or "",
            "video_url": entry.get("url") or "",
            "published_at": iso_now(),
            "telegram_message_id": sent.get("message_id"),
            "image_url": preview_url if preview_url != str(entry.get("url") or "") else "",
            "Gemini_video_input": video_input,
        }
        store.data.setdefault("news_topics", []).append(record)
        store.event(
            "ai_brief_published",
            video_id=entry.get("video_id"),
            topic=topic_key,
            official_url=record["official_url"],
            Gemini_video_input=video_input,
        )
        store.save()
        return {
            "ok": True,
            "published": True,
            "headline": record["headline"],
            "telegram_message_id": sent.get("message_id"),
            "Gemini_video_input": video_input,
            "rejections": dict(rejected),
        }

    store.event("ai_brief_skipped", rejections=dict(rejected))
    store.save()
    return {"ok": True, "published": False, "reason": "no_eligible_video", "rejections": dict(rejected)}


def digest_command(config: Config, store: StateStore) -> dict[str, Any]:
    config.require("TELEGRAM_BOT_TOKEN")
    chat_id = config.telegram_chat_id
    records = sorted(_recent_records(store, days=7), key=lambda item: float(item.get("score") or 0), reverse=True)[:5]
    if not records:
        return {"ok": True, "published": False, "reason": "no_records"}
    telegram = TelegramClient(config.telegram_bot_token)
    image_url = ""
    with tempfile.TemporaryDirectory() as tmp:
        path = render_digest_card(records, Path(tmp) / "sunday-digest.png")
        try:
            image_url = TelegraphClient(config.telegraph_access_token).upload_image_path(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Digest card upload failed: %s", type(exc).__name__)
    lines = ["📰 <b>The Open Source Daily — Top 5 of the Week</b>", ""]
    for index, record in enumerate(records, 1):
        name = html.escape(str(record.get("name") or record.get("full_name") or "Project"))
        link = str(record.get("telegram_link") or record.get("url") or "")
        title = f'<a href="{html.escape(link, quote=True)}">{name}</a>' if link.startswith("https://") else name
        generated = record.get("generated") or {}
        hook = html.escape(str(generated.get("hook") or record.get("description") or "")[:220])
        try:
            stars = f" ⭐ {int(record.get('stars') or 0):,}".replace(",", " ")
        except (TypeError, ValueError):
            stars = ""
        lines.append(f"{index}. <b>{title}</b>{stars}")
        if hook:
            lines.append(f"   {hook}")
    lines += ["", "Vote in the poll below: which one deserves Project of the Week?"]
    sent = telegram.send_text(chat_id, "\n".join(lines), preview_url=image_url)
    poll = None
    try:
        poll = telegram.send_poll(
            chat_id,
            "Which project should win Project of the Week?",
            [str(record.get("name") or record.get("full_name") or "Project") for record in records],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Digest poll failed: %s", sanitize(str(exc))[:200])
    store.event(
        "digest_published",
        telegram_message_id=sent.get("message_id"),
        poll_message_id=(poll or {}).get("message_id"),
        repos=[record.get("full_name") for record in records],
    )
    store.save()
    return {"ok": True, "published": True, "telegram_message_id": sent.get("message_id"), "count": len(records)}


def report_command(config: Config, store: StateStore) -> dict[str, Any]:
    records = _recent_records(store, days=7)
    top = sorted(records, key=lambda item: float(item.get("score") or 0), reverse=True)[:3]
    languages = Counter(str(record.get("language") or "Unknown") for record in records)
    sources = Counter(source for record in records for source in (record.get("sources") or []))
    lines = [
        "<b>GitHub Open Source v6 — weekly report</b>",
        "",
        f"Projects published (7d): <b>{len(records)}</b>",
        f"Queued now: <b>{len(store.data.get('queue') or [])}</b>",
        f"Dead letters: <b>{len(store.data.get('dead_letters') or [])}</b>",
        f"AI Briefs recorded: <b>{len(store.data.get('news_topics') or [])}</b>",
    ]
    if top:
        lines += ["", "<b>Top by editorial score</b>"]
        for index, record in enumerate(top, 1):
            lines.append(
                f"{index}. {html.escape(str(record.get('name') or record.get('full_name') or ''))} — {float(record.get('score') or 0):.1f}"
            )
    if languages:
        lines += ["", "<b>Languages</b>: " + ", ".join(f"{k} {v}" for k, v in languages.most_common(6))]
    if sources:
        lines.append("<b>Sources</b>: " + ", ".join(f"{k} {v}" for k, v in sources.most_common(6)))
    text = "\n".join(lines)
    sent = None
    if config.telegram_bot_token and config.telegram_owner_chat_id:
        sent = TelegramClient(config.telegram_bot_token).send_owner(config.telegram_owner_chat_id, text)
    store.event("weekly_report", sent=bool(sent), projects_7d=len(records))
    store.save()
    return {"ok": True, "sent": bool(sent), "projects_7d": len(records), "text": text}


_SPAM_RE = re.compile(
    r"(crypto giveaway|airdrop claim|double your|investment profit|casino|betting bonus|"
    r"earn \$|work from home.*\$|telegram premium free|seed phrase)",
    re.I,
)


def moderation_command(config: Config, store: StateStore) -> dict[str, Any]:
    config.require("TELEGRAM_BOT_TOKEN")
    telegram = TelegramClient(config.telegram_bot_token)
    last_offset = int(store.data.setdefault("last_runs", {}).get("telegram_update_offset") or 0)
    payload: dict[str, Any] = {"timeout": 0, "limit": 100}
    if last_offset:
        payload["offset"] = last_offset + 1
    updates = list(telegram.api("getUpdates", payload) or [])
    deleted = 0
    max_update_id = last_offset
    for update in updates:
        update_id = int(update.get("update_id") or 0)
        max_update_id = max(max_update_id, update_id)
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("type") not in {"group", "supergroup"}:
            continue
        sender = message.get("from") or {}
        if sender.get("is_bot"):
            continue
        text = str(message.get("text") or message.get("caption") or "")
        urls = re.findall(r"https?://|t\.me/", text, flags=re.I)
        suspicious = bool(_SPAM_RE.search(text)) or len(urls) >= 3
        if not suspicious:
            continue
        try:
            member = telegram.api(
                "getChatMember",
                {"chat_id": chat.get("id"), "user_id": sender.get("id")},
            )
            if (member or {}).get("status") in {"creator", "administrator"}:
                continue
            telegram.delete_message(int(chat["id"]), int(message["message_id"]))
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            logger.info("Moderation delete skipped: %s", sanitize(str(exc))[:160])
    store.data.setdefault("last_runs", {})["telegram_update_offset"] = max_update_id
    store.event("moderation_completed", updates=len(updates), deleted=deleted)
    store.save()
    return {"ok": True, "updates": len(updates), "deleted": deleted}
