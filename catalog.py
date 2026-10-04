"""Read-only Spotify sources; data is returned to the requesting browser session."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from requests.exceptions import RequestException, Timeout
from spotipy.exceptions import SpotifyException, SpotifyOauthError

MAX_PLAYLIST_ITEMS = 500
TOP_WINDOWS = {
    "short_term": "~4 weeks",
    "medium_term": "~6 months",
    "long_term": "~1 year",
}
_SPOTIFY_ID = re.compile(r"[A-Za-z0-9]{22}")
_YEAR_END_NAME = re.compile(r"Your Top Songs (20\d{2})", re.IGNORECASE)


@dataclass(frozen=True)
class Track:
    name: str
    artists: tuple[str, ...]
    album: str = ""
    image_url: str | None = None
    spotify_url: str = ""


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    owner: str = ""
    spotify_url: str = ""
    image_url: str | None = None


@dataclass(frozen=True)
class Selection:
    key: str
    title: str
    subtitle: str
    tracks: tuple[Track, ...]
    spotify_url: str = ""
    is_demo: bool = False
    truncated: bool = False


class SourceError(RuntimeError):
    """An actionable source failure without response bodies or authorization data."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def parse_playlist_id(value: str) -> str:
    """Accept a Spotify playlist link/URI/ID; never request a user-supplied URL."""
    value = value.strip()
    if _SPOTIFY_ID.fullmatch(value):
        return value
    if match := re.fullmatch(r"spotify:playlist:([A-Za-z0-9]{22})", value):
        return match[1]
    try:
        url = urlsplit(value)
        match = re.fullmatch(r"/playlist/([A-Za-z0-9]{22})/?", url.path)
        query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        if (
            url.scheme == "https"
            and url.netloc == "open.spotify.com"
            and match
            and not url.fragment
            and not any(ord(char) < 32 for char in value)
            and all(
                key in {"si", "pi"}
                and len(values) == 1
                and re.fullmatch(r"[A-Za-z0-9_-]{1,200}", values[0])
                for key, values in query.items()
            )
        ):
            return match[1]
    except ValueError:
        pass
    raise ValueError("Use a Spotify playlist link, Spotify playlist URI, or playlist ID.")


def _request(function: Callable, *args, playlist: bool = False, **kwargs) -> Any:
    try:
        return function(*args, **kwargs)
    except SpotifyOauthError:
        raise SourceError(
            "Spotify authorization expired. Disconnect and reconnect your account."
        ) from None
    except SpotifyException as exc:
        status = exc.http_status
        if status == 401:
            message = "Spotify authorization expired. Disconnect and reconnect your account."
        elif status == 403 and playlist:
            message = (
                "Spotify denied access to this playlist. Choose one you own or collaborate on. "
                "For a Spotify-owned year-end playlist, make your own copy in Spotify first. "
                "Also check the app's allowed users and permissions."
            )
        elif status == 403:
            message = (
                "Spotify denied access. Check the app's allowed users and permissions, "
                "then reconnect your account."
            )
        elif status == 404:
            message = "This Spotify source is unavailable. Check the playlist link and your access."
        elif status == 429:
            message = "Spotify is limiting requests. Wait before trying again."
        else:
            message = "Spotify is unavailable right now. Try again later."
        raise SourceError(message, status=status) from None
    except Timeout:
        raise SourceError("Spotify took too long to respond. Try again.") from None
    except RequestException:
        raise SourceError("Could not reach Spotify. Try again.") from None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _image(images: Any) -> str | None:
    if not isinstance(images, list):
        return None
    return next(
        (
            image["url"]
            for image in images
            if isinstance(image, dict) and _text(image.get("url")).startswith("https://")
        ),
        None,
    )


def _spotify_url(data: Mapping, kind: str) -> str:
    if _SPOTIFY_ID.fullmatch(_text(data.get("id"))):
        return f"https://open.spotify.com/{kind}/{data['id']}"
    urls = data.get("external_urls") or {}
    value = _text(urls.get("spotify")) if isinstance(urls, dict) else ""
    return (
        value
        if re.fullmatch(rf"https://open\.spotify\.com/{kind}/[A-Za-z0-9]{{22}}", value)
        else ""
    )


def _playlist(data: Any) -> Playlist | None:
    if not isinstance(data, dict) or not _SPOTIFY_ID.fullmatch(_text(data.get("id"))):
        return None
    owner = data.get("owner") or {}
    return Playlist(
        id=data["id"],
        name=_text(data.get("name")) or "Untitled playlist",
        owner=(_text(owner.get("display_name")) or _text(owner.get("id")))
        if isinstance(owner, dict)
        else "",
        spotify_url=_spotify_url(data, "playlist"),
        image_url=_image(data.get("images")),
    )


