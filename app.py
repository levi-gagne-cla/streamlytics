"""Streamlytics Studio: one source, one poster, one download."""

import re
from pathlib import Path

import streamlit as st

from catalog import (
    TOP_WINDOWS,
    Playlist,
    Selection,
    SourceError,
    find_year_end_playlists,
    list_playlists,
    load_playlist,
    load_top_tracks,
    parse_playlist_id,
)
from posters import STYLES, THEMES, demo_selection, render_poster
from spotify import get_spotify_client, is_spotify_logged_in, logout_spotify

ROOT = Path(__file__).parent
st.set_page_config(
    page_title="Streamlytics Studio",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def remember_selection(selection: Selection):
    st.session_state.studio_selection = selection
    st.session_state.pop("studio_poster", None)
    st.session_state.studio_title = selection.title
    st.session_state.studio_count = min(16, len(selection.tracks))


def clear_studio():
    for key in tuple(st.session_state):
        if key.startswith("studio_"):
            st.session_state.pop(key, None)


def load_source(loader, *args):
    for key in ("studio_selection", "studio_poster"):
        st.session_state.pop(key, None)
    try:
        with st.spinner("Getting your tracks…"):
            selection = loader(*args)
            if not selection.tracks:
                raise SourceError("No available music tracks were found in this source.")
            remember_selection(selection)
    except SourceError as error:
        st.error(str(error))


def show_privacy():
    with st.expander("Privacy & account control"):
        st.write(
            "Your Spotify tokens, selected tracks and generated posters live in your "
            "app session. We do not save them to a database or output folder. "
            "Disconnect clears the session; reloading may require signing in again."
        )
        st.write(
            "The app reads playlists and top tracks. It cannot control playback, "
            "change playlists or modify your library."
        )
        st.link_button("Revoke Spotify permission", "https://www.spotify.com/account/apps/")
        st.link_button(
            "Contact the maintainer", "https://github.com/levi-gagne-cla/streamlytics/issues"
        )


def source_picker(client):
    st.markdown("### 01 / Choose your music")
    kind = st.radio(
        "Music source",
        ["My playlists", "My top tracks", "Saved year-end"],
        horizontal=True,
        key="studio_source_kind",
    )
    if st.session_state.get("studio_previous_kind") != kind:
        st.session_state.studio_previous_kind = kind
        for key in ("studio_selection", "studio_poster", "studio_source_attempt"):
            st.session_state.pop(key, None)
    if kind == "My top tracks":
        period = st.selectbox(
            "Listening window",
            list(TOP_WINDOWS),
            index=2,
            format_func=lambda value: TOP_WINDOWS[value],
            key="studio_period",
        )
        st.caption("Spotify's current top-track rankings. These are not official Wrapped results.")
        attempt = f"top:{period}"
        if st.session_state.get("studio_source_attempt") != attempt:
            st.session_state.studio_source_attempt = attempt
            st.session_state.pop("studio_selection", None)
            st.session_state.pop("studio_poster", None)
            load_source(load_top_tracks, client, period)
        if st.button("Refresh top tracks", width="stretch"):
            st.session_state.pop("studio_source_attempt", None)
            st.rerun()
        return

    try:
        if "studio_playlists" not in st.session_state:
            with st.spinner("Finding your playlists…"):
                st.session_state.studio_playlists = list_playlists(client)
        playlists = st.session_state.studio_playlists
    except SourceError as error:
        st.error(str(error))
        playlists = ()

    if kind == "Saved year-end":
        choices = find_year_end_playlists(playlists)
        st.caption(
            "Looks for saved playlists named “Your Top Songs YYYY”. "
            "You choose which playlist to use; this does not retrieve Wrapped."
        )
        if not choices:
            st.info(
                "No matching playlist was found. Save your year-end playlist in Spotify, "
                "refresh this list, or paste a playlist link below."
            )
    else:
        query = (
            st.text_input(
                "Find a playlist", placeholder="Search your playlists", key="studio_search"
            )
            .casefold()
            .strip()
        )
        choices = tuple(p for p in playlists if query in p.name.casefold())
        if not choices:
            st.info("No playlists matched. You can also paste a playlist link below.")

    if choices:
        by_id = {p.id: p for p in choices}
        selected_id = st.selectbox(
            "Playlist",
            list(by_id),
            format_func=lambda value: f"{by_id[value].name} · {by_id[value].owner or value[-6:]}",
            key=f"studio_playlist_{kind}",
        )
        label = "Use my saved top songs" if kind == "Saved year-end" else "Use this playlist"
        if kind == "Saved year-end":
            attempt = f"playlist:{selected_id}"
            if st.session_state.get("studio_source_attempt") != attempt:
                st.session_state.studio_source_attempt = attempt
                st.session_state.pop("studio_selection", None)
                st.session_state.pop("studio_poster", None)
                load_source(load_playlist, client, by_id[selected_id])
        elif st.button(label, type="primary", width="stretch"):
            load_source(load_playlist, client, by_id[selected_id])

    if st.button("Refresh playlists", width="stretch"):
        st.session_state.pop("studio_playlists", None)
        st.rerun()

    with st.expander("Use a playlist link"):
        with st.form("playlist_link"):
            value = st.text_input(
                "Spotify playlist URL or URI", placeholder="https://open.spotify.com/playlist/…"
            )
            submitted = st.form_submit_button("Use playlist", width="stretch")
        if submitted:
            try:
                playlist_id = parse_playlist_id(value)
                load_source(load_playlist, client, Playlist(id=playlist_id, name="Playlist"))
            except ValueError:
                st.session_state.pop("studio_selection", None)
                st.session_state.pop("studio_poster", None)
                st.error("Paste a Spotify playlist link, URI, or playlist ID.")


def poster_editor(selection: Selection):
    st.markdown("### 02 / Make it yours")
    st.text(selection.title)
    st.caption(selection.subtitle)
    if selection.truncated:
        st.caption("This selection uses the first 500 playlist items.")
    with st.form("poster_editor"):
        title = st.text_input("Poster title", key="studio_title", max_chars=100)
        style = st.selectbox("Layout", STYLES, key="studio_style")
        theme = st.selectbox("Palette", list(THEMES), key="studio_theme")
        maximum = min(36, len(selection.tracks))
        count = st.number_input(
            "Tracks to include",
            min_value=1,
            max_value=maximum,
            step=1,
            key="studio_count",
        )
        submitted = st.form_submit_button("Create poster", type="primary", width="stretch")
    if submitted:
        try:
            with st.spinner("Creating your poster…"):
                st.session_state.studio_poster = render_poster(
                    selection,
                    title=title.strip() or selection.title,
                    style=style,
                    theme=theme,
                    count=int(count),
                )
                st.session_state.studio_filename = (
                    re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:60] or "my-music"
                ) + ".png"
                st.session_state.studio_rendered_count = int(count)
        except (ValueError, OSError):
            st.error("The poster could not be created. Try fewer tracks or a different layout.")


