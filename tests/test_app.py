from pathlib import Path
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

import spotify

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SETTINGS = {"client_id": "test", "redirect_uri": "http://127.0.0.1:8501/"}


def test_home_starts_without_spotify_credentials():
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert app.button[0].label == "Log in to Spotify"


def test_login_prepares_browser_component_without_exposing_tokens():
    app = AppTest.from_file(APP)
    app.secrets["spotify"] = SETTINGS
    app.run().button[0].click().run()
    assert not app.exception
    assert len(app.get("component_instance")) == 1
    assert "spotify_token_info" not in app.session_state


def test_login_link_is_native_and_returns_to_same_tab(monkeypatch):
    monkeypatch.setattr(spotify, "browser_auth", Mock(return_value={
        "status": "login_ready",
        "authorize_url": "https://accounts.spotify.com/authorize?state=test&code_challenge=test",
    }))
    app = AppTest.from_file(APP)
    app.secrets["spotify"] = SETTINGS
    app.run().button[0].click().run()
    assert not app.exception
    links = [item.value for item in app.markdown if "Connect with Spotify</a>" in item.value]
    assert len(links) == 1
    assert 'target="_self"' in links[0]
    assert "&amp;code_challenge=" in links[0]


def test_home_processes_callback_without_old_login_session_flag(monkeypatch):
    monkeypatch.setattr(spotify, "browser_auth", Mock(return_value={"status": "missing", "pending": None}))
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
