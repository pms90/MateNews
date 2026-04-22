from __future__ import annotations

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


class NodalSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []

        for article in soup.find_all("article", class_="listing-item")[: self.config.limit]:
            title_tag = article.find("h2", class_="title")
            if title_tag is None:
                continue

            link_tag = title_tag.find("a", class_=["post-title", "post-url"]) or title_tag.find("a", href=True)
            if link_tag is None:
                continue

            title = link_tag.get_text(strip=True)
            url = link_tag.get("href", "")
            if not title or not url:
                continue

            try:
                text = self._fetch_text(client, url)
            except Exception as exc:
                text = f"No se pudo obtener texto: {exc}"

            articles.append(Article(title=title, url=url, text=text))

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_soup(url)
        content = soup.find("article", class_="single-post-content")
        if content is None:
            return FAILED_TEXT

        parts: list[str] = []
        for element in content.find_all(["p", "h3"]):
            if "cgk" in element.get("class", []):
                continue
            if "addtoany_share_save_container" in element.get("class", []):
                continue
            if "cptch_block" in element.get("class", []):
                continue
            if element.find("script"):
                continue
            if element.find("div", class_="cgk-container"):
                continue
            if element.find("blockquote", class_="twitter-tweet"):
                continue

            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue
            if text.startswith("Solve :") or text.startswith("Compartir:") or text.startswith("<?xml"):
                continue
            parts.append(text)

        return normalize_text_blocks(parts)