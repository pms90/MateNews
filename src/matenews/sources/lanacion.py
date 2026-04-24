from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


ARTICLE_PATH_RE = re.compile(r"^/.+-nid\d{8}/?$")
EXCLUDED_PATH_PREFIXES = (
    "/autor/",
    "/tema/",
    "/mapa-del-sitio",
    "/dolar-hoy/",
    "/juegos/",
    "/suscribirme",
)
BODY_STOP_MARKERS = (
    "Otras noticias de",
    "Últimas Noticias",
    "Ahora para comentar",
    "Conforme a The Trust Project",
    "© Copyright",
    "Protegido por reCAPTCHA",
)


class LanacionSource(BaseSource):
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

            candidate_title = self._extract_candidate_title(link)
            if not candidate_title:
                continue

            seen_urls.add(url)
            try:
                title, text, author = self._fetch_article_details(client, url)
            except Exception:
                title, text, author = candidate_title, FAILED_TEXT, ""

            articles.append(Article(title=title or candidate_title, url=url, text=text, author=author))
            if len(articles) >= self.config.limit:
                break

        return SourceBatch(source=self.config, articles=articles)

    def _is_article_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.netloc != "www.lanacion.com.ar":
            return False

        path = parsed.path
        if any(path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
            return False
        return bool(ARTICLE_PATH_RE.match(path))

    def _extract_candidate_title(self, link: Tag) -> str:
        for tag_name in ("h1", "h2", "h3", "h4"):
            heading = link.find(tag_name)
            if heading is None:
                continue
            title = self._normalize_title(heading.get_text(" ", strip=True))
            if title:
                return title

        text = " ".join(link.get_text(" ", strip=True).split())
        if len(text) < 30:
            return ""
        text = re.sub(r"\s+Por\s+.+$", "", text)
        return self._normalize_title(text)

    def _fetch_article_details(self, client: HttpClient, url: str) -> tuple[str, str, str]:
        soup = client.get_soup(url)
        h1 = soup.find("h1")
        title = self._normalize_title(h1.get_text(" ", strip=True)) if h1 is not None else ""
        author = self._extract_author(soup)

        parts: list[str] = []
        subtitle = self._extract_subtitle(soup)
        if subtitle:
            parts.append(subtitle)

        body = soup.find("section", id="cuerpo__nota") or soup.find("section", class_="cuerpo__nota")
        content_root = body or soup.find("main") or soup
        seen_texts: set[str] = set(parts)

        for element in content_root.find_all("p"):
            if not isinstance(element, Tag):
                continue
            classes = set(element.get("class", []))
            if body is not None and "com-paragraph" not in classes:
                continue

            text = " ".join(element.get_text(" ", strip=True).split())
            if not text:
                continue
            if self._should_stop(text):
                break
            if len(text) < 30 or text in seen_texts:
                continue
            seen_texts.add(text)
            parts.append(text)

        return title, normalize_text_blocks(parts), author

    def _extract_author(self, soup: BeautifulSoup) -> str:
        author_link = soup.find("a", href=re.compile(r"/autor/"))
        if author_link is None:
            return ""
        return " ".join(author_link.get_text(" ", strip=True).split())

    def _extract_subtitle(self, soup: BeautifulSoup) -> str:
        subtitle = soup.find("h2", class_=re.compile(r"com-subhead"))
        if subtitle is None:
            return ""
        return " ".join(subtitle.get_text(" ", strip=True).split())

    def _normalize_title(self, title: str) -> str:
        title = " ".join(title.split()).strip()
        if not title:
            return ""
        if title[-1] not in ".!?":
            title += "."
        return title

    def _should_stop(self, text: str) -> bool:
        return any(marker in text for marker in BODY_STOP_MARKERS)