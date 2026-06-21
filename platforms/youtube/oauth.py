"""OAuth 2.0 handling for the YouTube platform.

YouTube uses Google's "installed app" OAuth flow (loopback redirect):
the user logs into their Google account in a browser, grants consent, and
Google redirects to a temporary local web server that FastSM spins up to
capture the authorization code. The code is exchanged for an access token
and a long-lived refresh token. Only the refresh token (plus the access
token and its expiry) is persisted in the per-account config; the access
token is silently refreshed from the refresh token on later launches, so
the browser is only needed once.

What OAuth unlocks (YouTube Data API v3):
    - Account identity (channels.list mine=true)
    - Subscriptions (subscriptions.list mine=true)
    - Likes / ratings, subscribe/unsubscribe, comments, uploads

What OAuth does NOT cover (handled elsewhere, via cookies + InnerTube):
    - The personalized recommendations / home feed
    - Community ("posts" tab) reading and posting

google-auth, google-auth-oauthlib and google-api-python-client are imported
lazily inside the functions that need them so importing this module never
fails on a machine that hasn't installed them yet (mirrors how the Bluesky
backend imports atproto lazily).
"""

from typing import Optional, Callable, Dict, Any

try:
    from logging_config import get_logger
    _logger = get_logger('api')
except ImportError:
    _logger = None


# ---------------------------------------------------------------------------
# Client configuration
# ---------------------------------------------------------------------------
#
# These are the credentials for the single, Google-verified FastSM OAuth
# client (consent screen published to "In production"). A "Desktop app"
# client secret is not actually secret — Google treats installed-app clients
# as public, so shipping it in the binary is expected and supported.
#
# Fill these in after creating the OAuth client in Google Cloud Console and
# completing sensitive-scope verification. Until then, the login flow will
# raise a clear error telling the developer the client isn't configured.
#
# A user may also override these with their own client by setting
# prefs.youtube_client_id / prefs.youtube_client_secret (see get_client_config).

BUNDLED_CLIENT_ID = ""        # e.g. "1234567890-abc.apps.googleusercontent.com"
BUNDLED_CLIENT_SECRET = ""    # e.g. "GOCSPX-..."

# Scopes requested at consent time. Keep this list minimal — every sensitive
# scope added here lengthens Google's verification review.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",   # identity, subscriptions
    "https://www.googleapis.com/auth/youtube.force-ssl",  # like, subscribe, comment
    # "https://www.googleapis.com/auth/youtube.upload",   # enable if/when uploads land
]

# Google's standard installed-app endpoints.
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


class YouTubeAuthError(Exception):
    """Raised when the OAuth flow fails or the client is not configured.

    Treated as a transient/ordinary error by callers — the stored token is NOT
    discarded (e.g. a network blip during refresh shouldn't strand a valid login).
    """
    pass


class YouTubeReauthRequired(YouTubeAuthError):
    """The stored token is permanently unusable (revoked, or expired after the
    7-day Google "Testing" limit). Callers should clear the saved token and
    prompt the user to sign in again."""
    pass


# Path to an optional, git-ignored credentials file sitting next to this module.
# Save the JSON Google Cloud Console gives you ("Download JSON" on the OAuth
# client) here and login works with no source edits.
import os as _os
LOCAL_CLIENT_FILE = _os.path.join(_os.path.dirname(__file__), "client_secret.json")


def _load_local_client_config() -> Optional[Dict[str, Any]]:
    """Load client_secret.json if present, normalized to the 'installed' shape.

    Accepts Google's native download (top-level 'installed' or 'web' key).
    Returns None when the file is absent or unusable.
    """
    if not _os.path.isfile(LOCAL_CLIENT_FILE):
        return None
    try:
        import json
        with open(LOCAL_CLIENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        if _logger:
            _logger.warning("Could not read %s: %s", LOCAL_CLIENT_FILE, e)
        return None

    block = data.get("installed") or data.get("web") or data
    client_id = (block.get("client_id") or "").strip()
    client_secret = (block.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        if _logger:
            _logger.warning("%s is missing client_id/client_secret.", LOCAL_CLIENT_FILE)
        return None

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": block.get("auth_uri", AUTH_URI),
            "token_uri": block.get("token_uri", TOKEN_URI),
            "redirect_uris": block.get("redirect_uris", ["http://localhost"]),
        }
    }


