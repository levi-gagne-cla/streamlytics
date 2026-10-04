# Privacy, account control, and release limitations

This describes the current code and its known limitations. It is a maintainer-facing draft, not a claim that the existing app is ready for public multi-user use. Before wider release, publish an accessible user-facing policy with the operator's identity, contact details, and verified retention/deletion behavior.

## Spotify authorization

The app asks Spotify for access to the account the user selects. A Client ID identifies Streamlytics; it does not sign visitors into the app owner's account. Authorization Code with PKCE and a verified random `state` bind a returning callback to the flow started in that browser tab.

Only the temporary verifier, state, and timestamp are kept in browser `sessionStorage`, for a ten-minute valid flow. They are removed when a matching callback is consumed or the user disconnects. Expired pending requests are rejected and cleared when processed; a tab that is abandoned can retain the storage record until that tab closes. Access and refresh tokens are kept in server-side Streamlit session memory, with an explicit cache handler; tokens are not intentionally written to disk, global Streamlit caches, or browser storage. Spotify receives the authorization and API requests. Requests for cover images also contact the image URLs supplied by the source.

Session memory is not permanent storage. Reloads, disconnections that replace a session, and server restarts can require authorization again. This design does not keep an account signed in across visits.

## Requested permissions

| Spotify scope | Reason in the retained app |
| --- | --- |
| `user-read-private` | Identify the connected account |
| `user-library-read` | Read saved tracks, albums, and shows for analytics/exports |
| `user-read-playback-state` | Show playback state and devices |
| `user-modify-playback-state` | Existing Playback page controls the connected user's playback |
| `user-read-currently-playing` | Show the current track |
| `playlist-read-private` | Read the connected user's private playlists |
| `playlist-read-collaborative` | Read collaborative playlists |
| `user-read-recently-played` | Show available recent listening history |
| `user-top-read` | Read top tracks and artists for analytics/posters |

Unused email, library-write, playlist-write, and follow scopes were removed. Playback write access remains because playback controls remain. A future posters-only product should remove that scope together with the corresponding controls. [Spotify scopes](https://developer.spotify.com/documentation/web-api/concepts/scopes)

## Logout and disconnect

Use **Disconnect Spotify** on Home to clear the app's Streamlit session state, including its tokens and fetched data. This does not sign out of Spotify in the browser, revoke the app's Spotify permission, erase your own downloaded files, or remove files from the app's shared server directories.

To revoke Spotify permission, open [Spotify account → Apps](https://www.spotify.com/account/apps/) and remove Streamlytics. After revocation, do not reconnect if you want the app to stop accessing your account. Tell the operator if you need saved generated data removed; a reliable per-user deletion mechanism has not yet been implemented for the shared directories.

## Generated files are still shared

The existing pages write playlist/track JSON under `json/`, downloaded cover images under `data/cover_art/`, and posters to configured output paths. Filenames and directories are not partitioned by authenticated user. They can collide, overwrite each other, or be selected by another session. Checked-in example images remain accessible with the repository/app. A `.gitignore` prevents accidental addition of new generated files but does not isolate them or remove files already tracked.

Logout cannot safely delete these directories because another active session can use them. No scheduled cleanup or reliable retention period is implemented. The hosted filesystem is also not a durable backup service. Do not generate sensitive/private playlist outputs for a public deployment until files are owned per user/session, inaccessible to other sessions, and cleaned up with explicit deletion behavior.

The authentication fix resolves shared Spotify credentials. It does not resolve this separate file boundary. Page layout, generation logic, and fetch behavior remain unchanged in this release.

## Listening and artwork claims

Spotify's top-item endpoint returns affinity rankings across approximate windows; it does not supply exact yearly play counts or Spotify Wrapped. The recent-playback endpoint is not a complete lifetime listening archive. Describe posters by their actual source and selected time window. [Top items reference](https://developer.spotify.com/documentation/web-api/reference/get-users-top-artists-and-tracks), [recent playback reference](https://developer.spotify.com/documentation/web-api/reference/get-recently-played)

Before distributing downloadable album-art posters, review Spotify's [Developer Policy](https://developer.spotify.com/policy) and [design guidelines](https://developer.spotify.com/documentation/design). They require Spotify attribution and content links, restrict standalone metadata/cover-art products, and prohibit artwork cropping, distortion, and overlays. A standalone collage/download feature needs a specific rights and policy decision; existing code is not evidence of permission. Current layouts were preserved for this focused fix, so policy approval is still outstanding.

Spotify also requires transparency about data use and deletion when a user disconnects. The shared-file deletion gap above must be resolved before claiming that requirement is met. Do not describe the current limited beta as a completed privacy implementation.
