from __future__ import annotations

from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


class ElObservadorSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []

        for note in soup.find_all("article")[: self.config.limit]:
            link = note.find("a", href=True)
            if link is None:
                continue

            title = link.get("title", "").replace("El Observador |", "").strip()
            url = urljoin(self.config.base_url or self.config.homepage_url, link["href"])
            if not title or not url:
                continue

            try:
                text = self._fetch_text(client, url)
            except Exception:
                text = FAILED_TEXT

            articles.append(Article(title=title, url=url, text=text))

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_soup(url)
        parts = [
            article.get_text(separator=" ", strip=True)
            for article in soup.find_all("article", class_="article-body")
        ]
        return normalize_text_blocks(parts)