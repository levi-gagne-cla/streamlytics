# Privacy and account control

Streamlytics is an independent personal project. It uses the Spotify account you authorize to read playlist and top-track data and create a poster in your current browser session. It does not change your library, playlists, follows, or playback.

## Data used and storage

| Data | Use and storage |
| --- | --- |
| Spotify profile | Show the identifier/display name of the account connected to this session |
| Playlists and their tracks | Let you choose and label a poster source |
| Top tracks | Offer Spotify's approximate four-week, six-month, and one-year affinity lists |
| Album artwork URLs/images | Render full-cover artwork in the selected poster |
| Title, settings, and generated PNG | Preview/download in this Streamlit session |
| Access/refresh tokens | Server-side session memory through an explicit session-only cache handler |
| Pending OAuth state/verifier/timestamp | Browser `sessionStorage`; valid for ten minutes and consumed by a matching callback |

The app does not write these data or generated files to server directories, databases, global Streamlit caches, or its GitHub repository. Tokens are not stored in browser storage. Image requests contact the source URLs, and Spotify receives authorization/API requests. The hosting provider handles the normal web connection; provider-level logs and retention are separate from this application's memory storage.

The offline demo uses invented music metadata and original generated geometric tiles. It fetches no Spotify data and needs no account.

## Permissions

Only `user-read-private`, `playlist-read-private`, `playlist-read-collaborative`, and `user-top-read` are requested. These support account identity, accessible playlist selection, and top-track sources. Playback-control, library-write, playlist-write, follow, and email permissions are not requested. [Spotify scopes](https://developer.spotify.com/documentation/web-api/concepts/scopes)

## Disconnect and deletion

Use the app's disconnect action to clear the session's tokens, source data, images, settings, and generated PNG. Reloading or restarting can also replace the session; the app does not offer a permanent account or output archive. Pending login storage is consumed after a matching callback or cleared on disconnect; abandoned storage can remain until that tab closes, although expired login requests are rejected.

App disconnect does not log out of Spotify in your browser or revoke Spotify's authorization grant. Remove Streamlytics under [Spotify account → Apps](https://www.spotify.com/account/apps/) to revoke permission, and avoid reconnecting if you want access to remain removed. PNGs you downloaded to your own device remain yours to delete.

Do not post tokens, private playlist details, or account data in GitHub issues. Contact the maintainer for questions about the app's data use. Before a wider public release, confirm the public operator/contact information and hosted behavior match this notice.

## Artwork and listening claims

Top tracks are calculated affinity rankings, not exact calendar-year play counts or official Wrapped results. Year-end playlist detection uses a name pattern and asks you to choose the actual playlist; it does not verify a playlist's provenance. [Top items reference](https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks)

Gallery and Receipt outputs keep complete artwork aspect ratios and carry Spotify attribution, playlist links when available, and track links in PNG metadata. The app also links each track. Spotify's policy restricts standalone metadata/cover-art products, requires links, and its guidelines prohibit artwork cropping or overlays. Whether distribution of downloadable collages meets that standalone-content restriction is unresolved; the policy does not name this exact product. Personal-beta status does not create an exemption. Public release requires resolving distribution rights and policy compliance. [Developer Policy](https://developer.spotify.com/policy), [design guidelines](https://developer.spotify.com/documentation/design)
