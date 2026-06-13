from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from ..fetchers.translate import TranslationClient, translate_to_spanish
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


TITLE_ENDINGS = ".!?:;"
ARTICLE_PATH_RE = re.compile(r"^/a/\d{6}/\d{2}/WS[a-zA-Z0-9]+\.html$")
AUTHOR_RE = re.compile(r"\bBy\s+([^|\n]+?)\s+\|", re.IGNORECASE)
SKIP_PREFIXES = (
    "Contact the writer at",
    "China Daily -",
    "Copyright 1994 -",
    "Updated:",
    "Home",
)
SKIP_CONTAINS = (
    "@chinadaily.com.cn",
    "@chinadailyusa.com",
    "Additional Links",
    "BACK TO THE TOP",
    "facebook",
    "twitter",
    "linkedin",
    "wechat",
    "sinaweibo",
)


class ChinaDailySource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url, encoding="utf-8")
        translator = TranslationClient()
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            if not isinstance(heading, Tag):
                continue

            link = self._find_heading_link(heading)
            if link is None:
                continue

            url = urljoin(self.config.base_url or self.config.homepage_url, link.get("href", ""))
            if not url or url in seen_urls:
                continue
            if not self._is_article_url(url):
                continue

            raw_title = " ".join(heading.get_text(" ", strip=True).split())
            if not raw_title:
                continue

            try:
                author, raw_description, raw_text = self._fetch_article(client, url)
            except Exception:
                author = ""
                raw_description = ""
                raw_text = FAILED_TEXT

            translated_title = self._normalize_title(translate_to_spanish(raw_title, translator=translator))
            translated_description = translate_to_spanish(raw_description, translator=translator)
            translated_text = raw_text if raw_text == FAILED_TEXT else translate_to_spanish(raw_text, translator=translator)

            articles.append(
                Article(
                    title=translated_title or self._normalize_title(raw_title),
                    url=url,
                    description=translated_description,
                    text=translated_text,
                    author=author,
                )
            )
            seen_urls.add(url)

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
        if parsed.netloc not in {"chinadaily.com.cn", "www.chinadaily.com.cn"}:
            return False
        return bool(ARTICLE_PATH_RE.match(parsed.path))

    def _fetch_article(self, client: HttpClient, url: str) -> tuple[str, str, str]:
        soup = client.get_article_soup(url, encoding="utf-8")
        h1 = soup.find("h1")
        if not isinstance(h1, Tag):
            return "", "", FAILED_TEXT

        content_root = h1.find_parent("article") or h1.find_parent("main") or soup
        author = self._extract_author(content_root)
        parts: list[str] = []
        seen_texts: set[str] = set()

        for element in content_root.find_all(["p", "h2", "h3"]):
            if not isinstance(element, Tag):
                continue

            text = " ".join(element.get_text(" ", strip=True).split())
            if not self._is_body_text(text):
                continue
            if text in seen_texts:
                continue
            seen_texts.add(text)
            parts.append(text)

        description = self._extract_description(soup, parts)
        if not parts and description:
            parts.append(description)

        return author, description, normalize_text_blocks(parts)

    def _extract_author(self, content_root: Tag | BeautifulSoup) -> str:
        text = content_root.get_text("\n", strip=True)
        match = AUTHOR_RE.search(text)
        if not match:
            return ""
        return " ".join(match.group(1).split())

    def _extract_description(self, soup: BeautifulSoup, parts: list[str]) -> str:
        meta = soup.find("meta", attrs={"name": "description"})
        if isinstance(meta, Tag):
            content = " ".join(str(meta.get("content", "")).split())
            if self._is_body_text(content):
                return content
        return parts[0] if parts else ""

    def _is_body_text(self, text: str) -> bool:
        if not text:
            return False
        if any(text.startswith(prefix) for prefix in SKIP_PREFIXES):
            return False
        if any(marker in text for marker in SKIP_CONTAINS):
            return False
        if re.fullmatch(r"\[?\d+/\d+\]?", text):
            return False
        if text == "Next":
            return False
        if len(text) <= 3:
            return False
        return True

    def _normalize_title(self, title: str) -> str:
        title = re.sub(r"\s+", " ", title).strip()
        if title and title[-1] not in TITLE_ENDINGS:
            title += "."
        return title