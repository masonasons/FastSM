"""YouTube platform implementation."""

from .account import YouTubeAccount
from .models import (
    youtube_channel_to_universal,
    youtube_video_to_universal,
    youtube_subscription_to_universal,
)

__all__ = [
    'YouTubeAccount',
    'youtube_channel_to_universal',
    'youtube_video_to_universal',
    'youtube_subscription_to_universal',
]

# Register this platform
from platforms import register_platform
register_platform('youtube', YouTubeAccount)
