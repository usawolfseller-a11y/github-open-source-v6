"""Small HTTP helper with bounded retries and secret-safe errors."""
from __future__ import annotations

import os
import re
import time
from typing import Any

import requests

USER_AGENT = "GitHubOpenSourceBot/6.0 (+https://t.me/GitHub_Open_Source)"


def sanitize(text: str) -> str:
    """Remove credential-shaped substrings before text can reach a log."""
    out = str(text)
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "GEMINI_API_KEY",
        "GH_API_TOKEN",
        "GITHUB_TOKEN",
        "DEV_API_KEY",
        "BLUESKY_APP_PASSWORD",
        "MASTODON_ACCESS_TOKEN",
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "TELEGRAPH_ACCESS_TOKEN",
    ):
        value = os.getenv(name)
        if value and len(value) >= 8:
            out = out.replace(value, "[REDACTED]")
    out = re.sub(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b", "[REDACTED]", out)
    out = re.sub(r"github_pat_[A-Za-z0-9_]{10,}", "[REDACTED]", out)
    return out


class HttpError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(sanitize(message))
        self.status = status


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    data: Any = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    retries: int = 2,
    retry_post: bool = False,
) -> tuple[int, Any, requests.Response | None]:
    """Request JSON. Returns ``(status, parsed_json_or_text, response)``.

    Retries are limited to idempotent methods unless ``retry_post`` is set.
    HTTP error statuses are returned, not raised, so callers can make
    provider-specific fallbacks. Network failures raise :class:`HttpError`
    after retries.
    """
    merged_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged_headers.update(headers)
    attempts = retries + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.request(
                method,
                url,
                headers=merged_headers,
                json=json_body,
                data=data,
                params=params,
                timeout=timeout,
            )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                if method.upper() in {"GET", "HEAD"} or retry_post:
                    time.sleep(min(2**attempt, 4))
                    continue
            try:
                parsed = response.json() if response.content else {}
            except ValueError:
                parsed = sanitize(response.text[:1000])
            return response.status_code, parsed, response
        except requests.RequestException as exc:  # noqa: PERF203 - explicit retry loop
            last_error = exc
            if attempt < attempts - 1 and (method.upper() in {"GET", "HEAD"} or retry_post):
                time.sleep(min(2**attempt, 4))
                continue
            break
    raise HttpError(0, f"network error: {last_error}")


def download_bytes(url: str, *, max_bytes: int = 8_000_000, timeout: int = 30) -> bytes:
    """Download a bounded response body. Caller validates scheme/host first."""
    with requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
        stream=True,
    ) as response:
        response.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise HttpError(413, f"download exceeds {max_bytes} bytes")
            chunks.append(chunk)
    return b"".join(chunks)
