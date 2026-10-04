# Streamlytics

A small Spotify playlist poster studio built with Streamlit. Choose a playlist or your current top tracks, customize a Gallery or Receipt poster, and download a PNG. One page, one workflow.

This rewrite is a separate proposal on `rewrite/playlist-studio`. The original app remains in `main`; opening this pull request does not deploy the rewrite.

## Try it

Use Python 3.12:

```sh
git clone https://github.com/levi-gagne-cla/streamlytics.git
cd streamlytics
git switch rewrite/playlist-studio
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate`.

The offline demo needs no Spotify account, configuration, or API connection. Its invented tracks and original geometric cover tiles are labeled as demo content.

## Connect your Spotify account

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, then set:

```toml
[spotify]
client_id = "your-spotify-client-id"
redirect_uri = "http://127.0.0.1:8501/"
```

Register that exact Home URL in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard). Open **http://127.0.0.1:8501/** and complete login in the same browser tab. Spotify rejects `localhost` redirect aliases. When hosted, use the exact HTTPS app URL instead.

The app uses Authorization Code with PKCE: no client secret, no owner token in config, no shared disk token cache. It verifies callback state and keeps each user's Spotify tokens in their Streamlit session. Disconnect clears that session's data; removing the grant requires [Spotify account → Apps](https://www.spotify.com/account/apps/). [Privacy and account control](docs/privacy.md)

## Sources and output

| Source | What it means |
| --- | --- |
| Your playlists | Owned or followed playlists returned for the connected account |
| Saved year-end playlists | Opens the newest accessible saved `Your Top Songs YYYY` match; choose another year when available |
| My top tracks | Opens the approximate one-year affinity list in one click; switch to four weeks or six months |
| Offline demo | Invented tracks and original generated color tiles |

The app does not fetch official Wrapped results, exact calendar-year listening counts, or a complete listening archive. A saved year-end playlist is a playlist source, not a Wrapped API response. Spotify's release date for future Wrapped content is not promised by this app.

Posters use Gallery or Receipt layouts, Paper/Midnight/Mint themes, and up to 36 tracks. Downloads are **2400 × 3000 PNGs**. Covers keep their aspect ratio. Spotify outputs carry attribution, playlist links when available, and track links in PNG metadata; the app also links each track. Track lists, fetched images, and generated PNGs stay in session memory; the app writes no user outputs to shared server directories.

Spotify API access still depends on the app's quota mode, allowlist, and endpoint access. An older client may have access that a newly created client lacks. See [deployment and compatibility](docs/deployment.md).

## Development and deployment

```sh
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
node --test tests/auth_component.test.cjs
python -m compileall -q app.py spotify.py auth_component.py catalog.py posters.py tests
```

Node 22 runs the browser-component protocol tests; no npm build is needed. CI checks the whole Python codebase, auth/source/rendering tests, component protocol, compilation, and Streamlit server startup. It does not perform live Spotify authorization. [Contributing](CONTRIBUTING.md)

Community Cloud can deploy `app.py` from a GitHub branch after one-time configuration. Protect the deployment branch with the CI check before merge; Cloud does not wait for Actions. [Deployment guide](docs/deployment.md)

## Before public release

The PNG feature works for personal beta testing. That does not establish permission to redistribute Spotify artwork: its policy restricts standalone content products, and the interpretation for downloadable collages remains unresolved. Review attribution, links, artwork treatment, and distribution rights before a public launch. [Product scope and release checks](docs/product.md)

No software license has been chosen or added. Decide on one before presenting the project as open source; Spotify content remains subject to its own terms. See [third-party asset notes](THIRD_PARTY.md). Streamlytics is an independent personal project and is not endorsed by Spotify.
