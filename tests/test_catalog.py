"""Source behavior without Spotify credentials or real account requests."""

from unittest.mock import Mock

import pytest
from requests.exceptions import ConnectionError, Timeout
from spotipy.exceptions import SpotifyException, SpotifyOauthError

from catalog import (
    MAX_PLAYLIST_ITEMS,
    Playlist,
    SourceError,
    find_year_end_playlists,
    list_playlists,
    load_playlist,
    load_top_tracks,
    parse_playlist_id,
)

PLAYLIST_ID = "3cEYpjA9oz9GiPac4AsH4n"
SECOND_ID = "37i9dQZF1DXcBWIGoYBM5M"
TRACK_ID = "2jCnn1QPQ3E8ExtLe6INsx"


def track(name="Song", **changes):
    return {
        "id": TRACK_ID,
        "type": "track",
        "name": name,
        "artists": [{"name": "Artist"}],
        "album": {"name": "Album", "images": [{"url": "https://i.scdn.co/image/cover"}]},
        **changes,
    }


def page(items, next_url=None):
    return {"items": items, "next": next_url}


def client():
    sp = Mock(
        spec=["current_user_playlists", "current_user_top_tracks", "playlist", "_get", "next"]
    )
    sp.playlist.return_value = {
        "id": PLAYLIST_ID,
        "name": "Latest title",
        "owner": {"display_name": "Levi"},
        "images": [],
    }
    return sp


@pytest.mark.parametrize(
    "value",
    [
        PLAYLIST_ID,
        f"spotify:playlist:{PLAYLIST_ID}",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}/?si=A0_-abc",
        f"  https://open.spotify.com/playlist/{PLAYLIST_ID}?si=abc  ",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=dd7SD75pRmWqm2cfXxBZ_A&pi=rUMOHlMtTvC9P",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?pi=rUMOHlMtTvC9P",
    ],
)
def test_parse_playlist_id_extracts_only_id(value):
    assert parse_playlist_id(value) == PLAYLIST_ID


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        f"spotify:track:{TRACK_ID}",
        f"http://open.spotify.com/playlist/{PLAYLIST_ID}",
        f"https://open.spotify.com.evil.test/playlist/{PLAYLIST_ID}",
        f"https://open.spotify.com@evil.test/playlist/{PLAYLIST_ID}",
        f"https://evil.test@open.spotify.com/playlist/{PLAYLIST_ID}",
        f"https://open.spotify.com:443/playlist/{PLAYLIST_ID}",
        f"https://open.spotify.com/track/{PLAYLIST_ID}",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}/more",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?redirect=https://evil.test",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=first&si=second",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?pi=first&pi=second",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?pi=",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}?pi={'x' * 201}",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID}#fragment",
        f"https://open.spotify.com/playlist/{PLAYLIST_ID[:10]}\n{PLAYLIST_ID[10:]}",
        f"https://open.spotify.com/playlist/%2f{PLAYLIST_ID}",
    ],
)
def test_parse_playlist_id_rejects_other_objects_and_untrusted_links(value):
    with pytest.raises(ValueError, match="Spotify playlist"):
        parse_playlist_id(value)


def test_library_paginates_and_keeps_equal_names_as_distinct_ids():
    sp = client()
    first = page(
        [
            None,
            {"id": PLAYLIST_ID, "name": "Favorites", "owner": {"display_name": "Levi"}},
        ],
        "https://api.spotify.com/v1/me/playlists?offset=50",
    )
    sp.current_user_playlists.return_value = first
    sp.next.return_value = page(
        [
            {"id": SECOND_ID, "name": "Favorites", "owner": None, "images": None},
            {"id": None, "name": "Unavailable"},
        ]
    )

    playlists = list_playlists(sp)

    assert [playlist.id for playlist in playlists] == [PLAYLIST_ID, SECOND_ID]
    assert [playlist.name for playlist in playlists] == ["Favorites", "Favorites"]
    assert playlists[1].owner == ""
    assert playlists[1].image_url is None
    sp.current_user_playlists.assert_called_once_with(limit=50)
    sp.next.assert_called_once_with(first)


def test_empty_library_returns_no_playlists():
    sp = client()
    sp.current_user_playlists.return_value = page([])
    assert list_playlists(sp) == ()
    sp.next.assert_not_called()


def test_playlist_uses_current_items_endpoint_and_preserves_duplicate_tracks():
    sp = client()
    first = page(
        [
            {"item": track("First")},
            {"item": track("Repeat")},
        ],
        "https://api.spotify.com/v1/playlists/next",
    )
    sp._get.return_value = first
    sp.next.return_value = page([{"item": track("Repeat")}, {"item": track("Last")}])

    selection = load_playlist(sp, Playlist(PLAYLIST_ID, "Old title"))

    assert selection.key == f"playlist:{PLAYLIST_ID}"
    assert selection.title == "Latest title"
    assert selection.subtitle == "Playlist by Levi"
    assert selection.spotify_url == f"https://open.spotify.com/playlist/{PLAYLIST_ID}"
    assert [song.name for song in selection.tracks] == ["First", "Repeat", "Repeat", "Last"]
    assert selection.tracks[0].artists == ("Artist",)
    assert selection.tracks[0].album == "Album"
    assert selection.tracks[0].spotify_url == f"https://open.spotify.com/track/{TRACK_ID}"
    assert selection.truncated is False
    sp._get.assert_called_once_with(f"playlists/{PLAYLIST_ID}/items", limit=50)
    sp.next.assert_called_once_with(first)


