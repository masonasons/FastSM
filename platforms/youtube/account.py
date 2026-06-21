"""YouTube platform account implementation.

This is a *skeleton*: the OAuth/identity/subscriptions paths are real and use
the YouTube Data API v3; search uses the InnerTube scraper (the c:\\yt
youtube-search-python rebuild); and the parts the official API can't do —
the personalized recommendations feed and community ("posts" tab) posting —
are clearly marked stubs to be filled in with the cookie + InnerTube work.

Design notes mapping FastSM concepts onto YouTube:
  * A *status* is a video. The author account is the channel.
  * The *home* timeline is recommendations (InnerTube, cookie-based).
  * *following* a user means subscribing; *get_following(me)* is your
    subscription list.
  * *favourite* maps to a video "like" (videos.rate); *get_favourites* is
    your liked-videos playlist.
  * *replying* (post with reply_to_id) maps to posting a comment.
  * Boost/block/mute and DMs have no YouTube equivalent and return falsy.
"""

import threading
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone

from platforms.base import PlatformAccount
from models import UniversalStatus, UniversalUser, UniversalNotification, UserCache
from cache import TimelineCache

from . import oauth
from .models import (
    youtube_channel_to_universal,
    youtube_video_to_universal,
    youtube_subscription_to_universal,
    youtube_search_result_to_universal,
    youtube_comment_to_universal,
    innertube_video_to_universal,
    innertube_channel_to_universal,
    watch_url,
    PLATFORM,
)

try:
    from logging_config import get_logger
    _logger = get_logger('api')
except ImportError:
    _logger = None


