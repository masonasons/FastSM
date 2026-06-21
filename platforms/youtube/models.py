"""Conversion functions from YouTube Data API v3 resources to universal models.

Two shapes of input show up here:

  * Official Data API resources (dicts from google-api-python-client), used
    for identity, subscriptions, a channel's uploads, single videos, etc.
  * InnerTube/scraped dicts from the youtube-search-python library, used for
    search and the recommendations feed. Those are converted by the
    innertube_* helpers, which tolerate the looser, differently-named fields.

Everything funnels into UniversalStatus / UniversalUser so the rest of FastSM
(timelines, the audio player, the post renderer) treats YouTube like any
other platform.
"""

from datetime import datetime, timezone
from typing import Optional, Any, Dict

from models import UniversalStatus, UniversalUser, UniversalMedia

PLATFORM = "youtube"


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else ""


def channel_url(channel_id: str) -> str:
    return f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""


def _dig(obj: Any, *keys, default=None):
    """Safely walk nested dict keys: _dig(item, 'snippet', 'title')."""
    cur = obj
    for key in keys:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur


def _best_thumbnail(thumbnails: Optional[dict]) -> Optional[str]:
    """Pick the highest-resolution thumbnail URL available."""
    if not isinstance(thumbnails, dict):
        return None
    for size in ("maxres", "standard", "high", "medium", "default"):
        url = _dig(thumbnails, size, "url")
        if url:
            return url
    return None


def parse_datetime(value) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (e.g. '2021-01-01T00:00:00Z')."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Data API resources
# ---------------------------------------------------------------------------

def youtube_channel_to_universal(channel: dict) -> Optional[UniversalUser]:
    """Convert a channels.list item to a UniversalUser."""
    if not channel:
        return None
    channel_id = channel.get("id", "")
    snippet = channel.get("snippet", {}) or {}
    stats = channel.get("statistics", {}) or {}
    custom_url = snippet.get("customUrl", "")  # e.g. "@handle"
    handle = custom_url.lstrip("@") if custom_url else (channel_id or "")

    return UniversalUser(
        id=channel_id,
        acct=handle or channel_id,
        username=handle or channel_id,
        display_name=snippet.get("title", "") or handle or channel_id,
        note=snippet.get("description", "") or "",
        avatar=_best_thumbnail(snippet.get("thumbnails")),
        followers_count=_to_int(stats.get("subscriberCount")),
        following_count=0,  # YouTube doesn't expose who a channel subscribes to
        statuses_count=_to_int(stats.get("videoCount")),
        created_at=parse_datetime(snippet.get("publishedAt")),
        url=channel_url(channel_id),
        _platform_data=channel,
        _platform=PLATFORM,
    )


def _channel_ref_to_universal(channel_id: str, title: str,
                              thumbnails: Optional[dict] = None) -> UniversalUser:
    """Build a lightweight author UniversalUser from a video's snippet.

    Video snippets only carry channelId/channelTitle, not full channel stats,
    so this fills the bare minimum needed to render a post author.
    """
    # Use the channel name as the "acct" so the display reads "Name (@Name)"
    # rather than the cryptic "@UC..." channel ID. The real ID stays in `id`
    # for follow/subscribe actions.
    return UniversalUser(
        id=channel_id or "",
        acct=title or channel_id or "",
        username=title or channel_id or "",
        display_name=title or "",
        avatar=_best_thumbnail(thumbnails),
        url=channel_url(channel_id),
        _platform=PLATFORM,
    )


def youtube_video_to_universal(video: dict, channel_id: str = "",
                               channel_title: str = "") -> Optional[UniversalStatus]:
    """Convert a videos.list item (or anything with snippet+id) to a status.

    A video becomes a "post": the channel is the author, the title+description
    is the body, and the watch URL is attached as a video media attachment so
    the existing yt-dlp audio player can play it.
    """
    if not video:
        return None

    video_id = video.get("id", "")
    snippet = video.get("snippet", {}) or {}
    stats = video.get("statistics", {}) or {}

    title = snippet.get("title", "") or ""
    description = snippet.get("description", "") or ""
    # Timeline line = title only (clean); full description lives in `content`
    # for the detail view. Avoids dumping long descriptions into the timeline.
    text = title
    content = description or title

    author = _channel_ref_to_universal(
        channel_id or snippet.get("channelId", ""),
        channel_title or snippet.get("channelTitle", ""),
        snippet.get("thumbnails"),
    )

    url = watch_url(video_id)
    media = []
    if url:
        # description=None so the media line doesn't repeat the title.
        media.append(UniversalMedia(
            id=video_id,
            type="video",
            url=url,
            preview_url=_best_thumbnail(snippet.get("thumbnails")),
            description=None,
            _platform_data=video,
        ))

    return UniversalStatus(
        id=video_id,
        account=author,
        content=content,
        text=text,
        created_at=parse_datetime(snippet.get("publishedAt")) or datetime.now(timezone.utc),
        favourites_count=_to_int(stats.get("likeCount")),
        replies_count=_to_int(stats.get("commentCount")),
        media_attachments=media,
        url=url,
        _platform_data=video,
        _platform=PLATFORM,
    )


