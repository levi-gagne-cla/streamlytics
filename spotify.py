"""Browser-bound Spotify authorization; tokens never leave this Streamlit session."""

import base64
import hashlib
import html
import re
import secrets
import time
from collections.abc import MutableMapping
from urllib.parse import urlencode, urlsplit

import spotipy
import streamlit as st
from requests.exceptions import RequestException
from spotipy.cache_handler import CacheHandler
from spotipy.exceptions import SpotifyException, SpotifyOauthError
from spotipy.oauth2 import SpotifyPKCE

from auth_component import browser_auth

SPOTIFY_SCOPE = "user-read-private playlist-read-private playlist-read-collaborative user-top-read"
TOKEN_KEY = "spotify_token_info"
LOGIN_TTL_SECONDS = 600
AUTH_PARAMS = ("code", "state", "error", "error_description")


class SessionTokenCache(CacheHandler):
    def __init__(self, session: MutableMapping):
        self.session = session

    def get_cached_token(self):
        return self.session.get(TOKEN_KEY)

    def save_token_to_cache(self, token_info):
        self.session[TOKEN_KEY] = token_info


class SessionPKCE(SpotifyPKCE):
    def get_authorization_code(self, response=None):
        # Spotipy's interactive fallback would prompt on the shared app server.
        raise SpotifyOauthError("Reconnect Spotify from the app.")


def _settings():
    cfg = st.secrets["spotify"]
    client_id, redirect_uri = cfg["client_id"], cfg["redirect_uri"]
    url = urlsplit(redirect_uri)
    loopback = url.hostname in {"127.0.0.1", "::1"}
    if (
        not client_id
        or not url.hostname
        or url.hostname == "localhost"
        or url.fragment
        or not (url.scheme == "https" or (url.scheme == "http" and loopback))
    ):
        raise ValueError("Use an HTTPS redirect or an explicit loopback IP URL.")
    return client_id, redirect_uri


def _get_auth_manager(client_id, redirect_uri, session=None):
    return SessionPKCE(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=SPOTIFY_SCOPE,
        cache_handler=SessionTokenCache(st.session_state if session is None else session),
        open_browser=False,
        requests_timeout=15,
    )


def _validate_callback(params, pending, now=None):
    """Validate before exchanging any code, including denied authorization."""
    if any(len(params.get_all(key)) > 1 for key in AUTH_PARAMS):
        raise ValueError("Ambiguous OAuth callback.")
    state = params.get("state", "")
    if not isinstance(pending, dict) or not isinstance(state, str):
        raise ValueError("Missing browser login.")
    expected, verifier = pending.get("state"), pending.get("verifier")
    created = pending.get("created_at")
    if (
        not isinstance(expected, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", expected)
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", state)
        or not secrets.compare_digest(state, expected)
    ):
        raise ValueError("Login state mismatch.")
    if (
        not isinstance(created, (int, float))
        or not 0 <= ((time.time() if now is None else now) - created) <= LOGIN_TTL_SECONDS
    ):
        raise ValueError("Login expired.")
    if not isinstance(verifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", verifier):
        raise ValueError("Invalid PKCE verifier.")
    if "error" in params:
        raise ValueError("Spotify authorization was denied.")
    code = params.get("code", "")
    if not isinstance(code, str) or not code:
        raise ValueError("Missing authorization code.")
    return code, verifier


def _clear_callback():
    for key in AUTH_PARAMS:
        st.query_params.pop(key, None)


def _forget_spotify():
    for key in tuple(st.session_state):
        if key in (TOKEN_KEY, "spotify_client", "spotify_user") or key.startswith("studio_"):
            st.session_state.pop(key, None)


def logout_spotify():
    """Forget session data; Spotify's connected-app grant is revoked separately."""
    st.session_state.spotify_logout_pending = True
    client_id, redirect_uri = _settings()
    result = browser_auth("clear", client_id, redirect_uri)
    if not isinstance(result, dict) or result.get("status") not in {"cleared", "unavailable"}:
        st.stop()
    _clear_callback()
    st.session_state.clear()
    st.rerun()


def get_spotify_client():
    try:
        client_id, redirect_uri = _settings()
    except (KeyError, FileNotFoundError, ValueError):
        st.error("Configure Spotify client_id and redirect_uri in Streamlit secrets first.")
        st.stop()

    oauth = _get_auth_manager(client_id, redirect_uri)
    if any(key in st.query_params for key in AUTH_PARAMS):
        st.session_state.spotify_auth_started = True
        result = browser_auth(
            "consume", client_id, redirect_uri, callback_state=st.query_params.get("state", "")
        )
        if not isinstance(result, dict) or result.get("status") not in {
            "ready",
            "missing",
            "unavailable",
        }:
            st.stop()
        try:
            code, verifier = _validate_callback(st.query_params, result.get("pending"))
            _forget_spotify()
            oauth.code_verifier = verifier
            oauth.code_challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
                .decode("ascii")
                .rstrip("=")
            )
            # SpotifyPKCE saves the full token via our handler and returns a string.
            oauth.get_access_token(code, check_cache=False)
        except (ValueError, SpotifyOauthError, RequestException):
            _forget_spotify()
            st.session_state.spotify_login_error = (
                "Spotify login could not be completed. Start a new login in this tab."
            )
        finally:
            _clear_callback()
        st.rerun()

    if oauth.cache_handler.get_cached_token():
        try:
            token = oauth.validate_token(oauth.cache_handler.get_cached_token())
            if token is None:
                raise SpotifyOauthError("Reconnect Spotify.")
            # Every request obtains or refreshes this session's token.
            client = spotipy.Spotify(auth_manager=oauth, requests_timeout=15)
            if "spotify_user" not in st.session_state:
                st.session_state.spotify_user = client.current_user()
            st.session_state.spotify_client = client
            return client
        except (SpotifyOauthError, SpotifyException, RequestException):
            _forget_spotify()
            st.warning(
                "Spotify access is unavailable. Reconnect, or ask the app owner to add "
                "your Spotify account to the allowed users."
            )

    if error := st.session_state.pop("spotify_login_error", None):
        st.warning(error)
    authorize_url = "https://accounts.spotify.com/authorize?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SPOTIFY_SCOPE,
            "show_dialog": "true",
        }
    )
    result = browser_auth("login", client_id, redirect_uri, authorize_url=authorize_url)
    if isinstance(result, dict) and result.get("status") == "login_ready":
        login_url = result.get("authorize_url", "")
        destination = urlsplit(login_url)
        if destination.scheme == "https" and destination.netloc == "accounts.spotify.com":
            # Streamlit's component iframe cannot navigate its parent; this link can.
            st.markdown(
                f'<a href="{html.escape(login_url, quote=True)}" target="_self" '
                'rel="noreferrer">Connect with Spotify</a>',
                unsafe_allow_html=True,
            )
    st.info("Connect your own Spotify account. Login returns to this same browser tab.")
    st.stop()


def is_spotify_logged_in():
    return bool(st.session_state.get(TOKEN_KEY))
