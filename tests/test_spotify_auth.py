import base64
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from spotipy.exceptions import SpotifyOauthError

import spotify


class Params(dict):
    def get_all(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]


class Session(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


class Rerun(Exception):
    pass


def token(access="alice", refresh="alice-refresh", expires=None):
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": time.time() + 3600 if expires is None else expires,
        "scope": spotify.SPOTIFY_SCOPE,
    }


def pending():
    return {"state": "s" * 43, "verifier": "v" * 86, "created_at": 1000}


def test_callback_validation():
    assert spotify._validate_callback(Params(code="code", state="s" * 43), pending(), now=1001) == (
        "code",
        "v" * 86,
    )


@pytest.mark.parametrize(
    "params,handshake,now",
    [
        (Params(code="code"), pending(), 1001),
        (Params(code="code", state="x" * 43), pending(), 1001),
        (Params(code="code", state="ü" * 43), pending(), 1001),
        (Params(code="code", state="s" * 43), None, 1001),
        (Params(code="code", state="s" * 43), pending(), 1601),
        (Params(code="code", state="s" * 43), pending(), 999),
        (Params(code="", state="s" * 43), pending(), 1001),
        (Params(error="access_denied", state="s" * 43), pending(), 1001),
        (Params(code=["one", "two"], state="s" * 43), pending(), 1001),
        (Params(code="code", state=["s" * 43, "x" * 43]), pending(), 1001),
        (Params(code="code", state="s" * 43), {**pending(), "verifier": "/" * 43}, 1001),
    ],
)
def test_rejects_unbound_expired_denied_or_duplicate_callback(params, handshake, now):
    with pytest.raises(ValueError):
        spotify._validate_callback(params, handshake, now=now)


def test_tokens_and_refresh_are_isolated_from_disk_and_other_sessions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".cache").write_text('{"access_token":"owner"}')
    alice, bob = {}, {}
    a = spotify._get_auth_manager("client", "http://127.0.0.1:8501/", alice)
    b = spotify._get_auth_manager("client", "http://127.0.0.1:8501/", bob)
    assert a.cache_handler.get_cached_token() is None
    assert b.cache_handler.get_cached_token() is None
    a.cache_handler.save_token_to_cache(token(expires=0))
    b.cache_handler.save_token_to_cache(token("bob", "bob-refresh"))
    response = Mock()
    response.json.return_value = {
        "access_token": "alice-refreshed",
        "expires_in": 3600,
        "scope": spotify.SPOTIFY_SCOPE,
    }
    a._session = Mock()
    a._session.post.return_value = response
    assert a.get_access_token() == "alice-refreshed"
    assert alice[spotify.TOKEN_KEY]["refresh_token"] == "alice-refresh"
    assert b.get_access_token() == "bob"
    assert bob[spotify.TOKEN_KEY]["refresh_token"] == "bob-refresh"
    assert [p.name for p in tmp_path.iterdir()] == [".cache"]
    assert (tmp_path / ".cache").read_text() == '{"access_token":"owner"}'


def test_missing_token_never_prompts_or_opens_server_browser(monkeypatch):
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("stdin used")))
    oauth = spotify._get_auth_manager("client", "http://127.0.0.1:8501/", {})
    with pytest.raises(SpotifyOauthError, match="Reconnect"):
        oauth.get_access_token()


def test_existing_pages_refresh_on_api_requests():
    session = {spotify.TOKEN_KEY: token(expires=0)}
    oauth = spotify._get_auth_manager("client", "http://127.0.0.1:8501/", session)
    response = Mock()
    response.json.return_value = {
        "access_token": "fresh",
        "expires_in": 3600,
        "scope": spotify.SPOTIFY_SCOPE,
    }
    oauth._session = Mock()
    oauth._session.post.return_value = response
    client = spotify.spotipy.Spotify(auth_manager=oauth)
    assert client._auth_headers() == {"Authorization": "Bearer fresh"}
    assert session[spotify.TOKEN_KEY]["access_token"] == "fresh"


