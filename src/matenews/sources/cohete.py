from __future__ import annotations

from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


class CoheteSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []

        for note in soup.find_all("article")[: self.config.limit]:
            title_element = note.find(class_="title")
            meta = note.find(class_="post-meta")
            summary_element = note.find(class_="post-summary")
            if title_element is None or meta is None or summary_element is None:
                continue

            author_element = meta.find(class_="post-author")
            if author_element is None:
                continue

            title = title_element.get_text(strip=True)
            author = author_element.get_text(strip=True)
            summary = summary_element.get_text(strip=True)
            if not title or not summary:
                continue

            composed_title = f"{title}. {summary}."
            if author != "El Cohete a la Luna":
                composed_title += f" Por {author}."
            composed_title = composed_title.replace("..", ".").replace("..", ".").replace("..", ".")

            link = note.find("a", attrs={"class": "post-url", "href": True})
            if link is None:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, link.get("href", ""))
            if not url:
                continue

            try:
                text = self._fetch_text(client, url)
            except Exception:
                text = FAILED_TEXT

            articles.append(Article(title=composed_title, url=url, text=text, author=author))

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_soup(url)
        paragraphs = []
        for paragraph in soup.find_all("p", attrs={"class": False, "href": False}):
            if paragraph.find("a"):
                continue
            paragraphs.append(paragraph.get_text(strip=True))

        if len(paragraphs) >= 4:
            paragraphs = paragraphs[:-4]
        return normalize_text_blocks(paragraphs)