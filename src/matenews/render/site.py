from __future__ import annotations

from datetime import datetime
from html import escape

from matenews.domain.paths import current_article_relpath

from ..domain.models import Article, SourceBatch


def source_section_id(slug: str) -> str:
    return f"source-{slug}"


def build_article_html(text: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        paragraphs = ["No se pudo obtener texto."]
    return "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)


def article_href(batch: SourceBatch, article: Article, index: int, now: datetime) -> str:
    if not article.url:
        return ""
    if article.has_local_page:
        return current_article_relpath(batch.source, index, now).as_posix()
    return article.url


def render_index_section(batch: SourceBatch, now: datetime) -> str:
    rendered: list[str] = []
    homepage_url = escape(batch.source.homepage_url, quote=True)
    section_id = source_section_id(batch.source.slug)
    heading_id = f"{section_id}-heading"
    rendered.append(f'<section class="source-section" id="{section_id}" aria-labelledby="{heading_id}">')
    rendered.append(f'<h3 class="source-heading" id="{heading_id}"><a href="{homepage_url}">{escape(batch.source.name)}</a></h3>')
    rendered.append('<ol class="source-notes">')
    for index, article in enumerate(batch.articles, start=1):
        href = article_href(batch, article, index, now)
        note_id = f"{batch.source.slug}_{index - 1}"
        note_title = escape(f"{index}) {article.title}")
        if href:
            safe_href = escape(href, quote=True)
            rendered.append(f'<li class="nota" id="{note_id}"><a href="{safe_href}">{note_title}</a></li>')
        else:
            rendered.append(f'<li class="nota" id="{note_id}"><a>{note_title}</a></li>')
    rendered.append("</ol>")
    rendered.append("</section>")
    return "\n".join(rendered)


def render_index_sections(batches: list[SourceBatch], now: datetime) -> str:
    return "\n".join(render_index_section(batch, now) for batch in batches)


def render_index_page(
    template: str,
    frontend_date_text: str,
    frontend_time_text: str,
    sections_html: str,
    previous_edition_url: str,
) -> str:
    return (
        template.replace("__FECHA__", frontend_date_text)
        .replace("__HORA__", frontend_time_text)
        .replace("__SECCIONES__", sections_html)
        .replace("__LAST_PREV__", previous_edition_url)
    )


def render_article_page(template: str, article: Article) -> str:
    text_html = build_article_html(article.text)
    return (
        template.replace("__TITULO__", escape(article.title))
        .replace("__TEXTO__", text_html)
        .replace("__URL__", escape(article.url, quote=True))
    )