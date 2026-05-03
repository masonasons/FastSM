"""Abstract base class for platform implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from models import UniversalStatus, UniversalUser, UniversalNotification, UserCache


class PlatformAccount(ABC):
    """Abstract base class for platform-specific account implementations.

    Each platform (Mastodon, Bluesky, etc.) should implement this interface.
    """

    # Platform identification
    platform_name: str = ""

    # Feature flags - override in subclasses
    supports_visibility: bool = False
    supports_content_warning: bool = False
    supports_quote_posts: bool = False
    supports_polls: bool = False
    supports_lists: bool = False
    supports_direct_messages: bool = False
    supports_media_attachments: bool = False
    supports_scheduling: bool = False
    supports_editing: bool = False
    # Pleroma/Akkoma/Glitch-soc accept a content_type form field on
    # status_post / status_update. Vanilla Mastodon silently ignores it,
    # so it's safe to enable for any Mastodon-family backend.
    supports_content_type: bool = False

    def __init__(self, app, index: int):
        self.app = app
        self.index = index
        self.user_cache: Optional[UserCache] = None
        self._me: Optional[UniversalUser] = None
        self._max_chars: int = 500

    @property
    def me(self) -> UniversalUser:
        """Current authenticated user."""
        return self._me

    @property
    def max_chars(self) -> int:
        """Maximum characters allowed in a post."""
        return self._max_chars

    def supports_feature(self, feature: str) -> bool:
        """Check if this platform supports a feature."""
        feature_map = {
            'visibility': self.supports_visibility,
            'content_warning': self.supports_content_warning,
            'cw': self.supports_content_warning,
            'quote': self.supports_quote_posts,
            'quote_posts': self.supports_quote_posts,
            'polls': self.supports_polls,
            'lists': self.supports_lists,
            'direct_messages': self.supports_direct_messages,
            'dm': self.supports_direct_messages,
            'media_attachments': self.supports_media_attachments,
            'scheduling': self.supports_scheduling,
            'editing': self.supports_editing,
            'content_type': self.supports_content_type,
        }
        return feature_map.get(feature, False)

    # ============ Timeline Methods ============

    @abstractmethod
    def get_home_timeline(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get home timeline statuses."""
        pass

    @abstractmethod
    def get_mentions(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get mentions as statuses (extracted from notifications)."""
        pass

    @abstractmethod
    def get_notifications(self, limit: int = 40, **kwargs) -> List[UniversalNotification]:
        """Get notifications."""
        pass

    @abstractmethod
    def get_conversations(self, limit: int = 40, **kwargs) -> List[Any]:
        """Get direct message conversations."""
        pass

    @abstractmethod
    def get_favourites(self, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get favourited/liked statuses."""
        pass

    @abstractmethod
    def get_user_statuses(self, user_id: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get statuses from a specific user."""
        pass

    @abstractmethod
    def get_list_timeline(self, list_id: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Get statuses from a list."""
        pass

    @abstractmethod
    def search_statuses(self, query: str, limit: int = 40, **kwargs) -> List[UniversalStatus]:
        """Search for statuses."""
        pass

    @abstractmethod
    def get_status(self, status_id: str) -> Optional[UniversalStatus]:
        """Get a single status by ID."""
        pass

    @abstractmethod
    def get_status_context(self, status_id: str) -> Dict[str, List[UniversalStatus]]:
        """Get replies and ancestors of a status."""
        pass

    # ============ Action Methods ============

    @abstractmethod
    def post(self, text: str, reply_to_id: Optional[str] = None,
             visibility: Optional[str] = None, spoiler_text: Optional[str] = None,
             **kwargs) -> UniversalStatus:
        """Create a new post/status."""
        pass

    @abstractmethod
    def boost(self, status_id: str) -> bool:
        """Boost/reblog a status."""
        pass

    @abstractmethod
    def unboost(self, status_id: str) -> bool:
        """Remove boost from a status."""
        pass

    @abstractmethod
    def favourite(self, status_id: str) -> bool:
        """Favourite/like a status."""
        pass

    @abstractmethod
    def unfavourite(self, status_id: str) -> bool:
        """Remove favourite from a status."""
        pass

    @abstractmethod
    def delete_status(self, status_id: str) -> bool:
        """Delete a status."""
        pass

    # ============ User Methods ============

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[UniversalUser]:
        """Get user by ID."""
        pass

    @abstractmethod
    def search_users(self, query: str, limit: int = 10) -> List[UniversalUser]:
        """Search for users."""
        pass

    @abstractmethod
    def follow(self, user_id: str) -> bool:
        """Follow a user."""
        pass

    @abstractmethod
    def unfollow(self, user_id: str) -> bool:
        """Unfollow a user."""
        pass

    @abstractmethod
    def block(self, user_id: str) -> bool:
        """Block a user."""
        pass

    @abstractmethod
    def unblock(self, user_id: str) -> bool:
        """Unblock a user."""
        pass

    @abstractmethod
    def mute(self, user_id: str) -> bool:
        """Mute a user."""
        pass

    @abstractmethod
    def unmute(self, user_id: str) -> bool:
        """Unmute a user."""
        pass

    @abstractmethod
    def get_followers(self, user_id: str, limit: int = 80) -> List[UniversalUser]:
        """Get followers of a user."""
        pass

    @abstractmethod
    def get_following(self, user_id: str, limit: int = 80) -> List[UniversalUser]:
        """Get users that a user is following."""
        pass

    # ============ List Methods ============

    def get_lists(self) -> List[Any]:
        """Get user's lists. Override if platform supports lists."""
        return []

    def get_list_members(self, list_id: str) -> List[UniversalUser]:
        """Get members of a list. Override if platform supports lists."""
        return []

    def add_to_list(self, list_id: str, user_id: str) -> bool:
        """Add user to a list. Override if platform supports lists."""
        return False

    def remove_from_list(self, list_id: str, user_id: str) -> bool:
        """Remove user from a list. Override if platform supports lists."""
        return False
