from __future__ import annotations

from datetime import datetime, timedelta
import logging
from pathlib import Path
import re
from shutil import copy2, rmtree

from ..domain.dates import argentina_now, file_date_name, frontend_date, short_day_code
from ..domain.models import RunConfig, SourceBatch
from ..domain.paths import (
    archived_article_path,
    current_article_path,
    current_prev_index_path,
    resolve_previous_edition_url,
)
from ..fetchers.http import HttpClient
from ..render.site import render_article_page, render_index_page, render_index_section
from ..sources.registry import get_source_definitions, get_source_instances


logger = logging.getLogger(__name__)
_DATED_DIRECTORY_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-[^.]+$")


def fetch_source_batches(
    selected_slugs: set[str] | None = None,
    client: HttpClient | None = None,
    now: datetime | None = None,
    ignore_schedule: bool = False,
) -> list[SourceBatch]:
    http_client = client or HttpClient()
    current_time = argentina_now(now)
    current_day = short_day_code(current_time)
    batches: list[SourceBatch] = []
    for source in get_source_instances(selected_slugs=selected_slugs):
        if not source.config.enabled:
            continue
        if not ignore_schedule and current_day not in source.config.day_codes:
            continue
        logger.info("Recuperando diario %s (%s)", source.config.name, source.config.homepage_url)
        try:
            batch = source.fetch(http_client)
        except Exception:
            logger.exception(
                "Fallo la recuperacion del diario %s (%s)",
                source.config.name,
                source.config.homepage_url,
            )
            continue
        logger.info(
            "Diario %s: %s articulos recuperados",
            source.config.name,
            len(batch.articles),
        )
        for article in batch.articles:
            logger.info("Articulo recuperado [%s] %s", source.config.name, article.title)
        batches.append(batch)
    return batches


def build_site(
    batches: list[SourceBatch],
    config: RunConfig | None = None,
    now: datetime | None = None,
    selected_slugs: set[str] | None = None,
) -> Path:
    build_config = config or RunConfig()
    current_time = argentina_now(now)
    output_dir = build_config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prev").mkdir(parents=True, exist_ok=True)
    _cleanup_expired_source_directories(output_dir, current_time)

    index_template = (build_config.templates_dir / "index.html").read_text(encoding="utf-8")
    article_template = (build_config.templates_dir / "noticia.html").read_text(encoding="utf-8")

    current_prev_name = f"{file_date_name(current_time)}.html"
    sections_html = _collect_sections_html(batches, build_config, current_time, selected_slugs)
    root_previous_edition_url = resolve_previous_edition_url(build_config, current_prev_name)
    prev_previous_edition_url = resolve_previous_edition_url(
        build_config,
        current_prev_name,
        inside_prev_dir=True,
    )
    index_html = render_index_page(index_template, frontend_date(current_time), sections_html, root_previous_edition_url)
    prev_index_html = render_index_page(index_template, frontend_date(current_time), sections_html, prev_previous_edition_url)

    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    current_prev_index_path(build_config, current_time).write_text(prev_index_html, encoding="utf-8")

    for batch in batches:
        for index, article in enumerate(batch.articles, start=1):
            if not article.has_local_page:
                continue

            article_html = render_article_page(article_template, article)
            current_path = current_article_path(build_config, batch.source, index, current_time)
            archived_path = archived_article_path(build_config, batch.source, index, current_time)

            current_path.parent.mkdir(parents=True, exist_ok=True)
            archived_path.parent.mkdir(parents=True, exist_ok=True)

            current_path.write_text(article_html, encoding="utf-8")
            archived_path.write_text(article_html, encoding="utf-8")

    _copy_assets(build_config)
    return output_dir


def _collect_sections_html(
    batches: list[SourceBatch],
    config: RunConfig,
    now: datetime,
    selected_slugs: set[str] | None,
) -> str:
    batch_by_slug = {batch.source.slug: batch for batch in batches}
    rendered_sections: list[str] = []

    for definition in get_source_definitions():
        slug = definition.config.slug
        if selected_slugs and slug not in selected_slugs:
            continue

        if slug in batch_by_slug:
            section_html = render_index_section(batch_by_slug[slug], now)
            _section_cache_path(config, slug).parent.mkdir(parents=True, exist_ok=True)
            _section_cache_path(config, slug).write_text(section_html, encoding="utf-8")
            rendered_sections.append(section_html)
            continue

        cached_section_path = _section_cache_path(config, slug)
        if cached_section_path.exists():
            rendered_sections.append(cached_section_path.read_text(encoding="utf-8"))

    return "\n".join(rendered_sections)


def _section_cache_path(config: RunConfig, slug: str) -> Path:
    return config.output_dir / slug / "index_section.html"


def _cleanup_expired_source_directories(output_dir: Path, now: datetime, retention_days: int = 7) -> None:
    cutoff_date = argentina_now(now).date() - timedelta(days=retention_days)

    for source_dir in output_dir.iterdir():
        if not source_dir.is_dir() or source_dir.name == "prev":
            continue
        _remove_expired_dated_directories(source_dir, cutoff_date)

    prev_dir = output_dir / "prev"
    if not prev_dir.exists():
        return

    for source_dir in prev_dir.iterdir():
        if not source_dir.is_dir():
            continue
        _remove_expired_dated_directories(source_dir, cutoff_date)


def _remove_expired_dated_directories(source_dir: Path, cutoff_date) -> None:
    for child in source_dir.iterdir():
        if not child.is_dir():
            continue

        child_date = _parse_dated_directory_name(child.name)
        if child_date is None or child_date >= cutoff_date:
            continue

        rmtree(child)


def _parse_dated_directory_name(name: str):
    match = _DATED_DIRECTORY_PATTERN.match(name)
    if match is None:
        return None

    year, month, day = map(int, match.groups())
    return datetime(year, month, day).date()


def _copy_assets(config: RunConfig) -> None:
    if not config.assets_dir.exists():
        return

    for asset in config.assets_dir.iterdir():
        if asset.is_file():
            destination = config.output_dir / asset.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy2(asset, destination)