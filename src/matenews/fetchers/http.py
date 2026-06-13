from __future__ import annotations

import hashlib
import json
from pathlib import Path
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

DEFAULT_ARTICLE_DELAY_SECONDS = 0.25
DEFAULT_ARTICLE_JITTER_MIN_SECONDS = 0.05
DEFAULT_ARTICLE_JITTER_MAX_SECONDS = 0.15
DEFAULT_ARTICLE_CACHE_DIR = Path(".cache") / "matenews" / "articles"


class HttpClient:
    def __init__(
        self,
        article_delay_seconds: float = DEFAULT_ARTICLE_DELAY_SECONDS,
        article_jitter_min_seconds: float = DEFAULT_ARTICLE_JITTER_MIN_SECONDS,
        article_jitter_max_seconds: float = DEFAULT_ARTICLE_JITTER_MAX_SECONDS,
        timeout_seconds: float = 30.0,
        article_cache_dir: Path | None = DEFAULT_ARTICLE_CACHE_DIR,
    ) -> None:
        self.article_delay_seconds = article_delay_seconds
        self.article_jitter_min_seconds = article_jitter_min_seconds
        self.article_jitter_max_seconds = article_jitter_max_seconds
        self.timeout_seconds = timeout_seconds
        self.article_cache_dir = Path(article_cache_dir) if article_cache_dir is not None else None
        self.article_cache_hits: dict[str, bool] = {}
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if self.article_cache_dir is not None:
            self.article_cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response

    def get_article(self, url: str) -> requests.Response:
        cached_response = self._load_cached_article_response(url)
        if cached_response is not None:
            self.article_cache_hits[url] = True
            return cached_response

        self.article_cache_hits[url] = False
        self._sleep_before_article_fetch()
        response = self.get(url)
        self._store_cached_article_response(url, response)
        return response

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

    def was_article_retrieved_from_cache(self, url: str) -> bool:
        return self.article_cache_hits.get(url, False)

    def _sleep_before_article_fetch(self) -> None:
        jitter_seconds = random.uniform(self.article_jitter_min_seconds, self.article_jitter_max_seconds)
        time.sleep(self.article_delay_seconds + jitter_seconds)

    def _load_cached_article_response(self, url: str) -> requests.Response | None:
        data_path, metadata_path = self._article_cache_paths(url)
        if data_path is None or not data_path.exists():
            return None

        try:
            content = data_path.read_bytes()
            metadata = self._load_article_metadata(metadata_path)
        except OSError:
            return None

        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = content
        response.encoding = metadata.get("encoding") or None
        return response

    def _store_cached_article_response(self, url: str, response: requests.Response) -> None:
        data_path, metadata_path = self._article_cache_paths(url)
        if data_path is None or metadata_path is None:
            return

        content = getattr(response, "content", None)
        if not isinstance(content, (bytes, bytearray)):
            return

        metadata = {
            "url": url,
            "encoding": response.encoding or "",
        }

        try:
            data_path.write_bytes(bytes(content))
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        except OSError:
            return

    def _article_cache_paths(self, url: str) -> tuple[Path | None, Path | None]:
        if self.article_cache_dir is None:
            return None, None

        cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return (
            self.article_cache_dir / f"{cache_key}.bin",
            self.article_cache_dir / f"{cache_key}.json",
        )

    def _load_article_metadata(self, metadata_path: Path | None) -> dict[str, str]:
        if metadata_path is None or not metadata_path.exists():
            return {}

        try:
            raw_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

        if not isinstance(raw_metadata, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in raw_metadata.items()
            if isinstance(key, str) and isinstance(value, str)
        }