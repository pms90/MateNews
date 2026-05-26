from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


ARTICLE_PATH_RE = re.compile(r"^/la-ciudad/[^/]+/?$")
BODY_STOP_MARKERS = (
    "Las noticias locales nunca fueron tan importantes",
    "Para comentar",
    "NOTAS RELACIONADAS",
    "LAS MÁS LEÍDAS",
    "ÚLTIMAS NOTICIAS",
    "TAGS",
)


def _clean_title(text: str) -> str:
    cleaned = text.replace("√°", "á").replace("√∫", "ú")
    cleaned = " ".join(cleaned.split()).strip()
    if cleaned and cleaned[-1] not in ".!?:;":
        cleaned += "."
    return cleaned


class ElDiaSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for note in soup.find_all("article"):
            if not isinstance(note, Tag) or not self._is_listing_note(note):
                continue

            link = note.find("a", href=True)
            if not isinstance(link, Tag):
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, link["href"])
            if not self._is_article_url(url) or url in seen_urls:
                continue

            title = self._extract_title(note)
            if not title or "Cartonazo" in title:
                continue

            seen_urls.add(url)
            try:
                title, text = self._fetch_article_details(client, url, fallback_title=title)
            except Exception:
                title, text = title, FAILED_TEXT

            articles.append(Article(title=title, url=url, text=text))

            if len(articles) >= self.config.limit:
                break

        return SourceBatch(source=self.config, articles=articles)

    def _is_listing_note(self, note: Tag) -> bool:
        classes = set(note.get("class", []))
        return "nota" in classes and "articulo" not in classes

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc != "www.eldia.com":
            return False
        if not ARTICLE_PATH_RE.match(parsed.path):
            return False

        slug = parsed.path.removeprefix("/la-ciudad/").strip("/")
        return bool(slug) and not slug.isdigit()

    def _extract_title(self, note: Tag) -> str:
        for tag_name in ("h1", "h2", "h3", "h4"):
            heading = note.find(tag_name)
            if heading is None:
                continue
            title = _clean_title(heading.get_text(" ", strip=True))
            if title:
                return title
        return ""

    def _fetch_article_details(self, client: HttpClient, url: str, fallback_title: str) -> tuple[str, str]:
        soup = client.get_article_soup(url)
        h1 = soup.find("h1")
        title = _clean_title(h1.get_text(" ", strip=True)) if h1 is not None else fallback_title

        parts: list[str] = []
        subtitle = self._extract_subtitle(soup)
        if subtitle:
            parts.append(subtitle)

        content_root = soup.find("article", class_="articulo")
        if not isinstance(content_root, Tag):
            return title, normalize_text_blocks(parts)

        seen_texts: set[str] = set(parts)
        for paragraph in content_root.find_all("p"):
            if not isinstance(paragraph, Tag):
                continue

            text = " ".join(paragraph.get_text(" ", strip=True).split())
            if not text:
                continue
            if self._should_stop(paragraph, text):
                break
            if text in seen_texts:
                continue

            seen_texts.add(text)
            parts.append(text)

        return title, normalize_text_blocks(parts)

    def _extract_subtitle(self, soup: BeautifulSoup) -> str:
        description = soup.find("meta", attrs={"name": "description"})
        if description is None:
            return ""
        return " ".join(description.get("content", "").split())

    def _should_stop(self, paragraph: Tag, text: str) -> bool:
        if "nota__titulo-item" in paragraph.get("class", []):
            return True
        return any(marker in text for marker in BODY_STOP_MARKERS)