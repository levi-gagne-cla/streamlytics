"""Render shareable playlist prints without storing listener data or artwork on disk."""

from __future__ import annotations

import io
import math
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps, PngImagePlugin

from catalog import Selection, Track

STYLES = ("Gallery", "Receipt")
THEMES = {
    "Paper": {
        "background": "#F3EFE5",
        "foreground": "#191916",
        "accent": "#D3562D",
        "muted": "#645F56",
    },
    "Midnight": {
        "background": "#141B2D",
        "foreground": "#F4F0E5",
        "accent": "#B79AF8",
        "muted": "#ACAFC0",
    },
    "Mint": {
        "background": "#F5F8F3",
        "foreground": "#25342F",
        "accent": "#2E775C",
        "muted": "#67776E",
    },
}
SIZE = (2400, 3000)
MAX_TRACKS = 36
_MAX_IMAGE_BYTES = 2 * 1024 * 1024
_MAX_IMAGE_PIXELS = 8_000_000
_IMAGE_HOSTS = frozenset({"i.scdn.co", "mosaic.scdn.co", "image-cdn-ak.spotifycdn.com"})


def _font(size: int) -> ImageFont.FreeTypeFont:
    # Pillow bundles its default Aileron face, so deployed prints do not depend
    # on a machine's fonts or the old repository's unverified font files.
    return ImageFont.load_default(size=size)


def _text(value: str) -> str:
    """Keep user-controlled labels on one line; the bundled font has limited glyphs."""
    return " ".join(str(value).replace("\x00", "").split())


def _width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _fit(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont, width: int) -> str:
    text = _text(value)
    if _width(draw, text, font) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        midpoint = (low + high + 1) // 2
        if _width(draw, text[:midpoint] + "…", font) <= width:
            low = midpoint
        else:
            high = midpoint - 1
    return text[:low].rstrip() + "…"


def _lines(
    draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont, width: int
) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in _text(value).split():
        candidate = f"{line} {word}".strip()
        if line and _width(draw, candidate, font) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]


def _title(draw: ImageDraw.ImageDraw, value: str, color: str) -> None:
    title = _text(value) or "My music, in print"
    for size in range(138, 73, -4):
        font = _font(size)
        lines = _lines(draw, title, font, 2120)
        if len(lines) <= 2 and all(_width(draw, line, font) <= 2120 for line in lines):
            break
    for index, line in enumerate(lines[:2]):
        if index == 1 and len(lines) > 2:
            line = " ".join(lines[1:])
        draw.text((140, 186 + index * 151), _fit(draw, line, font, 2120), fill=color, font=font)


def _valid_image_url(url: str | None) -> bool:
    if not url or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname in _IMAGE_HOSTS
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
            and bool(parsed.path.strip("/"))
        )
    except ValueError:
        return False


def _download_image(url: str | None) -> Image.Image | None:
    """Bound both compressed and decoded image sizes; never follow CDN redirects."""
    if not _valid_image_url(url):
        return None
    try:
        with requests.get(url, stream=True, timeout=(3, 10), allow_redirects=False) as response:
            if response.status_code != 200:
                return None
            length = response.headers.get("Content-Length")
            if length and int(length) > _MAX_IMAGE_BYTES:
                return None
            content = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if len(content) + len(chunk) > _MAX_IMAGE_BYTES:
                    return None
                content.extend(chunk)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > _MAX_IMAGE_PIXELS:
                    return None
                image = ImageOps.exif_transpose(image)
                image.thumbnail((640, 640), Image.Resampling.LANCZOS)
                return image.convert("RGB")
    except (
        requests.RequestException,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return None


def _artwork(tracks: Iterable[Track]) -> list[Image.Image | None]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(_download_image, (track.image_url for track in tracks)))


