import httpx
import os

from youtubesearchpython.core.constants import userAgent

class RequestCore:
    def __init__(self):
        self.url = None
        self.data = None
        self.timeout = 2
        self.proxy = None
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        
        proxy_url = https_proxy or http_proxy
        if proxy_url:
            self.proxy = proxy_url

    def _get_client_kwargs(self):
        kwargs = {
            "headers": {"User-Agent": userAgent},
            "timeout": self.timeout,
        }
        if self.proxy:
            kwargs["proxy"] = self.proxy
        return kwargs

    def syncPostRequest(self) -> httpx.Response:
        client_kwargs = self._get_client_kwargs()
        return httpx.post(
            self.url,
            json=self.data,
            **client_kwargs
        )

    async def asyncPostRequest(self) -> httpx.Response:
        client_kwargs = self._get_client_kwargs()
        async with httpx.AsyncClient(**client_kwargs) as client:
            r = await client.post(self.url, json=self.data)
            return r

    def syncGetRequest(self) -> httpx.Response:
        client_kwargs = self._get_client_kwargs()
        return httpx.get(self.url, **client_kwargs)

    async def asyncGetRequest(self) -> httpx.Response:
        client_kwargs = self._get_client_kwargs()
        async with httpx.AsyncClient(**client_kwargs) as client:
            r = await client.get(self.url)
            return r
