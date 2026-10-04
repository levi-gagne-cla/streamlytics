# Deployment

## Local configuration

Run from the repository root using Python 3.12:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The demo works without Spotify settings. For account sources, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and configure only `[spotify].client_id` and `[spotify].redirect_uri`. PKCE requires no client secret or owner token.

Register **`http://127.0.0.1:8501/`** in Spotify's dashboard and open that exact URL locally. The callback goes to Home, served by `app.py`; there is no separate `/callback` route. Spotify requires HTTPS for hosted redirects and rejects `localhost` aliases. Keep path and trailing slash identical in config and the dashboard. [Spotify redirect requirements](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)

Authorization must finish in the same tab and origin within ten minutes. Tokens live only in the resulting Streamlit session, so a reload or restart can require login again.

## Community Cloud

1. Create a Community Cloud app connected to this GitHub repository. For review, choose `rewrite/playlist-studio` as a separate preview app; leave the original deployment's branch unchanged.
2. Choose main file **`app.py`** and Python **3.12**.
3. Register the exact preview/production Home URL in the Spotify Developer Dashboard.
4. Paste the following into Community Cloud's app secrets, with your actual URL and Client ID:

   ```toml
   [spotify]
   client_id = "your-spotify-client-id"
   redirect_uri = "https://your-app.streamlit.app/"
   ```

5. Add beta testers to the Spotify app's allowlist where required, then run the account check below.

Do not copy access tokens, refresh tokens, legacy `.cache` files, or a client secret into the deployment. The local secrets file is excluded from Git. If credentials were ever committed, rotate them and inspect history before publishing the repository.

Community Cloud updates its app from the configured GitHub branch; changing dependencies triggers reinstall/redeploy. This setup needs no custom deploy action or deployment token. Configure a branch protection rule requiring the **Test** job from the **CI** workflow before merge into the production branch. Cloud itself does not wait for Actions, so direct pushes can deploy before tests finish. [Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management), [GitHub updates](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#update-your-app)

Roll back by reverting the release commit on the deployed branch, then check the app after Cloud updates. Opening the rewrite PR does not alter the current live app.

## Spotify compatibility

Checked against official documentation on October 4, 2026; the repository cannot establish its app's dashboard status.

- Development Mode normally allows five allowlisted users and requires the owner to have Premium. Existing larger allowlists may be grandfathered. A successful authorization can still lead to a 403 for an unallowlisted user. [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes), [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
- Spotify postponed endpoint access changes for existing integrations on March 9. An older Client ID may retain capabilities unavailable to a new client; this rewrite still uses the current playlist API. Hosting or OAuth changes do not expand API permissions. [Updated announcement](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security)
- Playlist contents use `GET /playlists/{id}/items` and its `item` response field, with no legacy route fallback. Spotipy 2.25.2's public playlist-item methods still address the deprecated `/tracks` route, so `catalog.py` makes one explicit request through the client's transport. The current endpoint requires playlist ownership or collaboration; listing/following a playlist does not guarantee its contents can be read. [Playlist items reference](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items)
- A saved Spotify-owned year-end playlist may return 403 under restricted access. Saving/following does not make the user its owner. The user can create their own copy through Spotify's **Add to other playlist** UI, then select that copy. Streamlytics does not write or copy playlists into accounts. [Playlist migration details](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide), [Spotify playlist help](https://support.spotify.com/us/article/save-recover-playlists/)
- Development Mode quotas are shared across the developer's apps. A 429 with `reason: QUOTA_EXCEEDED` is a quota issue. Do not retry continuously. [July quota update](https://developer.spotify.com/blog/2026-07-23-web-api-quota-updates)

## Acceptance check

1. Try the offline demo without secrets: preview both layouts, change theme/count/title, and download a PNG.
2. Connect different Spotify accounts in two browser profiles. Confirm each app session names the correct account and lists that account's playlists.
3. Generate different posters in each profile; confirm previews/downloads stay separate. Disconnect one profile and confirm its source/PNG/session data clears while the other remains connected.
4. Check playlist pagination, a year-end playlist if available, all three top-track periods, and an unavailable/forbidden playlist. Sources should be honestly labeled and errors should leave the app usable.
5. Check denial, expired login, and an OAuth callback opened in another tab. None should authenticate the wrong session.

CI uses test fixtures and browser-component protocol tests; it does not replace this live two-account check. Its HTTP health smoke verifies server startup, not actual OAuth or API access.
