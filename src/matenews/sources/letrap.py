from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


ARTICLE_PATH_RE = re.compile(r"^/(?:[^/?#]+/)?[^/?#]+-n\d+$")
EXCLUDED_PATH_PREFIXES = (
    "/seccion/",
    "/region/",
    "/regiones",
    "/tag/",
    "/contacto",
    "/login",
    "/registro",
    "/staff",
    "/suscripcion-newsletter",
    "/contenidos/",
)
BODY_STOP_MARKERS = (
    "Notas Relacionadas",
    "Las Más Leídas",
    "También te puede interesar",
    "Temas",
    "Suscribirse a notificaciones",
)
BODY_SKIP_MARKERS = (
    "Escuchá la nota completa",
    "Powered by Thinkindot Audio",
    "Registrate para continuar leyendo",
    "Ads powered by",
    "Compartir en:",
    "Embed -",
)


class LetraPSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, href)
            if not self._is_article_url(url) or url in seen_urls:
                continue

            title = self._extract_title(link)
            if not title:
                continue

            seen_urls.add(url)
            try:
                text, author = self._fetch_text(client, url)
            except Exception:
                text, author = FAILED_TEXT, ""

            articles.append(Article(title=title, url=url, text=text, author=author))
            if len(articles) >= self.config.limit:
                break

        return SourceBatch(source=self.config, articles=articles)

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc != "www.letrap.com.ar":
            return False
        path = parsed.path.rstrip("/")
        if any(path.startswith(prefix.rstrip("/")) for prefix in EXCLUDED_PATH_PREFIXES):
            return False
        return bool(ARTICLE_PATH_RE.match(path))

    def _extract_title(self, link: Tag) -> str:
        for tag_name in ("h1", "h2", "h3"):
            heading = link.find(tag_name)
            if heading is not None:
                title = heading.get_text(" ", strip=True)
                if title:
                    return self._normalize_title(title)

        title = link.get_text(" ", strip=True)
        if len(title) < 30 or title.lower().startswith("letra p"):
            return ""
        return self._normalize_title(title)

    def _normalize_title(self, title: str) -> str:
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"^Letra P\s*\|\s*", "", title)
        if title and title[-1] not in ".!?":
            title += "."
        return title

    def _fetch_text(self, client: HttpClient, url: str) -> tuple[str, str]:
        soup = client.get_article_soup(url)
        author = self._extract_author(soup)

        h1 = soup.find("h1")
        if h1 is None:
            return FAILED_TEXT, author

        parts: list[str] = []
        content_root = h1.find_parent("main") or h1.parent or soup
        seen_texts: set[str] = set()

        for element in content_root.find_all(["p", "h2"]):
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

        return normalize_text_blocks(parts), author

    def _extract_author(self, soup: BeautifulSoup) -> str:
        author_link = soup.find("a", href=re.compile(r"/perfil/"))
        if author_link is None:
            return ""
        return author_link.get_text(" ", strip=True)

    def _should_stop(self, text: str) -> bool:
        return any(marker in text for marker in BODY_STOP_MARKERS)

    def _should_skip(self, element: Tag, text: str) -> bool:
        classes = element.get("class", [])
        if "ignore-parser" in classes:
            return True
        if any(marker in text for marker in BODY_SKIP_MARKERS):
            return True
        if len(text) < 25 and element.name == "p":
            return True
        return False