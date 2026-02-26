"""Bluesky platform account implementation."""

from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from atproto import Client
from atproto.exceptions import AtProtocolError, InvokeTimeoutError

from platforms.base import PlatformAccount
from models import UniversalStatus, UniversalUser, UniversalNotification, UserCache
from models.status import UniversalMention
from cache import TimelineCache
from .models import (
    bluesky_post_to_universal,
    bluesky_profile_to_universal,
    bluesky_notification_to_universal,
    extract_rkey_from_uri,
)


class BlueskyAccount(PlatformAccount):
    """Bluesky-specific account implementation."""

    platform_name = "bluesky"

    # Feature flags - Bluesky has different capabilities than Mastodon
    supports_visibility = False  # All posts are public
    supports_content_warning = False  # Uses labels instead of CW
    supports_quote_posts = True
    supports_polls = False
    supports_lists = False  # Bluesky has feeds but not traditional lists
    supports_direct_messages = False  # No DM API
    supports_media_attachments = False  # TODO: Bluesky uses different upload API
    supports_scheduling = False  # No scheduling API

    def __init__(self, app, index: int, client: Client, profile, confpath: str, prefs=None):
        super().__init__(app, index)
        self.client = client
        self._me = bluesky_profile_to_universal(profile)
        self.confpath = confpath
        self._max_chars = 300  # Bluesky character limit
        self._prefs = prefs  # Store reference to account wrapper's prefs

        # Initialize user cache
        self.user_cache = UserCache(confpath, 'bluesky', str(self._me.id))
        self.user_cache.load()

        # Initialize timeline cache for fast startup
        if app.prefs.timeline_cache_enabled:
            self.timeline_cache = TimelineCache(confpath, str(self._me.id))
        else:
            self.timeline_cache = None

        # Cursor tracking for pagination (Bluesky uses cursors, not max_id)
        self._cursors = {}  # timeline_type -> cursor

    @property
    def me(self) -> UniversalUser:
        return self._me

    def _store_cursor(self, timeline_type: str, cursor: str):
        """Store cursor for pagination."""
        if cursor:
            self._cursors[timeline_type] = cursor

    def _get_cursor(self, timeline_type: str) -> str:
        """Get stored cursor for pagination."""
        return self._cursors.get(timeline_type)

    def _convert_feed_posts(self, feed) -> List[UniversalStatus]:
        """Convert a list of feed view posts to universal statuses."""
        statuses = []
        for item in feed:
            post = bluesky_post_to_universal(item)
            if post:
                statuses.append(post)
                self.user_cache.add_users_from_status(post)
        return statuses

    def _convert_posts(self, posts) -> List[UniversalStatus]:
        """Convert a list of post views to universal statuses."""
        statuses = []
        for post in posts:
            status = bluesky_post_to_universal(post)
            if status:
                statuses.append(status)
                self.user_cache.add_users_from_status(status)
        return statuses

    def _convert_profiles(self, profiles) -> List[UniversalUser]:
        """Convert a list of profiles to universal users."""
        users = []
        for profile in profiles:
            user = bluesky_profile_to_universal(profile)
            if user:
                users.append(user)
                self.user_cache.add_user(user)
        return users

    # ============ Timeline Methods ============

    def get_home_timeline(self, limit: int = 40, cursor: str = None, max_id: str = None, **kwargs) -> List[UniversalStatus]:
        """Get home timeline (Following feed)."""
        try:
            params = {'limit': min(limit, 100)}  # Bluesky max is 100

            # For "load previous", use the stored cursor (max_id signals pagination request)
            if max_id and not cursor:
                cursor = self._get_cursor('home')
            if cursor:
                params['cursor'] = cursor

            response = self.client.get_timeline(**params)

            # Store cursor for next pagination request
            self._store_cursor('home', getattr(response, 'cursor', None))

            return self._convert_feed_posts(response.feed)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "home timeline")
            return []
        except Exception as e:
            # Handle Pydantic validation errors and other unexpected errors
            error_msg = str(e)
            if 'validation error' in error_msg.lower():
                self.app.handle_error(f"API response parsing error (try refreshing): {error_msg[:100]}", "home timeline")
            else:
                self.app.handle_error(e, "home timeline")
            return []

    def get_mentions(self, limit: int = 40, cursor: str = None, max_id: str = None, **kwargs) -> List[UniversalStatus]:
        """Get mentions as statuses (extracted from notifications)."""
        try:
            from atproto import models

            # For "load previous", use the stored cursor
            if max_id and not cursor:
                cursor = self._get_cursor('mentions')

            params = models.AppBskyNotificationListNotifications.Params(
                limit=min(limit, 100),
                cursor=cursor
            )
            response = self.client.app.bsky.notification.list_notifications(params)

            # Store cursor for next pagination request
            self._store_cursor('mentions', getattr(response, 'cursor', None))

            statuses = []

            for notif in response.notifications:
                reason = getattr(notif, 'reason', '')
                if reason in ('mention', 'reply', 'quote'):
                    # Get the post URI from the notification
                    uri = getattr(notif, 'uri', '')
                    if uri:
                        try:
                            # Fetch the actual post
                            post_response = self.client.get_posts([uri])
                            if post_response.posts:
                                status = bluesky_post_to_universal(post_response.posts[0])
                                if status:
                                    status._notification_id = uri
                                    statuses.append(status)
                                    self.user_cache.add_users_from_status(status)
                        except:
                            pass

            return statuses
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "mentions")
            return []

    def get_notifications(self, limit: int = 40, cursor: str = None, max_id: str = None, **kwargs) -> List[UniversalNotification]:
        """Get notifications."""
        try:
            from atproto import models

            # For "load previous", use the stored cursor
            if max_id and not cursor:
                cursor = self._get_cursor('notifications')

            params = models.AppBskyNotificationListNotifications.Params(
                limit=min(limit, 100),
                cursor=cursor
            )
            response = self.client.app.bsky.notification.list_notifications(params)

            # Store cursor for next pagination request
            self._store_cursor('notifications', getattr(response, 'cursor', None))

            # Collect URIs for like/repost notifications that need post data
            uris_to_fetch = []
            notif_uri_map = {}  # Map from reasonSubject URI to notification indices
            raw_notifs = list(response.notifications)

            for i, notif in enumerate(raw_notifs):
                reason = getattr(notif, 'reason', '')
                if reason in ('like', 'repost'):
                    reason_subject = getattr(notif, 'reason_subject', None) or getattr(notif, 'reasonSubject', None)
                    if reason_subject:
                        uris_to_fetch.append(reason_subject)
                        if reason_subject not in notif_uri_map:
                            notif_uri_map[reason_subject] = []
                        notif_uri_map[reason_subject].append(i)

            # Batch fetch posts for like/repost notifications (max 25 per request)
            fetched_posts = {}
            for batch_start in range(0, len(uris_to_fetch), 25):
                batch_uris = list(set(uris_to_fetch[batch_start:batch_start + 25]))
                if batch_uris:
                    try:
                        posts_response = self.client.get_posts(batch_uris)
                        for post in posts_response.posts:
                            post_uri = getattr(post, 'uri', '')
                            if post_uri:
                                fetched_posts[post_uri] = bluesky_post_to_universal(post)
                    except Exception:
                        pass  # Continue even if batch fetch fails

            # Check if mentions should be included in notifications
            include_mentions = False
            if self._prefs:
                include_mentions = getattr(self._prefs, 'mentions_in_notifications', False)

            notifications = []

            for i, notif in enumerate(raw_notifs):
                universal_notif = bluesky_notification_to_universal(notif)
                if universal_notif:
                    # Filter out mentions if setting is disabled
                    if not include_mentions and universal_notif.type == 'mention':
                        continue

                    # For like/repost notifications, attach the fetched post
                    reason = getattr(notif, 'reason', '')
                    if reason in ('like', 'repost') and universal_notif.status is None:
                        reason_subject = getattr(notif, 'reason_subject', None) or getattr(notif, 'reasonSubject', None)
                        if reason_subject and reason_subject in fetched_posts:
                            universal_notif.status = fetched_posts[reason_subject]

                    notifications.append(universal_notif)
                    self.user_cache.add_users_from_notification(universal_notif)

            return notifications
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "notifications")
            return []

    def get_conversations(self, limit: int = 40, **kwargs) -> List[Any]:
        """Get direct message conversations - NOT SUPPORTED on Bluesky."""
        return []

    def get_favourites(self, limit: int = 40, cursor: str = None, max_id: str = None, **kwargs) -> List[UniversalStatus]:
        """Get liked posts."""
        try:
            from atproto import models

            # For "load previous", use the stored cursor
            if max_id and not cursor:
                cursor = self._get_cursor('favourites')

            params = models.AppBskyFeedGetActorLikes.Params(
                actor=self._me.id,
                limit=min(limit, 100),
                cursor=cursor
            )
            response = self.client.app.bsky.feed.get_actor_likes(params)

            # Store cursor for next pagination request
            self._store_cursor('favourites', getattr(response, 'cursor', None))

            return self._convert_feed_posts(response.feed)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "favourites")
            return []

    def get_user_statuses(self, user_id: str, limit: int = 40, cursor: str = None, max_id: str = None, filter: str = None, include_pins: bool = True, **kwargs) -> List[UniversalStatus]:
        """Get statuses from a specific user.

        Args:
            user_id: The user's DID or handle
            limit: Maximum number of posts to return (max 100)
            cursor: Pagination cursor
            max_id: Signal to load previous (uses stored cursor)
            filter: Filter type - 'posts_with_replies' (default), 'posts_no_replies',
                   'posts_with_media', 'posts_and_author_threads', 'posts_with_video'
            include_pins: Whether to include pinned posts (default True)
        """
        try:
            # For "load previous", use the stored cursor (keyed by user_id)
            cursor_key = f'user_{user_id}'
            if max_id and not cursor:
                cursor = self._get_cursor(cursor_key)

            params = {
                'actor': user_id,
                'limit': min(limit, 100),
            }
            if cursor:
                params['cursor'] = cursor
            if filter:
                params['filter'] = filter

            # Try with include_pins first, fall back without if it fails
            # (older SDK versions may not support this parameter)
            if include_pins and not cursor:
                try:
                    params['include_pins'] = True
                    response = self.client.get_author_feed(**params)
                except Exception:
                    # Fall back without include_pins
                    del params['include_pins']
                    response = self.client.get_author_feed(**params)
            else:
                response = self.client.get_author_feed(**params)

            # Store cursor for next pagination request
            self._store_cursor(cursor_key, getattr(response, 'cursor', None))

            return self._convert_feed_posts(response.feed)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "user statuses")
            return []

    def get_list_timeline(self, list_id: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get statuses from a list - NOT SUPPORTED on Bluesky."""
        return []

    def get_feed_timeline(self, feed_uri: str, limit: int = 40, cursor: str = None, max_id: str = None, **kwargs) -> List[UniversalStatus]:
        """Get posts from a custom feed."""
        try:
            from atproto import models

            # For "load previous", use the stored cursor (keyed by feed)
            cursor_key = f'feed_{feed_uri}'
            if max_id and not cursor:
                cursor = self._get_cursor(cursor_key)

            params = models.AppBskyFeedGetFeed.Params(
                feed=feed_uri,
                limit=min(limit, 100),
                cursor=cursor
            )
            response = self.client.app.bsky.feed.get_feed(params)

            # Store cursor for next pagination request
            self._store_cursor(cursor_key, getattr(response, 'cursor', None))

            return self._convert_feed_posts(response.feed)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "feed")
            return []

    def get_saved_feeds(self) -> List[dict]:
        """Get user's saved/pinned feeds."""
        try:
            from atproto import models

            # Try to get preferences - may fail due to unknown preference types
            try:
                response = self.client.app.bsky.actor.get_preferences()
                preferences = response.preferences
            except Exception:
                # If preferences fail, fall back to searching popular feeds
                return self.search_feeds("")

            feeds = []
            for pref in preferences:
                # Check for savedFeedsPref or savedFeedsPrefV2
                pref_type = getattr(pref, 'py_type', '') or getattr(pref, '$type', '')
                if 'savedFeedsPref' in str(pref_type) or hasattr(pref, 'saved') or hasattr(pref, 'items'):
                    # savedFeedsPrefV2 uses 'items', savedFeedsPref uses 'saved'/'pinned'
                    saved = getattr(pref, 'saved', None) or []
                    pinned = getattr(pref, 'pinned', None) or []
                    items = getattr(pref, 'items', None) or []

                    # V2 format has items with 'value' (feed URI) and 'type'
                    feed_uris = []
                    if items:
                        for item in items:
                            if hasattr(item, 'value'):
                                feed_uris.append(item.value)
                            elif isinstance(item, dict) and 'value' in item:
                                feed_uris.append(item['value'])
                    else:
                        feed_uris = list(set(saved + pinned))

                    if feed_uris:
                        try:
                            feed_params = models.AppBskyFeedGetFeedGenerators.Params(feeds=feed_uris[:25])
                            feed_response = self.client.app.bsky.feed.get_feed_generators(feed_params)
                            for feed in feed_response.feeds:
                                feeds.append({
                                    'id': feed.uri,
                                    'name': feed.display_name,
                                    'description': getattr(feed, 'description', ''),
                                    'creator': getattr(feed.creator, 'handle', '') if hasattr(feed, 'creator') else ''
                                })
                        except:
                            pass

            # If no feeds found from preferences, return popular feeds
            if not feeds:
                return self.search_feeds("")

            return feeds
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "get saved feeds")
            return []
        except Exception as e:
            # Handle Pydantic validation errors and other issues
            # Fall back to popular feeds
            return self.search_feeds("")

    def search_feeds(self, query: str, limit: int = 25) -> List[dict]:
        """Search for feeds."""
        try:
            from atproto import models
            # Use popular feeds endpoint or search
            params = models.AppBskyUnspeccedGetPopularFeedGenerators.Params(
                limit=min(limit, 100),
                query=query if query else None
            )
            response = self.client.app.bsky.unspecced.get_popular_feed_generators(params)

            feeds = []
            for feed in response.feeds:
                feeds.append({
                    'id': feed.uri,
                    'name': feed.display_name,
                    'description': getattr(feed, 'description', ''),
                    'creator': getattr(feed.creator, 'handle', '') if hasattr(feed, 'creator') else ''
                })
            return feeds
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "search feeds")
            return []

    def search_statuses(self, query: str, limit: int = 40, cursor: str = None, max_id: str = None, **kwargs) -> List[UniversalStatus]:
        """Search for statuses."""
        try:
            from atproto import models

            # For "load previous", use the stored cursor (keyed by query)
            cursor_key = f'search_{query}'
            if max_id and not cursor:
                cursor = self._get_cursor(cursor_key)

            params = models.AppBskyFeedSearchPosts.Params(
                q=query,
                limit=min(limit, 100),
                cursor=cursor
            )
            response = self.client.app.bsky.feed.search_posts(params)

            # Store cursor for next pagination request
            self._store_cursor(cursor_key, getattr(response, 'cursor', None))

            return self._convert_posts(response.posts)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "search")
            return []

    def get_status(self, status_id: str) -> Optional[UniversalStatus]:
        """Get a single status by URI."""
        try:
            response = self.client.get_posts([status_id])
            if response.posts:
                return bluesky_post_to_universal(response.posts[0])
            return None
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "get status")
            return None

    def get_status_context(self, status_id: str) -> Dict[str, List[UniversalStatus]]:
        """Get thread context (replies and ancestors)."""
        try:
            response = self.client.get_post_thread(uri=status_id)

            ancestors = []
            descendants = []

            # Parse thread structure
            thread = response.thread

            # Get parent chain (ancestors)
            parent = getattr(thread, 'parent', None)
            while parent:
                post = getattr(parent, 'post', None)
                if post:
                    status = bluesky_post_to_universal(post)
                    if status:
                        ancestors.insert(0, status)
                parent = getattr(parent, 'parent', None)

            # Get replies (descendants) - recursively to get nested replies
            def collect_replies(thread_node, depth=0):
                """Recursively collect all replies from a thread node."""
                result = []
                replies = getattr(thread_node, 'replies', []) or []
                for reply in replies:
                    post = getattr(reply, 'post', None)
                    if post:
                        status = bluesky_post_to_universal(post)
                        if status:
                            result.append(status)
                            # Recursively get nested replies
                            result.extend(collect_replies(reply, depth + 1))
                return result

            descendants = collect_replies(thread)

            return {'ancestors': ancestors, 'descendants': descendants}
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "thread context")
            return {'ancestors': [], 'descendants': []}

    # ============ Action Methods ============

    def post(self, text: str, reply_to_id: Optional[str] = None,
             visibility: Optional[str] = None, spoiler_text: Optional[str] = None,
             **kwargs) -> UniversalStatus:
        """Create a new post."""
        try:
            post_kwargs = {'text': text}

            # Handle reply
            if reply_to_id:
                # Need to build reply reference with root and parent
                reply_ref = self._build_reply_ref(reply_to_id)
                if reply_ref:
                    post_kwargs['reply_to'] = reply_ref

            # Handle labels (content warning equivalent)
            labels = kwargs.get('labels', [])
            if labels:
                post_kwargs['labels'] = labels

            # Handle language parameter
            # Note: Bluesky's AT Protocol supports langs parameter in send_post
            language = kwargs.get('language', None)
            if language:
                post_kwargs['langs'] = [language]

            response = self.client.send_post(**post_kwargs)

            # Fetch the created post to return full data
            if hasattr(response, 'uri'):
                result = self.get_status(response.uri)
                if result:
                    return result
                # If get_status failed but we got a response, create a minimal status
                # This can happen due to indexing delay on Bluesky
                # We need at least an 'id' for timeline deduplication
                # Parse mentions from the text for reply functionality
                mentions = []
                import re
                for match in re.finditer(r'@([\w.-]+(?:\.[\w.-]+)*)', text):
                    handle = match.group(1)
                    mentions.append(UniversalMention(
                        id=handle,  # We don't have the DID, use handle
                        acct=handle,
                        username=handle.split('.')[0] if '.' in handle else handle,
                    ))
                minimal_status = UniversalStatus(
                    id=response.uri,
                    content=text,
                    text=text,
                    created_at=datetime.now(timezone.utc),
                    account=UniversalUser(
                        id=str(self.me.did),
                        username=self.me.handle,
                        display_name=getattr(self.me, 'display_name', '') or self.me.handle,
                        acct=self.me.handle,
                    ),
                    visibility='public',
                    url=response.uri,
                    mentions=mentions,
                    _platform='bluesky',
                )
                return minimal_status
            # If no uri in response, still return response as success indicator
            return response if response else False
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "post")
            raise  # Re-raise so caller can handle it
        except Exception as e:
            self.app.handle_error(e, "post")
            raise  # Re-raise so caller can handle it

    def _build_reply_ref(self, reply_to_uri: str):
        """Build a reply reference for threading."""
        try:
            # Get the parent post to find the thread root
            parent_thread = self.client.get_post_thread(uri=reply_to_uri)
            parent_post = getattr(parent_thread.thread, 'post', None)

            if not parent_post:
                return None

            parent_uri = getattr(parent_post, 'uri', '')
            parent_cid = getattr(parent_post, 'cid', '')

            # Find the thread root
            root_uri = parent_uri
            root_cid = parent_cid

            parent_ref = getattr(parent_thread.thread, 'parent', None)
            while parent_ref:
                root_post = getattr(parent_ref, 'post', None)
                if root_post:
                    root_uri = getattr(root_post, 'uri', root_uri)
                    root_cid = getattr(root_post, 'cid', root_cid)
                parent_ref = getattr(parent_ref, 'parent', None)

            from atproto import models
            return models.AppBskyFeedPost.ReplyRef(
                root=models.ComAtprotoRepoStrongRef.Main(uri=root_uri, cid=root_cid),
                parent=models.ComAtprotoRepoStrongRef.Main(uri=parent_uri, cid=parent_cid),
            )
        except Exception as e:
            print(f"Error building reply ref: {e}")
            return None

    def quote(self, status, text: str, visibility: Optional[str] = None, language: Optional[str] = None, **kwargs) -> UniversalStatus:
        """Quote a post."""
        try:
            status_uri = status.id if hasattr(status, 'id') else status
            status_cid = getattr(status, 'cid', None)

            # If we don't have the CID, fetch the post
            if not status_cid:
                post_response = self.client.get_posts([status_uri])
                if post_response.posts:
                    status_cid = getattr(post_response.posts[0], 'cid', '')

            from atproto import models
            embed = models.AppBskyEmbedRecord.Main(
                record=models.ComAtprotoRepoStrongRef.Main(uri=status_uri, cid=status_cid)
            )

            # Bluesky uses 'langs' as a list
            langs = [language] if language else None
            response = self.client.send_post(text=text, embed=embed, langs=langs)
            if hasattr(response, 'uri'):
                return self.get_status(response.uri)
            return None
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "quote")
            return None

    def boost(self, status_id: str) -> bool:
        """Repost a status."""
        try:
            # Get the CID for the post
            post_response = self.client.get_posts([status_id])
            if post_response.posts:
                cid = getattr(post_response.posts[0], 'cid', '')
                self.client.repost(uri=status_id, cid=cid)
                return True
            return False
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "repost")
            return False

    def unboost(self, status_id: str) -> bool:
        """Delete a repost."""
        try:
            # Need to find our repost record to delete it
            # This requires knowing the repost URI
            self.client.unrepost(status_id)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "unrepost")
            return False

    def favourite(self, status_id: str) -> bool:
        """Like a status."""
        try:
            post_response = self.client.get_posts([status_id])
            if post_response.posts:
                cid = getattr(post_response.posts[0], 'cid', '')
                self.client.like(uri=status_id, cid=cid)
                return True
            return False
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "like")
            return False

    def unfavourite(self, status_id: str) -> bool:
        """Unlike a status."""
        try:
            self.client.unlike(status_id)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "unlike")
            return False

    def delete_status(self, status_id: str) -> bool:
        """Delete a post."""
        try:
            self.client.delete_post(status_id)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "delete")
            return False

    def pin_status(self, status_id: str) -> bool:
        """Pin a status to your profile by updating the profile record."""
        try:
            from atproto import models

            # Get the post to get its CID
            post_response = self.client.get_posts([status_id])
            if not post_response.posts:
                return False

            post = post_response.posts[0]
            post_cid = getattr(post, 'cid', '')

            if not post_cid:
                return False

            # Get user DID
            user_did = getattr(self.client.me, 'did', None)
            if not user_did:
                return False

            # Try to get current profile record, handle if it doesn't exist
            current_value = None
            try:
                params = models.ComAtprotoRepoGetRecord.Params(
                    repo=user_did,
                    collection='app.bsky.actor.profile',
                    rkey='self'
                )
                profile_response = self.client.com.atproto.repo.get_record(params)
                current_value = profile_response.value if profile_response else None
            except Exception:
                # Profile record doesn't exist yet, will create new one
                current_value = None

            # Build updated profile record preserving existing data
            updated_profile = {
                '$type': 'app.bsky.actor.profile',
                'pinnedPost': {
                    'uri': status_id,
                    'cid': post_cid
                }
            }

            if current_value:
                # Preserve existing profile data
                display_name = getattr(current_value, 'display_name', None) or getattr(current_value, 'displayName', None)
                if display_name:
                    updated_profile['displayName'] = display_name
                description = getattr(current_value, 'description', None)
                if description:
                    updated_profile['description'] = description
                avatar = getattr(current_value, 'avatar', None)
                if avatar:
                    updated_profile['avatar'] = avatar
                banner = getattr(current_value, 'banner', None)
                if banner:
                    updated_profile['banner'] = banner

            # Put the updated profile
            data = models.ComAtprotoRepoPutRecord.Data(
                repo=user_did,
                collection='app.bsky.actor.profile',
                rkey='self',
                record=updated_profile
            )
            self.client.com.atproto.repo.put_record(data)

            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "pin post")
            return False
        except Exception as e:
            self.app.handle_error(e, "pin post")
            return False

    def unpin_status(self, status_id: str) -> bool:
        """Unpin a status from your profile by updating the profile record."""
        try:
            from atproto import models

            # Get user DID
            user_did = getattr(self.client.me, 'did', None)
            if not user_did:
                return False

            # Try to get current profile record
            current_value = None
            try:
                params = models.ComAtprotoRepoGetRecord.Params(
                    repo=user_did,
                    collection='app.bsky.actor.profile',
                    rkey='self'
                )
                profile_response = self.client.com.atproto.repo.get_record(params)
                current_value = profile_response.value if profile_response else None
            except Exception:
                # No profile record, nothing to unpin
                return True

            if not current_value:
                return True  # Nothing to unpin

            # Build updated profile record without pinnedPost
            updated_profile = {
                '$type': 'app.bsky.actor.profile'
            }

            # Preserve existing profile data (but not pinnedPost)
            display_name = getattr(current_value, 'display_name', None) or getattr(current_value, 'displayName', None)
            if display_name:
                updated_profile['displayName'] = display_name
            description = getattr(current_value, 'description', None)
            if description:
                updated_profile['description'] = description
            avatar = getattr(current_value, 'avatar', None)
            if avatar:
                updated_profile['avatar'] = avatar
            banner = getattr(current_value, 'banner', None)
            if banner:
                updated_profile['banner'] = banner

            # Put the updated profile without pinnedPost
            data = models.ComAtprotoRepoPutRecord.Data(
                repo=user_did,
                collection='app.bsky.actor.profile',
                rkey='self',
                record=updated_profile
            )
            self.client.com.atproto.repo.put_record(data)

            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "unpin post")
            return False
        except Exception as e:
            self.app.handle_error(e, "unpin post")
            return False

    # ============ User Methods ============

    def get_user(self, user_id: str) -> Optional[UniversalUser]:
        """Get user by DID or handle."""
        try:
            profile = self.client.get_profile(actor=user_id)
            user = bluesky_profile_to_universal(profile)
            if user:
                self.user_cache.add_user(user)
            return user
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "get user")
            return None

    def search_users(self, query: str, limit: int = 10) -> List[UniversalUser]:
        """Search for users."""
        try:
            from atproto import models
            params = models.AppBskyActorSearchActors.Params(
                q=query,
                limit=min(limit, 100)
            )
            response = self.client.app.bsky.actor.search_actors(params)
            return self._convert_profiles(response.actors)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "search users")
            return []

    def lookup_user_by_name(self, name: str) -> Optional[UniversalUser]:
        """Look up user by handle."""
        return self.get_user(name)

    def follow(self, user_id: str) -> bool:
        """Follow a user."""
        try:
            self.client.follow(user_id)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "follow")
            return False

    def unfollow(self, user_id: str) -> bool:
        """Unfollow a user.

        The atproto library's unfollow() expects a follow_uri, not a DID.
        We need to fetch the user's profile to get the follow record URI.
        """
        try:
            # Get the user's profile which includes viewer relationship info
            profile = self.client.get_profile(user_id)
            if not profile:
                self.app.handle_error(Exception("Could not fetch user profile"), "unfollow")
                return False

            # Get the follow URI from viewer.following
            viewer = getattr(profile, 'viewer', None)
            if not viewer:
                self.app.handle_error(Exception("No viewer info - may not be following"), "unfollow")
                return False

            follow_uri = getattr(viewer, 'following', None)
            if not follow_uri:
                self.app.handle_error(Exception("Not following this user"), "unfollow")
                return False

            # Now unfollow using the follow record URI
            self.client.unfollow(follow_uri)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "unfollow")
            return False

    def block(self, user_id: str) -> bool:
        """Block a user."""
        try:
            self.client.app.bsky.graph.block.create(self._me.id, {'subject': user_id})
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "block")
            return False

    def unblock(self, user_id: str) -> bool:
        """Unblock a user.

        Similar to unfollow, we need to get the block record URI from the profile's viewer info.
        """
        try:
            # Get the user's profile which includes viewer relationship info
            profile = self.client.get_profile(user_id)
            if not profile:
                self.app.handle_error(Exception("Could not fetch user profile"), "unblock")
                return False

            # Get the block URI from viewer.blocking
            viewer = getattr(profile, 'viewer', None)
            if not viewer:
                self.app.handle_error(Exception("No viewer info"), "unblock")
                return False

            block_uri = getattr(viewer, 'blocking', None)
            if not block_uri:
                self.app.handle_error(Exception("Not blocking this user"), "unblock")
                return False

            # Delete the block record using the URI's rkey
            rkey = extract_rkey_from_uri(block_uri)
            self.client.app.bsky.graph.block.delete(self._me.id, rkey)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "unblock")
            return False

    def mute(self, user_id: str) -> bool:
        """Mute a user."""
        try:
            self.client.mute(user_id)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "mute")
            return False

    def unmute(self, user_id: str) -> bool:
        """Unmute a user."""
        try:
            self.client.unmute(user_id)
            return True
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "unmute")
            return False

    def report(self, user_id: str, status_id: str = None, category: str = "other", comment: str = "") -> bool:
        """Report a user or post to moderation.

        Args:
            user_id: The DID of the user being reported
            status_id: Optional post URI to report (if reporting a specific post)
            category: Report category (spam, violation, other)
            comment: Additional context for the report
        """
        try:
            from atproto import models

            # Map category to Bluesky reason type
            reason_map = {
                'spam': 'com.atproto.moderation.defs#reasonSpam',
                'violation': 'com.atproto.moderation.defs#reasonViolation',
                'other': 'com.atproto.moderation.defs#reasonOther',
            }
            reason_type = reason_map.get(category, 'com.atproto.moderation.defs#reasonOther')

            # Build the subject - either a repo (user) or a record (post)
            if status_id:
                # Reporting a specific post
                # Parse the AT URI to get repo, collection, rkey
                # Format: at://did:plc:xxx/app.bsky.feed.post/rkey
                parts = status_id.replace('at://', '').split('/')
                if len(parts) >= 3:
                    repo = parts[0]
                    collection = parts[1]
                    rkey = parts[2]
                    subject = models.ComAtprotoAdminDefs.RepoRef(did=repo)
                    # Use strong ref for record
                    subject = {
                        '$type': 'com.atproto.repo.strongRef',
                        'uri': status_id,
                        'cid': ''  # CID not required for reports
                    }
                else:
                    # Fallback to user report
                    subject = {'$type': 'com.atproto.admin.defs#repoRef', 'did': user_id}
            else:
                # Reporting a user account
                subject = {'$type': 'com.atproto.admin.defs#repoRef', 'did': user_id}

            # Create the report
            data = {
                'reasonType': reason_type,
                'subject': subject,
            }
            if comment:
                data['reason'] = comment

            self.client.com.atproto.moderation.create_report(data)
            return True

        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "report")
            return False

    def get_followers(self, user_id: str, limit: int = 80, max_pages: int = 1) -> List[UniversalUser]:
        """Get followers of a user.

        Args:
            user_id: The user ID/DID to get followers for
            limit: Maximum users per page (default 80, max 100)
            max_pages: Maximum number of API calls/pages to fetch (default 1)
        """
        try:
            all_users = []
            cursor = None
            page_count = 0

            while page_count < max_pages:
                params = {'actor': user_id, 'limit': min(limit, 100)}
                if cursor:
                    params['cursor'] = cursor

                response = self.client.get_followers(**params)
                users = self._convert_profiles(response.followers)
                all_users.extend(users)
                page_count += 1

                cursor = getattr(response, 'cursor', None)
                if not cursor:
                    break

            return all_users
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "followers")
            return []

    def get_following(self, user_id: str, limit: int = 80, max_pages: int = 1) -> List[UniversalUser]:
        """Get users that a user is following.

        Args:
            user_id: The user ID/DID to get following for
            limit: Maximum users per page (default 80, max 100)
            max_pages: Maximum number of API calls/pages to fetch (default 1)
        """
        try:
            all_users = []
            cursor = None
            page_count = 0

            while page_count < max_pages:
                params = {'actor': user_id, 'limit': min(limit, 100)}
                if cursor:
                    params['cursor'] = cursor

                response = self.client.get_follows(**params)
                users = self._convert_profiles(response.follows)
                all_users.extend(users)
                page_count += 1

                cursor = getattr(response, 'cursor', None)
                if not cursor:
                    break

            return all_users
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "following")
            return []

    # ============ Explore/Discovery Methods ============

    def get_suggested_users(self, limit: int = 50) -> List[UniversalUser]:
        """Get suggested users to follow."""
        try:
            from atproto import models
            params = models.AppBskyActorGetSuggestions.Params(limit=min(limit, 100))
            response = self.client.app.bsky.actor.get_suggestions(params)
            actors = getattr(response, 'actors', [])
            return self._convert_profiles(actors)
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "suggested users")
            return []

    def get_suggested_feeds(self, limit: int = 50) -> List[dict]:
        """Get suggested feeds.

        Returns list of dicts with 'uri', 'name', 'description', 'creator' keys.
        """
        try:
            from atproto import models
            params = models.AppBskyFeedGetSuggestedFeeds.Params(limit=min(limit, 100))
            response = self.client.app.bsky.feed.get_suggested_feeds(params)
            feeds = []
            for feed in getattr(response, 'feeds', []):
                feeds.append({
                    'uri': getattr(feed, 'uri', ''),
                    'name': getattr(feed, 'display_name', ''),
                    'description': getattr(feed, 'description', ''),
                    'creator': getattr(feed.creator, 'handle', '') if hasattr(feed, 'creator') else '',
                    'likes': getattr(feed, 'like_count', 0)
                })
            return feeds
        except (AtProtocolError, InvokeTimeoutError) as e:
            self.app.handle_error(e, "suggested feeds")
            return []

    def get_popular_feeds(self, limit: int = 50, query: str = None) -> List[dict]:
        """Get popular feeds (wrapper for search_feeds)."""
        return self.search_feeds(query or '', limit=limit)

    # ============ Cleanup Methods ============

    def close(self):
        """Clean up resources when account is removed."""
        if self.timeline_cache:
            self.timeline_cache.close()
            self.timeline_cache = None