def _track(data: Any) -> Track | None:
    if (
        not isinstance(data, dict)
        or data.get("type") != "track"
        or data.get("is_local")
        or data.get("is_playable") is False
        or not _text(data.get("name"))
    ):
        return None
    album = data.get("album") or {}
    artists = data.get("artists") or []
    return Track(
        name=_text(data["name"]),
        artists=tuple(
            _text(artist.get("name"))
            for artist in artists
            if isinstance(artist, dict) and _text(artist.get("name"))
        ),
        album=_text(album.get("name")) if isinstance(album, dict) else "",
        image_url=_image(album.get("images")) if isinstance(album, dict) else None,
        spotify_url=_spotify_url(data, "track"),
    )


def _page(data: Any) -> dict:
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("items"), list)
        or (data.get("next") is not None and not isinstance(data["next"], str))
    ):
        raise SourceError("Spotify returned an incomplete response. Try again.")
    return data


def list_playlists(sp) -> tuple[Playlist, ...]:
    """Read every library page, preserving playlist IDs and library order."""
    page = _page(_request(sp.current_user_playlists, limit=50))
    playlists, visited = [], set()
    while True:
        playlists.extend(playlist for item in page["items"] if (playlist := _playlist(item)))
        if not page.get("next"):
            return tuple(playlists)
        if page["next"] in visited:
            raise SourceError("Spotify returned a repeated page. Try again.")
        visited.add(page["next"])
        page = _page(_request(sp.next, page))


def load_playlist(sp, playlist: Playlist) -> Selection:
    """Load the first 500 items; missing/local/episode items do not reorder tracks."""
    playlist_id = parse_playlist_id(playlist.id)
    metadata = _request(
        sp.playlist, playlist_id, fields="id,name,owner,external_urls,images", playlist=True
    )
    playlist = _playlist(metadata) or playlist
    # Spotipy 2.25.2's public playlist_items() still calls deprecated /tracks.
    # This pinned transport uses the current /items endpoint and its `item` field.
    page = _page(_request(sp._get, f"playlists/{playlist_id}/items", limit=50, playlist=True))
    tracks, visited, consumed = [], set(), 0
    while True:
        remaining = MAX_PLAYLIST_ITEMS - consumed
        for item in page["items"][:remaining]:
            if (
                isinstance(item, dict)
                and not item.get("is_local")
                and (track := _track(item.get("item")))
            ):
                tracks.append(track)
        consumed += min(len(page["items"]), remaining)
        truncated = len(page["items"]) > remaining or (
            consumed == MAX_PLAYLIST_ITEMS and bool(page.get("next"))
        )
        if truncated or not page.get("next"):
            return Selection(
                key=f"playlist:{playlist_id}",
                title=playlist.name,
                subtitle=f"Playlist by {playlist.owner}" if playlist.owner else "Spotify playlist",
                tracks=tuple(tracks),
                spotify_url=playlist.spotify_url,
                truncated=truncated,
            )
        if page["next"] in visited:
            raise SourceError("Spotify returned a repeated page. Try again.")
        visited.add(page["next"])
        page = _page(_request(sp.next, page, playlist=True))


def load_top_tracks(sp, time_range: str) -> Selection:
    """A bounded affinity snapshot, never an annual Wrapped or listening count."""
    if time_range not in TOP_WINDOWS:
        raise ValueError("Choose short_term, medium_term, or long_term.")
    page = _page(_request(sp.current_user_top_tracks, limit=50, time_range=time_range))
    return Selection(
        key=f"top:{time_range}",
        title=f"My top tracks · {TOP_WINDOWS[time_range]}",
        subtitle="Spotify affinity ranking · approximate window · not Spotify Wrapped",
        tracks=tuple(track for item in page["items"][:50] if (track := _track(item))),
    )


def find_year_end_playlists(playlists: tuple[Playlist, ...]) -> tuple[Playlist, ...]:
    """Name matches only: a playlist title cannot verify official Wrapped data."""
    matches = (
        (int(match[1]), playlist)
        for playlist in playlists
        if (match := _YEAR_END_NAME.fullmatch(playlist.name.strip()))
    )
    return tuple(
        playlist for _, playlist in sorted(matches, key=lambda item: item[0], reverse=True)
    )
