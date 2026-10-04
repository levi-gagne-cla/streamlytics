# Playlist studio scope

## Goal

Turn a user's chosen Spotify playlist or current top-track list into a useful, shareable poster. Keep the workflow small: choose source → customize → preview → download. The original multi-page app stays available on `main` while this rewrite is reviewed separately.

## Included

- A single Streamlit page and an offline demo with original synthetic content.
- Per-browser Spotify PKCE sign-in with verified state and session-only tokens.
- Playlist selection, best-effort saved `Your Top Songs YYYY` discovery, and top-track affinity periods labeled approximately four weeks, six months, and one year.
- Gallery and Receipt PNGs at 2400 × 3000 pixels, up to 36 tracks, three themes, and a custom title.
- Memory-only source data, artwork, settings, previews, and downloads; no shared files or account writes.

No playback control, Billboard integration, account dashboard, exact listening counts, account-side playlist creation, or official Wrapped API is included. Existing saved year-end playlists are ordinary playlist sources and can be inaccessible under some Spotify access modes.

## Implementation boundaries

| Module | Responsibility |
| --- | --- |
| `app.py` | Source/customization/preview/download flow and session state |
| `spotify.py` | PKCE callback validation, account identity, refresh, and logout |
| `auth_component.py` + `auth_component/index.html` | Same-tab pending OAuth storage and Streamlit component protocol |
| `catalog.py` | Spotify playlist/top-track source models and bounded fetching |
| `posters.py` | Original demo source, artwork retrieval, and in-memory PNG rendering |

List playlist pages fully, then load no more than the first 500 playlist items for a chosen source. Skip unsupported/unavailable entries and preserve the remaining order and duplicates. Top-track sources are limited to 50 items; poster rendering selects up to 36. A truncated source must be identified in the UI instead of presented as a complete playlist.

Keep source loading separate from rendering so the offline demo and renderer tests need no Spotify account. Do not add a persistent database or background jobs unless a product requirement earns them.

## Release checks

- Complete the live two-account isolation and download check from [deployment](deployment.md), including refresh, denial, expired state, forbidden sources, and disconnect.
- Verify the app's existing Client ID, endpoint access, allowlist, and Premium-owner status.
- Resolve Spotify artwork attribution/linking and public-distribution interpretation; personal beta testing is not an exemption.
- Decide the repository's software license and confirm bundled assets are distributable.
- Require CI on the deployment branch, verify the hosted redirect, and publish operator/contact information with [privacy behavior](privacy.md).

Aim to review the flow before year-end playlist sharing, but do not promise a Spotify Wrapped release date or exact yearly metrics.
