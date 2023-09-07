from typing import Optional

from requests import Response, Session

from brds.core.crawler.domain_rate_limiter import DomainRateLimiter


class BrowserEmulator:
    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None):
        if rate_limiter is None:
            rate_limiter = DomainRateLimiter()
        self.rate_limiter = rate_limiter
        self.session = Session()
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

    def get(self, url, **kwargs) -> Response:
        self.rate_limiter.limit(url)
        return self.session.get(url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs) -> Response:
        self.rate_limiter.limit(url)
        return self.session.post(url, data=data, json=json, **kwargs)

    def accept_header(self: "BrowserEmulator") -> str:
        return "text/html"

    def user_agent(self: "BrowserEmulator") -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 "
            + "Safari/537.36 Edg/116.0.1938.69"
        )
