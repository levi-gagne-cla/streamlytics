"""Poster rendering and its bounded, anonymous artwork fetch boundary."""

import io
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

import posters
from catalog import Selection, Track


def selection(*, size=16, image_url=None, title="My collection", demo=False):
    return Selection(
        key="test",
        title=title,
        subtitle="A playlist worth keeping",
        tracks=tuple(Track(f"Track {i}", ("Artist",), image_url=image_url) for i in range(size)),
        spotify_url="https://open.spotify.com/playlist/1234567890123456789012",
        is_demo=demo,
    )


class Response:
    def __init__(self, content=b"", status=200, headers=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, chunk_size):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]


def image_bytes(size=(120, 60), color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("style", posters.STYLES)
def test_demo_is_network_free_valid_png(style, monkeypatch):
    get = Mock(side_effect=AssertionError("Demo must not access the network"))
    monkeypatch.setattr(posters.requests, "get", get)
    result = posters.render_poster(posters.demo_selection(), "A sample collection", style=style)
    assert result.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(io.BytesIO(result)) as image:
        assert image.size == (2400, 3000)
        assert image.mode == "RGB"
        assert image.info["Source"] == ""
        assert "Original demo artwork" in image.info["Description"]
    get.assert_not_called()


@pytest.mark.parametrize("theme", posters.THEMES)
def test_long_unicode_labels_and_source_metadata(theme):
    value = "東京 🌿 Beyoncé " * 80
    result = posters.render_poster(selection(size=36, title=value), value, theme=theme, count=36)
    with Image.open(io.BytesIO(result)) as image:
        assert image.size == posters.SIZE
        assert image.info["Title"] == value.strip()
        assert image.info["Source"].endswith("1234567890123456789012")
        assert image.getpixel((0, 0)) == Image.new(
            "RGB", (1, 1), posters.THEMES[theme]["background"]
        ).getpixel((0, 0))


def test_downloads_only_requested_tracks(monkeypatch):
    download = Mock(return_value=None)
    monkeypatch.setattr(posters, "_download_image", download)
    posters.render_poster(
        selection(size=60, image_url="https://i.scdn.co/image/test"), "My music", count=4
    )
    assert download.call_count == 4


@pytest.mark.parametrize(
    "kwargs",
    [
        {"style": "Bogus"},
        {"theme": "Bogus"},
        {"count": 0},
        {"count": 37},
        {"count": -1},
        {"count": True},
        {"count": 1.5},
    ],
)
def test_invalid_controls_rejected(kwargs):
    with pytest.raises(ValueError):
        posters.render_poster(selection(), "My music", **kwargs)


def test_empty_collection_rejected():
    with pytest.raises(ValueError, match="at least one track"):
        posters.render_poster(selection(size=0), "My music")


@pytest.mark.parametrize(
    "url",
    [
        "http://i.scdn.co/image/test",
        "https://evil.example/image/test",
        "https://i.scdn.co.evil.example/image/test",
        "https://user:secret@i.scdn.co/image/test",
        "https://i.scdn.co:8443/image/test",
        "file:///etc/passwd",
        "https://127.0.0.1/test",
        "https://i.scdn.co",
        "https://i.scdn.co:invalid/test",
        None,
    ],
)
def test_untrusted_urls_do_not_make_requests(url, monkeypatch):
    get = Mock(side_effect=AssertionError("Untrusted URLs must never be requested"))
    monkeypatch.setattr(posters.requests, "get", get)
    assert posters._download_image(url) is None
    get.assert_not_called()


@pytest.mark.parametrize("host", ["i.scdn.co", "mosaic.scdn.co", "image-cdn-ak.spotifycdn.com"])
def test_spotify_art_fetch_is_bounded_and_anonymous(host, monkeypatch):
    get = Mock(return_value=Response(image_bytes()))
    monkeypatch.setattr(posters.requests, "get", get)
    image = posters._download_image(f"https://{host}/image/test")
    assert image.size == (120, 60)
    get.assert_called_once_with(
        f"https://{host}/image/test", stream=True, timeout=(3, 10), allow_redirects=False
    )


@pytest.mark.parametrize(
    "response",
    [
        Response(status=302, headers={"Location": "http://127.0.0.1/secret"}),
        Response(status=403),
        Response(b"not an image"),
        Response(headers={"Content-Length": str(posters._MAX_IMAGE_BYTES + 1)}),
        Response(headers={"Content-Length": "garbage"}),
    ],
)
def test_redirects_errors_and_bad_images_become_placeholders(response, monkeypatch):
    monkeypatch.setattr(posters.requests, "get", Mock(return_value=response))
    assert posters._download_image("https://i.scdn.co/image/test") is None


def test_streaming_byte_limit(monkeypatch):
    response = Response(b"x" * (posters._MAX_IMAGE_BYTES + 1))
    monkeypatch.setattr(posters.requests, "get", Mock(return_value=response))
    assert posters._download_image("https://i.scdn.co/image/test") is None


def test_decoded_pixel_limit(monkeypatch):
    monkeypatch.setattr(
        posters.requests, "get", Mock(return_value=Response(image_bytes((120, 60))))
    )
    monkeypatch.setattr(posters, "_MAX_IMAGE_PIXELS", 100)
    assert posters._download_image("https://i.scdn.co/image/test") is None


def test_timeout_does_not_leak_details(monkeypatch):
    monkeypatch.setattr(
        posters.requests, "get", Mock(side_effect=requests.Timeout("secret bearer token"))
    )
    assert posters._download_image("https://i.scdn.co/image/test") is None


def test_download_thumbnail_preserves_ratio(monkeypatch):
    monkeypatch.setattr(
        posters.requests, "get", Mock(return_value=Response(image_bytes((1600, 800))))
    )
    image = posters._download_image("https://i.scdn.co/image/test")
    assert image.size == (640, 320)


def test_cover_contains_full_image_without_overlay_or_crop():
    canvas = Image.new("RGB", (100, 100), "white")
    cover = Image.new("RGB", (200, 100), "red")
    for x in range(100, 200):
        for y in range(100):
            cover.putpixel((x, y), (0, 0, 255))
    posters._cover(canvas, cover, (0, 0, 100, 100), 0, posters.THEMES["Paper"], False)
    assert canvas.getpixel((0, 24)) == (255, 255, 255)
    assert canvas.getpixel((0, 25)) == (255, 0, 0)
    assert canvas.getpixel((99, 25)) == (0, 0, 255)
    assert canvas.getpixel((0, 75)) == (255, 255, 255)


def test_renderer_does_not_write_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    posters.render_poster(posters.demo_selection(), "My music", count=2)
    assert list(tmp_path.iterdir()) == []
