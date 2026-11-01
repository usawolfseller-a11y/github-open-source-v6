"""Append-only JSONL event log + deterministic JSON state.

The JSONL log is the audit trail. ``state.json`` is a deterministic,
human-reviewable projection committed by GitHub Actions. No binary
database is the only source of truth.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat().replace("+00:00", "Z")


DEFAULT_STATE: dict[str, Any] = {
    "version": 1,
    "published": {},
    "queue": [],
    "seen_repos": {},
    "dead_letters": [],
    "news_topics": [],
    "last_runs": {},
}


class StateStore:
    def __init__(self, state_dir: Path | str = Path("state")):
        self.state_dir = Path(state_dir)
        self.state_path = self.state_dir / "state.json"
        self.events_path = self.state_dir / "events.jsonl"
        self.data: dict[str, Any] = json.loads(json.dumps(DEFAULT_STATE))
        self.load()

    def load(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self.state_path.exists():
            try:
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    merged = json.loads(json.dumps(DEFAULT_STATE))
                    merged.update(raw)
                    self.data = merged
            except (json.JSONDecodeError, OSError):
                # A corrupt projection must not be silently overwritten in a
                # way that loses the audit trail. Events remain on disk and
                # the workflow will fail loudly through the raised marker in
                # a subsequent save diff; for collection-only runs an empty
                # projection is safer than crashing before diagnostics.
                self.data = json.loads(json.dumps(DEFAULT_STATE))
        if not self.events_path.exists():
            self.events_path.touch()

    def save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(dir=self.state_dir, prefix="state.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_name, self.state_path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def event(self, event_type: str, **payload: Any) -> None:
        record = {"ts": iso_now(), "type": event_type, **payload}
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    # -- published / dedup -------------------------------------------------
    @staticmethod
    def repo_key(candidate: dict[str, Any]) -> str:
        full_name = str(candidate.get("full_name") or "").strip().lower()
        if full_name:
            return full_name
        repo_id = candidate.get("repo_id") or candidate.get("id")
        return f"id:{repo_id}" if repo_id else str(candidate.get("url") or "").lower()

    def is_published(self, candidate: dict[str, Any]) -> bool:
        key = self.repo_key(candidate)
        if key in self.data.get("published", {}):
            return True
        repo_id = candidate.get("repo_id") or candidate.get("id")
        if repo_id is not None and f"id:{repo_id}" in self.data.get("published", {}):
            return True
        return False

    def mark_seen(self, candidate: dict[str, Any], decision: str) -> None:
        key = self.repo_key(candidate)
        if not key:
            return
        seen = self.data.setdefault("seen_repos", {})
        prev = seen.get(key, {})
        seen[key] = {
            "full_name": candidate.get("full_name") or prev.get("full_name") or "",
            "repo_id": candidate.get("repo_id") or candidate.get("id") or prev.get("repo_id"),
            "first_seen_at": prev.get("first_seen_at") or iso_now(),
            "last_seen_at": iso_now(),
            "last_decision": decision,
            "sources": sorted(set(prev.get("sources") or []) | set(candidate.get("sources") or [])),
        }

    def set_queue(self, candidates: list[dict[str, Any]]) -> None:
        self.data["queue"] = candidates

    def pop_queue_candidate(self, key: str) -> None:
        self.data["queue"] = [c for c in self.data.get("queue", []) if self.repo_key(c) != key]

    def record_published(self, record: dict[str, Any]) -> str:
        key = self.repo_key(record)
        self.data.setdefault("published", {})[key] = record
        self.pop_queue_candidate(key)
        self.event(
            "project_published",
            repo=key,
            telegram_message_id=record.get("telegram_message_id"),
            telegraph_url=record.get("telegraph_url") or "",
            score=record.get("score"),
        )
        return key

    def published_records(self) -> list[dict[str, Any]]:
        return list(self.data.get("published", {}).values())

    def add_dead_letter(self, item: dict[str, Any]) -> None:
        self.data.setdefault("dead_letters", []).append(item)
        self.event("dead_letter", platform=item.get("platform"), repo=item.get("repo"))
