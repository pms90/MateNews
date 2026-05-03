from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import Tag

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


ARTICLE_PATH_RE = re.compile(r"^/(?:[^/?#]+/)?articulo/\d{4}/\d{1,2}/[^/?#]+/?$")
BODY_STOP_MARKERS = (
    "Temas en este artículo",
    "Comentar este artículo",
    "Compartir este artículo",
    "Más de ",
    "Lo más leído hoy",
)
BODY_SKIP_MARKERS = (
    "Nuestro periodismo depende de vos",
    "Apoyá nuestro periodismo",
    "SUSCRIBITE POR",
    "Si ya tenés una cuenta",
    "Registrate",
    "Espacio publicitario",
)


class LaDiariaSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            if not isinstance(heading, Tag):
                continue

            link = self._find_heading_link(heading)
            if link is None:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, link.get("href", ""))
            if not self._is_article_url(url) or url in seen_urls:
                continue

            title = self._normalize_title(heading.get_text(" ", strip=True))
            if not title:
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

    def _find_heading_link(self, heading: Tag) -> Tag | None:
        link = heading.find("a", href=True)
        if isinstance(link, Tag):
            return link

        parent = heading.parent
        if isinstance(parent, Tag) and parent.name == "a" and parent.get("href"):
            return parent
        return None

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc not in {"ladiaria.com.uy", "www.ladiaria.com.uy"}:
            return False
        return bool(ARTICLE_PATH_RE.match(parsed.path))

    def _normalize_title(self, title: str) -> str:
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 15:
            return ""
        if title and title[-1] not in ".!?:;":
            title += "."
        return title

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        soup = client.get_article_soup(url)
        h1 = soup.find("h1")
        if h1 is None:
            return FAILED_TEXT

        content_root = h1.find_parent("article") or h1.find_parent("main") or soup
        parts: list[str] = []
        seen_texts: set[str] = set()

        for element in content_root.find_all(["h2", "p"]):
            if not isinstance(element, Tag):
                continue

            text = element.get_text(" ", strip=True)
            if not text:
                continue
            if self._should_stop(text):
                break
            if self._should_skip(element, text):
                continue
            if text in seen_texts:
                continue

            seen_texts.add(text)
            parts.append(text)

        return normalize_text_blocks(parts)

    def _should_stop(self, text: str) -> bool:
        return any(text.startswith(marker) for marker in BODY_STOP_MARKERS)

    def _should_skip(self, element: Tag, text: str) -> bool:
        if any(marker in text for marker in BODY_SKIP_MARKERS):
            return True
        if text.startswith("Foto:"):
            return True
        if len(text) < 30 and element.name == "p":
            return True
        return False