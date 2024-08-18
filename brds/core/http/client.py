from asyncio import run
from time import time
from typing import Optional
from uuid import uuid4

from aiohttp import ClientSession

from brds.core.http.domain_rate_limiter import DomainRateLimiter
from brds.core.logger import get_logger as _get_logger

LOGGER = _get_logger()


class HttpClient:
    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None):
        self.uuid = str(uuid4())
        LOGGER.info("Creating HTTP client with UUID: %s", self.uuid)
        self.session = ClientSession()
        if rate_limiter is None:
            rate_limiter = DomainRateLimiter()
        self.rate_limiter = rate_limiter
        LOGGER.debug("HTTP client created with UUID: %s", self.uuid)

    async def request(self, method, url, **kwargs):
        LOGGER.info(f"[{self.uuid}] {method} {url}")
        LOGGER.debug(f"[{self.uuid}] {method} {url} with kwargs: {kwargs}")
        self.rate_limiter.limit(url)
        response = await self.session.request(method, url, **kwargs)
        response.raise_for_status()
        LOGGER.info(f"[{self.uuid}] {method} {url} response: {response.status}")
        return response

    async def get(self, url, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url, **kwargs):
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url, **kwargs):
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url, **kwargs):
        return await self.request("OPTIONS", url, **kwargs)

    async def close(self):
        LOGGER.info(f"[{self.uuid}] Closing HTTP client")
        await self.session.close()

    async def __aenter__(self):
        """Allow the use of 'async with' syntax."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Close the session when exiting the context."""
        await self.close()

    async def __finalizer__(self):
        """Close the session when exitilsng the context."""
        await self.close()


async def test_http_client():
    rate_limiter = DomainRateLimiter(1)
    async with HttpClient(rate_limiter) as client:
        import json

        response = await client.get("https://httpbin.org/get")
        print(time(), json.dumps(await response.json(), indent=2))
        response = await client.post("https://httpbin.org/post", json={"key": "value"})
        print(time(), json.dumps(await response.json(), indent=2))
        response = await client.put("https://httpbin.org/put", json={"key": "value"})
        print(time(), json.dumps(await response.json(), indent=2))
        response = await client.delete("https://httpbin.org/delete")
        print(time(), json.dumps(await response.json(), indent=2))
        response = await client.patch("https://httpbin.org/patch", json={"key": "value"})
        print(time(), json.dumps(await response.json(), indent=2))


if __name__ == "__main__":
    run(test_http_client())
    run(test_http_client())
