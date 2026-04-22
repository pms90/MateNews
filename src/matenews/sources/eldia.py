from __future__ import annotations

from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource


def _clean_title(text: str) -> str:
    return text.strip().replace("\n", "").replace("√°", "á").replace("√∫", "ú")


class ElDiaSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []

        for note in soup.find_all("article"):
            title = self._extract_title(note)
            if not title or "Cartonazo" in title:
                continue

            link = note.find("a", href=True)
            if link is None:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, link["href"])
            articles.append(Article(title=title, url=url))

            if len(articles) >= self.config.limit:
                break

        return SourceBatch(source=self.config, articles=articles)

    def _extract_title(self, note) -> str:
        for link in note.find_all("a"):
            if link.find("h2") is not None:
                return _clean_title(link.get_text(strip=True))
        return ""