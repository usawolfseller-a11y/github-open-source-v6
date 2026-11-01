"""Optional own redirect layer for click-through measurement.

Telegram does not expose link clicks to anyone, so measuring them needs a
link *we* own: ``https://<domain>/r/<code>`` → 302 → the GitHub URL. The
deployment (Cloudflare Worker + KV, free tier) lives in
``infra/redirect/``. When ``REDIRECT_BASE_URL`` is unset every project link
stays a direct GitHub URL and clicks are simply not measured — nothing else
in the pipeline changes.
"""
from __future__ import annotations

import hashlib
import os


def base_url() -> str:
    return (os.getenv("REDIRECT_BASE_URL") or "").strip().rstrip("/")


def enabled() -> bool:
    return bool(base_url())


def code_for(full_name: str) -> str:
    return hashlib.sha1(full_name.strip().lower().encode("utf-8")).hexdigest()[:8]


def tracked_url(full_name: str) -> str:
    """Tracked link for a project, or ``""`` when the layer is off."""
    if not enabled() or not full_name:
        return ""
    return f"{base_url()}/r/{code_for(full_name)}"
