from __future__ import annotations

import random
import time

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class HttpClient:
    def __init__(
        self,
        article_delay_seconds: float = 0.05,
        article_jitter_min_seconds: float = 0.05,
        article_jitter_max_seconds: float = 0.1,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.article_delay_seconds = article_delay_seconds
        self.article_jitter_min_seconds = article_jitter_min_seconds
        self.article_jitter_max_seconds = article_jitter_max_seconds
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response

    def get_article(self, url: str) -> requests.Response:
        self._sleep_before_article_fetch()
        return self.get(url)

    def get_text(self, url: str, encoding: str | None = None) -> str:
        response = self.get(url)
        resolved_encoding = encoding or response.encoding or response.apparent_encoding or "utf-8"
        return response.content.decode(resolved_encoding, errors="replace")

    def get_article_text(self, url: str, encoding: str | None = None) -> str:
        response = self.get_article(url)
        resolved_encoding = encoding or response.encoding or response.apparent_encoding or "utf-8"
        return response.content.decode(resolved_encoding, errors="replace")

    def get_soup(self, url: str, encoding: str | None = None) -> BeautifulSoup:
        return BeautifulSoup(self.get_text(url, encoding=encoding), "html.parser")

    def get_article_soup(self, url: str, encoding: str | None = None) -> BeautifulSoup:
        return BeautifulSoup(self.get_article_text(url, encoding=encoding), "html.parser")

    def _sleep_before_article_fetch(self) -> None:
        jitter_seconds = random.uniform(self.article_jitter_min_seconds, self.article_jitter_max_seconds)
        time.sleep(self.article_delay_seconds + jitter_seconds)