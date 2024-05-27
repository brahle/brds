from collections import defaultdict
from time import sleep, time
from typing import Callable, Dict, Union
from urllib.parse import urlparse

from brds.core.logger import get_logger

Number = Union[int, float]
CallableOrNumber = Union[Number, Callable[[], Number]]


LOGGER = get_logger()


class DomainRateLimiter:
    def __init__(self: "DomainRateLimiter", delay: CallableOrNumber = 5) -> None:
        self.last_request_time: Dict[str, float] = defaultdict(float)
        self._delay = delay

    def get_domain(self: "DomainRateLimiter", url: str) -> str:
        return urlparse(url).netloc

    def wait_if_needed(self: "DomainRateLimiter", domain: str) -> None:
        elapsed_time = time() - self.last_request_time[domain]
        delay = self.delay
        if elapsed_time < delay:
            time_to_wait = delay - elapsed_time

            LOGGER.info("Sleeping %.2fs before continuing", time_to_wait)
            sleep(time_to_wait)

    def limit(self: "DomainRateLimiter", url: str) -> None:
        domain = self.get_domain(url)
        self.wait_if_needed(domain)
        self.last_request_time[domain] = time()

    @property
    def delay(self: "DomainRateLimiter") -> Number:
        if callable(self._delay):
            return self._delay()
        return self._delay
