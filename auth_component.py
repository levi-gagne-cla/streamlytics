"""Local component for a same-tab OAuth roundtrip. No frontend build required."""

from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "spotify_browser_auth", path=str(Path(__file__).parent / "auth_component")
)


def browser_auth(action, client_id, redirect_uri, **kwargs):
    return _component(
        action=action,
        storage_key=f"streamlytics:spotify:{client_id}:{redirect_uri}",
        ttl_seconds=600,
        key="spotify_browser_auth",
        default=None,
        **kwargs,
    )
