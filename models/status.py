"""Universal status representation for multi-platform support."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any


@dataclass
class UniversalMedia:
    """Universal media attachment representation."""
    id: str
    type: str  # 'image', 'video', 'audio', 'gifv'
    url: str
    preview_url: Optional[str] = None
    description: Optional[str] = None
    _platform_data: Any = None


@dataclass
class UniversalMention:
    """Universal mention representation."""
    id: str
    acct: str
    username: str
    url: Optional[str] = None
    _platform_data: Any = None


@dataclass
class UniversalStatus:
    """Universal status representation that works across platforms."""
    id: str
    account: 'UniversalUser'  # Forward reference
    content: str  # Raw HTML content
    text: str  # Clean text (HTML stripped)
    created_at: datetime
    favourites_count: int = 0
    boosts_count: int = 0
    replies_count: int = 0
    in_reply_to_id: Optional[str] = None
    reblog: Optional['UniversalStatus'] = None
    quote: Optional['UniversalStatus'] = None
    media_attachments: List[UniversalMedia] = field(default_factory=list)
    mentions: List[UniversalMention] = field(default_factory=list)
    url: Optional[str] = None

    # Platform-specific fields (may be None on some platforms)
    visibility: Optional[str] = None  # Mastodon: public, unlisted, private, direct
    spoiler_text: Optional[str] = None  # Mastodon content warning
    card: Optional[Any] = None  # Link preview card
    poll: Optional[Any] = None
    quote_approval: Optional[Any] = None  # Mastodon 4.5+: QuoteApproval object

    # Original platform object for fallback
    _platform_data: Any = None
    _platform: str = ""  # 'mastodon', 'bluesky', etc.

    # For notification-sourced statuses, store the notification ID
    _notification_id: Optional[str] = None

    def __getattr__(self, name):
        """Fallback to platform data for attributes we don't have."""
        if name.startswith('_'):
            raise AttributeError(name)
        if self._platform_data is not None and hasattr(self._platform_data, name):
            return getattr(self._platform_data, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
