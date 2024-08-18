from collections import defaultdict
from threading import Lock
from time import sleep, time
from typing import Callable, Dict, Optional, Union

from brds.core.http.url import Url
from brds.core.logger import get_logger

Number = Union[int, float]
# Warning: The function used to be Callable[[], Number]] - might cause breaks. The parameter is
# the URL.
CallableOrNumber = Union[Number, Callable[[str], Number]]


LOGGER = get_logger()


def default_delay(
    delay: Number = 0.1,
    domain_map: Optional[Dict[str, CallableOrNumber]] = None,
) -> Callable[[str], Number]:
    """
    Returns a function that returns the delay for a given URL. The delay is the time to wait
    before making a request to the same domain again. The delay can be a fixed number or a
    function that returns a number. The function receives the URL as a parameter.

    :param delay: The default delay to use if the domain is not in the domain map.
    :param domain_map: A dictionary that maps domains to delays. The delay can be a fixed number
        or a function that returns a number. The function receives the URL as a parameter.
    :return: A function that returns the delay for a given URL.
    """

    def _default_delay(url: str) -> Number:
        domain = Url(url).domain
        if domain_map is not None and domain in domain_map:
            for_domain = domain_map[domain]
            if callable(for_domain):
                return for_domain(url)
            return for_domain
        return delay

    return _default_delay


class DomainRateLimiter:
    """
    A rate limiter that limits the number of requests to the same domain. The rate limiter can
    be configured to use a fixed delay or a function that returns the delay. The function receives
    the URL as a parameter.

    :param delay: The delay to use. The delay can be a fixed number or a function that returns a
        number. The function receives the URL as a parameter.

    Example usage:
    >>> rate_limiter = DomainRateLimiter()
    >>> rate_limiter.limit("https://example.com")

    """

    def __init__(self: "DomainRateLimiter", delay: Optional[CallableOrNumber] = None) -> None:
        if delay is None:
            delay = default_delay()
        self.last_request_time: Dict[str, float] = defaultdict(float)
        self._delay = delay
        self._lock = Lock()

    def wait_if_needed(self: "DomainRateLimiter", url: str) -> None:
        domain = Url(url).domain
        with self._lock:
            start_time = self.last_request_time[domain]
            latest_time = time()
            elapsed_time = latest_time - start_time
            delay = self.delay(url)

            while elapsed_time < delay:
                time_to_wait = delay - elapsed_time
                LOGGER.info("Rate Limit - sleeping %.2fs before continuing", time_to_wait)
                sleep(time_to_wait)
                latest_time = time()
                elapsed_time = latest_time - start_time

            LOGGER.debug("Updating last request time for domain %s to %s", domain, latest_time)
            self.last_request_time[domain] = latest_time

    def limit(self: "DomainRateLimiter", url: str) -> None:
        self.wait_if_needed(url)

    def delay(self: "DomainRateLimiter", url: str) -> Number:
        if callable(self._delay):
            return self._delay(url)
        return self._delay


def test_domain_rate_limiter():
    rate_limiter = DomainRateLimiter(default_delay(0.5))
    for _ in range(5):
        print(f"Limiting {_}")
        rate_limiter.limit("https://example.com")


if __name__ == "__main__":
    test_domain_rate_limiter()
