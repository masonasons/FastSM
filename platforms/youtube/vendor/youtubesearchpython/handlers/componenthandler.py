from typing import Iterable, List, Union
from datetime import datetime, timezone

from youtubesearchpython.core.constants import *


class ComponentHandler:
    def _normalizeUrl(self, url: Union[str, None]) -> Union[str, None]:
        if not isinstance(url, str) or not url:
            return None
        if url.startswith('http://www.youtube.com/') or url.startswith('http://youtube.com/'):
            return 'https://' + url[len('http://'):]
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return 'https://www.youtube.com' + url
        return url

    def _getText(self, source: dict) -> Union[str, None]:
        if source is None:
            return None
        if isinstance(source, str):
            return source
        if isinstance(source, dict):
            if isinstance(source.get('simpleText'), str):
                return source['simpleText']
            if isinstance(source.get('content'), str):
                return source['content']
            if isinstance(source.get('text'), str):
                return source['text']
            if isinstance(source.get('text'), dict):
                return self._getText(source.get('text'))
            runs = source.get('runs')
            if isinstance(runs, list):
                texts = []
                for run in runs:
                    text = self._getText(run)
                    if text:
                        texts.append(text)
                if texts:
                    return ''.join(texts)
        if isinstance(source, list):
            texts = []
            for item in source:
                text = self._getText(item)
                if text:
                    texts.append(text)
            if texts:
                return ''.join(texts)
        return None

    def _getThumbnailSources(self, source: dict) -> Union[list, None]:
        if source is None:
            return None
        if isinstance(source, list):
            return source or None

        candidates = [
            ['thumbnails'],
            ['thumbnail', 'thumbnails'],
            ['image', 'sources'],
            ['sources'],
            ['thumbnailViewModel', 'image', 'sources'],
            ['primaryThumbnail', 'thumbnailViewModel', 'image', 'sources'],
        ]
        for path in candidates:
            value = self._getValue(source, path)
            if isinstance(value, list) and value:
                normalized = []
                for item in value:
                    if isinstance(item, dict) and item.get('url'):
                        item = dict(item)
                        item['url'] = self._normalizeUrl(item.get('url'))
                    normalized.append(item)
                return normalized
        return None

    def _getCanonicalUrl(self, endpoint: dict) -> Union[str, None]:
        if endpoint is None:
            return None
        url = self._getValue(endpoint, ['commandMetadata', 'webCommandMetadata', 'url'])
        if isinstance(url, str):
            return self._normalizeUrl(url)
        url = self._getValue(endpoint, ['browseEndpoint', 'canonicalBaseUrl'])
        if isinstance(url, str):
            return self._normalizeUrl(url)
        return None

    def _defaultText(self, value: Union[str, None], fallback: str) -> str:
        if isinstance(value, str) and value.strip():
            return value
        return fallback

    def _isMissingValue(self, value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            text = value.strip()
            return not text or text.lower().startswith('no ')
        if isinstance(value, list) or isinstance(value, dict):
            return len(value) == 0
        return False

    def _isShortsUrl(self, url: Union[str, None]) -> bool:
        return isinstance(url, str) and '/shorts/' in url

    def _seconds_to_timestamp(self, seconds: Union[str, int, None]) -> Union[str, None]:
        try:
            total_seconds = int(seconds)
        except (TypeError, ValueError):
            return None
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f'{hours}:{minutes:02d}:{secs:02d}'
        return f'{minutes}:{secs:02d}'

    def _seconds_to_accessibility_duration(self, seconds: Union[str, int, None]) -> Union[str, None]:
        try:
            total_seconds = int(seconds)
        except (TypeError, ValueError):
            return None
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f'{hours} hour' + ('s' if hours != 1 else ''))
        if minutes:
            parts.append(f'{minutes} minute' + ('s' if minutes != 1 else ''))
        if secs or not parts:
            parts.append(f'{secs} second' + ('s' if secs != 1 else ''))
        return ', '.join(parts)

    def _compact_number(self, value: Union[str, int, None]) -> Union[str, None]:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        thresholds = (
            (1_000_000_000, 'B'),
            (1_000_000, 'M'),
            (1_000, 'K'),
        )
        for threshold, suffix in thresholds:
            if number >= threshold:
                compact = number / threshold
                if compact >= 10:
                    return f'{compact:.0f}{suffix} views'
                return f'{compact:.1f}{suffix} views'
        return f'{number} views'

    def _build_view_count(self, value: Union[str, int, None]) -> dict:
        count_text = None
        count_short = None
        if isinstance(value, int):
            count_text = f'{value:,} views'
            count_short = self._compact_number(value)
        elif isinstance(value, str) and value.strip():
            normalized = value.strip()
            if normalized.isdigit():
                number = int(normalized)
                count_text = f'{number:,} views'
                count_short = self._compact_number(number)
            else:
                count_text = normalized if 'view' in normalized.lower() else f'{normalized} views'
                count_short = count_text
        return {
            'text': count_text,
            'short': count_short or count_text,
        }

    def _description_from_text(self, value: Union[str, None]) -> Union[list, None]:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        return [{'text': text}]

    def _iso_to_relative_time(self, value: Union[str, None]) -> Union[str, None]:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = value.strip().replace('Z', '+00:00')
        try:
            published = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - published.astimezone(timezone.utc)
        seconds = max(int(delta.total_seconds()), 0)

        units = (
            ('year', 365 * 24 * 60 * 60),
            ('month', 30 * 24 * 60 * 60),
            ('week', 7 * 24 * 60 * 60),
            ('day', 24 * 60 * 60),
            ('hour', 60 * 60),
            ('minute', 60),
        )
        for label, size in units:
            if seconds >= size:
                amount = seconds // size
                suffix = '' if amount == 1 else 's'
                return f'{amount} {label}{suffix} ago'
        return 'just now'

    def _withDefaultCounts(self, counts: dict, fallback: str) -> dict:
        text = self._defaultText(counts.get('text'), fallback)
        short = self._defaultText(counts.get('short'), text)
        result = dict(counts)
        result['text'] = text
        result['short'] = short
        if 'label' in result:
            result['label'] = self._defaultText(result.get('label'), text)
        return result

    def _finalizeComponent(self, component: dict) -> dict:
        accessibility = component.get('accessibility')
        if isinstance(accessibility, dict) and 'duration' in component:
            accessible_duration = accessibility.get('duration')
            if isinstance(accessible_duration, str) and accessible_duration.strip():
                component['duration'] = accessible_duration
        component['id'] = self._defaultText(component.get('id'), 'No id')
        component['title'] = self._defaultText(component.get('title'), 'No title')
        component['thumbnails'] = component.get('thumbnails') or []
        if 'richThumbnail' in component and component['richThumbnail'] is None:
            component['richThumbnail'] = {}
        if 'descriptionSnippet' in component and component['descriptionSnippet'] is None:
            component['descriptionSnippet'] = []
        if 'publishedTime' in component:
            component['publishedTime'] = self._defaultText(component.get('publishedTime'), 'No published time')
        if 'duration' in component:
            component['duration'] = self._defaultText(component.get('duration'), 'No duration')
        if 'viewCount' in component and isinstance(component['viewCount'], dict):
            component['viewCount'] = self._withDefaultCounts(component['viewCount'], 'No views')
        if 'link' in component:
            component['link'] = self._defaultText(self._normalizeUrl(component.get('link')), 'No link')
        if 'shelfTitle' in component:
            component['shelfTitle'] = self._defaultText(component.get('shelfTitle'), 'No shelf title')
        channel = component.get('channel')
        if isinstance(channel, dict):
            channel['name'] = self._defaultText(channel.get('name'), 'No channel')
            channel['id'] = self._defaultText(channel.get('id'), 'No channel id')
            channel['link'] = self._defaultText(self._normalizeUrl(channel.get('link')), 'No channel link')
            channel['thumbnails'] = channel.get('thumbnails') or []
            component['channel'] = channel
        return component

    def _getTextFromMetadataRows(self, rows: list) -> list:
        parsed_rows = []
        for row in rows or []:
            parts = self._getValue(row, ['metadataParts']) or []
            texts = []
            for part in parts:
                text = self._getText(self._getValue(part, ['text']))
                if text:
                    texts.append(text)
            if texts:
                parsed_rows.append(texts)
        return parsed_rows

    def _getVideoComponent(self, element: dict, shelfTitle: str = None) -> dict:
        video = element[videoElementKey]
        title = self._getText(self._getValue(video, ['title'])) or self._getText(self._getValue(video, ['headline']))
        view_text = self._getText(self._getValue(video, ['viewCountText']))
        view_short = self._getText(self._getValue(video, ['shortViewCountText']))
        channel_name = self._getText(self._getValue(video, ['ownerText'])) or self._getText(self._getValue(video, ['longBylineText'])) or self._getText(self._getValue(video, ['shortBylineText']))
        channel_id = self._getValue(video, ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']) or self._getValue(video, ['longBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']) or self._getValue(video, ['shortBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'])
        channel_navigation = self._getValue(video, ['ownerText', 'runs', 0, 'navigationEndpoint']) or self._getValue(video, ['longBylineText', 'runs', 0, 'navigationEndpoint']) or self._getValue(video, ['shortBylineText', 'runs', 0, 'navigationEndpoint'])
        link = self._getCanonicalUrl(self._getValue(video, ['navigationEndpoint']))
        component_type = 'shorts' if getattr(self, 'forceShorts', False) or self._isShortsUrl(link) else 'video'
        component = {
            'type': component_type,
            'id': self._getValue(video, ['videoId']),
            'title': title,
            'publishedTime': self._getText(self._getValue(video, ['publishedTimeText'])),
            'duration': self._getText(self._getValue(video, ['lengthText'])),
            'viewCount': {
                'text': view_text,
                'short': view_short or view_text,
            },
            'thumbnails': self._getThumbnailSources(self._getValue(video, ['thumbnail'])),
            'richThumbnail': self._getValue(video, ['richThumbnail', 'movingThumbnailRenderer', 'movingThumbnailDetails', 'thumbnails', 0]),
            'descriptionSnippet': self._getValue(video, ['detailedMetadataSnippets', 0, 'snippetText', 'runs']) or self._getValue(video, ['descriptionSnippet', 'runs']),
            'channel': {
                'name': channel_name,
                'id': channel_id,
                'thumbnails': self._getThumbnailSources(self._getValue(video, ['channelThumbnailSupportedRenderers', 'channelThumbnailWithLinkRenderer', 'thumbnail'])),
            },
            'accessibility': {
                'title': self._getValue(video, ['title', 'accessibility', 'accessibilityData', 'label']),
                'duration': self._getValue(video, ['lengthText', 'accessibility', 'accessibilityData', 'label']),
            },
        }
        if link:
            component['link'] = link
        elif component_type == 'shorts' and component['id']:
            component['link'] = 'https://www.youtube.com/shorts/' + component['id']
        else:
            component['link'] = 'https://www.youtube.com/watch?v=' + component['id'] if component['id'] else ''
        channel_id = component['channel']['id']
        component['channel']['link'] = self._getCanonicalUrl(channel_navigation) or ('https://www.youtube.com/channel/' + channel_id if channel_id else '')
        component['shelfTitle'] = shelfTitle
        return self._finalizeComponent(component)

    def _getChannelComponent(self, element: dict) -> dict:
        channel = element[channelElementKey]
        subscriber_text = self._getText(self._getValue(channel, ['videoCountText']))
        subscriber_label = self._getValue(channel, ['videoCountText', 'accessibility', 'accessibilityData', 'label'])
        video_count = None
        video_count_candidate = self._getText(self._getValue(channel, ['subscriberCountText']))
        if video_count_candidate and 'subscriber' not in video_count_candidate.lower() and not video_count_candidate.startswith('@'):
            video_count = video_count_candidate
        component = {
            'type': 'channel',
            'id': self._getValue(channel, ['channelId']),
            'title': self._getText(self._getValue(channel, ['title'])),
            'thumbnails': self._getThumbnailSources(self._getValue(channel, ['thumbnail'])),
            'videoCount': video_count,
            'descriptionSnippet': self._getValue(channel, ['descriptionSnippet', 'runs']),
            'subscribersCount': {
                'text': subscriber_text,
                'short': subscriber_text,
                'label': subscriber_label or subscriber_text,
            },
            'handle': self._getText(self._getValue(channel, ['subscriberCountText'])),
        }
        component['link'] = self._getCanonicalUrl(self._getValue(channel, ['navigationEndpoint'])) or ('https://www.youtube.com/channel/' + component['id'] if component['id'] else '')
        component['videoCount'] = self._defaultText(component.get('videoCount'), 'No videos')
        component['subscribersCount'] = self._withDefaultCounts(component['subscribersCount'], 'No subscribers')
        component['handle'] = self._defaultText(component.get('handle'), 'No handle')
        return self._finalizeComponent(component)

    def _getPlaylistComponent(self, element: dict) -> dict:
        if playlistElementKey in element:
            playlist = element[playlistElementKey]
            component = {
                'type': 'playlist',
                'id': self._getValue(playlist, ['playlistId']),
                'title': self._getText(self._getValue(playlist, ['title'])),
                'videoCount': self._getText(self._getValue(playlist, ['videoCountText'])) or self._getValue(playlist, ['videoCount']),
                'viewCount': {
                    'text': None,
                    'short': None,
                },
                'channel': {
                    'name': self._getText(self._getValue(playlist, ['shortBylineText'])),
                    'id': self._getValue(playlist, ['shortBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId']),
                },
                'thumbnails': self._getThumbnailSources(self._getValue(playlist, ['thumbnailRenderer', 'playlistVideoThumbnailRenderer', 'thumbnail'])),
                'descriptionSnippet': self._getValue(playlist, ['descriptionSnippet', 'runs']),
            }
            component['link'] = self._getCanonicalUrl(self._getValue(playlist, ['navigationEndpoint'])) or ('https://www.youtube.com/playlist?list=' + component['id'] if component['id'] else '')
            channel_id = component['channel']['id']
            component['channel']['link'] = self._getCanonicalUrl(self._getValue(playlist, ['shortBylineText', 'runs', 0, 'navigationEndpoint'])) or ('https://www.youtube.com/channel/' + channel_id if channel_id else '')
            component['videoCount'] = self._defaultText(component.get('videoCount'), 'No videos')
            component['viewCount'] = self._withDefaultCounts(component['viewCount'], 'No views')
            return self._finalizeComponent(component)

        playlist = element.get('lockupViewModel', {})
        metadata = self._getValue(playlist, ['metadata', 'lockupMetadataViewModel']) or {}
        metadata_rows = self._getTextFromMetadataRows(self._getValue(metadata, ['metadata', 'contentMetadataViewModel', 'metadataRows']) or [])
        thumbnail_badges = self._getValue(playlist, ['contentImage', 'collectionThumbnailViewModel', 'primaryThumbnail', 'thumbnailViewModel', 'overlays', 0, 'thumbnailOverlayBadgeViewModel', 'thumbnailBadges']) or []
        video_count = None
        for badge in thumbnail_badges:
            text = self._getText(self._getValue(badge, ['thumbnailBadgeViewModel', 'text']))
            if text and any(char.isdigit() for char in text):
                video_count = text
                break
        row0_part0 = self._getValue(playlist, ['metadata', 'lockupMetadataViewModel', 'metadata', 'contentMetadataViewModel', 'metadataRows', 0, 'metadataParts', 0, 'text'])
        command = self._getValue(row0_part0, ['commandRuns', 0, 'onTap', 'innertubeCommand']) or {}
        channel_name = metadata_rows[0][0] if metadata_rows else None
        channel_id = self._getValue(command, ['browseEndpoint', 'browseId'])
        channel_link = self._getCanonicalUrl(command)
        component = {
            'type': 'playlist',
            'id': self._getValue(playlist, ['contentId']),
            'title': self._getText(self._getValue(metadata, ['title'])),
            'videoCount': video_count,
            'viewCount': {
                'text': None,
                'short': None,
            },
            'channel': {
                'name': channel_name,
                'id': channel_id,
                'link': channel_link,
            },
            'thumbnails': self._getThumbnailSources(self._getValue(playlist, ['contentImage', 'collectionThumbnailViewModel'])),
            'descriptionSnippet': None,
        }
        component['link'] = 'https://www.youtube.com/playlist?list=' + component['id'] if component['id'] else self._getCanonicalUrl(self._getValue(playlist, ['rendererContext', 'commandContext', 'onTap', 'innertubeCommand']))
        component['videoCount'] = self._defaultText(component.get('videoCount'), 'No videos')
        component['viewCount'] = self._withDefaultCounts(component['viewCount'], 'No views')
        return self._finalizeComponent(component)

    def _getShortComponent(self, short: dict, shelfTitle: str = None) -> dict:
        title = self._getText(self._getValue(short, ['overlayMetadata', 'primaryText']))
        short_view_text = self._getText(self._getValue(short, ['overlayMetadata', 'secondaryText']))
        video_id = self._getValue(short, ['onTap', 'innertubeCommand', 'reelWatchEndpoint', 'videoId'])
        if not video_id:
            entity_id = self._getValue(short, ['entityId'])
            if isinstance(entity_id, str) and entity_id.startswith('shorts-shelf-item-'):
                video_id = entity_id.rsplit('-', 1)[-1]
        component = {
            'type': 'shorts',
            'id': video_id,
            'title': title,
            'publishedTime': None,
            'duration': None,
            'viewCount': {
                'text': short_view_text,
                'short': short_view_text,
            },
            'thumbnails': self._getThumbnailSources(self._getValue(short, ['thumbnailViewModel'])) or self._getThumbnailSources(self._getValue(short, ['onTap', 'innertubeCommand', 'reelWatchEndpoint', 'thumbnail'])),
            'richThumbnail': None,
            'descriptionSnippet': None,
            'channel': {
                'name': None,
                'id': None,
                'thumbnails': None,
                'link': None,
            },
            'accessibility': {
                'title': self._getValue(short, ['accessibilityText']),
                'duration': None,
            },
            'link': self._getCanonicalUrl(self._getValue(short, ['onTap', 'innertubeCommand'])) or ('https://www.youtube.com/shorts/' + video_id if video_id else ''),
            'shelfTitle': shelfTitle,
        }
        return self._finalizeComponent(component)

    def _getGridShelfComponents(self, element: dict) -> list:
        shelf = element.get('gridShelfViewModel', {})
        shelf_title = self._getText(self._getValue(shelf, ['header', 'sectionHeaderViewModel', 'headline']))
        components = []
        for item in self._getValue(shelf, ['contents']) or []:
            shorts_lockup = self._getValue(item, ['shortsLockupViewModel'])
            if shorts_lockup:
                components.append(self._getShortComponent(shorts_lockup, shelfTitle=shelf_title))
        return components

    def _getVideoFromChannelSearch(self, elements: list) -> list:
        channelsearch = []
        for element in elements:
            element = self._getValue(element, ["childVideoRenderer"])
            if element is None:
                continue
            json_data = {
                "id": self._getValue(element, ["videoId"]),
                "title": self._getText(self._getValue(element, ["title"])),
                "uri": self._getValue(element, ["navigationEndpoint", "commandMetadata", "webCommandMetadata", "url"]),
                "duration": {
                    "simpleText": self._getText(self._getValue(element, ["lengthText"])),
                    "text": self._getValue(element, ["lengthText", "accessibility", "accessibilityData", "label"])
                }
            }
            channelsearch.append(json_data)
        return channelsearch

    def _getChannelSearchComponent(self, elements: list) -> list:
        channelsearch = []
        for element in elements:
            responsetype = None

            if 'gridPlaylistRenderer' in element:
                element = element['gridPlaylistRenderer']
                responsetype = 'gridplaylist'
            elif 'itemSectionRenderer' in element:
                contents = element["itemSectionRenderer"].get("contents", [])
                if not contents:
                    continue
                first_content = contents[0]
                if 'videoRenderer' in first_content:
                    element = first_content['videoRenderer']
                    responsetype = "video"
                elif 'playlistRenderer' in first_content:
                    element = first_content["playlistRenderer"]
                    responsetype = "playlist"
                else:
                    continue
            elif 'continuationItemRenderer' in element:
                continue
            else:
                continue

            if responsetype == "video":
                json_data = {
                    "id": self._getValue(element, ["videoId"]),
                    "thumbnails": {
                        "normal": self._getThumbnailSources(self._getValue(element, ["thumbnail"])),
                        "rich": self._getValue(element, ["richThumbnail", "movingThumbnailRenderer", "movingThumbnailDetails", "thumbnails"])
                    },
                    "title": self._getText(self._getValue(element, ["title"])),
                    "descriptionSnippet": self._getText(self._getValue(element, ["descriptionSnippet"])) if self._getValue(element, ["descriptionSnippet"]) else None,
                    "uri": self._getValue(element, ["navigationEndpoint", "commandMetadata", "webCommandMetadata", "url"]),
                    "views": {
                        "precise": self._getText(self._getValue(element, ["viewCountText"])),
                        "simple": self._getText(self._getValue(element, ["shortViewCountText"])),
                        "approximate": self._getValue(element, ["shortViewCountText", "accessibility", "accessibilityData", "label"])
                    },
                    "duration": {
                        "simpleText": self._getText(self._getValue(element, ["lengthText"])),
                        "text": self._getValue(element, ["lengthText", "accessibility", "accessibilityData", "label"])
                    },
                    "published": self._getText(self._getValue(element, ["publishedTimeText"])),
                    "channel": {
                        "name": self._getText(self._getValue(element, ["ownerText"])),
                        "thumbnails": self._getThumbnailSources(self._getValue(element, ["channelThumbnailSupportedRenderers", "channelThumbnailWithLinkRenderer", "thumbnail"]))
                    },
                    "type": responsetype
                }
            elif responsetype == 'playlist':
                json_data = {
                    "id": self._getValue(element, ["playlistId"]),
                    "videos": self._getVideoFromChannelSearch(self._getValue(element, ["videos"]) or []),
                    "thumbnails": {
                        "normal": self._getThumbnailSources(self._getValue(element, ["thumbnails"])),
                    },
                    "title": self._getText(self._getValue(element, ["title"])),
                    "uri": self._getValue(element, ["navigationEndpoint", "commandMetadata", "webCommandMetadata", "url"]),
                    "channel": {
                        "name": self._getText(self._getValue(element, ["longBylineText"])),
                    },
                    "type": responsetype
                }
            else:
                json_data = {
                    "id": self._getValue(element, ["playlistId"]),
                    "thumbnails": {
                        "normal": self._getValue(element, ["thumbnail", "thumbnails", 0]) if self._getValue(element, ["thumbnail", "thumbnails"]) else None,
                    },
                    "title": self._getText(self._getValue(element, ["title"])),
                    "uri": self._getValue(element, ["navigationEndpoint", "commandMetadata", "webCommandMetadata", "url"]),
                    "type": 'playlist'
                }
            channelsearch.append(json_data)
        return channelsearch

    def _getShelfComponent(self, element: dict) -> dict:
        shelf = element[shelfElementKey]
        return {
            'title': self._getText(self._getValue(shelf, ['title'])),
            'elements': self._getValue(shelf, ['content', 'verticalListRenderer', 'items']),
        }

    def _getValue(self, source: dict, path: List[Union[str, int]]) -> Union[str, int, dict, list, None]:
        if source is None:
            return None
        value = source
        for key in path:
            if value is None:
                return None
            if type(key) is str:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            elif type(key) is int:
                if isinstance(value, list) and value:
                    try:
                        value = value[key]
                    except IndexError:
                        return None
                else:
                    return None
        return value
