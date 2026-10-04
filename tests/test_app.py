import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import catalog
import spotify
from posters import demo_selection

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SETTINGS = {"client_id": "test", "redirect_uri": "http://127.0.0.1:8501/"}
PLAYLIST_ID = "a" * 22


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_home_starts_without_spotify_credentials():
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert button(app, "Try the demo")
    assert len(app.error) == 1


def test_login_prepares_browser_component_without_exposing_tokens():
    app = AppTest.from_file(APP)
    app.secrets["spotify"] = SETTINGS
    app.run()
    assert not app.exception
    assert len(app.get("component_instance")) == 1
    assert "spotify_token_info" not in app.session_state


def test_login_link_is_native_and_returns_to_same_tab(monkeypatch):
    monkeypatch.setattr(
        spotify,
        "browser_auth",
        Mock(
            return_value={
                "status": "login_ready",
                "authorize_url": "https://accounts.spotify.com/authorize?state=test&code_challenge=test",
            }
        ),
    )
    app = AppTest.from_file(APP)
    app.secrets["spotify"] = SETTINGS
    app.run()
    assert not app.exception
    links = [item.value for item in app.markdown if "Connect with Spotify</a>" in item.value]
    assert len(links) == 1
    assert 'target="_self"' in links[0]
    assert "&amp;code_challenge=" in links[0]


def test_home_processes_callback_without_old_login_session_flag(monkeypatch):
    monkeypatch.setattr(
        spotify, "browser_auth", Mock(return_value={"status": "missing", "pending": None})
    )
    exchange = Mock(side_effect=AssertionError("unbound code exchanged"))
    monkeypatch.setattr(spotify.SessionPKCE, "get_access_token", exchange)
    app = AppTest.from_file(APP)
    app.secrets["spotify"] = SETTINGS
    app.query_params.update({"code": "foreign", "state": "s" * 43})
    app.run()
    assert not app.exception
    assert not app.query_params
    assert "spotify_token_info" not in app.session_state
    assert app.warning[0].value.startswith("Spotify login could not be completed.")
    exchange.assert_not_called()


def test_demo_creates_download_without_spotify_network_or_disk(tmp_path, monkeypatch):
    monkeypatch.setattr("requests.get", Mock(side_effect=AssertionError("network used")))
    app = AppTest.from_file(APP).run()
    button(app, "Try the demo").click().run()
    assert not app.exception
    assert app.session_state["studio_selection"].is_demo
    button(app, "Create poster").click().run()
    assert not app.exception
    assert app.session_state["studio_poster"].startswith(b"\x89PNG")
    assert len(app.get("download_button")) == 1
    assert "spotify_token_info" not in app.session_state
    assert not tuple(tmp_path.iterdir())


def test_demo_sessions_keep_titles_and_posters_separate():
    a, b = (AppTest.from_file(APP).run() for _ in range(2))
    for app in (a, b):
        button(app, "Try the demo").click().run()
    a.text_input(key="studio_title").set_value("Alice mix")
    button(a, "Create poster").click().run()
    assert a.session_state["studio_filename"] == "alice-mix.png"
    assert b.session_state["studio_title"] == "Demo mix"
    assert "studio_poster" not in b.session_state


@pytest.fixture
def connected_app(monkeypatch):
    client = Mock()
    client.current_user.return_value = {"id": "listener", "display_name": "Listener"}
    monkeypatch.setattr(spotify.spotipy, "Spotify", Mock(return_value=client))
    app = AppTest.from_file(APP)
    app.secrets["spotify"] = SETTINGS
    app.session_state[spotify.TOKEN_KEY] = {
        "access_token": "session-only",
        "refresh_token": "refresh",
        "expires_at": time.time() + 3600,
        "scope": spotify.SPOTIFY_SCOPE,
    }
    return app, client


