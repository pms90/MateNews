from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .dates import file_date_name
from .models import RunConfig, SourceConfig


def current_article_relpath(source: SourceConfig, index: int, now: datetime) -> Path:
    return Path(source.slug) / file_date_name(now) / f"{index}.html"


def archived_article_relpath(source: SourceConfig, index: int, now: datetime) -> Path:
    return Path("prev") / source.slug / file_date_name(now) / f"{index}.html"


def current_article_path(config: RunConfig, source: SourceConfig, index: int, now: datetime) -> Path:
    return config.output_dir / current_article_relpath(source, index, now)


def archived_article_path(config: RunConfig, source: SourceConfig, index: int, now: datetime) -> Path:
    return config.output_dir / archived_article_relpath(source, index, now)


def current_prev_index_path(config: RunConfig, now: datetime) -> Path:
    return config.output_dir / "prev" / f"{file_date_name(now)}.html"


def resolve_previous_edition_url(config: RunConfig, current_filename: str) -> str:
    prev_dir = config.output_dir / "prev"
    if not prev_dir.exists():
        return config.site_url.rstrip("/") + "/"

    candidates = sorted(path.name for path in prev_dir.glob("*.html") if path.name != current_filename)
    if not candidates:
        return config.site_url.rstrip("/") + "/"

    return f"{config.site_url.rstrip('/')}/prev/{candidates[-1]}"