from __future__ import annotations

from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


class RTSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []

        for note in soup.find_all("article")[: self.config.limit]:
            title_links = note.find_all("a")
            if not title_links:
                continue

            href = title_links[0].get("href", "")
            if not href:
                continue

            title = " ".join(part.get_text(strip=True) for part in title_links if part.get_text(strip=True)).strip()
            if not title:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, href)
            try:
                text = self._fetch_text(client, url)
            except Exception:
                text = FAILED_TEXT

            articles.append(Article(title=title, url=url, text=text))

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_article_soup(url)
        paragraphs = [
            paragraph.get_text(separator=" ", strip=True)
            for paragraph in soup.find_all("p", attrs={"class": False})
        ]
        return normalize_text_blocks(paragraphs)