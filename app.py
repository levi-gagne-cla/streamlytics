# app.py

import streamlit as st
from spotify import get_spotify_client, is_spotify_logged_in, logout_spotify

# Define green shades
green_shades = [
    "rgb(98, 201, 106)",    # Color 1
    "rgb(120, 216, 130)",   # Color 2
    "rgb(142, 231, 154)",   # Color 3
    "rgb(165, 241, 178)"    # Color 4
]

# Set up Streamlit page configuration
st.set_page_config(page_title="Streamlytics", layout="wide")

# Auth state flag (whether user clicked the login button)
if "spotify_auth_started" not in st.session_state:
    st.session_state.spotify_auth_started = False


def main():
    # Apply global styles to set the page background to black
    st.markdown(
        """
        <style>
        /* Set the entire page background to black */
        body {
            background-color: rgb(0, 0, 0);
        }
        /* Optional: Adjust the main container's padding */
        .css-18e3th9 {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Title with grey box and Color 1, including bottom margin for spacing
    st.markdown(
        f"""
        <div style="
            background-color: rgb(32, 32, 32); 
            padding: 20px; 
            border-radius: 10px; 
            text-align: center; 
            margin-bottom: 20px;">
            <h1 style="color: {green_shades[0]};">Streamlytics</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.write("Click the button below to log in to Spotify and start exploring your analytics.")

    if st.session_state.get("spotify_logout_pending"):
        logout_spotify()

    # External OAuth navigation creates a new session: process its callback directly.
    callback = any(key in st.query_params for key in ("code", "state", "error", "error_description"))
    if not is_spotify_logged_in() and st.button("Log in to Spotify"):
        st.session_state.spotify_auth_started = True

    # If auth has been started, try to run the OAuth flow
    if callback or is_spotify_logged_in() or st.session_state.spotify_auth_started:
        # This will either:
        # - show a login link and st.stop(), or
        # - complete the code exchange and store the token,
        # - or return a ready client (which we don't need to hold here).
        get_spotify_client()

    # Status section
    if is_spotify_logged_in():
        user = st.session_state.spotify_user
        st.success(f"Connected to Spotify as {user.get('display_name') or user['id']} ({user['id']}).")
        st.caption("Playback controls use this account. To switch accounts, disconnect and sign into the other account on Spotify.")
        st.link_button("Manage Spotify app access", "https://www.spotify.com/account/apps/")
        if st.button("Disconnect Spotify"):
            logout_spotify()
    else:
        st.warning("Not logged in. Please log in to access Spotify data.")
    
    # Updated About Section
    st.markdown(
        f"""
        <div style="
            background-color: rgb(32, 32, 32); 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;">
            <h3 style="color: {green_shades[1]};">About the App</h3>
            <p style="color: white; font-size: 18px;">
                Streamlytics is your one-stop solution for exploring and visualizing your Spotify streaming habits. 
                Discover trends in your listening behavior, analyze your most-played tracks and artists, and create 
                stunning posters featuring your top songs and playlists. The app also provides a seamless way to compare 
                your personal music taste with the Billboard Hot 100.
            </p>
            <p style="color: white; font-size: 18px;">
                Whether you're a casual listener or a dedicated music enthusiast, Streamlytics helps you uncover 
                insights into your music journey with a beautifully designed, user-friendly interface.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Features box with detailed feature breakdown
    st.markdown(
        f"""
        <div style="
            background-color: rgb(32, 32, 32); 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;">
            <h4 style="color: {green_shades[2]};">Features & Page Overview</h4>
            <ul style="color: white; font-size: 16px;">
                <li>
                    <strong style="color: {green_shades[3]};">🔑 Home Page (app.py):</strong> 
                    Securely log in to your Spotify account and navigate through the app's features.
                </li>
                <li>
                    <strong style="color: {green_shades[3]};">📊 Analytics Dashboard (1_Analytics.py):</strong> 
                    Explore detailed insights about your listening history, including top tracks and artists.
                </li>
                <li>
                    <strong style="color: {green_shades[3]};">⏮ Playback History (2_Playback.py):</strong> 
                    Review your recent playback history with timestamps and track details.
                </li>
                <li>
                    <strong style="color: {green_shades[3]};">📥 Download Statistics (3_Download_Statistics.py):</strong> 
                    Export your Spotify listening data in CSV format for further analysis.
                </li>
                <li>
                    <strong style="color: {green_shades[3]};">📈 Billboard Hot 100 (4_Billboard_100.py):</strong> 
                    Compare your Spotify listening trends with the latest Billboard Hot 100 charts.
                </li>
                <li>
                    <strong style="color: {green_shades[3]};">🎨 Playlist Cover Art (5_Playlist_Cover_Art.py):</strong> 
                    Generate high-resolution collages using album covers from your playlists.
                </li>
                <li>
                    <strong style="color: {green_shades[3]};">🏆 Top Tracks Posters (6_Top_Tracks_Cover_Art.py):</strong> 
                    Create visually appealing posters showcasing your top tracks.
                </li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Add vertical space
    st.markdown("<br><br>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
