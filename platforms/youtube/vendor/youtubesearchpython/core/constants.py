requestPayload = {
    "context": {
        "client": {
            "clientName": "WEB",
            "clientVersion": "2.20250514.01.00",
            "newVisitorCookie": True,
        },
        "user": {
            "lockedSafetyMode": False,
        }
    }
}
userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'


videoElementKey = 'videoRenderer'
channelElementKey = 'channelRenderer'
playlistElementKey = 'playlistRenderer'
shelfElementKey = 'shelfRenderer'
itemSectionKey = 'itemSectionRenderer'
continuationItemKey = 'continuationItemRenderer'
playerResponseKey = 'playerResponse'
richItemKey = 'richItemRenderer'
hashtagElementKey = 'hashtagTileRenderer'
hashtagBrowseKey = 'FEhashtag'
hashtagVideosPath = ['contents', 'twoColumnBrowseResultsRenderer', 'tabs', 0, 'tabRenderer', 'content', 'richGridRenderer', 'contents']
hashtagContinuationVideosPath = ['onResponseReceivedActions', 0, 'appendContinuationItemsAction', 'continuationItems']
searchKey = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
contentPath = ['contents', 'twoColumnSearchResultsRenderer', 'primaryContents', 'sectionListRenderer', 'contents']
fallbackContentPath = ['contents', 'twoColumnSearchResultsRenderer', 'primaryContents', 'richGridRenderer', 'contents']
continuationContentPath = ['onResponseReceivedCommands', 0, 'appendContinuationItemsAction', 'continuationItems']
continuationKeyPath = ['continuationItemRenderer', 'continuationEndpoint', 'continuationCommand', 'token']
playlistInfoPath = ['response', 'sidebar', 'playlistSidebarRenderer', 'items']
playlistVideosPath = ['response', 'contents', 'twoColumnBrowseResultsRenderer', 'tabs', 0, 'tabRenderer', 'content', 'sectionListRenderer', 'contents', 0, 'itemSectionRenderer', 'contents', 0, 'playlistVideoListRenderer', 'contents']
playlistPrimaryInfoKey = 'playlistSidebarPrimaryInfoRenderer'
playlistSecondaryInfoKey = 'playlistSidebarSecondaryInfoRenderer'
playlistVideoKey = 'playlistVideoRenderer'


class ResultMode:
    json = 0
    dict = 1


class SearchMode:
    all = None
    videos = 'EgIQAQ%3D%3D'
    shorts = 'EgIQCQ%3D%3D'
    channels = 'EgIQAg%3D%3D'
    playlists = 'EgIQAw%3D%3D'
    movies = 'EgIQBA%3D%3D'
    livestreams = 'EgJAAQ%3D%3D'


class VideoUploadDateFilter:
    today = 'EgIIAg%3D%3D'
    thisWeek = 'EgIIAw%3D%3D'
    thisMonth = 'EgIIBA%3D%3D'
    thisYear = 'EgIIBQ%3D%3D'


class VideoDurationFilter:
    under4Minutes = 'EgIYBA%3D%3D'
    between4And20Minutes = 'EgIYBQ%3D%3D'
    over20Minutes = 'EgIYAg%3D%3D'
    short = under4Minutes
    medium = between4And20Minutes
    long = over20Minutes


class VideoSortOrder:
    relevance = ''
    popularity = 'CAM%3D'
    viewCount = popularity


class VideoFeature:
    live = 'EgJAAQ%3D%3D'
    fourK = 'EgJwAQ%3D%3D'
    hd = 'EgIgAQ%3D%3D'
    subtitles = 'EgIoAQ%3D%3D'
    creativeCommons = 'EgIwAQ%3D%3D'
    spherical360 = 'EgJ4AQ%3D%3D'
    vr180 = 'EgPQAQE%3D'
    threeD = 'EgI4AQ%3D%3D'
    hdr = 'EgPIAQE%3D'
    location = 'EgO4AQE%3D'
    purchased = 'EgJIAQ%3D%3D'


class ChannelRequestType:
    info = "EgVhYm91dA%3D%3D"
    playlists = "EglwbGF5bGlzdHMYAyABcAA%3D"
