from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


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


def _clean_html_text(value: str) -> str:
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _extract_fusion_global_content(html: str) -> dict[str, object] | None:
    marker = "Fusion.globalContent="
    start = html.find(marker)
    if start == -1:
        return None

    json_start = html.find("{", start)
    if json_start == -1:
        return None

    depth = 0
    in_string = False
    escaping = False

    for index in range(json_start, len(html)):
        char = html[index]
        if escaping:
            escaping = False
            continue
        if char == "\\":
            escaping = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
            continue
        if char != "}":
            continue

        depth -= 1
        if depth == 0:
            payload = html[json_start : index + 1]
            try:
                loaded = json.loads(payload)
            except json.JSONDecodeError:
                return None
            return loaded if isinstance(loaded, dict) else None

    return None


def _collect_content_blocks(node: object) -> list[str]:
    parts: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return

        content = value.get("content")
        if isinstance(content, str) and value.get("type") in {"text", "raw_html"}:
            cleaned = _clean_html_text(content)
            if len(cleaned) >= 30:
                parts.append(cleaned)

        nested = value.get("content_elements")
        if isinstance(nested, list):
            visit(nested)

    visit(node)
    return parts


class Pagina12Source(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        soup = client.get_soup(self.config.homepage_url)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for block in soup.find_all("div", class_="p12-article-card-full")[: self.config.limit]:
            link = block.find("a", href=True)
            if link is None:
                continue

            title = _sentenceize_html_fragments(str(block))
            url = urljoin(self.config.base_url or self.config.homepage_url, link["href"])
            if not title or not url or url in seen_urls:
                continue
            seen_urls.add(url)

            author = ""
            author_element = block.find("span", class_="article-author")
            if author_element is not None:
                author_link = author_element.find("a")
                if author_link is not None:
                    author = author_link.get_text(strip=True)
                else:
                    author = author_element.get_text(" ", strip=True).replace("Por", "", 1).strip()

            try:
                text = self._fetch_text(client, url)
            except Exception:
                text = FAILED_TEXT

            articles.append(Article(title=title, url=url, text=text, author=author))

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str) -> str:
        html = client.get_article_text(url)
        payload = _extract_fusion_global_content(html)
        if payload is not None:
            parts = _collect_content_blocks(payload.get("content_elements", []))
            text = normalize_text_blocks(parts)
            if text != FAILED_TEXT:
                return text

        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("article", class_="p12-article-body")
        if body is None:
            return FAILED_TEXT

        parts: list[str] = []
        seen_texts: set[str] = set()

        for paragraph in body.find_all("p"):
            if not isinstance(paragraph, Tag):
                continue
            if "c-paragraph" not in paragraph.get("class", []):
                continue

            text = " ".join(paragraph.get_text(" ", strip=True).split())
            if len(text) < 30 or text in seen_texts:
                continue

            seen_texts.add(text)
            parts.append(text)

        return normalize_text_blocks(parts)