def youtube_subscription_to_universal(subscription: dict) -> Optional[UniversalUser]:
    """Convert a subscriptions.list item to a UniversalUser (the subscribed channel)."""
    if not subscription:
        return None
    snippet = subscription.get("snippet", {}) or {}
    channel_id = _dig(snippet, "resourceId", "channelId", default="") or ""
    title = snippet.get("title", "") or ""

    # acct falls back to the title (not the raw UC... id) for channels without
    # a handle, e.g. auto-generated "- Topic" music channels. _apply_handles
    # upgrades this to the real @handle when one exists.
    return UniversalUser(
        id=channel_id,
        acct=title or channel_id,
        username=title or channel_id,
        display_name=title,
        note=snippet.get("description", "") or "",
        avatar=_best_thumbnail(snippet.get("thumbnails")),
        url=channel_url(channel_id),
        _platform_data=subscription,
        _platform=PLATFORM,
    )


def youtube_comment_to_universal(comment: dict, video_id: str = "") -> Optional[UniversalStatus]:
    """Convert a comment resource (top-level comment or reply) to a status.

    Accepts the shape used by commentThreads (topLevelComment), comments.list
    replies, and comments.insert responses: a dict with 'id' and 'snippet'.
    """
    if not comment:
        return None
    cid = comment.get("id", "")
    sn = comment.get("snippet", {}) or {}
    author = UniversalUser(
        id=_dig(sn, "authorChannelId", "value", default="") or "",
        acct=sn.get("authorDisplayName", "") or "",
        username=sn.get("authorDisplayName", "") or "",
        display_name=sn.get("authorDisplayName", "") or "",
        avatar=sn.get("authorProfileImageUrl"),
        url=sn.get("authorChannelUrl", "") or "",
        _platform=PLATFORM,
    )
    text = sn.get("textOriginal", "") or sn.get("textDisplay", "") or ""
    return UniversalStatus(
        id=cid,
        account=author,
        content=text,
        text=text,
        created_at=parse_datetime(sn.get("publishedAt")) or datetime.now(timezone.utc),
        favourites_count=_to_int(sn.get("likeCount")),
        in_reply_to_id=sn.get("parentId") or video_id or None,
        url=watch_url(video_id) if video_id else None,
        _platform_data=comment,
        _platform=PLATFORM,
    )


def youtube_search_result_to_universal(item: dict):
    """Convert a search.list item to a status (video) or user (channel).

    search.list returns a heterogeneous list; the id.kind field says which.
    """
    if not item:
        return None
    kind = _dig(item, "id", "kind", default="")
    if kind == "youtube#channel":
        channel_id = _dig(item, "id", "channelId", default="") or ""
        snippet = item.get("snippet", {}) or {}
        return UniversalUser(
            id=channel_id,
            acct=channel_id,
            username=snippet.get("channelTitle", "") or snippet.get("title", "") or channel_id,
            display_name=snippet.get("title", "") or "",
            note=snippet.get("description", "") or "",
            avatar=_best_thumbnail(snippet.get("thumbnails")),
            url=channel_url(channel_id),
            _platform_data=item,
            _platform=PLATFORM,
        )
    # Default: treat as a video.
    video_id = _dig(item, "id", "videoId", default="") or ""
    video = {"id": video_id, "snippet": item.get("snippet", {})}
    return youtube_video_to_universal(video)


# ---------------------------------------------------------------------------
# InnerTube / youtube-search-python scraped dicts (search + recommendations)
# ---------------------------------------------------------------------------

def innertube_video_to_universal(item: Dict[str, Any]) -> Optional[UniversalStatus]:
    """Convert a youtube-search-python video dict to a status.

    Shape (abbreviated):
        {"id": "...", "title": "...", "channel": {"id": "...", "name": "..."},
         "publishedTime": "3 days ago", "thumbnails": [{"url": "..."}], ...}
    publishedTime is a fuzzy human string, so created_at is left as "now".
    """
    if not item:
        return None
    video_id = item.get("id", "") or ""
    channel = item.get("channel", {}) or {}
    thumbs = item.get("thumbnails") or []
    thumb_url = thumbs[-1].get("url") if thumbs else None

    author = _channel_ref_to_universal(
        channel.get("id", ""), channel.get("name", ""),
    )

    title = item.get("title", "") or ""
    url = item.get("link") or watch_url(video_id)
    media = []
    if url:
        media.append(UniversalMedia(
            id=video_id, type="video", url=url,
            preview_url=thumb_url, description=None, _platform_data=item,
        ))

    return UniversalStatus(
        id=video_id,
        account=author,
        content=title,
        text=title,
        created_at=datetime.now(timezone.utc),
        media_attachments=media,
        url=url,
        _platform_data=item,
        _platform=PLATFORM,
    )


def innertube_channel_to_universal(item: Dict[str, Any]) -> Optional[UniversalUser]:
    """Convert a youtube-search-python channel dict to a UniversalUser."""
    if not item:
        return None
    channel_id = item.get("id", "") or ""
    thumbs = item.get("thumbnails") or []
    return UniversalUser(
        id=channel_id,
        acct=channel_id,
        username=item.get("title", "") or channel_id,
        display_name=item.get("title", "") or "",
        note=item.get("descriptionSnippet", "") or "",
        avatar=(thumbs[-1].get("url") if thumbs else None),
        url=item.get("link") or channel_url(channel_id),
        _platform_data=item,
        _platform=PLATFORM,
    )
