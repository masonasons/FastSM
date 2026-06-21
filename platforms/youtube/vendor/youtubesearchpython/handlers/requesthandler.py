from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json
import copy
from youtubesearchpython.handlers.componenthandler import ComponentHandler
from youtubesearchpython.core.constants import *


class RequestHandler(ComponentHandler):
    def _collectSearchItems(self, elements):
        items = []
        for element in elements or []:
            if not isinstance(element, dict):
                continue
            if itemSectionKey in element:
                items.extend(self._collectSearchItems(self._getValue(element, [itemSectionKey, 'contents']) or []))
                continue
            if continuationItemKey in element:
                token = self._getValue(element, continuationKeyPath)
                if token:
                    self.continuationKey = token
                continue
            if (
                videoElementKey in element
                or channelElementKey in element
                or playlistElementKey in element
                or richItemKey in element
                or shelfElementKey in element
                or 'lockupViewModel' in element
                or 'gridShelfViewModel' in element
            ):
                items.append(element)
        return items

    def _makeRequest(self) -> None:
        ''' Fixes #47 '''
        requestBody = copy.deepcopy(requestPayload)
        requestBody['query'] = self.query
        requestBody['client'] = {
            'hl': self.language,
            'gl': self.region,
        }
        if self.searchPreferences:
            requestBody['params'] = self.searchPreferences
        if self.continuationKey:
            requestBody['continuation'] = self.continuationKey
        requestBodyBytes = json.dumps(requestBody).encode('utf_8')
        request = Request(
            'https://www.youtube.com/youtubei/v1/search' + '?' + urlencode({
                'key': searchKey,
            }),
            data = requestBodyBytes,
            headers = {
                'Content-Type': 'application/json; charset=utf-8',
                'Content-Length': len(requestBodyBytes),
                'User-Agent': userAgent,
            }
        )
        try:
            self.response = urlopen(request, timeout=self.timeout).read().decode('utf_8')
        except:
            raise Exception('ERROR: Could not make request.')
    
    def _parseSource(self) -> None:
        try:
            if not self.continuationKey:
                response = json.loads(self.response)
                responseContent = self._getValue(response, contentPath)
            else:
                response = json.loads(self.response)
                responseContent = self._getValue(response, continuationContentPath)
            if responseContent:
                self.responseSource = self._collectSearchItems(responseContent)
            else:
                fallback = self._getValue(response, fallbackContentPath) or []
                self.responseSource = self._collectSearchItems(fallback)
        except:
            raise Exception('ERROR: Could not parse YouTube response.')
