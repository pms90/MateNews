from __future__ import annotations

import re
from urllib.parse import urljoin

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource


def _sentenceize_html_fragments(html_string: str) -> str:
    fragments = re.findall(r">([^<]+)<", f">{html_string}<")
    parts: list[str] = []
    for fragment in fragments:
        text = fragment.strip()
        if not text:
            continue
        if not text.endswith((".", "!", "?", ":", ";")):
            text += "."
        parts.append(text)
    return " ".join(parts)


class Pagina12Source(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []

        for block in soup.find_all("div", class_="p12-article-card-full")[: self.config.limit]:
            link = block.find("a", href=True)
            if link is None:
                continue

            title = _sentenceize_html_fragments(str(block))
            url = urljoin(self.config.base_url or self.config.homepage_url, link["href"])
            if not title or not url:
                continue

            author = ""
            author_element = block.find("span", class_="article-author")
            if author_element is not None:
                author_link = author_element.find("a")
                if author_link is not None:
                    author = author_link.get_text(strip=True)
                else:
                    author = author_element.get_text(" ", strip=True).replace("Por", "", 1).strip()

            articles.append(Article(title=title, url=url, author=author))

        return SourceBatch(source=self.config, articles=articles)