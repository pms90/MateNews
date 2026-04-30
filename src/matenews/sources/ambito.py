from __future__ import annotations

import re

from ..domain.models import Article, SourceBatch
from ..fetchers.http import HttpClient
from .base import BaseSource
from .shared import FAILED_TEXT, normalize_text_blocks


def _strip_markdown(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"^#+\s*(.*)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*[-+*]\s+)(.*)$", r"\2", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s*(.*)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


class AmbitoSource(BaseSource):
    def fetch(self, client: HttpClient) -> SourceBatch:
        raw_text = client.get_text(self.config.homepage_url)
        articles: list[Article] = []

        for chunk in raw_text.split("\n----"):
            if len(articles) >= self.config.limit:
                break

            try:
                element = chunk.split("\n")[-1]
                title = element.split("](")[0][1:]
                url = element.split("](")[1].split(" ")[0]
            except Exception:
                continue

            if not title or not url:
                continue
            if not title.endswith("."):
                title += "."

            try:
                text = self._fetch_text(client, url, title)
            except Exception:
                text = FAILED_TEXT

            articles.append(Article(title=title, url=url, text=text))

        return SourceBatch(source=self.config, articles=articles)

    def _fetch_text(self, client: HttpClient, url: str, title: str) -> str:
        raw_text = client.get_article_text(f"https://r.jina.ai/{url}")
        parts: list[str] = []
        for row in raw_text.split("\n"):
            stripped = row.strip()
            if not stripped:
                continue
            if stripped.startswith("Title: "):
                continue
            if stripped.startswith("Director: "):
                continue
            if stripped.startswith(title[:-1]):
                continue
            if stripped.startswith("==="):
                continue
            if stripped[0] in ["*", "[", "-", "!"]:
                continue
            if len(stripped) <= 100 or "http" in stripped:
                continue
            parts.append(_strip_markdown(stripped))

        return normalize_text_blocks(parts)