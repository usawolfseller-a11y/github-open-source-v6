"""External article/social platform adapters.

Each adapter is independently feature-flagged by the pipeline; one
platform failure must never roll back the Telegram publication.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from .content_adapters import build_devto_body, build_devto_title, devto_tags
from .http import USER_AGENT, sanitize

URL_RE = re.compile(r"https://[^\s<>\"')]+")


class PlatformError(RuntimeError):
    pass


def _error(platform: str, response: requests.Response) -> PlatformError:
    try:
        body = response.json()
    except ValueError:
        body = response.text[:300]
    return PlatformError(sanitize(f"{platform} HTTP {response.status_code}: {body}")[:500])


class DevToClient:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.forem.api-v1+json",
                "api-key": self.api_key,
            }
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def me(self) -> dict[str, Any]:
        response = self.session.get("https://dev.to/api/users/me", timeout=30)
        if response.status_code != 200:
            raise _error("dev.to", response)
        return dict(response.json() or {})

    @staticmethod
    def _tags(record: dict[str, Any], generated: dict[str, Any] | None = None) -> list[str]:
        return devto_tags(record, generated)

    def publish_article(self, record: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise PlatformError("DEV_API_KEY is not set")
        markdown = build_devto_body(record, generated).strip()
        if not str(generated.get("article_markdown") or "").strip():
            raise PlatformError("dev.to article markdown is empty")
        article: dict[str, Any] = {
            "title": build_devto_title(record, generated),
            "body_markdown": markdown,
            "published": True,
            "tags": self._tags(record, generated),
            "series": "Open Source Finds",
        }
        # No canonical_url to Telegraph: the dev.to version is adapted
        # with its own TL;DR/discussion wrapper and should be indexable
        # as the public article surface.
        if str(record.get("image_url") or "").startswith("https://"):
            article["main_image"] = record["image_url"]
        response = self.session.post(
            "https://dev.to/api/articles",
            json={"article": article},
            timeout=60,
        )
        if response.status_code not in {200, 201}:
            raise _error("dev.to", response)
        return dict(response.json() or {})


def build_link_facets(text: str) -> list[dict[str, Any]]:
    """Build AT Protocol rich-text facets for links and hashtags.

    Byte offsets are UTF-8 based, as required by Bluesky.  Hashtag
    facets make our CamelCase tags clickable instead of plain text.
    """
    facets: list[dict[str, Any]] = []
    encoded = text.encode("utf-8")
    url_spans: list[tuple[int, int]] = []

    def byte_range(start: int, value: str) -> tuple[int, int]:
        byte_start = len(text[:start].encode("utf-8"))
        return byte_start, byte_start + len(value.encode("utf-8"))

    for match in URL_RE.finditer(text):
        value = match.group(0).rstrip(".,;:!?")
        if not value:
            continue
        byte_start, byte_end = byte_range(match.start(), value)
        if byte_end > len(encoded):
            continue
        url_spans.append((match.start(), match.start() + len(value)))
        facets.append(
            {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#link", "uri": value}
                ],
            }
        )

    for match in re.finditer(r"(?<![A-Za-z0-9_#])#([A-Za-z0-9_]+)", text):
        if any(start <= match.start() < end for start, end in url_spans):
            continue
        value = match.group(0)
        byte_start, byte_end = byte_range(match.start(), value)
        if byte_end > len(encoded):
            continue
        facets.append(
            {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#tag", "tag": match.group(1)}
                ],
            }
        )

    return sorted(facets, key=lambda item: item["index"]["byteStart"])

class BlueskyClient:
    def __init__(self, handle: str, app_password: str):
        handle = handle.strip().lstrip("@")
        if handle and "." not in handle:
            handle += ".bsky.social"
        self.handle = handle
        self.app_password = app_password.strip()
        self._session: dict[str, Any] | None = None

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.app_password)

    def create_session(self) -> dict[str, Any]:
        if self._session:
            return self._session
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if response.status_code != 200:
            raise _error("Bluesky", response)
        self._session = dict(response.json() or {})
        return self._session

    def verify(self) -> dict[str, Any]:
        session = self.create_session()
        return {"handle": session.get("handle"), "did": session.get("did")}

    def _upload_blob(self, data: bytes, content_type: str) -> dict[str, Any] | None:
        if not data:
            return None
        session = self.create_session()
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
            data=data[:990_000],
            headers={
                "Authorization": f"Bearer {session.get('accessJwt')}",
                "Content-Type": content_type or "image/png",
                "User-Agent": USER_AGENT,
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise _error("Bluesky upload", response)
        return (response.json() or {}).get("blob")

    def post(
        self,
        text: str,
        *,
        url: str = "",
        image_data: bytes = b"",
        content_type: str = "image/png",
        image_alt: str = "",
    ) -> dict[str, Any]:
        if not self.configured:
            raise PlatformError("Bluesky credentials are not set")
        session = self.create_session()
        body_text = str(text or "").strip()
        if url and url not in body_text:
            suffix = f"\n\n{url}"
            body_text = (body_text[: max(0, 300 - len(suffix))].rstrip() + suffix)[:300]
        else:
            body_text = body_text[:300]
        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": body_text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "langs": ["en"],
            "facets": build_link_facets(body_text),
        }
        blob = self._upload_blob(image_data, content_type) if image_data else None
        if blob:
            record["embed"] = {
                "$type": "app.bsky.embed.images",
                "images": [{"alt": image_alt[:300] or "Project cover", "image": blob}],
            }
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={
                "repo": session.get("did"),
                "collection": "app.bsky.feed.post",
                "record": record,
            },
            headers={"Authorization": f"Bearer {session.get('accessJwt')}", "User-Agent": USER_AGENT},
            timeout=45,
        )
        if response.status_code != 200:
            raise _error("Bluesky post", response)
        result = dict(response.json() or {})
        at_uri = str(result.get("uri") or "")
        rkey = at_uri.rsplit("/", 1)[-1] if at_uri else ""
        if rkey:
            result["url"] = f"https://bsky.app/profile/{session.get('handle')}/post/{rkey}"
        return result


class MastodonClient:
    def __init__(self, instance_url: str, access_token: str):
        self.base = (instance_url or "https://mastodon.social").rstrip("/")
        self.access_token = access_token.strip()
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {self.access_token}", "User-Agent": USER_AGENT}
        )

    @property
    def configured(self) -> bool:
        return bool(self.access_token)

    def verify(self) -> dict[str, Any]:
        response = self.session.get(f"{self.base}/api/v1/accounts/verify_credentials", timeout=30)
        if response.status_code != 200:
            raise _error("Mastodon", response)
        return dict(response.json() or {})

    def _upload_media(self, data: bytes, content_type: str, alt_text: str) -> str:
        if not data:
            return ""
        extension = {
            "image/jpeg": "jpg",
            "image/gif": "gif",
            "image/webp": "webp",
        }.get(content_type, "png")
        response = self.session.post(
            f"{self.base}/api/v2/media",
            files={"file": (f"cover.{extension}", data, content_type or "image/png")},
            data={"description": alt_text[:1500]},
            timeout=90,
        )
        if response.status_code not in {200, 202}:
            raise _error("Mastodon media", response)
        media = dict(response.json() or {})
        media_id = str(media.get("id") or "")
        if not media_id:
            return ""
        for _ in range(12):
            if media.get("url"):
                return media_id
            time.sleep(2)
            check = self.session.get(f"{self.base}/api/v1/media/{media_id}", timeout=30)
            if check.status_code == 200:
                media = dict(check.json() or {})
                if media.get("url"):
                    return media_id
        return media_id

    def post(
        self,
        text: str,
        *,
        url: str = "",
        image_data: bytes = b"",
        content_type: str = "image/png",
        image_alt: str = "",
    ) -> dict[str, Any]:
        if not self.configured:
            raise PlatformError("Mastodon token is not set")
        status_text = str(text or "").strip()
        if url and url not in status_text:
            suffix = f"\n\n{url}"
            status_text = status_text[: max(0, 500 - len(suffix))].rstrip() + suffix
        payload: dict[str, Any] = {
            "status": status_text[:500],
            "visibility": "public",
            "language": "en",
        }
        if image_data:
            media_id = self._upload_media(image_data, content_type, image_alt)
            if media_id:
                payload["media_ids"] = [media_id]
        response = self.session.post(f"{self.base}/api/v1/statuses", json=payload, timeout=45)
        if response.status_code not in {200, 201}:
            raise _error("Mastodon post", response)
        return dict(response.json() or {})


class FacebookClient:
    API = "https://graph.facebook.com/v26.0"

    def __init__(self, page_id: str, page_access_token: str):
        self.page_id = page_id.strip()
        self.token = page_access_token.strip()

    @property
    def configured(self) -> bool:
        return bool(self.page_id and self.token)

    def verify(self) -> dict[str, Any]:
        response = requests.get(
            f"{self.API}/{self.page_id}",
            params={"fields": "id,name", "access_token": self.token},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if response.status_code != 200:
            raise _error("Facebook", response)
        return dict(response.json() or {})

    def post(self, text: str, *, url: str = "") -> dict[str, Any]:
        if not self.configured:
            raise PlatformError("Facebook Page token is not set")
        payload: dict[str, Any] = {"message": str(text)[:5000], "access_token": self.token}
        if url.startswith("https://"):
            payload["link"] = url
        response = requests.post(
            f"{self.API}/{self.page_id}/feed",
            data=payload,
            headers={"User-Agent": USER_AGENT},
            timeout=45,
        )
        if response.status_code not in {200, 201}:
            raise _error("Facebook post", response)
        return dict(response.json() or {})
