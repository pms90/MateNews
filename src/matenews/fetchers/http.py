from __future__ import annotations

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
    def __init__(self, delay_seconds: float = 0.66, timeout_seconds: float = 30.0) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str) -> requests.Response:
        time.sleep(self.delay_seconds)
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response

    def get_text(self, url: str, encoding: str | None = None) -> str:
        response = self.get(url)
        resolved_encoding = encoding or response.encoding or response.apparent_encoding or "utf-8"
        return response.content.decode(resolved_encoding, errors="replace")

    def get_soup(self, url: str, encoding: str | None = None) -> BeautifulSoup:
        return BeautifulSoup(self.get_text(url, encoding=encoding), "html.parser")