"""Conversion functions from Mastodon objects to universal models."""

from datetime import datetime
from typing import Optional, List, Any
import html
import re

from models import (
    UniversalStatus,
    UniversalUser,
    UniversalNotification,
    UniversalMedia,
    UniversalMention,
)

# HTML tag pattern for stripping
_html_tag_re = re.compile(r'<[^>]+>')


def parse_datetime(value):
    """Parse a datetime from various formats (string or datetime object)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Try ISO format parsing
        try:
            # Handle ISO format with Z suffix
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            pass
        # Try common formats
        for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.strptime(value, fmt)
            except (ValueError, TypeError):
                continue
    return None


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    text = _html_tag_re.sub('', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def mastodon_user_to_universal(user, platform_data=None) -> Optional[UniversalUser]:
    """Convert a Mastodon user/account to UniversalUser."""
    if user is None:
        return None

    # Handle both dict and object formats
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    return UniversalUser(
        id=str(get_attr(user, 'id', '')),
        acct=get_attr(user, 'acct', ''),
        username=get_attr(user, 'username', ''),
        display_name=get_attr(user, 'display_name', '') or get_attr(user, 'acct', ''),
        note=get_attr(user, 'note', ''),
        avatar=get_attr(user, 'avatar', None),
        header=get_attr(user, 'header', None),
        followers_count=get_attr(user, 'followers_count', 0),
        following_count=get_attr(user, 'following_count', 0),
        statuses_count=get_attr(user, 'statuses_count', 0),
        created_at=parse_datetime(get_attr(user, 'created_at')),
        url=get_attr(user, 'url', None),
        bot=get_attr(user, 'bot', False),
        locked=get_attr(user, 'locked', False),
        _platform_data=platform_data or user,
        _platform='mastodon',
    )


def mastodon_media_to_universal(media) -> UniversalMedia:
    """Convert a Mastodon media attachment to UniversalMedia."""
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    return UniversalMedia(
        id=str(get_attr(media, 'id', '')),
        type=get_attr(media, 'type', 'unknown'),
        url=get_attr(media, 'url', ''),
        preview_url=get_attr(media, 'preview_url', None),
        description=get_attr(media, 'description', None),
        _platform_data=media,
    )


def mastodon_mention_to_universal(mention) -> UniversalMention:
    """Convert a Mastodon mention to UniversalMention."""
    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    return UniversalMention(
        id=str(get_attr(mention, 'id', '')),
        acct=get_attr(mention, 'acct', ''),
        username=get_attr(mention, 'username', ''),
        url=get_attr(mention, 'url', None),
        _platform_data=mention,
    )


def mastodon_status_to_universal(status, platform_data=None) -> Optional[UniversalStatus]:
    """Convert a Mastodon status to UniversalStatus."""
    if status is None:
        return None

    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    content = get_attr(status, 'content', '')
    text = strip_html(content)

    # Convert account
    account = mastodon_user_to_universal(get_attr(status, 'account', None))

    # Convert reblog if present
    reblog = None
    reblog_data = get_attr(status, 'reblog', None)
    if reblog_data:
        reblog = mastodon_status_to_universal(reblog_data)

    # Convert quote if present (Mastodon 4.0+)
    # In Mastodon.py 2.x, quote is a Quote object with quoted_status field
    quote = None
    quote_data = get_attr(status, 'quote', None)
    if quote_data:
        # Check if it's a Quote object (has quoted_status) or direct status
        quoted_status = get_attr(quote_data, 'quoted_status', None)
        if quoted_status:
            quote = mastodon_status_to_universal(quoted_status)
        else:
            # Fallback: maybe it's directly a status (older format)
            quote = mastodon_status_to_universal(quote_data)

    # Convert media attachments
    media_attachments = []
    for media in get_attr(status, 'media_attachments', []):
        media_attachments.append(mastodon_media_to_universal(media))

    # Convert mentions
    mentions = []
    for mention in get_attr(status, 'mentions', []):
        mentions.append(mastodon_mention_to_universal(mention))

    return UniversalStatus(
        id=str(get_attr(status, 'id', '')),
        account=account,
        content=content,
        text=text,
        created_at=parse_datetime(get_attr(status, 'created_at')) or datetime.now(),
        favourites_count=get_attr(status, 'favourites_count', 0),
        boosts_count=get_attr(status, 'reblogs_count', 0),
        replies_count=get_attr(status, 'replies_count', 0),
        in_reply_to_id=str(get_attr(status, 'in_reply_to_id', '')) if get_attr(status, 'in_reply_to_id') else None,
        reblog=reblog,
        quote=quote,
        media_attachments=media_attachments,
        mentions=mentions,
        url=get_attr(status, 'url', None),
        visibility=get_attr(status, 'visibility', None),
        spoiler_text=get_attr(status, 'spoiler_text', None),
        card=get_attr(status, 'card', None),
        poll=get_attr(status, 'poll', None),
        quote_approval=get_attr(status, 'quote_approval', None),
        _platform_data=platform_data or status,
        _platform='mastodon',
    )


def mastodon_notification_to_universal(notification) -> Optional[UniversalNotification]:
    """Convert a Mastodon notification to UniversalNotification."""
    if notification is None:
        return None

    def get_attr(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    account = mastodon_user_to_universal(get_attr(notification, 'account', None))

    status = None
    status_data = get_attr(notification, 'status', None)
    if status_data:
        status = mastodon_status_to_universal(status_data)

    return UniversalNotification(
        id=str(get_attr(notification, 'id', '')),
        type=get_attr(notification, 'type', 'unknown'),
        account=account,
        created_at=parse_datetime(get_attr(notification, 'created_at')) or datetime.now(),
        status=status,
        _platform_data=notification,
        _platform='mastodon',
    )
