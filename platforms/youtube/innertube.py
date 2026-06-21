"""Cookie-based InnerTube access for the personalized recommendations feed.

The official YouTube Data API has no recommendations endpoint, so the Home
feed is fetched the same way youtube.com's own web client does: a POST to
the private InnerTube `browse` endpoint with browseId 'FEwhat_to_watch'.

To get *personalized* results (rather than generic trending) the request must
be authenticated. We reuse the user's yt-dlp cookies file (the existing
prefs.ytdlp_cookies, Netscape format) and build the SAPISIDHASH Authorization
header exactly like a browser does. Without cookies the call still works but
returns a generic feed.

This is unofficial and can break whenever YouTube changes its internal
response shape — hence it lives apart from the Data API code, fails soft
(returns []), and parses defensively. Only `requests` is required (already a
FastSM dependency); google-api-python-client is not involved here.
"""

import time
import hashlib
from http.cookiejar import MozillaCookieJar
from typing import List, Dict, Any, Optional

import requests

from .models import watch_url

try:
    from logging_config import get_logger
    _logger = get_logger('api')
except ImportError:
    _logger = None

# Reuse the search library's client identity when it's importable so we stay in
# step with its maintained clientVersion; otherwise fall back to local copies.
try:
    from youtubesearchpython.core.constants import (
        userAgent as _USER_AGENT,
        searchKey as _API_KEY,
        requestPayload as _BASE_PAYLOAD,
    )
    import copy as _copy
    _BASE_PAYLOAD = _copy.deepcopy(_BASE_PAYLOAD)
except Exception:
    _USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
    _API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
    _BASE_PAYLOAD = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20250514.01.00",
                "newVisitorCookie": True,
            },
            "user": {"lockedSafetyMode": False},
        }
    }

BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse"
HOME_BROWSE_ID = "FEwhat_to_watch"
ORIGIN = "https://www.youtube.com"


# ---------------------------------------------------------------------------
# Cookies + auth
# ---------------------------------------------------------------------------

def _load_cookies(cookies_path: str) -> Optional[MozillaCookieJar]:
    """Load a Netscape-format cookies.txt into a jar, or None on failure."""
    if not cookies_path:
        return None
    try:
        jar = MozillaCookieJar()
        jar.load(cookies_path, ignore_discard=True, ignore_expires=True)
        return jar
    except Exception as e:
        if _logger:
            _logger.info("YouTube: could not load cookies file %r: %s", cookies_path, e)
        return None


def _cookie_dict(jar: MozillaCookieJar) -> Dict[str, str]:
    """Flatten a cookie jar to a name->value dict."""
    out = {}
    for c in jar:
        out[c.name] = c.value
    return out


def _sapisid_hash_header(cookies: Dict[str, str]) -> Optional[str]:
    """Build the SAPISIDHASH Authorization header from session cookies.

    Mirrors the browser: SHA1 of "<ts> <SAPISID> <origin>". YouTube accepts a
    combined header carrying the same hash under the SAPISID / 1P / 3P labels.
    """
    sapisid = (cookies.get("SAPISID")
               or cookies.get("__Secure-3PAPISID")
               or cookies.get("__Secure-1PAPISID"))
    if not sapisid:
        return None
    ts = str(int(time.time()))
    digest = hashlib.sha1(f"{ts} {sapisid} {ORIGIN}".encode("utf-8")).hexdigest()
    token = f"{ts}_{digest}"
    return f"SAPISIDHASH {token} SAPISID1PHASH {token} SAPISID3PHASH {token}"


# ---------------------------------------------------------------------------
# Response parsing (defensive)
# ---------------------------------------------------------------------------