def _placeholder(size: int, index: int, colors: dict[str, str], demo: bool) -> Image.Image:
    image = Image.new("RGB", (size, size), colors["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, size - 2, size - 2), outline=colors["accent"], width=max(2, size // 120))
    if demo:
        # Original geometric sample covers; no third-party album artwork.
        inset = size // 8
        for offset in range(3):
            radius = size // 7 + offset * size // 12
            center_x = size // 2 + ((index % 3) - 1) * size // 12
            center_y = size // 2
            draw.ellipse(
                (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
                outline=colors["accent"] if offset % 2 == 0 else colors["foreground"],
                width=max(2, size // 30),
            )
        draw.text(
            (inset, inset),
            f"{index + 1:02d}",
            font=_font(max(14, size // 9)),
            fill=colors["foreground"],
        )
        draw.text(
            (inset, size - inset - size // 16),
            "DEMO",
            font=_font(max(10, size // 20)),
            fill=colors["muted"],
        )
    elif size >= 90:
        font = _font(max(12, size // 24))
        label = "ARTWORK UNAVAILABLE"
        draw.text((size // 2, size // 2), label, font=font, fill=colors["muted"], anchor="mm")
    return image


def _cover(
    canvas: Image.Image,
    image: Image.Image | None,
    box: tuple[int, int, int, int],
    index: int,
    colors: dict[str, str],
    demo: bool,
) -> None:
    x, y, width, height = box
    if image is None:
        image = _placeholder(min(width, height), index, colors, demo)
    # Contain the complete image. No cropping, overlays, rounded corners, or filters.
    fitted = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
    canvas.paste(fitted, (x + (width - fitted.width) // 2, y + (height - fitted.height) // 2))


def _gallery(
    canvas: Image.Image,
    tracks: tuple[Track, ...],
    artwork: list[Image.Image | None],
    colors: dict[str, str],
    demo: bool,
) -> None:
    draw = ImageDraw.Draw(canvas)
    columns = min(6, max(2, math.ceil(math.sqrt(len(tracks)))))
    rows = math.ceil(len(tracks) / columns)
    cell_width, cell_height = 2120 / columns, 1890 / rows
    size = int(min(cell_width - 36, cell_height - 104, 620))
    name_font = _font(min(38, max(25, size // 10)))
    artist_font = _font(min(28, max(20, size // 14)))
    for index, (track, image) in enumerate(zip(tracks, artwork)):
        row, column = divmod(index, columns)
        x = int(140 + column * cell_width + (cell_width - size) / 2)
        y = int(650 + row * cell_height + max(0, (cell_height - size - 104) / 2))
        _cover(canvas, image, (x, y, size, size), index, colors, demo)
        draw.text(
            (x, y + size + 15),
            _fit(draw, track.name, name_font, size),
            font=name_font,
            fill=colors["foreground"],
        )
        draw.text(
            (x, y + size + 61),
            _fit(draw, ", ".join(track.artists), artist_font, size),
            font=artist_font,
            fill=colors["muted"],
        )


def _receipt(
    canvas: Image.Image,
    tracks: tuple[Track, ...],
    artwork: list[Image.Image | None],
    colors: dict[str, str],
    demo: bool,
) -> None:
    draw = ImageDraw.Draw(canvas)
    row_height = min(122, 1890 / len(tracks))
    cover_size = int(min(102, row_height - 14))
    name_font = _font(min(47, max(23, int(row_height * 0.38))))
    artist_font = _font(min(29, max(19, int(row_height * 0.25))))
    number_font = _font(min(35, max(22, int(row_height * 0.31))))
    for index, (track, image) in enumerate(zip(tracks, artwork)):
        y = int(650 + index * row_height)
        draw.text(
            (140, y + row_height / 2),
            f"{index + 1:02d}",
            font=number_font,
            fill=colors["accent"],
            anchor="lm",
        )
        _cover(canvas, image, (237, y + 7, cover_size, cover_size), index, colors, demo)
        x = 237 + cover_size + 30
        name_y = y + max(0, (row_height - name_font.size - artist_font.size - 6) / 2)
        draw.text(
            (x, name_y),
            _fit(draw, track.name, name_font, 2260 - x),
            font=name_font,
            fill=colors["foreground"],
        )
        draw.text(
            (x, name_y + name_font.size + 9),
            _fit(draw, ", ".join(track.artists), artist_font, 2260 - x),
            font=artist_font,
            fill=colors["muted"],
        )
    ending = min(2590, int(650 + len(tracks) * row_height + 45))
    draw.line((140, ending, 2260, ending), fill=colors["accent"], width=2)
    draw.text(
        (140, ending + 24), "A collection worth keeping.", font=_font(35), fill=colors["muted"]
    )


def render_poster(
    selection: Selection, title: str, style: str = "Gallery", theme: str = "Paper", count: int = 16
) -> bytes:
    """Return a 2400 × 3000 PNG; authenticated data and downloaded art stay local to this call."""
    if style not in STYLES:
        raise ValueError(f"Unknown poster style: {style}")
    if theme not in THEMES:
        raise ValueError(f"Unknown poster theme: {theme}")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_TRACKS:
        raise ValueError(f"Track count must be between 1 and {MAX_TRACKS}")
    tracks = tuple(selection.tracks[:count])
    if not tracks:
        raise ValueError("Choose a collection with at least one track")
    colors = THEMES[theme]
    canvas = Image.new("RGB", SIZE, colors["background"])
    draw = ImageDraw.Draw(canvas)
    draw.text((140, 105), "STREAMLYTICS", font=_font(41), fill=colors["foreground"])
    draw.text(
        (2260, 113), "YOUR MUSIC / IN PRINT", font=_font(27), fill=colors["accent"], anchor="ra"
    )
    _title(draw, title or selection.title, colors["foreground"])
    subtitle = selection.subtitle or selection.title
    draw.text(
        (140, 501), _fit(draw, subtitle, _font(36), 1810), font=_font(36), fill=colors["muted"]
    )
    draw.text(
        (2260, 506), f"{len(tracks):02d} TRACKS", font=_font(30), fill=colors["accent"], anchor="ra"
    )
    draw.line((140, 589, 2260, 589), fill=colors["foreground"], width=2)
    artwork = [None] * len(tracks) if selection.is_demo else _artwork(tracks)
    (_gallery if style == "Gallery" else _receipt)(
        canvas, tracks, artwork, colors, selection.is_demo
    )
    draw.line((140, 2720, 2260, 2720), fill=colors["foreground"], width=2)
    draw.text((140, 2760), "MADE WITH STREAMLYTICS", font=_font(30), fill=colors["accent"])
    source = selection.spotify_url
    attribution = (
        "Original demo artwork · Sample music labels"
        if selection.is_demo
        else "Artwork and music data provided by Spotify"
    )
    draw.text((140, 2814), attribution, font=_font(27), fill=colors["muted"])
    if not selection.is_demo:
        # Preserve the existing official mark and its aspect ratio.
        with Image.open(Path(__file__).parent / "assets" / "spotify-logo.png") as mark:
            mark = mark.convert("RGBA")
            mark.thumbnail((240, 72), Image.Resampling.LANCZOS)
            canvas.paste(mark, (2260 - mark.width, 2760), mark)
    if source:
        draw.text(
            (140, 2862),
            _fit(draw, source, _font(26), 2120),
            font=_font(26),
            fill=colors["foreground"],
        )
    else:
        draw.text(
            (140, 2862),
            "Demo collection" if selection.is_demo else "Spotify listening collection",
            font=_font(26),
            fill=colors["muted"],
        )
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Title", _text(title or selection.title))
    metadata.add_text("Source", source)
    metadata.add_text("Description", attribution)
    metadata.add_text(
        "TrackLinks", "\n".join(track.spotify_url for track in tracks if track.spotify_url)
    )
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG", pnginfo=metadata, optimize=False)
    return buffer.getvalue()


def demo_selection() -> Selection:
    """A network-free collection with original geometric artwork, safe to preview."""
    names = (
        "Golden Hour",
        "After the Rain",
        "Late Checkout",
        "Low Tide",
        "Soft Focus",
        "The Long Way Home",
        "Sunday Morning",
        "Night Drive",
        "Quiet Company",
        "Second Wind",
        "Open Windows",
        "Little Detours",
        "Electric Blue",
        "Somewhere New",
        "Daydream Radio",
        "Stay a While",
    )
    return Selection(
        key="demo",
        title="Demo mix",
        subtitle="Original sample collection · 16 tracks",
        tracks=tuple(Track(name=name, artists=("Streamlytics demo",)) for name in names),
        is_demo=True,
    )