def test_top_tracks_shortcut_fetches_once_and_updates_window(connected_app, monkeypatch):
    app, _ = connected_app
    top = Mock(
        side_effect=lambda sp, period: catalog.Selection(
            key=f"top:{period}",
            title=period,
            subtitle="Affinity ranking",
            tracks=demo_selection().tracks,
            is_demo=True,
        )
    )
    monkeypatch.setattr(catalog, "list_playlists", Mock(return_value=()))
    monkeypatch.setattr(catalog, "load_top_tracks", top)
    app.run().radio(key="studio_source_kind").set_value("My top tracks").run()
    assert not app.exception
    top.assert_called_once()
    assert top.call_args.args[1] == "long_term"
    app.selectbox(key="studio_period").set_value("short_term").run()
    assert app.session_state["studio_selection"].key == "top:short_term"
    assert top.call_count == 2
    button(app, "Create poster").click().run()
    assert top.call_count == 2  # rendering/typing must not re-query Spotify
    app.radio(key="studio_source_kind").set_value("My playlists").run()
    app.radio(key="studio_source_kind").set_value("My top tracks").run()
    assert app.session_state["studio_selection"].key.startswith("top:")
    assert "studio_poster" not in app.session_state


def test_saved_year_end_shortcut_uses_latest_matching_playlist(connected_app, monkeypatch):
    app, _ = connected_app
    playlists = (
        catalog.Playlist(id="b" * 22, name="Your Top Songs 2024", owner="Spotify"),
        catalog.Playlist(id=PLAYLIST_ID, name="Your Top Songs 2025", owner="Spotify"),
    )
    monkeypatch.setattr(catalog, "list_playlists", Mock(return_value=playlists))
    load = Mock(
        side_effect=lambda sp, playlist: catalog.Selection(
            key=f"playlist:{playlist.id}",
            title=playlist.name,
            subtitle="Saved playlist",
            tracks=demo_selection().tracks,
            is_demo=True,
        )
    )
    monkeypatch.setattr(catalog, "load_playlist", load)
    app.run().radio(key="studio_source_kind").set_value("Saved year-end").run()
    assert not app.exception
    assert load.call_args.args[1].id == PLAYLIST_ID
    assert app.session_state["studio_selection"].title == "Your Top Songs 2025"


def test_forbidden_year_end_does_not_leave_previous_poster(connected_app, monkeypatch):
    app, _ = connected_app
    monkeypatch.setattr(
        catalog,
        "list_playlists",
        Mock(return_value=(catalog.Playlist(id=PLAYLIST_ID, name="Your Top Songs 2025"),)),
    )
    monkeypatch.setattr(
        catalog, "load_playlist", Mock(side_effect=catalog.SourceError("Access denied", status=403))
    )
    app.session_state["studio_selection"] = demo_selection()
    app.session_state["studio_poster"] = b"old"
    app.run().radio(key="studio_source_kind").set_value("Saved year-end").run()
    assert not app.exception
    assert app.error[0].value == "Access denied"
    assert "studio_selection" not in app.session_state
    assert "studio_poster" not in app.session_state


def test_failed_manual_playlist_never_leaves_previous_download(connected_app, monkeypatch):
    app, _ = connected_app
    playlists = (
        catalog.Playlist(id=PLAYLIST_ID, name="First mix"),
        catalog.Playlist(id="b" * 22, name="Second mix"),
    )
    monkeypatch.setattr(catalog, "list_playlists", Mock(return_value=playlists))
    first = catalog.Selection(
        key=f"playlist:{PLAYLIST_ID}",
        title="First mix",
        subtitle="Playlist",
        tracks=demo_selection().tracks,
        is_demo=True,
    )
    monkeypatch.setattr(
        catalog,
        "load_playlist",
        Mock(side_effect=[first, catalog.SourceError("Access denied", status=403)]),
    )
    app.run()
    button(app, "Use this playlist").click().run()
    button(app, "Create poster").click().run()
    assert "studio_poster" in app.session_state
    app.selectbox(key="studio_playlist_My playlists").set_value("b" * 22).run()
    button(app, "Use this playlist").click().run()
    assert not app.exception
    assert app.error[0].value == "Access denied"
    assert "studio_selection" not in app.session_state
    assert "studio_poster" not in app.session_state
    assert not app.get("download_button")