def get_client_config(prefs=None) -> Dict[str, Any]:
    """Build the client_config dict google-auth-oauthlib expects.

    Prefers a user-supplied client (prefs.youtube_client_id/secret) when
    present, otherwise falls back to the bundled FastSM client.
    """
    # 1. A local, git-ignored client_secret.json (the file Google lets you
    #    download with one click) wins if present — no source editing needed.
    local = _load_local_client_config()
    if local is not None:
        return local

    # 2. Otherwise fall back to the bundled constants / prefs override.
    client_id = BUNDLED_CLIENT_ID
    client_secret = BUNDLED_CLIENT_SECRET
    if prefs is not None:
        client_id = (prefs.get("youtube_client_id", "") or "").strip() or client_id
        client_secret = (prefs.get("youtube_client_secret", "") or "").strip() or client_secret

    if not client_id or not client_secret:
        raise YouTubeAuthError(
            "No YouTube OAuth client is configured. Save Google's downloaded "
            "client_secret.json into platforms/youtube/, or set BUNDLED_CLIENT_ID/"
            "BUNDLED_CLIENT_SECRET in platforms/youtube/oauth.py."
        )

    # "installed" is Google's key for desktop/loopback clients.
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }


def run_oauth_flow(prefs=None) -> Dict[str, Any]:
    """Run the interactive browser login and return a token dict to persist.

    Spins up a temporary localhost web server, opens the user's browser to
    Google's consent screen, and blocks until the user finishes (or the flow
    errors / is abandoned). Must be called on a thread where blocking is fine
    — for FastSM that's the account-setup path, same place the Mastodon code
    enters its browser auth.

    Returns a JSON-serializable dict (see credentials_to_dict) suitable for
    storing in prefs.youtube_token.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise YouTubeAuthError(
            "google-auth-oauthlib is not installed. Run "
            "'pip install google-auth-oauthlib google-api-python-client' "
            "and try again."
        ) from e

    client_config = get_client_config(prefs)
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

    # port=0 lets the OS pick a free port for the loopback redirect.
    # access_type=offline + prompt=consent guarantees we receive a refresh
    # token (without prompt=consent Google omits it on repeat authorizations).
    try:
        flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent",
            authorization_prompt_message=(
                "Your browser has been opened to log in to your Google account. "
                "After granting access you can return to FastSM."
            ),
            success_message=(
                "FastSM is now connected to your YouTube account. "
                "You can close this tab and return to the app."
            ),
            open_browser=True,
        )
    except Exception as e:
        if _logger:
            _logger.exception("YouTube OAuth flow failed: %s", e)
        raise YouTubeAuthError(f"YouTube login failed: {e}") from e

    creds = flow.credentials
    if not creds or not creds.refresh_token:
        raise YouTubeAuthError(
            "Google did not return a refresh token. Remove FastSM from your "
            "Google account permissions and try logging in again."
        )
    if _logger:
        _logger.info("YouTube OAuth flow completed; refresh token obtained.")
    return credentials_to_dict(creds)


def credentials_to_dict(creds) -> Dict[str, Any]:
    """Serialize a google.oauth2.credentials.Credentials to a plain dict."""
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "expiry": creds.expiry.isoformat() if getattr(creds, "expiry", None) else None,
    }


def dict_to_credentials(data: Dict[str, Any], prefs=None):
    """Rebuild a Credentials object from a stored token dict.

    Falls back to the current bundled client_id/secret if the stored dict
    predates a credential change, so an app update that rotates the client
    doesn't strand existing logins.
    """
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as e:
        raise YouTubeAuthError(
            "google-auth is not installed. Run "
            "'pip install google-auth google-api-python-client'."
        ) from e

    if not data or not data.get("refresh_token"):
        raise YouTubeAuthError("No stored YouTube refresh token; login required.")

    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    if not client_id or not client_secret:
        cfg = get_client_config(prefs)["installed"]
        client_id = client_id or cfg["client_id"]
        client_secret = client_secret or cfg["client_secret"]

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", TOKEN_URI),
        client_id=client_id,
        client_secret=client_secret,
        scopes=data.get("scopes", SCOPES),
    )
    # Restore expiry so a still-valid cached access token is reused instead of
    # forcing a refresh on every launch. Credentials.expiry must be naive UTC.
    expiry = data.get("expiry")
    if expiry:
        try:
            import datetime as _dt
            dt = _dt.datetime.fromisoformat(expiry)
            if dt.tzinfo is not None:
                dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
            creds.expiry = dt
        except Exception:
            pass  # bad value -> leave unset, which just forces a refresh
    return creds


def ensure_valid_credentials(creds, on_token_refresh: Optional[Callable] = None):
    """Refresh the access token if it's missing or expired.

    Calls on_token_refresh(token_dict) after a successful refresh so the
    caller can persist the new access token/expiry back to prefs.
    """
    try:
        from google.auth.transport.requests import Request
    except ImportError as e:
        raise YouTubeAuthError("google-auth is not installed.") from e

    # If the stored scopes no longer cover what the app now needs (e.g. a new
    # scope was added in an update), force a fresh consent rather than failing
    # later with opaque 403s.
    have = set(creds.scopes or [])
    if have and not set(SCOPES).issubset(have):
        raise YouTubeReauthRequired(
            "YouTube permissions changed; please sign in again to grant them.")

    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            # invalid_grant => the refresh token is revoked or expired (the
            # 7-day Google "Testing" limit). That needs a full re-login and the
            # dead token should be cleared. Anything else (network/5xx) is
            # transient and must NOT discard a possibly-valid token.
            msg = str(e)
            low = msg.lower()
            if _logger:
                _logger.warning("YouTube token refresh failed: %s", msg)
            # Only treat the precise OAuth dead-token signals as fatal. Match
            # Google's exact phrase, NOT a bare "expired" (which also appears in
            # transient errors like "certificate has expired" and must not wipe
            # a valid refresh token).
            if ("invalid_grant" in low or "invalid_token" in low
                    or "token has been expired or revoked" in low):
                raise YouTubeReauthRequired(
                    "Your YouTube session expired. Please sign in again.") from e
            raise YouTubeAuthError(
                f"Could not refresh YouTube access token (temporary): {e}") from e
        if on_token_refresh:
            try:
                on_token_refresh(credentials_to_dict(creds))
            except Exception as save_err:
                if _logger:
                    _logger.warning("Could not persist refreshed YouTube token: %s", save_err)
        return creds
    raise YouTubeReauthRequired(
        "YouTube credentials are invalid and cannot be refreshed; please sign in again.")


def build_youtube_service(creds):
    """Build a YouTube Data API v3 client from credentials."""
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        raise YouTubeAuthError(
            "google-api-python-client is not installed. Run "
            "'pip install google-api-python-client'."
        ) from e
    # cache_discovery=False avoids the noisy file-cache warning in frozen builds.
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def revoke_token(data: Dict[str, Any]) -> bool:
    """Best-effort revoke the grant at Google on sign-out.

    Revokes the refresh token (which also invalidates derived access tokens).
    Returns True on success; never raises (network failures are non-fatal).
    """
    if not data:
        return False
    tok = data.get("refresh_token") or data.get("token")
    if not tok:
        return False
    try:
        import requests
        resp = requests.post(
            REVOKE_URL, data={"token": tok},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        if _logger:
            _logger.info("YouTube token revoke failed (non-fatal): %s", e)
        return False