def _find_renderers(node: Any, key: str, out: list) -> None:
    """Recursively collect every dict stored under `key` anywhere in `node`."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, dict):
                out.append(v)
            else:
                _find_renderers(v, key, out)
    elif isinstance(node, list):
        for item in node:
            _find_renderers(item, key, out)


def _text(node: Any) -> str:
    """Pull display text out of the various text wrappers YouTube uses."""
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return node.get("simpleText", "") or ""
    if "content" in node:  # viewModel style
        return node.get("content", "") or ""
    runs = node.get("runs")
    if isinstance(runs, list) and runs:
        return "".join(r.get("text", "") for r in runs if isinstance(r, dict))
    return ""


def _last_thumb(thumbs: Any) -> Optional[str]:
    """Highest-res URL from a thumbnail list (renderer or viewModel shape)."""
    if isinstance(thumbs, dict):
        thumbs = thumbs.get("thumbnails") or thumbs.get("sources")
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1]
        if isinstance(last, dict):
            return last.get("url")
    return None


def _parse_video_renderer(vr: dict) -> Optional[Dict[str, Any]]:
    """videoRenderer -> the dict shape models.innertube_video_to_universal wants."""
    video_id = vr.get("videoId")
    if not video_id:
        return None
    byline = vr.get("longBylineText") or vr.get("ownerText") or {}
    channel_name = _text(byline)
    channel_id = ""
    runs = byline.get("runs") if isinstance(byline, dict) else None
    if isinstance(runs, list) and runs:
        channel_id = (((runs[0].get("navigationEndpoint", {}) or {})
                       .get("browseEndpoint", {})) or {}).get("browseId", "") or ""
    return {
        "id": video_id,
        "title": _text(vr.get("title")),
        "channel": {"id": channel_id, "name": channel_name},
        "thumbnails": [{"url": _last_thumb(vr.get("thumbnail"))}] if _last_thumb(vr.get("thumbnail")) else [],
        "link": watch_url(video_id),
    }


def _parse_lockup(lvm: dict) -> Optional[Dict[str, Any]]:
    """lockupViewModel (newer format) -> the same dict shape, best-effort."""
    if lvm.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
        return None
    video_id = lvm.get("contentId")
    if not video_id:
        return None
    meta = (((lvm.get("metadata", {}) or {}).get("lockupMetadataViewModel", {})) or {})
    title = _text(meta.get("title"))
    thumb = _last_thumb((((lvm.get("contentImage", {}) or {})
                          .get("thumbnailViewModel", {})) or {}).get("image"))
    channel_name, channel_id = _lockup_channel(meta)
    return {
        "id": video_id,
        "title": title,
        "channel": {"id": channel_id, "name": channel_name},
        "thumbnails": [{"url": thumb}] if thumb else [],
        "link": watch_url(video_id),
    }


def _lockup_channel(meta: dict):
    """Best-effort channel (name, id) from a lockup's metadata rows."""
    rows = (((meta.get("metadata", {}) or {})
             .get("contentMetadataViewModel", {})) or {}).get("metadataRows") or []
    for row in rows:
        for part in (row.get("metadataParts") or []):
            text_node = part.get("text") or {}
            name = text_node.get("content") or _text(text_node)
            if not name:
                continue
            # The channel row carries a browse command; views/dates don't.
            cid = ""
            for run in (text_node.get("commandRuns") or []):
                cid = (((run.get("onTap", {}) or {}).get("innertubeCommand", {})
                        .get("browseEndpoint", {})) or {}).get("browseId", "") or ""
                if cid:
                    break
            if cid or not name[0].isdigit():
                return name, cid
    return "", ""


def _parse_home(response: dict, limit: int) -> List[Dict[str, Any]]:
    """Extract video dicts from a browse(FEwhat_to_watch) response."""
    videos: List[Dict[str, Any]] = []
    seen = set()

    renderers: list = []
    _find_renderers(response, "videoRenderer", renderers)
    for vr in renderers:
        parsed = _parse_video_renderer(vr)
        if parsed and parsed["id"] not in seen:
            seen.add(parsed["id"])
            videos.append(parsed)

    if len(videos) < limit:  # newer responses use lockupViewModel
        lockups: list = []
        _find_renderers(response, "lockupViewModel", lockups)
        for lvm in lockups:
            parsed = _parse_lockup(lvm)
            if parsed and parsed["id"] not in seen:
                seen.add(parsed["id"])
                videos.append(parsed)

    return videos[:limit]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_recommendations(cookies_path: str = "", limit: int = 40,
                        region: str = "US", language: str = "en",
                        timeout: int = 10) -> List[Dict[str, Any]]:
    """Fetch the Home / recommendations feed as a list of video dicts.

    Each dict matches models.innertube_video_to_universal's expected shape.
    Returns [] (never raises) on any failure so the timeline degrades cleanly.
    """
    import copy
    payload: Dict[str, Any] = copy.deepcopy(_BASE_PAYLOAD)
    payload["context"]["client"]["hl"] = language
    payload["context"]["client"]["gl"] = region
    payload["browseId"] = HOME_BROWSE_ID

    headers = {
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
        "Origin": ORIGIN,
        "X-Origin": ORIGIN,
        "X-Goog-AuthUser": "0",
    }

    jar = _load_cookies(cookies_path)
    cookies = _cookie_dict(jar) if jar else {}
    if cookies:
        auth = _sapisid_hash_header(cookies)
        if auth:
            headers["Authorization"] = auth
        else:
            if _logger:
                _logger.info("YouTube: cookies present but no SAPISID; feed will be generic.")

    try:
        resp = requests.post(
            BROWSE_URL,
            params={"key": _API_KEY, "prettyPrint": "false"},
            json=payload,
            headers=headers,
            cookies=cookies or None,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        if _logger:
            _logger.info("YouTube recommendations request failed: %s", e)
        return []

    try:
        return _parse_home(data, limit)
    except Exception as e:
        if _logger:
            _logger.info("YouTube recommendations parse failed: %s", e)
        return []