class YouTubeAccount(PlatformAccount):
    """YouTube-specific account implementation (Data API + InnerTube)."""

    platform_name = "youtube"

    # Feature flags. YouTube's "social" surface is comments + subscriptions;
    # it has no boosts, polls, CWs, DMs, or quote posts.
    supports_visibility = False
    supports_content_warning = False
    supports_quote_posts = False
    supports_polls = False
    supports_lists = False
    supports_direct_messages = False
    supports_media_attachments = False
    supports_scheduling = False
    supports_editing = False

    def __init__(self, app, index: int, service, me_channel: dict, confpath: str,
                 credentials=None, prefs=None, on_token_refresh=None):
        super().__init__(app, index)
        self.service = service            # googleapiclient youtube resource
        self.credentials = credentials    # google.oauth2.credentials.Credentials
        self._on_token_refresh = on_token_refresh
        self._prefs = prefs
        self.confpath = confpath
        self._me = youtube_channel_to_universal(me_channel)
        self._max_chars = 10000  # comment length ceiling; community posts differ

        # Playlist IDs for "your" content, pulled from the channel resource.
        related = (me_channel.get("contentDetails", {}) or {}).get("relatedPlaylists", {}) or {}
        self._uploads_playlist = related.get("uploads", "")
        self._likes_playlist = related.get("likes", "")

        self.user_cache = UserCache(confpath, PLATFORM, str(self._me.id) if self._me else "")
        self.user_cache.load()

        if app.prefs.timeline_cache_enabled:
            self.timeline_cache = TimelineCache(confpath, str(self._me.id) if self._me else "")
        else:
            self.timeline_cache = None

        # Page-token cursors for Data API pagination, keyed by timeline type.
        self._page_tokens: Dict[str, str] = {}

        # google-api-python-client's service wraps a single httplib2.Http, which
        # is NOT thread-safe. FastSM loads timelines concurrently, so without
        # serialization the shared SSL connection corrupts (RECORD_LAYER_FAILURE).
        # Guard every Data API call with this lock.
        self._api_lock = threading.Lock()

        # channel_id -> @handle (without the @). Lets us show "@brandonbracey"
        # instead of the channel title or raw UC... id. Seeded with our own
        # channel (its handle came from channels.list customUrl at login).
        self._handle_cache: Dict[str, str] = {}
        if self._me and self._me.acct and self._me.acct != self._me.id:
            self._handle_cache[self._me.id] = self._me.acct

        # Set once the stored token is found permanently dead (revoked / expired)
        # so we stop hammering the API and re-speaking the same error all session.
        self._auth_dead = False

    @property
    def me(self) -> UniversalUser:
        return self._me

    # ============ Internal helpers ============

    def _ensure_creds(self):
        """Refresh the access token if needed, persisting any new token."""
        if self.credentials is not None:
            oauth.ensure_valid_credentials(self.credentials, self._on_token_refresh)

    def _on_auth_dead(self):
        """Token is unusable: clear it (so next launch re-prompts) and tell the
        user once. Subsequent API calls short-circuit via self._auth_dead."""
        if self._auth_dead:
            return
        self._auth_dead = True
        try:
            if self._on_token_refresh:
                self._on_token_refresh({})  # wipe the stored token
        except Exception:
            pass
        self.app.handle_error(
            "Your YouTube session expired. Sign out and sign in again from the "
            "YouTube options.", "YouTube login")

    def _execute(self, request, context: str = "YouTube API"):
        """Run a Data API request with refresh + uniform error handling.

        Serialized via _api_lock because httplib2 (the transport under the
        service) isn't thread-safe and FastSM fetches timelines concurrently.
        """
        if self._auth_dead:
            return None
        try:
            with self._api_lock:
                self._ensure_creds()
                return request.execute()
        except oauth.YouTubeReauthRequired:
            self._on_auth_dead()
            return None
        except Exception as e:
            self.app.handle_error(e, context)
            return None

    def _cookies_path(self) -> str:
        """Path to the user's yt-dlp cookies file (reused for InnerTube).

        ytdlp_cookies is a GLOBAL setting (app.prefs / main config), same as
        sound.py uses for playback — not a per-account pref. Read it from there,
        falling back to the account pref only if a per-account override exists.
        """
        path = getattr(self.app.prefs, "ytdlp_cookies", "") or ""
        if not path and self._prefs is not None:
            path = self._prefs.get("ytdlp_cookies", "") or ""
        return path

    def _convert_playlist_items(self, items) -> List[UniversalStatus]:
        """Turn playlistItems entries into video statuses (resolving full stats)."""
        video_ids = []
        for it in items or []:
            vid = (((it.get("snippet", {}) or {}).get("resourceId", {})) or {}).get("videoId")
            if vid:
                video_ids.append(vid)
        return self._videos_by_ids(video_ids)

    def _videos_by_ids(self, video_ids: List[str]) -> List[UniversalStatus]:
        """Fetch full video resources for a batch of IDs (<=50) and convert."""
        if not video_ids:
            return []
        resp = self._execute(
            self.service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids[:50]),
                maxResults=50,
            ),
            "videos",
        )
        if not resp:
            return []
        # videos.list doesn't guarantee response order matches the request, so
        # rebuild in the requested id order (preserves recommendation ranking).
        by_id = {}
        for item in resp.get("items", []):
            status = youtube_video_to_universal(item)
            if status:
                by_id[status.id] = status
                self.user_cache.add_users_from_status(status)
        statuses = [by_id[v] for v in video_ids[:50] if v in by_id]
        self._apply_handles([s.account for s in statuses])
        return statuses

    def _apply_handles(self, users) -> None:
        """Resolve channel @handles (customUrl) and set each author's acct.

        Turns "@UC..." / channel-title into the real "@brandonbracey". Results
        are cached per channel id, and channels.list costs only 1 quota unit
        per batch of 50, so this is cheap across timeline refreshes.
        """
        if not users:
            return
        need = []
        for u in users:
            cid = getattr(u, "id", "") or ""
            if cid.startswith("UC") and cid not in self._handle_cache:
                need.append(cid)
        need = list(dict.fromkeys(need))  # de-dupe, preserve order
        for i in range(0, len(need), 50):
            chunk = need[i:i + 50]
            resp = self._execute(
                self.service.channels().list(part="snippet", id=",".join(chunk), maxResults=50),
                "channel handles",
            )
            if not resp:
                continue
            for item in resp.get("items", []):
                cid = item.get("id", "")
                custom = ((item.get("snippet", {}) or {}).get("customUrl", "") or "")
                if cid and custom:
                    self._handle_cache[cid] = custom.lstrip("@")
        for u in users:
            handle = self._handle_cache.get(getattr(u, "id", ""))
            if handle:
                u.acct = handle
                u.username = handle

    # ============ Timeline Methods ============

    def get_home_timeline(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Home feed.

        Prefers personalized recommendations (InnerTube, cookie-based), but
        YouTube rotates/expires browser cookies and sometimes serves an empty
        feed, so when recommendations come back empty we fall back to recent
        uploads from your subscriptions via the Data API (always available).
        """
        # Recent uploads from your subscriptions (durable, newest first).
        subs = self.get_subscription_uploads(limit=limit)
        # Recommendations when YouTube serves them (cookie-based; often empty).
        recs = self._get_recommendations(limit=max(10, limit // 3))
        if not recs:
            return subs
        # Mix: a few recommendations up top, then the recent subscription feed,
        # de-duplicated by video id.
        seen = set()
        combined = []
        for s in recs + subs:
            if s.id and s.id not in seen:
                seen.add(s.id)
                combined.append(s)
        return combined[:limit]

    def _get_recommendations(self, limit: int = 40) -> List[UniversalStatus]:
        """Cookie-based recommendations feed via the InnerTube browse endpoint.

        Uses the user's yt-dlp cookies for personalization; falls back to a
        generic feed when no cookies are configured. Never raises.
        """
        from . import innertube
        region = "US"
        language = "en"
        if self._prefs is not None:
            region = self._prefs.get("youtube_region", "") or region
            language = self._prefs.get("youtube_language", "") or language
        items = innertube.get_recommendations(
            cookies_path=self._cookies_path(), limit=limit,
            region=region, language=language,
        )
        # InnerTube only gives a fuzzy "3 days ago" time, so hydrate the IDs via
        # the Data API for exact publish dates, real stats, and @handles.
        video_ids = [it.get("id") for it in items if it.get("id")]
        statuses = self._videos_by_ids(video_ids)
        if statuses:
            return statuses
        # Fallback (e.g. Data API hiccup): use the InnerTube data as-is.
        fallback = []
        for item in items:
            status = innertube_video_to_universal(item)
            if status:
                fallback.append(status)
                self.user_cache.add_users_from_status(status)
        return fallback

    def get_subscription_uploads(self, limit: int = 40, max_channels: int = 30) -> List[UniversalStatus]:
        """Recent uploads from channels you subscribe to, newest first (Data API).

        The official API has no subscription-feed endpoint, so we sample your
        subscriptions (ordered by relevance), read each channel's latest uploads
        from its computed uploads playlist (UU + channelId[2:], which avoids a
        channels.list call per channel), then merge and sort by actual upload
        date. One batched videos.list hydrates the final set.
        """
        # Subscriptions ordered by relevance (more useful than alphabetical).
        resp = self._execute(
            self.service.subscriptions().list(
                part="snippet", mine=True, maxResults=min(max_channels, 50),
                order="relevance",
            ),
            "subscription feed",
        )
        if not resp:
            return []
        channel_ids = []
        for item in resp.get("items", []):
            cid = (((item.get("snippet", {}) or {}).get("resourceId", {})) or {}).get("channelId", "")
            if cid.startswith("UC"):
                channel_ids.append(cid)

        # Collect (upload_date, video_id) across channels' latest uploads.
        candidates = []
        for cid in channel_ids:
            uploads = "UU" + cid[2:]
            r = self._execute(
                self.service.playlistItems().list(
                    part="contentDetails", playlistId=uploads, maxResults=2,
                ),
                "subscription uploads",
            )
            if not r:
                continue
            for it in r.get("items", []):
                cd = it.get("contentDetails", {}) or {}
                vid = cd.get("videoId")
                date = cd.get("videoPublishedAt", "")
                if vid:
                    candidates.append((date or "", vid))

        # Newest first, de-duped, then hydrate the top slice in that order.
        candidates.sort(key=lambda c: c[0], reverse=True)
        seen = set()
        top_ids = []
        for _, vid in candidates:
            if vid not in seen:
                seen.add(vid)
                top_ids.append(vid)
            if len(top_ids) >= limit:
                break
        return self._videos_by_ids(top_ids)

    def get_mentions(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """No direct "mentions" concept on YouTube."""
        return []

    def get_notifications(self, limit: int = 40, **kwargs) -> List[UniversalNotification]:
        """No notifications API on YouTube."""
        return []

    def get_conversations(self, limit: int = 40, **kwargs) -> List[Any]:
        """No direct messages on YouTube."""
        return []

    def get_favourites(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Your liked videos (the 'LL' likes playlist)."""
        if not self._likes_playlist:
            return []
        resp = self._execute(
            self.service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=self._likes_playlist,
                maxResults=min(limit, 50),
            ),
            "liked videos",
        )
        if not resp:
            return []
        return self._convert_playlist_items(resp.get("items", []))

    def get_user_statuses(self, user_id: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """A channel's uploads (resolve channel -> uploads playlist -> items)."""
        if not user_id:
            return []
        # Our own uploads playlist is already known.
        if self.me and user_id == self.me.id and self._uploads_playlist:
            uploads = self._uploads_playlist
        else:
            ch = self._execute(
                self.service.channels().list(part="contentDetails", id=user_id),
                "channel uploads",
            )
            items = ch.get("items", []) if ch else []
            if not items:
                return []
            uploads = (((items[0].get("contentDetails", {}) or {})
                        .get("relatedPlaylists", {})) or {}).get("uploads", "")
        if not uploads:
            return []
        resp = self._execute(
            self.service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads,
                maxResults=min(limit, 50),
            ),
            "channel uploads",
        )
        if not resp:
            return []
        return self._convert_playlist_items(resp.get("items", []))

    def get_list_timeline(self, list_id: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Playlists could map here later; not implemented yet."""
        return []

    def search_statuses(self, query: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Search videos via InnerTube (no API quota), Data API as fallback."""
        try:
            from youtubesearchpython import VideosSearch
            results = VideosSearch(query, limit=min(limit, 20)).result() or {}
            # Hydrate via Data API for exact dates/stats/handles (InnerTube only
            # gives fuzzy "3 days ago" times).
            video_ids = [it.get("id") for it in results.get("result", []) if it.get("id")]
            statuses = self._videos_by_ids(video_ids)
            if statuses:
                return statuses
        except ImportError:
            if _logger:
                _logger.info("youtubesearchpython not available; using Data API search.")
        except Exception as e:
            self.app.handle_error(e, "search")
        # Fallback: Data API search (costs 100 quota units per call).
        resp = self._execute(
            self.service.search().list(
                part="snippet", q=query, type="video", maxResults=min(limit, 25),
            ),
            "search",
        )
        if not resp:
            return []
        statuses = []
        for item in resp.get("items", []):
            status = youtube_search_result_to_universal(item)
            if isinstance(status, UniversalStatus):
                statuses.append(status)
        self._apply_handles([s.account for s in statuses])
        return statuses

    def get_status(self, status_id: str) -> Optional[UniversalStatus]:
        """Fetch a single video by ID."""
        results = self._videos_by_ids([status_id])
        return results[0] if results else None

    def get_status_context(self, status_id: str) -> Dict[str, List[UniversalStatus]]:
        """Comments for a video (descendants), or replies to a comment.

        Loaded via FastSM's "Load conversation" (Ctrl+G): on a video this shows
        its comment threads + replies; on a comment it shows that comment's
        replies.
        """
        descendants: List[UniversalStatus] = []
        if self._is_comment_id(status_id):
            descendants = self._get_comment_replies(status_id)
            self._apply_handles([d.account for d in descendants])
            return {"ancestors": [], "descendants": descendants}

        # Handle this call directly so we can give a friendly message when a
        # video has comments turned off (a normal state, not a real error).
        resp = None
        if self._auth_dead:
            return {"ancestors": [], "descendants": []}
        try:
            with self._api_lock:
                self._ensure_creds()
                resp = self.service.commentThreads().list(
                    part="snippet,replies", videoId=status_id,
                    maxResults=50, order="relevance", textFormat="plainText",
                ).execute()
        except oauth.YouTubeReauthRequired:
            self._on_auth_dead()
            return {"ancestors": [], "descendants": []}
        except Exception as e:
            msg = str(e)
            if "commentsDisabled" in msg or "disabled comments" in msg:
                self.app.handle_error("Comments are turned off for this video.", "comments")
            else:
                self.app.handle_error(e, "comments")
            return {"ancestors": [], "descendants": []}
        if resp:
            for item in resp.get("items", []):
                tlc = ((item.get("snippet", {}) or {}).get("topLevelComment", {})) or {}
                top = youtube_comment_to_universal(tlc, video_id=status_id)
                if top:
                    descendants.append(top)
                    self.user_cache.add_user(top.account)
                for rep in ((item.get("replies", {}) or {}).get("comments", []) or []):
                    rst = youtube_comment_to_universal(rep, video_id=status_id)
                    if rst:
                        descendants.append(rst)
                        self.user_cache.add_user(rst.account)
        self._apply_handles([d.account for d in descendants])
        return {"ancestors": [], "descendants": descendants}

    def _get_comment_replies(self, parent_id: str) -> List[UniversalStatus]:
        """Replies to a single top-level comment."""
        resp = self._execute(
            self.service.comments().list(
                part="snippet", parentId=parent_id, maxResults=50, textFormat="plainText",
            ),
            "comment replies",
        )
        out = []
        if resp:
            for c in resp.get("items", []):
                st = youtube_comment_to_universal(c)
                if st:
                    out.append(st)
                    self.user_cache.add_user(st.account)
        return out

    @staticmethod
    def _is_comment_id(value: str) -> bool:
        """Heuristic: video IDs are 11 chars; comment IDs are much longer."""
        return bool(value) and len(value) > 15

    # ============ Action Methods ============

    def post(self, text: str, reply_to_id: Optional[str] = None,
             visibility: Optional[str] = None, spoiler_text: Optional[str] = None,
             **kwargs) -> Optional[UniversalStatus]:
        """Reply to a video -> top-level comment; reply to a comment -> a reply.

        A top-level post (no reply target) would be a community update, which has
        no official API, so it raises a clear message instead of failing quietly.
        """
        if reply_to_id:
            if self._is_comment_id(reply_to_id):
                return self._reply_to_comment(reply_to_id, text)
            return self._post_comment(reply_to_id, text)
        raise NotImplementedError(
            "Posting a YouTube community update isn't supported (no official API). "
            "Reply to a video to comment, or reply to a comment to respond."
        )

    def _reply_to_comment(self, parent_id: str, text: str) -> Optional[UniversalStatus]:
        """Reply to an existing comment (requires youtube.force-ssl)."""
        body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
        resp = self._execute(
            self.service.comments().insert(part="snippet", body=body),
            "reply to comment",
        )
        return youtube_comment_to_universal(resp) if resp else None

    def _post_comment(self, video_id: str, text: str) -> Optional[UniversalStatus]:
        """Post a top-level comment on a video (requires youtube.force-ssl)."""
        body = {
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }
        }
        resp = self._execute(
            self.service.commentThreads().insert(part="snippet", body=body),
            "post comment",
        )
        if not resp:
            return None
        # Represent the posted comment as a lightweight status.
        return UniversalStatus(
            id=resp.get("id", ""),
            account=self.me,
            content=text,
            text=text,
            created_at=datetime.now(timezone.utc),
            in_reply_to_id=video_id,
            url=watch_url(video_id),
            _platform_data=resp,
            _platform=PLATFORM,
        )

    def boost(self, status_id: str) -> bool:
        return False  # No "boost" on YouTube

    def unboost(self, status_id: str) -> bool:
        return False

    def favourite(self, status_id: str) -> bool:
        """Like a video (videos.rate). The API can't like comments."""
        if self._is_comment_id(status_id):
            return False
        self._execute(
            self.service.videos().rate(id=status_id, rating="like"),
            "like video",
        )
        return True  # rate() returns an empty body on success

    def unfavourite(self, status_id: str) -> bool:
        """Remove a like (rating=none)."""
        if self._is_comment_id(status_id):
            return False
        self._execute(
            self.service.videos().rate(id=status_id, rating="none"),
            "unlike video",
        )
        return True

    def delete_status(self, status_id: str) -> bool:
        """Delete one of your own comments (videos can't be deleted via this API)."""
        if not self._is_comment_id(status_id):
            return False
        self._execute(self.service.comments().delete(id=status_id), "delete comment")
        return True

    def edit(self, status_id: str, text: str, **kwargs) -> Optional[UniversalStatus]:
        """Edit one of your own comments (comments.update)."""
        if not self._is_comment_id(status_id):
            return None
        body = {"id": status_id, "snippet": {"textOriginal": text}}
        resp = self._execute(
            self.service.comments().update(part="snippet", body=body),
            "edit comment",
        )
        return youtube_comment_to_universal(resp) if resp else None

    # ============ User Methods ============

    def get_user(self, user_id: str) -> Optional[UniversalUser]:
        """Fetch a channel by ID."""
        resp = self._execute(
            self.service.channels().list(
                part="snippet,statistics,contentDetails", id=user_id,
            ),
            "channel",
        )
        items = resp.get("items", []) if resp else []
        if not items:
            return None
        user = youtube_channel_to_universal(items[0])
        if user:
            self.user_cache.add_user(user)
        return user

    def search_users(self, query: str, limit: int = 10) -> List[UniversalUser]:
        """Search channels via InnerTube, Data API as fallback."""
        try:
            from youtubesearchpython import ChannelsSearch
            results = ChannelsSearch(query, limit=min(limit, 20)).result() or {}
            users = []
            for item in results.get("result", []):
                user = innertube_channel_to_universal(item)
                if user:
                    users.append(user)
                    self.user_cache.add_user(user)
            if users:
                return users
        except ImportError:
            pass
        except Exception as e:
            self.app.handle_error(e, "search users")
        resp = self._execute(
            self.service.search().list(
                part="snippet", q=query, type="channel", maxResults=min(limit, 25),
            ),
            "search users",
        )
        if not resp:
            return []
        users = []
        for item in resp.get("items", []):
            result = youtube_search_result_to_universal(item)
            if isinstance(result, UniversalUser):
                users.append(result)
        return users

    def follow(self, user_id: str) -> bool:
        """Subscribe to a channel."""
        body = {"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": user_id}}}
        return self._execute(
            self.service.subscriptions().insert(part="snippet", body=body),
            "subscribe",
        ) is not None

    def unfollow(self, user_id: str) -> bool:
        """Unsubscribe from a channel (look up the subscription id first)."""
        resp = self._execute(
            self.service.subscriptions().list(
                part="snippet", mine=True, forChannelId=user_id, maxResults=1,
            ),
            "unsubscribe lookup",
        )
        items = resp.get("items", []) if resp else []
        if not items:
            return False
        sub_id = items[0].get("id")
        if not sub_id:
            return False
        self._execute(self.service.subscriptions().delete(id=sub_id), "unsubscribe")
        return True

    def block(self, user_id: str) -> bool:
        return False  # No public block API

    def unblock(self, user_id: str) -> bool:
        return False

    def mute(self, user_id: str) -> bool:
        return False

    def unmute(self, user_id: str) -> bool:
        return False

    def get_followers(self, user_id: str, limit: int = 80, **kwargs) -> List[UniversalUser]:
        """Subscriber lists aren't exposed by the API."""
        return []

    def get_following(self, user_id: str, limit: int = 80, **kwargs) -> List[UniversalUser]:
        """Your subscriptions (only available for the authenticated user)."""
        if not self.me or user_id != self.me.id:
            return []
        resp = self._execute(
            self.service.subscriptions().list(
                part="snippet", mine=True, maxResults=min(limit, 50),
                order="alphabetical",
            ),
            "subscriptions",
        )
        if not resp:
            return []
        users = []
        for item in resp.get("items", []):
            user = youtube_subscription_to_universal(item)
            if user:
                users.append(user)
                self.user_cache.add_user(user)
        self._apply_handles(users)
        return users

    # ============ Lifecycle ============

    def close(self):
        """Release resources on account removal / app shutdown."""
        pass
