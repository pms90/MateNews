from __future__ import annotations

from datetime import datetime
import re
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
        return "./"

    current_date = _parse_prev_filename_date(current_filename)
    candidates = [path for path in prev_dir.glob("*.html") if path.name != current_filename]
    dated_candidates = [path for path in candidates if _parse_prev_filename_date(path.name) is not None]
    if current_date is not None:
        dated_candidates = [path for path in dated_candidates if _parse_prev_filename_date(path.name) < current_date]

    if not dated_candidates:
        return "./"

    latest = max(dated_candidates, key=lambda path: _parse_prev_filename_date(path.name))
    return f"prev/{latest.name}"


def _parse_prev_filename_date(filename: str) -> datetime | None:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-[^.]+\.html$", filename)
    if match is None:
        return None

    year, month, day = map(int, match.groups())
    return datetime(year, month, day)