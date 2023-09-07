from collections import defaultdict
from time import time, sleep
from typing import Callable, Union
from urllib.parse import urlparse

Number = Union[int, float]
CallableOrNumber = Union[Number, Callable[[], Number]]


class DomainRateLimiter:
    def __init__(self: "DomainRateLimiter", delay: CallableOrNumber = 5) -> None:
        self.last_request_time = defaultdict(float)
        self._delay = delay

    def get_domain(self: "DomainRateLimiter", url: str) -> str:
        return urlparse(url).netloc

    def wait_if_needed(self: "DomainRateLimiter", domain: str) -> str:
        elapsed_time = time() - self.last_request_time[domain]
        delay = self.delay
        if elapsed_time < delay:
            time_to_wait = delay - elapsed_time
            print(f"Sleeping for {time_to_wait}")
            sleep(time_to_wait)

    def limit(self: "DomainRateLimiter", url: str) -> str:
        domain = self.get_domain(url)
        self.wait_if_needed(domain)
        self.last_request_time[domain] = time()

    @property
    def delay(self: "DomainRateLimiter") -> Number:
        if callable(self._delay):
            return self._delay()
        return self._delay

