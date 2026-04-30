from __future__ import annotations

from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


class InfobaeSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        cards = soup.find_all("a", class_="story-card-ctn")
        articles: list[Article] = []

        for card in cards[: self.config.limit]:
            title_element = card.find("h2", class_="story-card-hl")
            if title_element is None:
                continue

            title = title_element.get_text(strip=True)
            if title and not title.endswith("."):
                title += "."

            href = card.get("href", "")
            if not href:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, href)
            description_element = card.find("div", class_="story-card-deck")
            description = description_element.get_text(strip=True) if description_element else ""

            try:
                text = self._fetch_text(client, url)
            except Exception:
                text = FAILED_TEXT

            articles.append(
                Article(
                    title=title,
                    url=url,
                    description=description,
                    text=text,
                )
            )

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_article_soup(url)
        body = soup.find("div", class_="body-article")
        if body is None:
            return FAILED_TEXT

        parts = [element.get_text(strip=True) for element in body.find_all(["p", "h3"])]
        return normalize_text_blocks(parts)