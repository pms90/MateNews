from __future__ import annotations

from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


class LPOSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for item in soup.find_all("div", class_="item"):
            title_tag = item.find(class_="title")
            link = item.find("a", href=True)
            if title_tag is None or link is None:
                continue

            title = title_tag.get_text(" ", strip=True)
            url = urljoin(self.config.base_url or self.config.homepage_url, link["href"])
            if not title or not url or url in seen_urls:
                continue

            seen_urls.add(url)
            try:
                text = self._fetch_text(client, url)
            except Exception:
                text = FAILED_TEXT

            articles.append(Article(title=title, url=url, text=text))
            if len(articles) >= self.config.limit:
                break

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_article_soup(url)
        parts: list[str] = []

        description = soup.find("div", class_="description")
        if description is not None:
            description_text = description.get_text(" ", strip=True)
            if description_text:
                parts.append(description_text)

        body = soup.find("div", class_="body") or soup.find("article")
        if body is not None:
            for paragraph in body.find_all("p"):
                text = paragraph.get_text(" ", strip=True)
                if len(text) < 30:
                    continue
                if text not in parts:
                    parts.append(text)

        return normalize_text_blocks(parts)