# Streamlytics

A personal Streamlit app for exploring Spotify listening data and creating cover-art posters. The existing analytics, playback, exports, Billboard, playlist art, top-track art, and output pages remain in place.

Spotify sign-in belongs to each browser session. The app uses Authorization Code with PKCE, verifies the callback state, and keeps access and refresh tokens in Streamlit session memory. It does not use Spotipy's shared disk token cache. A friend's Spotify requests therefore use the account that friend authorizes, rather than a cached account belonging to the app owner.

**Launch limitation:** generated JSON, cover images, and posters still use shared server directories. Account authentication is isolated; generated files are not. Keep this as a limited personal beta until output isolation, cleanup, and the cover-art policy review are complete. See [privacy and release limitations](docs/privacy.md).

## Run locally

Use Python 3.12, matching CI and the recommended Community Cloud setting.

```sh
git clone https://github.com/levi-gagne-cla/streamlytics.git
cd streamlytics
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

On Windows, activate with `.venv\Scripts\activate`.

In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), use your app's Client ID and register `http://127.0.0.1:8501/` as a redirect URI. Edit `.streamlit/secrets.toml`:

```toml
[spotify]
client_id = "your-spotify-client-id"
redirect_uri = "http://127.0.0.1:8501/"
```

PKCE does not require a client secret. Do not add an owner access token or refresh token to configuration. The real secrets file is ignored by Git.

```sh
python -m streamlit run app.py
```

Open **http://127.0.0.1:8501/**, even if Streamlit prints a `localhost` link. Spotify does not accept `localhost` as a redirect URI, and pending login state must remain on the same origin and browser tab. Use the app's **Log in to Spotify** flow, complete Spotify authorization, and return to Home. See [deployment](docs/deployment.md) for hosted configuration and troubleshooting.

## What the app reads and changes

| Page | Existing behavior |
| --- | --- |
| Analytics | Spotify library totals, top tracks, and top artists |
| Playback | Current/recent playback and playback controls for the connected account |
| Download Statistics | CSV exports of available Spotify account data |
| Billboard 100 | Historical chart data from the repository's Parquet file, with metadata enrichment |
| Playlist Cover Art | Playlist tracks and album covers for poster generation |
| Top Tracks Cover Art | Spotify top-track lists and poster generation |
| Outputs | Checked-in example images |

Top tracks are Spotify's calculated affinity lists over approximate time windows. They are not complete listening history, exact annual play counts, or Spotify Wrapped. Do not label a poster as an official Wrapped result. Endpoint availability also depends on the Spotify app's access mode and history.

The retained Playback page requests permission to control the connected user's playback. Unused email, playlist-write, library-write, and follow permissions are not requested. [Privacy details](docs/privacy.md) describe the remaining scopes and storage.

## Sign-in behavior

- Each browser tab keeps only its pending PKCE verifier and random state in `sessionStorage`, with a ten-minute validity window. Tokens never go into browser storage.
- OAuth must finish in the same tab. A new tab, a cleared storage area, or an expired request requires starting login again.
- Reloading the app or restarting the server can reset the Streamlit session and require login again. Navigation through the app's own pages retains the session.
- Logging out clears the app's session data. It does not log out of Spotify itself or revoke Spotify authorization. To disconnect permission, remove Streamlytics from your [Spotify account's Apps page](https://www.spotify.com/account/apps/).

## Tests and deployment

```sh
python -m pip install -r requirements-dev.txt
python -m ruff check spotify.py auth_component.py tests
python -m pytest -q
node --test tests/auth_component.test.cjs
python -m compileall -q app.py spotify.py auth_component.py coverArt.py image_processing.py spotify_cover_art.py utils.py pages tests
```

The browser-component protocol tests use Node 22; no npm build or JavaScript packages are required. GitHub Actions runs these checks on pull requests and pushes to `main`, plus a Streamlit HTTP health check. Tests do not log into Spotify or validate a deployed callback end to end.

Community Cloud supplies GitHub-based deployment after its one-time app setup. Configure it to run `app.py` from the deployment branch and put the hosted redirect URI in its app settings. Require the CI check before merging to that branch; Community Cloud itself does not wait for GitHub Actions. [Deployment guide](docs/deployment.md)

## Before sharing more broadly

Spotify's current Development Mode allows up to five allowlisted users and requires the app owner to have Premium. Some existing allowlisted users may be grandfathered. Correct OAuth does not remove those platform limits. New extended-access applications are currently restricted to qualifying organizations. [Spotify quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)

Review Spotify's [Developer Policy](https://developer.spotify.com/policy) and [design guidelines](https://developer.spotify.com/documentation/design) before distributing downloadable cover-art collages. They restrict standalone cover-art products, require attribution and links, and prohibit cropping or overlays. Existing poster layouts have not been redesigned or approved in this authentication change.

## License

No license has been selected or added to this repository. The previous README's MIT claim was unsupported. Choose a license and review the rights for bundled fonts, logos, datasets, and images before distributing the project as open source. Spotify content remains subject to its own terms.
