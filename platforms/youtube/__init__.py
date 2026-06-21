"""YouTube platform implementation."""

# Make the vendored youtube-search-python copy importable as the top-level
# package `youtubesearchpython` (see vendor/README.md). Inserted at the front
# of sys.path so the maintained vendored copy wins over any stale PyPI install.
import os as _os
import sys as _sys
_vendor_dir = _os.path.join(_os.path.dirname(__file__), "vendor")
if _vendor_dir not in _sys.path:
    _sys.path.insert(0, _vendor_dir)

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
