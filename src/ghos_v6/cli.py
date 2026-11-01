"""Command-line entry point used by GitHub Actions."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from .config import Config
from .doctor import run_doctor
from .http import sanitize
from .pipeline import (
    alert_owner,
    article_of_day,
    collect_command,
    digest_command,
    moderation_command,
    news_command,
    process_crossposts,
    publish_slot,
    report_command,
)
from .state import StateStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ghos-v6")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Run non-destructive integration checks")
    doctor.add_argument("--hello", action="store_true", help="Send a hello to the resolved test channel")
    doctor.add_argument("--configure-bot", action="store_true", help="Set bot commands/descriptions")
    doctor.add_argument("--news-spike", action="store_true", help="Try Gemini YouTube URL input on the latest WorldofAI video")

    sub.add_parser("collect", help="Collect, enrich, gate and queue candidates")

    publish = sub.add_parser("publish", help="Publish one queued project")
    publish.add_argument("--slot", default="manual")

    sub.add_parser("crossposts", help="Process due social crossposts")
    sub.add_parser("article", help="Publish the best project of the day as an article")

    news = sub.add_parser("news", help="Publish one verified WorldofAI AI Brief")
    news.add_argument("--force", action="store_true", help="Run even if FEATURE_AI_BRIEF=false")

    sub.add_parser("digest", help="Publish Sunday Top 5 and poll")
    sub.add_parser("report", help="Send the weekly owner report")
    sub.add_parser("moderation", help="Poll discussion updates and delete obvious spam")

    scheduled = sub.add_parser("scheduled", help="Dispatch by the GitHub cron string")
    scheduled.add_argument("--schedule", required=True)
    return parser


def _run_scheduled(config: Config, store: StateStore, schedule: str) -> dict[str, Any]:
    normalized = " ".join(schedule.split())
    routes: dict[str, Any] = {
        "20 4 * * *": lambda: collect_command(config, store),
        "10 7 * * *": lambda: publish_slot(config, store, "europe_morning"),
        "40 12 * * *": lambda: publish_slot(config, store, "europe_us_morning"),
        "15 17 * * *": lambda: publish_slot(config, store, "us_peak"),
        "35 22 * * *": lambda: publish_slot(config, store, "us_evening"),
        "*/30 * * * *": lambda: process_crossposts(config, store),
        "30 13 * * *": lambda: article_of_day(config, store),
        "40 15 * * 1,3,5": lambda: news_command(config, store),
        "10 16 * * 0": lambda: digest_command(config, store),
        "40 16 * * 0": lambda: report_command(config, store),
        "15 */6 * * *": lambda: moderation_command(config, store),
    }
    action = routes.get(normalized)
    if action is None:
        raise RuntimeError(f"Unknown schedule: {normalized}")
    return dict(action())


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parser().parse_args(argv)
    config = Config.from_env()
    store: StateStore | None = None
    try:
        store = StateStore(config.state_dir)
        if args.command == "doctor":
            result = run_doctor(
                config,
                configure_bot=args.configure_bot,
                hello=args.hello,
                news_spike=args.news_spike,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result.get("ok") else 1
        if args.command == "collect":
            result = collect_command(config, store)
        elif args.command == "publish":
            result = publish_slot(config, store, args.slot)
        elif args.command == "crossposts":
            result = process_crossposts(config, store)
        elif args.command == "article":
            result = article_of_day(config, store)
        elif args.command == "news":
            result = news_command(config, store, force=args.force)
        elif args.command == "digest":
            result = digest_command(config, store)
        elif args.command == "report":
            result = report_command(config, store)
        elif args.command == "moderation":
            result = moderation_command(config, store)
        elif args.command == "scheduled":
            result = _run_scheduled(config, store, args.schedule)
        else:  # pragma: no cover - argparse prevents this
            raise RuntimeError(f"Unhandled command {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except BaseException as exc:  # noqa: BLE001
        message = sanitize(f"{type(exc).__name__}: {exc}")[:1200]
        logging.error("Command failed: %s", message)
        if store is not None:
            try:
                store.event("command_failed", command=args.command, error=message)
                store.save()
            except Exception:
                logging.exception("Failed to persist command failure")
        alert_owner(config, "GitHub Open Source v6 failure", f"{args.command}: {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
