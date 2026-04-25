# -*- coding: utf-8 -*-
"""Serialization helpers for converting Universal models to/from database rows."""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from models import (
    UniversalUser,
    UniversalStatus,
    UniversalNotification,
    UniversalMedia,
    UniversalMention,
)


def _is_json_serializable(value) -> bool:
    """Check if a value can be JSON serialized."""
    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_json_serializable(v) for v in value)
    if isinstance(value, dict):
        return all(_is_json_serializable(v) for v in value.values())
    return False


def _datetime_to_str(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO format string."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _str_to_datetime(s: Optional[str]) -> Optional[datetime]:
    """Convert ISO format string to datetime."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ============ User Serialization ============

def user_to_row(user: UniversalUser) -> Dict[str, Any]:
    """Convert a UniversalUser to a database row dict."""
    if user is None:
        return None
    return {
        'id': str(user.id),
        'acct': user.acct,
        'username': user.username,
        'display_name': user.display_name,
        'note': user.note or '',
        'avatar': user.avatar,
        'header': user.header,
        'followers_count': user.followers_count,
        'following_count': user.following_count,
        'statuses_count': user.statuses_count,
        'created_at': _datetime_to_str(user.created_at),
        'url': user.url,
        'bot': 1 if user.bot else 0,
        'locked': 1 if user.locked else 0,
        'platform': user._platform or '',
    }


def row_to_user(row: Dict[str, Any]) -> Optional[UniversalUser]:
    """Convert a database row dict to a UniversalUser."""
    if row is None:
        return None
    return UniversalUser(
        id=str(row['id']),
        acct=row['acct'],
        username=row['username'],
        display_name=row['display_name'],
        note=row.get('note', ''),
        avatar=row.get('avatar'),
        header=row.get('header'),
        followers_count=row.get('followers_count', 0),
        following_count=row.get('following_count', 0),
        statuses_count=row.get('statuses_count', 0),
        created_at=_str_to_datetime(row.get('created_at')),
        url=row.get('url'),
        bot=bool(row.get('bot', 0)),
        locked=bool(row.get('locked', 0)),
        _platform=row.get('platform', ''),
    )


# ============ Media Serialization ============

def media_to_dict(media: UniversalMedia) -> Dict[str, Any]:
    """Convert a UniversalMedia to a JSON-serializable dict."""
    if media is None:
        return None
    return {
        'id': str(media.id),
        'type': media.type,
        'url': media.url,
        'preview_url': media.preview_url,
        'description': media.description,
    }


def dict_to_media(d: Dict[str, Any]) -> Optional[UniversalMedia]:
    """Convert a dict to a UniversalMedia."""
    if d is None:
        return None
    return UniversalMedia(
        id=str(d['id']),
        type=d.get('type', 'image'),
        url=d.get('url', ''),
        preview_url=d.get('preview_url'),
        description=d.get('description'),
    )


# ============ Mention Serialization ============

def mention_to_dict(mention: UniversalMention) -> Dict[str, Any]:
    """Convert a UniversalMention to a JSON-serializable dict."""
    if mention is None:
        return None
    return {
        'id': str(mention.id),
        'acct': mention.acct,
        'username': mention.username,
        'url': mention.url,
    }


def dict_to_mention(d: Dict[str, Any]) -> Optional[UniversalMention]:
    """Convert a dict to a UniversalMention."""
    if d is None:
        return None
    return UniversalMention(
        id=str(d['id']),
        acct=d.get('acct', ''),
        username=d.get('username', ''),
        url=d.get('url'),
    )


# ============ Status Serialization ============

def status_to_row(status: UniversalStatus, include_nested: bool = True) -> Dict[str, Any]:
    """Convert a UniversalStatus to a database row dict.

    Args:
        status: The status to serialize
        include_nested: If True, serialize reblog/quote as JSON; if False, store only IDs
    """
    if status is None:
        return None

    # Serialize media attachments as JSON
    media_json = None
    if status.media_attachments:
        media_json = json.dumps([media_to_dict(m) for m in status.media_attachments])

    # Serialize mentions as JSON
    mentions_json = None
    if status.mentions:
        mentions_json = json.dumps([mention_to_dict(m) for m in status.mentions])

    # Serialize card as JSON (already a dict/object)
    card_json = None
    if status.card:
        try:
            # Card might be a dict or an object with attributes
            if hasattr(status.card, '__dict__'):
                card_json = json.dumps({k: v for k, v in status.card.__dict__.items()
                                       if not k.startswith('_') and isinstance(v, (str, int, float, bool, type(None)))})
            elif isinstance(status.card, dict):
                card_json = json.dumps(status.card)
        except (TypeError, ValueError):
            pass

    # Serialize poll as JSON
    poll_json = None
    if status.poll:
        try:
            poll = status.poll
            if hasattr(poll, '__dict__'):
                # Convert poll object to serializable dict
                poll_dict = {}
                for k, v in poll.__dict__.items():
                    if k.startswith('_'):
                        continue
                    # Handle options list - each option may be an object
                    if k == 'options' and isinstance(v, list):
                        poll_dict[k] = []
                        for opt in v:
                            if hasattr(opt, '__dict__'):
                                poll_dict[k].append({ok: ov for ok, ov in opt.__dict__.items()
                                                    if not ok.startswith('_') and _is_json_serializable(ov)})
                            elif isinstance(opt, dict):
                                poll_dict[k].append(opt)
                            else:
                                poll_dict[k].append(str(opt))
                    elif _is_json_serializable(v):
                        poll_dict[k] = v
                    elif hasattr(v, 'isoformat'):
                        # Handle datetime
                        poll_dict[k] = v.isoformat()
                poll_json = json.dumps(poll_dict)
            elif isinstance(poll, dict):
                poll_json = json.dumps(poll)
        except (TypeError, ValueError) as e:
            print(f"[CACHE] Failed to serialize poll: {e}")

    # Get reblog/quote IDs
    reblog_id = None
    quote_id = None
    if status.reblog:
        reblog_id = str(status.reblog.id)
    if status.quote:
        quote_id = str(status.quote.id)

    # Get account ID
    account_id = str(status.account.id) if status.account else None

    return {
        'id': str(status.id),
        'account_id': account_id,
        'content': status.content,
        'text': status.text,
        'created_at': _datetime_to_str(status.created_at),
        'favourites_count': status.favourites_count,
        'boosts_count': status.boosts_count,
        'replies_count': status.replies_count,
        'in_reply_to_id': str(status.in_reply_to_id) if status.in_reply_to_id else None,
        'reblog_id': reblog_id,
        'quote_id': quote_id,
        'url': status.url,
        'visibility': status.visibility,
        'spoiler_text': status.spoiler_text,
        'pinned': 1 if status.pinned else 0,
        'platform': status._platform or '',
        'media_attachments_json': media_json,
        'mentions_json': mentions_json,
        'card_json': card_json,
        'poll_json': poll_json,
        # Store special attributes for mentions timeline
        '_notification_id': getattr(status, '_notification_id', None),
        '_original_status_id': getattr(status, '_original_status_id', None),
    }


def row_to_status(row: Dict[str, Any], user_lookup: callable = None,
                  status_lookup: callable = None) -> Optional[UniversalStatus]:
    """Convert a database row dict to a UniversalStatus.

    Args:
        row: The database row dict
        user_lookup: Function to look up a user by ID
        status_lookup: Function to look up a status by ID (for reblog/quote)
    """
    if row is None:
        return None

    # Look up account
    account = None
    if row.get('account_id') and user_lookup:
        account = user_lookup(row['account_id'])

    # Parse media attachments
    media_attachments = []
    if row.get('media_attachments_json'):
        try:
            media_list = json.loads(row['media_attachments_json'])
            media_attachments = [dict_to_media(m) for m in media_list if m]
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse mentions
    mentions = []
    if row.get('mentions_json'):
        try:
            mention_list = json.loads(row['mentions_json'])
            mentions = [dict_to_mention(m) for m in mention_list if m]
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse card
    card = None
    if row.get('card_json'):
        try:
            card = json.loads(row['card_json'])
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse poll
    poll = None
    if row.get('poll_json'):
        try:
            poll = json.loads(row['poll_json'])
        except (json.JSONDecodeError, TypeError):
            pass

    # Look up reblog/quote (avoid infinite recursion by limiting depth)
    reblog = None
    quote = None
    if status_lookup:
        if row.get('reblog_id'):
            reblog = status_lookup(row['reblog_id'])
        if row.get('quote_id'):
            quote = status_lookup(row['quote_id'])

    status = UniversalStatus(
        id=str(row['id']),
        account=account,
        content=row.get('content', ''),
        text=row.get('text', ''),
        created_at=_str_to_datetime(row.get('created_at')) or datetime.now(),
        favourites_count=row.get('favourites_count', 0),
        boosts_count=row.get('boosts_count', 0),
        replies_count=row.get('replies_count', 0),
        in_reply_to_id=row.get('in_reply_to_id'),
        reblog=reblog,
        quote=quote,
        media_attachments=media_attachments,
        mentions=mentions,
        url=row.get('url'),
        visibility=row.get('visibility'),
        spoiler_text=row.get('spoiler_text'),
        card=card,
        poll=poll,
        pinned=bool(row.get('pinned', 0)),
        _platform=row.get('platform', ''),
    )

    # Restore special attributes
    if row.get('_notification_id'):
        status._notification_id = row['_notification_id']
    if row.get('_original_status_id'):
        status._original_status_id = row['_original_status_id']

    # If the row references a quote we couldn't satisfy from the cache (e.g.
    # the quoted post was streamed in after the last cache write), record the
    # ID so the timeline loader can resolve it from the API in the background.
    if row.get('quote_id') and quote is None:
        status._unresolved_quote_id = str(row['quote_id'])

    return status


# ============ Notification Serialization ============

def notification_to_row(notification: UniversalNotification) -> Dict[str, Any]:
    """Convert a UniversalNotification to a database row dict."""
    if notification is None:
        return None

    account_id = str(notification.account.id) if notification.account else None
    status_id = str(notification.status.id) if notification.status else None

    return {
        'id': str(notification.id),
        'type': notification.type,
        'account_id': account_id,
        'created_at': _datetime_to_str(notification.created_at),
        'status_id': status_id,
        'platform': notification._platform or '',
    }


def row_to_notification(row: Dict[str, Any], user_lookup: callable = None,
                        status_lookup: callable = None) -> Optional[UniversalNotification]:
    """Convert a database row dict to a UniversalNotification.

    Args:
        row: The database row dict
        user_lookup: Function to look up a user by ID
        status_lookup: Function to look up a status by ID
    """
    if row is None:
        return None

    # Look up account
    account = None
    if row.get('account_id') and user_lookup:
        account = user_lookup(row['account_id'])

    # Look up status
    status = None
    if row.get('status_id') and status_lookup:
        status = status_lookup(row['status_id'])

    return UniversalNotification(
        id=str(row['id']),
        type=row.get('type', ''),
        account=account,
        created_at=_str_to_datetime(row.get('created_at')) or datetime.now(),
        status=status,
        _platform=row.get('platform', ''),
    )
