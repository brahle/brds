from typing import Optional

from brds.core.http.client import HttpClient
from brds.core.http.domain_rate_limiter import DomainRateLimiter


class BrowserEmulator(HttpClient):
    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None):
        super().__init__(rate_limiter)
        self.session.headers.update(
            {
                "User-Agent": self.user_agent(),
                "Accept": self.accept_header(),
                "Accept-Language": "en-US,en;q=0.5",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def accept_header(self: "BrowserEmulator") -> str:
        return "text/html"

    def user_agent(self: "BrowserEmulator") -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 "
            + "Safari/537.36 Edg/116.0.1938.69"
        )


async def test_browser_emulator():
    async with BrowserEmulator() as emualtor:
        response = await emualtor.get("https://httpbin.org/get")
        print(await response.text())


if __name__ == "__main__":
    from asyncio import run

    run(test_browser_emulator())