def test_playlist_skips_unsupported_items_and_handles_sparse_metadata():
    sp = client()
    sp._get.return_value = page(
        [
            None,
            {},
            {"item": None},
            {"item": track(type="episode")},
            {"is_local": True, "item": track()},
            {"item": track(is_local=True)},
            {"item": track(is_playable=False)},
            {"item": track(name="")},
            {"item": {"type": "track", "name": "Sparse", "album": None, "artists": None}},
            {"item": track("Available", artists=[None, {"name": ""}, {"name": "Singer"}])},
        ]
    )

    songs = load_playlist(sp, Playlist(PLAYLIST_ID, "Playlist")).tracks

    assert [song.name for song in songs] == ["Sparse", "Available"]
    assert songs[0].artists == ()
    assert songs[0].album == ""
    assert songs[0].image_url is None
    assert songs[0].spotify_url == ""
    assert songs[1].artists == ("Singer",)


def test_playlist_cap_counts_raw_items_and_does_not_request_an_extra_page():
    sp = client()
    pages = [
        page(
            [{"item": track(str(index * 50 + offset))} for offset in range(50)], f"next:{index + 1}"
        )
        for index in range(10)
    ]
    pages[0]["items"][0] = {"item": None}
    sp._get.return_value = pages[0]
    sp.next.side_effect = pages[1:]

    selection = load_playlist(sp, Playlist(PLAYLIST_ID, "Playlist"))

    assert selection.truncated is True
    assert len(selection.tracks) == MAX_PLAYLIST_ITEMS - 1
    assert selection.tracks[-1].name == "499"
    assert sp.next.call_count == 9


def test_exact_cap_without_another_page_is_complete():
    sp = client()
    pages = [
        page([{"item": track()} for _ in range(50)], f"next:{index + 1}") for index in range(10)
    ]
    pages[-1]["next"] = None
    sp._get.return_value = pages[0]
    sp.next.side_effect = pages[1:]
    selection = load_playlist(sp, Playlist(PLAYLIST_ID, "Playlist"))
    assert len(selection.tracks) == MAX_PLAYLIST_ITEMS
    assert selection.truncated is False


@pytest.mark.parametrize(
    "status, fragment",
    [
        (401, "reconnect"),
        (403, "own or collaborate"),
        (404, "unavailable"),
        (429, "Wait"),
        (500, "later"),
    ],
)
def test_playlist_failures_are_actionable_and_hide_response_bodies(status, fragment):
    sp = client()
    sp._get.side_effect = SpotifyException(status, -1, "Bearer secret-token; private-account")
    with pytest.raises(SourceError, match=fragment) as failure:
        load_playlist(sp, Playlist(PLAYLIST_ID, "Playlist"))
    assert failure.value.status == status
    assert "secret-token" not in str(failure.value)
    assert "private-account" not in str(failure.value)
    assert failure.value.__suppress_context__ is True
    sp.next.assert_not_called()


@pytest.mark.parametrize(
    "error, fragment",
    [
        (Timeout("secret"), "too long"),
        (ConnectionError("secret"), "reach Spotify"),
        (SpotifyOauthError("secret"), "reconnect"),
    ],
)
def test_network_and_refresh_failures_have_safe_messages(error, fragment):
    sp = client()
    sp.current_user_playlists.side_effect = error
    with pytest.raises(SourceError, match=fragment) as failure:
        list_playlists(sp)
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize(
    "time_range, window",
    [
        ("short_term", "~4 weeks"),
        ("medium_term", "~6 months"),
        ("long_term", "~1 year"),
    ],
)
def test_top_tracks_are_an_affinity_snapshot_and_never_wrapped(time_range, window):
    sp = client()
    sp.current_user_top_tracks.return_value = page([track("One"), None, track("Two")], "more")
    selection = load_top_tracks(sp, time_range)
    assert window in selection.title
    assert "affinity" in selection.subtitle
    assert "not Spotify Wrapped" in selection.subtitle
    assert [song.name for song in selection.tracks] == ["One", "Two"]
    assert selection.key == f"top:{time_range}"
    sp.current_user_top_tracks.assert_called_once_with(limit=50, time_range=time_range)
    sp.next.assert_not_called()


def test_invalid_top_window_makes_no_request():
    sp = client()
    with pytest.raises(ValueError, match="short_term"):
        load_top_tracks(sp, "wrapped_2026")
    sp.current_user_top_tracks.assert_not_called()


def test_year_end_discovery_is_an_exact_name_heuristic_sorted_by_year():
    playlists = tuple(
        Playlist(str(index), name)
        for index, name in enumerate(
            [
                "Your Top Songs 2023",
                "your top songs 2025",
                "Your Top Songs 2024",
                "Top Songs 2025",
                "Your Top Songs 2025 remix",
                "Your Top Songs 20250",
                "Wrapped 2025",
            ]
        )
    )
    assert [playlist.name for playlist in find_year_end_playlists(playlists)] == [
        "your top songs 2025",
        "Your Top Songs 2024",
        "Your Top Songs 2023",
    ]


@pytest.mark.parametrize("response", [None, {}, {"items": None}, {"items": [], "next": []}])
def test_incomplete_library_responses_are_source_failures(response):
    sp = client()
    sp.current_user_playlists.return_value = response
    with pytest.raises(SourceError, match="incomplete"):
        list_playlists(sp)


def test_repeated_pagination_does_not_loop_forever():
    sp = client()
    repeated = page([], "https://api.spotify.com/v1/me/playlists?offset=50")
    sp.current_user_playlists.return_value = repeated
    sp.next.return_value = repeated
    with pytest.raises(SourceError, match="repeated page"):
        list_playlists(sp)
    sp.next.assert_called_once()


def test_invalid_playlist_id_makes_no_request():
    sp = client()
    with pytest.raises(ValueError, match="Spotify playlist"):
        load_playlist(sp, Playlist("../../me", "Malicious"))
    sp.playlist.assert_not_called()
    sp._get.assert_not_called()
