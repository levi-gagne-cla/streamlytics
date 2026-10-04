# Contributing

Use Python 3.12 and Node 22. The app needs no npm build. Develop against the playlist-studio branch while the separate rewrite is under review; do not replace the original deployment branch implicitly.

```sh
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
node --test tests/auth_component.test.cjs
python -m compileall -q app.py spotify.py auth_component.py catalog.py posters.py tests
```

Use offline demo data and fixtures for automated checks. Do not require real Spotify tokens in tests, print credentials, write user images/data to disk, or put user-specific data in a global Streamlit cache. Keep OAuth state verification and the explicit session-only Spotipy cache intact.

Preserve source order, label affinity windows and truncation honestly, keep artwork uncropped, and retain source attribution. Add tests for meaningful behavior changes in fetching, authentication, or rendering. Run the [live acceptance check](docs/deployment.md#acceptance-check) before a release that changes OAuth or Spotify endpoint behavior.

Open a pull request with the concrete behavior change and validation. Keep deployment changes explicit. See [product scope](docs/product.md) before adding pages, accounts, storage, or background work. Report problems without private account data or tokens; no software license has been selected yet.