def poster_preview(selection: Selection | None):
    st.markdown("### 03 / Your poster")
    if poster := st.session_state.get("studio_poster"):
        st.image(poster, width="stretch")
        st.download_button(
            "Download PNG",
            data=poster,
            file_name=st.session_state.studio_filename,
            mime="image/png",
            type="primary",
            width="stretch",
            on_click="ignore",
        )
        st.caption("2400 × 3000 pixels · Made for sharing")
    else:
        st.markdown(
            '<div class="poster-empty"><span>YOUR MUSIC.</span><br>'
            "<span>YOUR WALL.</span><p>Choose a source, then create your poster.</p></div>",
            unsafe_allow_html=True,
        )
    if selection and selection.spotify_url:
        st.link_button("Open source on Spotify", selection.spotify_url, width="stretch")
    if selection and st.session_state.get("studio_poster"):
        with st.expander("Tracks in this poster"):
            count = st.session_state.studio_rendered_count
            for index, track in enumerate(selection.tracks[:count], 1):
                label = f"{index:02d} · {track.name} — {', '.join(track.artists)}"
                if track.spotify_url.startswith("https://open.spotify.com/"):
                    st.link_button(label, track.spotify_url)
                else:
                    st.text(label)


def main():
    st.markdown(
        """
        <style>
        .block-container { max-width: 1240px; padding-top: 2rem; padding-bottom: 3rem; }
        .studio-wordmark { font-size: 15px; font-weight: 750; letter-spacing: .13em; }
        .studio-hero { font-size: clamp(38px, 5vw, 68px); line-height: 1.04;
                       letter-spacing: -.055em; font-weight: 750; margin: 22px 0 14px; }
        .studio-hero em { color: #6d5ce7; font-style: normal; }
        .poster-empty { min-height: 540px; padding: 64px 38px; background: #e9e1d5;
                        display: flex; flex-direction: column; justify-content: center; }
        .poster-empty span { font-size: clamp(32px, 4vw, 52px); line-height: 1.06;
                             font-weight: 800; letter-spacing: -.06em; }
        .poster-empty p { font-size: 16px; line-height: 1.5; max-width: 260px; margin-top: 28px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="studio-wordmark">STREAMLYTICS / STUDIO</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="studio-hero">Your music.<br><em>Make it a keepsake.</em></div>',
        unsafe_allow_html=True,
    )
    st.write("A playlist, your top tracks, or a saved year-end mix. One poster worth keeping.")

    if st.session_state.get("spotify_logout_pending"):
        logout_spotify()
    demo = st.session_state.get("studio_demo", False)
    if not demo and not is_spotify_logged_in():
        st.caption("Personal beta · Connect your own account")
        if st.button("Try the demo", width="content"):
            clear_studio()
            st.session_state.studio_demo = True
            remember_selection(demo_selection())
            st.rerun()
        show_privacy()
        get_spotify_client()

    client = None if demo else get_spotify_client()
    account, action = st.columns([3, 1])
    with account:
        if demo:
            st.caption("DEMO MODE · Synthetic tracks and original placeholder art")
        else:
            user = st.session_state.spotify_user
            st.text(f"Connected as {user.get('display_name') or user['id']}")
    with action:
        if demo:
            if st.button("Connect Spotify", width="stretch"):
                clear_studio()
                st.rerun()
        elif st.button("Disconnect", width="stretch"):
            logout_spotify()
    st.divider()

    controls, preview = st.columns([1, 1.3], gap="large")
    with controls:
        if demo:
            st.markdown("### 01 / A sample mix")
            st.write("Try both layouts and palettes. Your account is not connected.")
        else:
            source_picker(client)
        selection = st.session_state.get("studio_selection")
        if selection and selection.tracks:
            st.divider()
            poster_editor(selection)
    with preview:
        poster_preview(st.session_state.get("studio_selection"))

    st.divider()
    if not demo:
        logo, attribution = st.columns([1, 5])
        with logo:
            st.image(str(ROOT / "assets" / "spotify-logo.png"), width=96)
        with attribution:
            st.caption("Music metadata and album artwork supplied by Spotify.")
    st.caption("Independent personal beta. Not affiliated with Spotify.")
    show_privacy()


if __name__ == "__main__":
    main()
