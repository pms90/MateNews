from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from ..fetchers.translate import TranslationClient, translate_to_spanish
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


TITLE_ENDINGS = ".!?:;"
SKIP_PREFIXES = (
    "Contact the writer at",
    "China Daily -",
)
SKIP_CONTAINS = (
    "@chinadaily.com.cn",
    "@chinadailyusa.com",
)


class ChinaDailySource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        rss_text = client.get_text(self.config.homepage_url, encoding="utf-8")
        root = ET.fromstring(rss_text)
        translator = TranslationClient()
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for item in root.findall("./channel/item"):
            url = self._item_text(item, "link")
            if not url or url in seen_urls:
                continue

            raw_title = self._item_text(item, "title")
            if not raw_title:
                continue

            raw_description = self._item_text(item, "description")
            raw_text = self._extract_text(item)
            translated_title = self._normalize_title(translate_to_spanish(raw_title, translator=translator))
            translated_description = translate_to_spanish(raw_description, translator=translator)
            translated_text = raw_text if raw_text == FAILED_TEXT else translate_to_spanish(raw_text, translator=translator)

            articles.append(
                Article(
                    title=translated_title or self._normalize_title(raw_title),
                    url=url,
                    description=translated_description,
                    text=translated_text,
                    author=self._item_text(item, "AuthorName"),
                )
            )
            seen_urls.add(url)

            if len(articles) >= self.config.limit:
                break

        return SourceBatch(source=self.config, articles=articles)

    def _item_text(self, item: ET.Element, tag_name: str) -> str:
        element = item.find(tag_name)
        if element is None:
            return ""
        return " ".join("".join(element.itertext()).split())

    def _extract_text(self, item: ET.Element) -> str:
        content_html = self._item_text(item, "content")
        if not content_html:
            description = self._item_text(item, "description")
            return description or FAILED_TEXT

        soup = BeautifulSoup(content_html, "html.parser")
        parts: list[str] = []
        seen_texts: set[str] = set()

        for element in soup.find_all(["p", "h2", "h3"]):
            text = " ".join(element.get_text(" ", strip=True).split())
            if not self._is_body_text(text):
                continue
            if text in seen_texts:
                continue
            seen_texts.add(text)
            parts.append(text)

        if not parts:
            description = self._item_text(item, "description")
            if description:
                parts.append(description)

        return normalize_text_blocks(parts)

    def _is_body_text(self, text: str) -> bool:
        if not text:
            return False
        if any(text.startswith(prefix) for prefix in SKIP_PREFIXES):
            return False
        if any(marker in text for marker in SKIP_CONTAINS):
            return False
        if len(text) <= 3:
            return False
        return True

    def _normalize_title(self, title: str) -> str:
        title = re.sub(r"\s+", " ", title).strip()
        if title and title[-1] not in TITLE_ENDINGS:
            title += "."
        return title