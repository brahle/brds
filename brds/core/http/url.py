from urllib.parse import urlparse


class Url:
    def __init__(self, url: str):
        """
        Initialize the URL object with the given URL.

        >>> url = Url("https://www.example.com/some/path;p1=v1;p2=v2?q1=v1&q2=v2#fragment")
        >>> url.get()
        'https://www.example.com/some/path;p1=v1;p2=v2?q1=v1&q2=v2#fragment'
        >>> url.domain
        'www.example.com'
        >>> url.protocol
        'https'
        >>> url.path
        '/some/path'
        >>> url.params
        'p1=v1;p2=v2'
        >>> url.query
        'q1=v1&q2=v2'
        >>> url.path = '/new/path'
        >>> url.get()
        'https://www.example.com/new/path;p1=v1;p2=v2?q1=v1&q2=v2#fragment'
        """
        self._set(url)

    def get(self):
        """
        Get the URL

        >>> url = Url("https://www.example.com/some/path;p1=v1;p2=v2?q1=v1&q2=v2#fragment")
        >>> url.get()
        'https://www.example.com/some/path;p1=v1;p2=v2?q1=v1&q2=v2#fragment'
        """
        url = f"{self.protocol}://{self.domain}{self.path}"
        if self.params:
            url += f";{self.params}"
        if self.query:
            url += f"?{self.query}"
        if self.fragment:
            url += f"#{self.fragment}"
        return url

    def set(self, url):
        return self.__class__(url)

    def _set(self, url):
        self._initial_url = url
        self._parsed = urlparse(url)
        self.protocol = self._parsed.scheme
        self.domain = self._parsed.netloc
        self.path = self._parsed.path
        self.params = self._parsed.params
        self.query = self._parsed.query
        self.fragment = self._parsed.fragment
        return self


if __name__ == "__main__":
    import doctest

    doctest.testmod()
