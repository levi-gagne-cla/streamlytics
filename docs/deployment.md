# Deployment and Spotify configuration

## Local setup

1. Use Python 3.12 and install `requirements.txt`.
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
3. Set `[spotify].client_id` to your Spotify app's Client ID.
4. Register `http://127.0.0.1:8501/` in the Spotify Developer Dashboard and set the same value as `[spotify].redirect_uri`.
5. Run `python -m streamlit run app.py` from the repository root and open `http://127.0.0.1:8501/`.

The callback is the Home page served by `app.py`, not a separate `/callback` endpoint or a page under `pages/`. Match the entire URI, including its path and trailing slash. Spotify requires HTTPS except for explicit loopback IP addresses; `localhost` aliases are not accepted. [Redirect URI requirements](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)

The config contains a public application identifier, not an owner's login. PKCE requires no client secret. The app exchanges each user's authorization code using that tab's verifier, then stores that user's tokens only in Streamlit session memory.

## Streamlit Community Cloud

1. Connect the repository in Community Cloud and select its deployment branch, normally `main`.
2. Set the main file to **`app.py`** and Python to **3.12**.
3. Choose the final hosted URL. Register its exact Home URL in the Spotify Developer Dashboard, for example `https://your-app.streamlit.app/`.
4. In Community Cloud's **Advanced settings / Secrets**, enter:

   ```toml
   [spotify]
   client_id = "your-spotify-client-id"
   redirect_uri = "https://your-app.streamlit.app/"
   ```

5. Deploy or reboot the app after changing its settings. If the app URL changes, update both Spotify's registered URI and the app's configured URI.
6. Confirm the app's quota mode and add each test user's Spotify email to its allowlist when required.
7. Run the two-account check below before inviting people.

Do not upload access tokens, refresh tokens, `.cache` files, or an owner's Spotify credentials. Existing `client_secret` configuration is no longer used and can be removed. If a secret was ever committed, deleting it from the latest commit is insufficient; rotate it in the provider and review repository history before making the code public.

Community Cloud reads deployment code directly from GitHub and updates it when the deployment branch changes. Dependency changes trigger reinstall/redeploy. No deployment key, personal access token, or extra GitHub deploy action is needed for this setup. [Deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management), [GitHub updates](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#update-your-app)

## CI and release gates

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`:

- Install runtime dependencies and pinned test/lint tools under Python 3.12.
- Lint the auth module, browser-component wrapper, and tests.
- Run the Python auth regression tests and Node 22 browser-component protocol tests.
- Compile all application Python sources, including the existing pages.
- Start Streamlit and check `/_stcore/health`, without Spotify credentials.

The lint scope deliberately covers the auth change and tests. Existing page logic has not been reformatted or refactored. The HTTP smoke check verifies server startup; it does not prove page execution, live Spotify compatibility, or a real browser OAuth round trip.

Configure a GitHub branch protection rule or ruleset for the deployment branch that requires the **CI / Test** status check before merge, and route changes through pull requests. This is a repository setting; adding a workflow file alone does not enable branch protection. Community Cloud does not gate deployment on a workflow's success, so direct pushes can deploy before CI completes.

For a preview, create a separate Community Cloud app pointed at a feature branch, give it its own URL, and register that URL with Spotify. Do not change the live app's configured redirect to the preview URL. The browser's stored pending flow is origin-bound, so always start authorization at the same URL used for its return.

To roll back a release, revert the merge in GitHub, wait for Community Cloud to update, and rerun the account check. No database migration or permanent auth-token store is introduced by this fix.

## Two-account acceptance check

Use different browser profiles or a normal and private window, each signed into a different Spotify account. Both accounts must be permitted to use your Spotify app.

1. In browser A, connect account A and confirm Home identifies account A.
2. In browser B, connect account B and confirm Home identifies account B.
3. Open Analytics in each and check that private account data corresponds to that browser's account.
4. If checking playback controls, use an active device for each account. A playback action from B should target B only.
5. Log out in B; B should lose app access while A stays connected.
6. Reload B and verify that it needs to connect again. Test denial, an expired login request, and a callback opened in another tab; none should create an authenticated session.

Generated files still use shared paths. This check proves the Spotify account boundary, not private ownership of saved JSON or posters. Output isolation remains a separate prerequisite for a public multi-user launch.

## Spotify limits to verify before a release

Checked against official documentation on October 4, 2026. Inspect the actual app's dashboard; its creation date and previous approvals are not available from this repository.

- Development Mode currently requires the owner to have Premium and normally limits an app to five allowlisted users. Authorization can succeed for an unallowlisted user while API calls return 403. [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
- Spotify's February migration guide says existing users above the new cap can be retained. Do not assume this app has that exemption. [Migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
- On March 9, Spotify postponed endpoint access changes for existing integrations; the account restrictions still took effect. Newly created apps can have different endpoint access. Existing audio-feature and playlist enrichment calls must be tested with this app's Client ID. [Updated announcement](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security)
- The July update raised the Client ID cap to 25 per developer and made Development Mode quota shared across that developer's apps. A 429 with `reason: QUOTA_EXCEEDED` is a quota issue, not an account mix-up. [July quota update](https://developer.spotify.com/blog/2026-07-23-web-api-quota-updates)

Opening the app source or changing hosting providers does not expand Spotify API access. Do not promise an unrestricted public launch or official Wrapped data from these endpoints.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Redirect URI error | Configured URI exactly matches the dashboard; use HTTPS when hosted and `127.0.0.1` locally |
| Login request missing, invalid, or expired | Start again in the same tab and origin; allow browser session storage and finish within ten minutes |
| Wrong Spotify account selected | Log out of the app, then change the Spotify account in that browser or use a separate browser profile |
| Reload asks for login | Expected: tokens are not persisted across replacement Streamlit sessions |
| 403 after authorization | Allowlist, app access mode, endpoint restrictions, and requested scopes |
| Playback control error | Connected user's active device and Spotify's endpoint/Premium requirements |
| 429 | Rate limits or the developer account's shared quota; avoid repeated retries |
| Data/cover-art endpoint errors | App-specific API access and current endpoint availability; login isolation does not change API permissions |
| App starts but a poster fails | Existing input files, image paths, fonts, and shared output directories; generation code is unchanged |

The old code passed `cache_path=None` to Spotipy, which does not disable its default disk cache handler. The new flow passes an explicit session-only cache handler. Stop old deployments before removing any leftover `.cache` / `.cache-*` token files from their working directory, and never commit those files. If anyone used the owner's cached authorization, remove the app's access from the owner's Spotify account and connect again.
