"""Mastodon platform account implementation."""

from typing import List, Optional, Any, Dict
from mastodon import Mastodon, MastodonError

from platforms.base import PlatformAccount
from models import UniversalStatus, UniversalUser, UniversalNotification, UserCache
from cache import TimelineCache
from .models import (
    mastodon_status_to_universal,
    mastodon_user_to_universal,
    mastodon_notification_to_universal,
)


class MastodonAccount(PlatformAccount):
    """Mastodon-specific account implementation."""

    platform_name = "mastodon"

    # Feature flags
    supports_visibility = True
    supports_content_warning = True
    supports_quote_posts = True  # Mastodon 4.0+
    supports_polls = True
    supports_lists = True
    supports_direct_messages = True
    supports_media_attachments = True
    supports_scheduling = True
    supports_editing = True

    def __init__(self, app, index: int, api: Mastodon, me, confpath: str, max_chars: int = 500, prefs=None):
        super().__init__(app, index)
        self.api = api
        self._me = mastodon_user_to_universal(me)
        self.confpath = confpath
        self._max_chars = max_chars
        self._prefs = prefs  # Store reference to account wrapper's prefs

        # Initialize user cache (in-memory only, no disk persistence)
        self.user_cache = UserCache(confpath, 'mastodon', str(self._me.id))

        # Initialize timeline cache for fast startup
        if app.prefs.timeline_cache_enabled:
            self.timeline_cache = TimelineCache(confpath, str(self._me.id))
        else:
            self.timeline_cache = None

        # Get default visibility
        try:
            self.default_visibility = getattr(me, 'source', {}).get('privacy', 'public')
        except:
            self.default_visibility = 'public'

    @property
    def me(self) -> UniversalUser:
        return self._me

    def _convert_statuses(self, statuses) -> List[UniversalStatus]:
        """Convert a list of Mastodon statuses to universal statuses."""
        return [mastodon_status_to_universal(s) for s in statuses if s]

    def _convert_users(self, users) -> List[UniversalUser]:
        """Convert a list of Mastodon users to universal users."""
        return [mastodon_user_to_universal(u) for u in users if u]

    # ============ Timeline Methods ============

    def get_home_timeline(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get home timeline statuses."""
        statuses = self.api.timeline_home(limit=limit, **kwargs)
        result = self._convert_statuses(statuses)
        # Cache users
        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    # ============ Timeline Marker Methods ============

    def get_timeline_marker(self, timeline: str = 'home') -> Optional[str]:
        """Get the last read position marker for a timeline.

        Args:
            timeline: The timeline to get marker for ('home' or 'notifications')

        Returns:
            The last read status/notification ID, or None if no marker set
        """
        try:
            markers = self.api.markers_get(timeline=[timeline])
            if markers and timeline in markers:
                marker = markers[timeline]
                return getattr(marker, 'last_read_id', None)
        except MastodonError:
            pass
        return None

    def set_timeline_marker(self, timeline: str, last_read_id: str) -> bool:
        """Set the last read position marker for a timeline.

        Args:
            timeline: The timeline to set marker for ('home' or 'notifications')
            last_read_id: The ID of the last read status/notification

        Returns:
            True if successful, False otherwise
        """
        try:
            # markers_set takes (timelines, last_read_ids) as positional args
            self.api.markers_set(timeline, last_read_id)
            return True
        except MastodonError:
            return False

    def get_mentions(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get mentions as statuses (extracted from notifications).

        This is the key method that fixes the mentions buffer - it returns
        actual status objects instead of notification objects.
        """
        notifications = self.api.notifications(mentions_only=True, limit=limit, **kwargs)
        statuses = []

        for notif in notifications:
            if hasattr(notif, 'status') and notif.status:
                status = mastodon_status_to_universal(notif.status)
                if status:
                    # Store notification ID for deduplication
                    status._notification_id = str(notif.id)
                    # Store original status ID for replies/interactions
                    status._original_status_id = str(status.id)
                    # Use notification ID as the status ID for this timeline
                    # This ensures proper pagination with since_id/max_id
                    status.id = str(notif.id)
                    statuses.append(status)
                    self.user_cache.add_users_from_status(status)

        return statuses

    def get_notifications(self, limit: int = 40, **kwargs) -> List[UniversalNotification]:
        """Get notifications (optionally excludes mentions based on account setting)."""
        # Check if mentions should be included in notifications
        include_mentions = False
        if self._prefs:
            include_mentions = getattr(self._prefs, 'mentions_in_notifications', False)

        if include_mentions:
            notifications = self.api.notifications(limit=limit, **kwargs)
        else:
            # Exclude mentions - they're shown in the mentions timeline instead
            notifications = self.api.notifications(limit=limit, exclude_types=['mention'], **kwargs)
        result = [mastodon_notification_to_universal(n) for n in notifications if n]
        # Cache users
        for notif in result:
            self.user_cache.add_users_from_notification(notif)
        return result

    def get_conversations(self, limit: int = 40, **kwargs) -> List[Any]:
        """Get direct message conversations."""
        # Return raw conversations - these have special structure
        return self.api.conversations(limit=limit, **kwargs)

    def get_favourites(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get favourited statuses."""
        statuses = self.api.favourites(limit=limit, **kwargs)
        result = self._convert_statuses(statuses)
        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    def get_bookmarks(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get bookmarked statuses."""
        statuses = self.api.bookmarks(limit=limit, **kwargs)
        result = self._convert_statuses(statuses)
        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    def get_pinned_statuses(self, **kwargs) -> List[UniversalStatus]:
        """Get user's own pinned statuses."""
        try:
            statuses = self.api.account_statuses(id=self.me.id, pinned=True)
            result = self._convert_statuses(statuses)
            for status in result:
                status._pinned = True
                self.user_cache.add_users_from_status(status)
            return result
        except MastodonError:
            return []

    def get_scheduled_statuses(self, **kwargs) -> List[UniversalStatus]:
        """Get user's scheduled statuses."""
        try:
            statuses = self.api.scheduled_statuses()
            # Scheduled statuses have a different format
            result = []
            for s in statuses:
                # Convert scheduled status to a pseudo-status for display
                status = mastodon_status_to_universal(s.params)
                if status:
                    status._scheduled = True
                    status._scheduled_id = s.id
                    status._scheduled_at = s.scheduled_at
                    # Preserve the text from params (params has 'text', not 'content')
                    params_text = getattr(s.params, 'text', None) or s.params.get('text', '') if hasattr(s.params, 'get') else ''
                    if params_text and not status.content:
                        status.content = params_text
                    result.append(status)
            return result
        except MastodonError:
            return []

    def get_user_statuses(self, user_id: str, limit: int = 40, filter: str = None, include_pins: bool = True, **kwargs) -> List[UniversalStatus]:
        """Get statuses from a specific user.

        Args:
            user_id: The user's ID
            limit: Maximum number of posts to return
            filter: Filter type - 'posts_with_replies' (default), 'posts_no_replies',
                   'posts_with_media', 'posts_no_boosts'
            include_pins: Whether to include pinned posts at the top (default True)
        """
        # Map filter to Mastodon API parameters
        api_kwargs = dict(kwargs)
        if filter == 'posts_no_replies':
            api_kwargs['exclude_replies'] = True
        elif filter == 'posts_with_media':
            api_kwargs['only_media'] = True
        elif filter == 'posts_no_boosts':
            api_kwargs['exclude_reblogs'] = True
        # 'posts_with_replies' is the default (no filtering)

        result = []

        # First fetch pinned posts if requested and this is the initial load (no max_id/since_id)
        if include_pins and 'max_id' not in kwargs and 'since_id' not in kwargs:
            try:
                pinned_statuses = self.api.account_statuses(id=user_id, pinned=True, limit=20)
                pinned_result = self._convert_statuses(pinned_statuses)
                # Mark pinned posts (could be useful for display)
                for status in pinned_result:
                    status._pinned = True
                result.extend(pinned_result)
            except:
                pass  # Pinned posts may not be available for remote users

        # Then fetch regular posts
        statuses = self.api.account_statuses(id=user_id, limit=limit, **api_kwargs)
        regular_result = self._convert_statuses(statuses)

        # Remove duplicates (pinned posts may also appear in regular timeline)
        if result:
            pinned_ids = {s.id for s in result}
            regular_result = [s for s in regular_result if s.id not in pinned_ids]

        result.extend(regular_result)

        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    def get_list_timeline(self, list_id: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get statuses from a list."""
        statuses = self.api.timeline_list(id=list_id, limit=limit, **kwargs)
        result = self._convert_statuses(statuses)
        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    def get_local_timeline(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get local timeline (posts from users on this instance)."""
        statuses = self.api.timeline_local(limit=limit, **kwargs)
        result = self._convert_statuses(statuses)
        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    def get_public_timeline(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get federated/public timeline (posts from all known instances)."""
        statuses = self.api.timeline_public(limit=limit, **kwargs)
        result = self._convert_statuses(statuses)
        for status in result:
            self.user_cache.add_users_from_status(status)
        return result

    def get_available_timelines(self) -> List[dict]:
        """Get available custom timelines for this platform."""
        return [
            {'type': 'favourites', 'id': 'favourites', 'name': 'Favourites', 'description': 'Posts you have favourited'},
            {'type': 'bookmarks', 'id': 'bookmarks', 'name': 'Bookmarks', 'description': 'Posts you have bookmarked'},
            {'type': 'local', 'id': 'local', 'name': 'Local Timeline', 'description': 'Posts from users on this instance'},
            {'type': 'federated', 'id': 'federated', 'name': 'Federated Timeline', 'description': 'Posts from all known instances'},
            {'type': 'instance', 'id': 'instance', 'name': 'Instance Timeline', 'description': 'Local timeline from another instance'},
            {'type': 'remote_user', 'id': 'remote_user', 'name': 'Remote User Timeline', 'description': 'User timeline from another instance'},
        ]

    # ============ Instance Timeline Methods ============

    def get_or_create_remote_api(self, instance_url: str) -> Mastodon:
        """Get or create an unauthenticated API client for a remote instance.

        Args:
            instance_url: The URL of the remote instance (e.g., 'mastodon.social')

        Returns:
            An unauthenticated Mastodon API client for the instance
        """
        # Normalize URL
        if not instance_url.startswith('http'):
            instance_url = 'https://' + instance_url
        instance_url = instance_url.rstrip('/')

        # Get the account wrapper to access remote_apis
        account = self.app.currentAccount

        # Check if we already have this API
        if instance_url in account.remote_apis:
            return account.remote_apis[instance_url]

        # Create new unauthenticated client
        remote_api = Mastodon(api_base_url=instance_url)
        account.remote_apis[instance_url] = remote_api
        return remote_api

    def get_instance_timeline(self, instance_url: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Fetch local timeline from a remote instance.

        Args:
            instance_url: The URL of the remote instance
            limit: Maximum number of statuses to fetch
            **kwargs: Additional parameters (max_id, since_id, etc.)

        Returns:
            List of statuses from the remote instance's local timeline
        """
        try:
            remote_api = self.get_or_create_remote_api(instance_url)
            statuses = remote_api.timeline_local(limit=limit, **kwargs)
            result = self._convert_statuses(statuses)

            # Extract domain from instance URL for user accts
            from urllib.parse import urlparse
            parsed = urlparse(instance_url)
            instance_domain = parsed.netloc or parsed.path.strip('/')

            def fix_user_acct(user):
                """Add instance domain to user acct if not present."""
                if user and '@' not in user.acct:
                    user.acct = f"{user.acct}@{instance_domain}"
                if user:
                    user._instance_url = instance_url

            # Mark all statuses as being from a remote instance
            for status in result:
                status._instance_url = instance_url
                # Mark users as remote too (don't cache - IDs are local to remote instance)
                if hasattr(status, 'account') and status.account:
                    fix_user_acct(status.account)
                # Also handle reblogged posts
                if hasattr(status, 'reblog') and status.reblog:
                    status.reblog._instance_url = instance_url
                    if hasattr(status.reblog, 'account') and status.reblog.account:
                        fix_user_acct(status.reblog.account)
                # Handle mentions
                if hasattr(status, 'mentions') and status.mentions:
                    for mention in status.mentions:
                        if hasattr(mention, 'acct') and '@' not in mention.acct:
                            mention.acct = f"{mention.acct}@{instance_domain}"
                # Store the original remote URL for resolving later
                if not hasattr(status, 'url') or not status.url:
                    # Construct URL if not present
                    status.url = f"{instance_url}/@{status.account.acct}/{status.id}"
                # Don't cache users from instance timelines - their IDs are from the remote instance

            return result
        except MastodonError:
            return []
        except Exception:
            return []

    def get_remote_user_timeline(self, instance_url: str, username: str, limit: int = 40, filter: str = None, include_pins: bool = True, **kwargs) -> List[UniversalStatus]:
        """Fetch a user's timeline from a remote instance.

        Args:
            instance_url: The URL of the remote instance
            username: The username on that instance (without @)
            limit: Maximum number of statuses to fetch
            filter: Filter type - 'posts_no_replies', 'posts_with_media', 'posts_no_boosts'
            include_pins: Whether to include pinned posts at the top (default True)
            **kwargs: Additional parameters (max_id, since_id, etc.)

        Returns:
            List of statuses from the user's timeline
        """
        try:
            remote_api = self.get_or_create_remote_api(instance_url)

            # Look up the user on the remote instance
            # Try account_lookup first (works without auth), fall back to search
            remote_user = None
            try:
                remote_user = remote_api.account_lookup(username)
            except Exception:
                pass

            if not remote_user:
                # Fall back to search
                try:
                    results = remote_api.account_search(username, limit=5)
                    if results:
                        for user in results:
                            if user.acct.lower() == username.lower() or user.username.lower() == username.lower():
                                remote_user = user
                                break
                        if not remote_user:
                            remote_user = results[0]
                except Exception:
                    pass

            if not remote_user:
                return []

            # Map filter to Mastodon API parameters
            api_kwargs = dict(kwargs)
            if filter == 'posts_no_replies':
                api_kwargs['exclude_replies'] = True
            elif filter == 'posts_with_media':
                api_kwargs['only_media'] = True
            elif filter == 'posts_no_boosts':
                api_kwargs['exclude_reblogs'] = True

            result = []

            # First fetch pinned posts if requested and this is the initial load
            if include_pins and 'max_id' not in kwargs and 'since_id' not in kwargs:
                try:
                    pinned_statuses = remote_api.account_statuses(remote_user.id, pinned=True, limit=20)
                    pinned_result = self._convert_statuses(pinned_statuses)
                    for status in pinned_result:
                        status._pinned = True
                    result.extend(pinned_result)
                except:
                    pass  # Pinned posts may not be available

            # Get the user's statuses
            statuses = remote_api.account_statuses(remote_user.id, limit=limit, **api_kwargs)
            regular_result = self._convert_statuses(statuses)

            # Remove duplicates (pinned posts may also appear in regular timeline)
            if result:
                pinned_ids = {s.id for s in result}
                regular_result = [s for s in regular_result if s.id not in pinned_ids]

            result.extend(regular_result)

            # Extract domain from instance URL for user accts
            from urllib.parse import urlparse
            parsed = urlparse(instance_url)
            instance_domain = parsed.netloc or parsed.path.strip('/')

            def fix_user_acct(user):
                """Add instance domain to user acct if not present."""
                if user and '@' not in user.acct:
                    user.acct = f"{user.acct}@{instance_domain}"
                if user:
                    user._instance_url = instance_url

            # Mark all statuses as being from a remote instance
            for status in result:
                status._instance_url = instance_url
                if hasattr(status, 'account') and status.account:
                    fix_user_acct(status.account)
                if hasattr(status, 'reblog') and status.reblog:
                    status.reblog._instance_url = instance_url
                    if hasattr(status.reblog, 'account') and status.reblog.account:
                        fix_user_acct(status.reblog.account)
                if hasattr(status, 'mentions') and status.mentions:
                    for mention in status.mentions:
                        if hasattr(mention, 'acct') and '@' not in mention.acct:
                            mention.acct = f"{mention.acct}@{instance_domain}"
                if not hasattr(status, 'url') or not status.url:
                    status.url = f"{instance_url}/@{status.account.acct}/{status.id}"

            return result
        except MastodonError:
            return []
        except Exception:
            return []

    def resolve_remote_status(self, status) -> str:
        """Convert a remote instance status to a local status ID for interactions.

        When you view a post from a remote instance timeline, the ID is local to
        that instance. To interact with it (boost, favourite, reply), you need
        the ID as known by your own instance. This method uses the search API
        to resolve the remote URL to a local status.

        Args:
            status: The status object (must have _instance_url attribute or url)

        Returns:
            The local status ID for use in API calls
        """
        # If no instance URL marker, it's already local
        if not hasattr(status, '_instance_url'):
            return status.id

        # Try multiple URL formats to find the post
        urls_to_try = []

        # First try the URL from the status (most reliable)
        remote_url = getattr(status, 'url', None)
        if remote_url and remote_url.strip():
            urls_to_try.append(remote_url)

        # Try the URI (ActivityPub identifier)
        uri = getattr(status, 'uri', None)
        if uri and uri.strip() and uri not in urls_to_try:
            urls_to_try.append(uri)

        # Construct URL as fallback
        instance_url = status._instance_url
        acct = getattr(status.account, 'acct', '') if hasattr(status, 'account') else ''
        if acct and not '@' in acct:
            # Local user on remote instance - construct full URL
            constructed_url = f"{instance_url}/@{acct}/{status.id}"
            if constructed_url not in urls_to_try:
                urls_to_try.append(constructed_url)

        for search_url in urls_to_try:
            try:
                # Use search with resolve=True to fetch the status into our instance
                result = self.api.search_v2(q=search_url, resolve=True, result_type='statuses')
                statuses = result.statuses if hasattr(result, 'statuses') else result.get('statuses', [])

                if statuses and len(statuses) > 0:
                    # Return the local ID
                    local_id = str(statuses[0].id)
                    # Cache the resolved ID on the status for future use
                    status._resolved_id = local_id
                    return local_id
            except MastodonError as e:
                print(f"Search failed for {search_url}: {e}")
                continue
            except Exception as e:
                print(f"Search error for {search_url}: {e}")
                continue

        # Fallback to original ID (will likely fail on interaction)
        print(f"Could not resolve status. Tried URLs: {urls_to_try}")
        return status.id

    def search_statuses(self, query: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Search for statuses."""
        # Build search kwargs - some older Mastodon.py versions don't support limit
        search_kwargs = {'q': query, 'result_type': 'statuses'}
        if kwargs.get('max_id'):
            search_kwargs['max_id'] = kwargs['max_id']

        try:
            # Try with limit first (Mastodon.py 2.8.0+)
            result = self.api.search_v2(limit=limit, **search_kwargs)
        except TypeError:
            # Fall back without limit for older Mastodon.py versions
            result = self.api.search_v2(**search_kwargs)

        statuses = result.statuses if hasattr(result, 'statuses') else result.get('statuses', [])
        converted = self._convert_statuses(statuses)
        for status in converted:
            self.user_cache.add_users_from_status(status)
        return converted

    def get_status(self, status_id: str) -> Optional[UniversalStatus]:
        """Get a single status by ID."""
        try:
            status = self.api.status(id=status_id)
            return mastodon_status_to_universal(status)
        except MastodonError:
            return None

    def get_status_context(self, status_id: str) -> Dict[str, List[UniversalStatus]]:
        """Get replies and ancestors of a status."""
        try:
            context = self.api.status_context(id=status_id)
            return {
                'ancestors': self._convert_statuses(context.ancestors if hasattr(context, 'ancestors') else context.get('ancestors', [])),
                'descendants': self._convert_statuses(context.descendants if hasattr(context, 'descendants') else context.get('descendants', [])),
            }
        except MastodonError:
            return {'ancestors': [], 'descendants': []}

    # ============ Action Methods ============

    def post(self, text: str, reply_to_id: Optional[str] = None,
             visibility: Optional[str] = None, spoiler_text: Optional[str] = None,
             **kwargs) -> UniversalStatus:
        """Create a new post/status."""
        if visibility is None:
            visibility = self.default_visibility

        post_kwargs = {
            'status': text,
            'visibility': visibility,
        }

        if spoiler_text:
            post_kwargs['spoiler_text'] = spoiler_text

        if reply_to_id:
            post_kwargs['in_reply_to_id'] = reply_to_id

        post_kwargs.update(kwargs)

        status = self.api.status_post(**post_kwargs)
        return mastodon_status_to_universal(status)

    def quote(self, status, text: str, visibility: Optional[str] = None) -> UniversalStatus:
        """Quote a status."""
        if visibility is None:
            visibility = self.default_visibility

        # Get the actual status ID (handle _original_status_id for mentions)
        status_id = getattr(status, '_original_status_id', None) or (str(status.id) if hasattr(status, 'id') else str(status))
        status_url = getattr(status, 'url', None)

        # Check if this is a remote status (acct contains @)
        is_remote = False
        if hasattr(status, 'account') and status.account:
            acct = getattr(status.account, 'acct', '')
            is_remote = '@' in acct

        result = None
        quote_succeeded = False

        # Method 1: Try native Mastodon 4.5+ quoting via direct API call
        try:
            # Mastodon.py doesn't natively support quoted_status_id, so use __api_request
            params = {
                'status': text,
                'visibility': visibility,
                'quoted_status_id': status_id
            }
            result = self.api._Mastodon__api_request('POST', '/api/v1/statuses', params)
            # Verify the quote was actually attached
            # Check for quote, quote_id, or quoted_status_id in response
            if result and ('quote' in result or 'quote_id' in result or 'quoted_status_id' in result):
                quote_succeeded = True
        except Exception:
            pass

        # Method 2: Try Mastodon.py's quote_id (for Fedibird/compatible servers)
        if not quote_succeeded:
            result = None
            try:
                result = self.api.status_post(status=text, quote_id=status_id, visibility=visibility)
                # Check if quote was attached - also check for quote_id attribute
                if result and (
                    (hasattr(result, 'quote') and result.quote) or
                    (hasattr(result, 'quote_id') and result.quote_id) or
                    (hasattr(result, 'quoted_status_id') and result.quoted_status_id)
                ):
                    quote_succeeded = True
            except Exception:
                pass

        # Method 3: For remote posts, try using the status URL instead of ID
        if not quote_succeeded and is_remote and status_url:
            try:
                params = {
                    'status': text,
                    'visibility': visibility,
                    'quote_url': status_url  # Some servers support URL-based quoting
                }
                result = self.api._Mastodon__api_request('POST', '/api/v1/statuses', params)
                if result and ('quote' in result or 'quote_id' in result or 'quoted_status_id' in result):
                    quote_succeeded = True
            except Exception:
                pass

        # Method 4: Fallback - include link to original post
        if not quote_succeeded:
            original_url = status_url
            if not original_url and hasattr(status, 'account'):
                original_url = f"{self.api.api_base_url}/@{status.account.acct}/{status_id}"
            result = self.api.status_post(status=f"{text}\n\n{original_url}", visibility=visibility)

        return mastodon_status_to_universal(result)

    def edit(self, status_id: str, text: str, visibility: Optional[str] = None,
             spoiler_text: Optional[str] = None, media_ids: Optional[list] = None,
             **kwargs) -> UniversalStatus:
        """Edit an existing status."""
        edit_kwargs = {
            'id': status_id,
            'status': text,
        }

        if spoiler_text:
            edit_kwargs['spoiler_text'] = spoiler_text

        if media_ids:
            edit_kwargs['media_ids'] = media_ids

        result = self.api.status_update(**edit_kwargs)
        return mastodon_status_to_universal(result)

    def boost(self, status_id: str) -> bool:
        """Boost/reblog a status."""
        try:
            self.api.status_reblog(id=status_id)
            return True
        except MastodonError:
            return False

    def unboost(self, status_id: str) -> bool:
        """Remove boost from a status."""
        try:
            self.api.status_unreblog(id=status_id)
            return True
        except MastodonError:
            return False

    def favourite(self, status_id: str) -> bool:
        """Favourite a status."""
        try:
            self.api.status_favourite(id=status_id)
            return True
        except MastodonError:
            return False

    def unfavourite(self, status_id: str) -> bool:
        """Remove favourite from a status."""
        try:
            self.api.status_unfavourite(id=status_id)
            return True
        except MastodonError:
            return False

    def pin_status(self, status_id: str) -> bool:
        """Pin a status to your profile."""
        try:
            self.api.status_pin(id=status_id)
            return True
        except MastodonError:
            return False

    def unpin_status(self, status_id: str) -> bool:
        """Unpin a status from your profile."""
        try:
            self.api.status_unpin(id=status_id)
            return True
        except MastodonError:
            return False

    def delete_status(self, status_id: str) -> bool:
        """Delete a status."""
        try:
            self.api.status_delete(id=status_id)
            return True
        except MastodonError:
            return False

    # ============ User Methods ============

    def get_user(self, user_id: str) -> Optional[UniversalUser]:
        """Get user by ID."""
        try:
            user = self.api.account(id=user_id)
            universal = mastodon_user_to_universal(user)
            self.user_cache.add_user(universal)
            return universal
        except MastodonError:
            return None

    def search_users(self, query: str, limit: int = 10) -> List[UniversalUser]:
        """Search for users."""
        results = self.api.account_search(q=query, limit=limit)
        users = self._convert_users(results)
        for user in users:
            self.user_cache.add_user(user)
        return users

    def lookup_user_by_name(self, name: str) -> Optional[UniversalUser]:
        """Look up user by acct/username - for user cache callback."""
        results = self.search_users(name, limit=1)
        return results[0] if results else None

    def follow(self, user_id: str) -> bool:
        """Follow a user."""
        try:
            self.api.account_follow(id=user_id)
            return True
        except MastodonError:
            return False

    def unfollow(self, user_id: str) -> bool:
        """Unfollow a user."""
        try:
            self.api.account_unfollow(id=user_id)
            return True
        except MastodonError:
            return False

    def block(self, user_id: str) -> bool:
        """Block a user."""
        try:
            self.api.account_block(id=user_id)
            return True
        except MastodonError:
            return False

    def unblock(self, user_id: str) -> bool:
        """Unblock a user."""
        try:
            self.api.account_unblock(id=user_id)
            return True
        except MastodonError:
            return False

    def mute(self, user_id: str, duration: int = 0, notifications: bool = True) -> bool:
        """Mute a user.

        Args:
            user_id: The user ID to mute
            duration: Mute duration in seconds (0 = indefinite)
            notifications: Whether to also mute notifications
        """
        try:
            self.api.account_mute(
                id=user_id,
                notifications=notifications,
                duration=duration if duration > 0 else None
            )
            return True
        except MastodonError:
            return False

    def unmute(self, user_id: str) -> bool:
        """Unmute a user."""
        try:
            self.api.account_unmute(id=user_id)
            return True
        except MastodonError:
            return False

    def mute_conversation(self, status_id: str) -> bool:
        """Mute notifications for a conversation/thread."""
        self.api.status_mute(id=status_id)
        return True

    def unmute_conversation(self, status_id: str) -> bool:
        """Unmute notifications for a conversation/thread."""
        self.api.status_unmute(id=status_id)
        return True

    def accept_follow_request(self, user_id: str) -> bool:
        """Accept an incoming follow request."""
        try:
            self.api.follow_request_authorize(id=user_id)
            return True
        except MastodonError:
            return False

    def reject_follow_request(self, user_id: str) -> bool:
        """Reject an incoming follow request."""
        try:
            self.api.follow_request_reject(id=user_id)
            return True
        except MastodonError:
            return False

    def get_followers(self, user_id: str, limit: int = 80, max_pages: int = 1) -> List[UniversalUser]:
        """Get followers of a user.

        Args:
            user_id: The user ID to get followers for
            limit: Maximum users per page (default 80)
            max_pages: Maximum number of API calls/pages to fetch (default 1)
        """
        try:
            all_users = []
            page = self.api.account_followers(id=user_id, limit=limit)
            users = self._convert_users(page)
            for user in users:
                self.user_cache.add_user(user)
            all_users.extend(users)

            page_count = 1
            while page and page_count < max_pages:
                page = self.api.fetch_next(page)
                if page:
                    users = self._convert_users(page)
                    for user in users:
                        self.user_cache.add_user(user)
                    all_users.extend(users)
                    page_count += 1

            return all_users
        except MastodonError:
            return []

    def get_following(self, user_id: str, limit: int = 80, max_pages: int = 1) -> List[UniversalUser]:
        """Get users that a user is following.

        Args:
            user_id: The user ID to get following for
            limit: Maximum users per page (default 80)
            max_pages: Maximum number of API calls/pages to fetch (default 1)
        """
        try:
            all_users = []
            page = self.api.account_following(id=user_id, limit=limit)
            users = self._convert_users(page)
            for user in users:
                self.user_cache.add_user(user)
            all_users.extend(users)

            page_count = 1
            while page and page_count < max_pages:
                page = self.api.fetch_next(page)
                if page:
                    users = self._convert_users(page)
                    for user in users:
                        self.user_cache.add_user(user)
                    all_users.extend(users)
                    page_count += 1

            return all_users
        except MastodonError:
            return []

    # ============ List Methods ============

    def get_lists(self) -> List[Any]:
        """Get user's lists."""
        try:
            return self.api.lists()
        except MastodonError:
            return []

    def get_list_members(self, list_id: str) -> List[UniversalUser]:
        """Get members of a list."""
        try:
            members = self.api.list_accounts(id=list_id)
            return self._convert_users(members)
        except MastodonError:
            return []

    def add_to_list(self, list_id: str, user_id: str) -> bool:
        """Add user to a list."""
        try:
            self.api.list_accounts_add(id=list_id, account_ids=[user_id])
            return True
        except MastodonError:
            return False

    def remove_from_list(self, list_id: str, user_id: str) -> bool:
        """Remove user from a list."""
        try:
            self.api.list_accounts_delete(id=list_id, account_ids=[user_id])
            return True
        except MastodonError:
            return False

    # ============ Explore/Discovery Methods ============

    def get_directory(self, limit: int = 40, order: str = 'active', local: bool = False) -> List[UniversalUser]:
        """Get profile directory for user discovery.

        Args:
            limit: Maximum number of users to return (default 40, max 80)
            order: Sort order - 'active' (most recent posts) or 'new' (recently created)
            local: Only return local users if True
        """
        try:
            users = self.api.directory(limit=min(limit, 80), order=order, local=local)
            return self._convert_users(users)
        except MastodonError:
            return []

    def get_trending_statuses(self, limit: int = 20) -> List[UniversalStatus]:
        """Get trending posts."""
        try:
            statuses = self.api.trending_statuses(limit=min(limit, 40))
            return self._convert_statuses(statuses)
        except MastodonError:
            return []

    def get_trending_tags(self, limit: int = 20) -> List[dict]:
        """Get trending hashtags.

        Returns list of dicts with 'name', 'url', and 'history' keys.
        """
        try:
            tags = self.api.trending_tags(limit=min(limit, 20))
            result = []
            for tag in tags:
                result.append({
                    'name': getattr(tag, 'name', ''),
                    'url': getattr(tag, 'url', ''),
                    'history': getattr(tag, 'history', [])
                })
            return result
        except MastodonError:
            return []

    def get_trending_links(self, limit: int = 20) -> List[dict]:
        """Get trending links/articles.

        Returns list of dicts with 'title', 'url', 'description', 'author' keys.
        """
        try:
            links = self.api.trending_links(limit=min(limit, 20))
            result = []
            for link in links:
                result.append({
                    'title': getattr(link, 'title', ''),
                    'url': getattr(link, 'url', ''),
                    'description': getattr(link, 'description', ''),
                    'author_name': getattr(link, 'author_name', ''),
                    'provider_name': getattr(link, 'provider_name', '')
                })
            return result
        except MastodonError:
            return []

    # ============ Hashtag Methods ============

    def follow_hashtag(self, hashtag: str) -> bool:
        """Follow a hashtag. Posts with this hashtag will appear in home timeline.

        Args:
            hashtag: The hashtag name (without #)
        """
        try:
            # Remove # if present
            hashtag = hashtag.lstrip('#')
            self.api.tag_follow(hashtag)
            return True
        except MastodonError:
            return False

    def unfollow_hashtag(self, hashtag: str) -> bool:
        """Unfollow a hashtag.

        Args:
            hashtag: The hashtag name (without #)
        """
        try:
            # Remove # if present
            hashtag = hashtag.lstrip('#')
            self.api.tag_unfollow(hashtag)
            return True
        except MastodonError:
            return False

    def get_followed_hashtags(self, limit: int = 100) -> List[dict]:
        """Get list of hashtags the user follows.

        Returns list of dicts with 'name', 'url', 'following' keys.
        """
        try:
            tags = self.api.followed_tags(limit=min(limit, 200))
            result = []
            for tag in tags:
                result.append({
                    'name': getattr(tag, 'name', ''),
                    'url': getattr(tag, 'url', ''),
                    'following': getattr(tag, 'following', True)
                })
            return result
        except MastodonError:
            return []

    def get_hashtag_info(self, hashtag: str) -> Optional[dict]:
        """Get information about a hashtag including whether user follows it.

        Args:
            hashtag: The hashtag name (without #)

        Returns dict with 'name', 'url', 'following' keys or None on error.
        """
        try:
            # Remove # if present
            hashtag = hashtag.lstrip('#')
            tag = self.api.tag(hashtag)
            return {
                'name': getattr(tag, 'name', hashtag),
                'url': getattr(tag, 'url', ''),
                'following': getattr(tag, 'following', False)
            }
        except MastodonError:
            return None

    # ============ Cleanup Methods ============

    def close(self):
        """Clean up resources when account is removed."""
        if self.timeline_cache:
            self.timeline_cache.close()
            self.timeline_cache = None
