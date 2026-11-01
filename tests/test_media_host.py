from datetime import datetime, timezone

import pytest

from ghos_v6.media_host import GitHubReleaseMediaHost, MediaHostError
from ghos_v6.telegraph import TelegraphClient, TelegraphError


def _fixed_now():
    return datetime(2026, 11, 1, tzinfo=timezone.utc)


def test_GitHub_release_host_creates_monthly_prerelease_and_uploads_asset():
    calls = []

    def fake(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "GET" and url.endswith("/releases/tags/media-2026-11"):
            return 404, {"message": "Not Found"}, None
        if method == "POST" and url.endswith("/releases"):
            body = kwargs["json_body"]
            assert body["tag_name"] == "media-2026-11"
            assert body["prerelease"] is True
            return (
                201,
                {
                    "id": 7,
                    "upload_url": "https://uploads.github.com/repos/acme/repo/releases/7/assets{?name,label}",
                },
                None,
            )
        if method == "POST" and url.startswith("https://uploads.github.com/"):
            assert kwargs["data"] == b"png-bytes"
            assert kwargs["params"]["name"].startswith("card-")
            assert kwargs["params"]["name"].endswith(".png")
            return (
                201,
                {
                    "browser_download_url": (
                        "https://github.com/acme/repo/releases/download/"
                        "media-2026-11/card.png"
                    )
                },
                None,
            )
        raise AssertionError((method, url))

    host = GitHubReleaseMediaHost("token", "acme/repo", request_fn=fake, now_fn=_fixed_now)
    url = host.upload_image(b"png-bytes", filename="card.png")
    assert url.startswith("https://github.com/acme/repo/releases/download/media-2026-11/")
    assert [call[0] for call in calls] == ["GET", "POST", "POST"]


def test_GitHub_release_host_reuses_deterministic_asset_on_already_exists():
    def fake(method, url, **kwargs):
        if method == "GET":
            return (
                200,
                {
                    "id": 7,
                    "upload_url": "https://uploads.github.com/repos/acme/repo/releases/7/assets{?name,label}",
                },
                None,
            )
        return 422, {"errors": [{"code": "already_exists", "field": "name"}]}, None

    host = GitHubReleaseMediaHost("token", "acme/repo", request_fn=fake, now_fn=_fixed_now)
    url = host.upload_image(b"same-bytes", filename="cover.png")
    assert "/releases/download/media-2026-11/cover-" in url
    assert url.endswith(".png")


def test_GitHub_release_host_requires_token_and_repository():
    host = GitHubReleaseMediaHost("", "", request_fn=lambda *a, **k: (500, {}, None))
    with pytest.raises(MediaHostError):
        host.upload_image(b"png")


def test_telegraph_upload_surfaces_unknown_error_string(monkeypatch):
    class Response:
        status_code = 400

        @staticmethod
        def json():
            return "Unknown error"

    monkeypatch.setattr(
        "ghos_v6.telegraph.requests.post", lambda *args, **kwargs: Response()
    )
    with pytest.raises(TelegraphError, match="Unknown error"):
        TelegraphClient("token").upload_image(b"png-bytes")