def fake_streamlit(monkeypatch, params=None, session=None):
    session = Session() if session is None else session
    ui = SimpleNamespace(
        secrets={"spotify": {"client_id": "client", "redirect_uri": "http://127.0.0.1:8501/"}},
        session_state=session,
        query_params=Params() if params is None else params,
        warning=Mock(),
        error=Mock(),
        info=Mock(),
        rerun=Mock(side_effect=Rerun),
        stop=Mock(side_effect=Rerun),
    )
    monkeypatch.setattr(spotify, "st", ui)
    return ui


def test_callback_restores_pkce_and_publishes_client_after_redirect(monkeypatch):
    handshake = {**pending(), "created_at": time.time()}
    ui = fake_streamlit(
        monkeypatch, Params(code="alice-code", state=handshake["state"], keep="yes")
    )
    monkeypatch.setattr(
        spotify, "browser_auth", Mock(return_value={"status": "ready", "pending": handshake})
    )
    oauth = spotify._get_auth_manager("client", "http://127.0.0.1:8501/")
    monkeypatch.setattr(spotify, "_get_auth_manager", Mock(return_value=oauth))
    response = Mock()
    response.json.return_value = {
        "access_token": "alice",
        "refresh_token": "refresh",
        "expires_in": 3600,
        "scope": spotify.SPOTIFY_SCOPE,
    }
    oauth._session = Mock()
    oauth._session.post.return_value = response
    with pytest.raises(Rerun):
        spotify.get_spotify_client()
    payload = oauth._session.post.call_args.kwargs["data"]
    assert payload["code_verifier"] == handshake["verifier"]
    assert payload["code"] == "alice-code"
    assert oauth.code_challenge == base64.urlsafe_b64encode(
        hashlib.sha256(handshake["verifier"].encode()).digest()
    ).decode().rstrip("=")
    assert ui.session_state[spotify.TOKEN_KEY]["access_token"] == "alice"
    assert ui.query_params == {"keep": "yes"}
    client = Mock()
    client.current_user.return_value = {"id": "alice"}
    monkeypatch.setattr(spotify.spotipy, "Spotify", Mock(return_value=client))
    assert spotify.get_spotify_client() is client
    assert ui.session_state.spotify_client is client
    assert ui.session_state.spotify_user == {"id": "alice"}


def test_invalid_callback_never_exchanges_a_code(monkeypatch):
    ui = fake_streamlit(monkeypatch, Params(code="foreign", state="x" * 43))
    monkeypatch.setattr(
        spotify, "browser_auth", Mock(return_value={"status": "ready", "pending": pending()})
    )
    exchange = Mock(side_effect=AssertionError("code exchanged"))
    monkeypatch.setattr(spotify.SessionPKCE, "get_access_token", exchange)
    with pytest.raises(Rerun):
        spotify.get_spotify_client()
    exchange.assert_not_called()
    assert not ui.query_params
    assert spotify.TOKEN_KEY not in ui.session_state


def test_logout_waits_for_browser_ack_and_clears_session_data(monkeypatch):
    ui = fake_streamlit(
        monkeypatch,
        session=Session(
            {
                spotify.TOKEN_KEY: token(),
                "spotify_client": Mock(),
                "selected_tracks": ["private"],
            }
        ),
    )
    browser = Mock(return_value={"status": "ready"})  # stale component result
    monkeypatch.setattr(spotify, "browser_auth", browser)
    with pytest.raises(Rerun):
        spotify.logout_spotify()
    assert spotify.TOKEN_KEY in ui.session_state
    browser.return_value = {"status": "cleared"}
    with pytest.raises(Rerun):
        spotify.logout_spotify()
    assert not ui.session_state


@pytest.mark.parametrize(
    "uri",
    [
        "http://localhost:8501/",
        "https://localhost:8501/",
        "http://example.com/",
        "ftp://example.com/",
    ],
)
def test_redirect_rejects_insecure_or_localhost_urls(monkeypatch, uri):
    ui = fake_streamlit(monkeypatch)
    ui.secrets["spotify"]["redirect_uri"] = uri
    with pytest.raises(ValueError):
        spotify._settings()
