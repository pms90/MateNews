from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import unicodedata

from bs4 import BeautifulSoup

from ..sources.registry import get_source_definitions


_DATED_DIRECTORY_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-[^.]+$")
_ORIGINAL_URL_PATTERN = re.compile(r"window\.location\.href\s*=\s*(['\"])(?P<url>.+?)\1")
_SHARE_URL_PATTERN = re.compile(r"url\s*:\s*(['\"])(?P<url>.+?)\1")


@dataclass(slots=True, frozen=True)
class WeeklyNote:
    published_on: date
    date_label: str
    source_slug: str
    source_name: str
    title: str
    original_url: str
    content: str
    article_path: Path


@dataclass(slots=True, frozen=True)
class WeeklyMarkdownSummary:
    output_path: Path
    note_count: int
    date_count: int
    source_count: int


def export_weekly_markdown(
    docs_dir: Path = Path("docs"),
    output_path: Path = Path("weekly_md") / "semana_actual.md",
    source_selection: Mapping[str, bool] | None = None,
) -> WeeklyMarkdownSummary:
    notes = collect_weekly_notes(docs_dir, source_selection=source_selection)
    markdown_text = build_weekly_markdown(notes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_text, encoding="utf-8")
    return WeeklyMarkdownSummary(
        output_path=output_path,
        note_count=len(notes),
        date_count=len({note.date_label for note in notes}),
        source_count=len({note.source_slug for note in notes}),
    )


def collect_weekly_notes(
    docs_dir: Path,
    source_selection: Mapping[str, bool] | None = None,
) -> list[WeeklyNote]:
    notes: list[WeeklyNote] = []
    source_order = {
        definition.config.slug: index
        for index, definition in enumerate(get_source_definitions())
    }

    for source_slug, source_name, source_dir in _ordered_source_directories(
        docs_dir,
        source_selection=source_selection,
    ):
        for date_dir, published_on in _dated_directories(source_dir):
            for article_path in _article_pages(date_dir):
                notes.append(
                    parse_article_page(
                        article_path,
                        published_on=published_on,
                        date_label=date_dir.name,
                        source_slug=source_slug,
                        source_name=source_name,
                    )
                )
    notes.sort(
        key=lambda note: (
            note.published_on,
            source_order.get(note.source_slug, 10**9),
            _article_sort_key(note.article_path),
        )
    )
    return notes


def parse_article_page(
    article_path: Path,
    *,
    published_on: date,
    date_label: str,
    source_slug: str,
    source_name: str,
) -> WeeklyNote:
    soup = BeautifulSoup(article_path.read_text(encoding="utf-8"), "html.parser")
    text_container = soup.find(id="texto")
    title_node = None
    if text_container is not None:
        title_node = text_container.find("h1")
    if title_node is None:
        title_node = soup.find("h1") or soup.find("title")

    paragraphs: list[str] = []
    if text_container is not None:
        for paragraph in text_container.find_all("p"):
            paragraph_text = _clean_text(paragraph.get_text(" ", strip=True))
            if paragraph_text:
                paragraphs.append(paragraph_text)

    return WeeklyNote(
        published_on=published_on,
        date_label=date_label,
        source_slug=source_slug,
        source_name=source_name,
        title=_clean_text(title_node.get_text(" ", strip=True)) if title_node is not None else article_path.stem,
        original_url=_extract_original_url(soup),
        content="\n\n".join(paragraphs),
        article_path=article_path,
    )


def build_weekly_markdown(notes: list[WeeklyNote]) -> str:
    if not notes:
        return "# Resumen semanal\n\nNo se encontraron notas locales en docs/.\n"

    lines: list[str] = []
    current_date_label = ""
    current_source_slug = ""

    for note in notes:
        if note.date_label != current_date_label:
            if lines:
                lines.append("")
            lines.append(f"## {note.date_label}")
            lines.append("")
            current_date_label = note.date_label
            current_source_slug = ""

        if note.source_slug != current_source_slug:
            lines.append(f"### {note.source_name}")
            lines.append("")
            current_source_slug = note.source_slug

        lines.append(f"#### {note.title}")
        lines.append("")
        if note.original_url:
            lines.append(note.original_url)
            lines.append("")
        if note.content:
            lines.append(note.content)
        else:
            lines.append("No se encontro contenido local en docs/ para esta nota.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _ordered_source_directories(
    docs_dir: Path,
    source_selection: Mapping[str, bool] | None = None,
) -> list[tuple[str, str, Path]]:
    definitions = get_source_definitions()
    ordered_sources: list[tuple[str, str, Path]] = []
    seen_slugs: set[str] = set()

    for definition in definitions:
        source_dir = docs_dir / definition.config.slug
        if not source_dir.is_dir():
            continue
        ordered_sources.append((definition.config.slug, definition.config.name, source_dir))
        seen_slugs.add(definition.config.slug)

    extra_sources = sorted(
        [path for path in docs_dir.iterdir() if path.is_dir() and path.name not in {"prev", *seen_slugs}],
        key=lambda path: path.name,
    )
    for source_dir in extra_sources:
        ordered_sources.append((source_dir.name, source_dir.name.replace("_", " ").title(), source_dir))

    if source_selection is None:
        return ordered_sources

    selection_by_key = _normalize_source_selection(source_selection)
    known_keys = _known_source_keys(definitions, ordered_sources)
    unknown_keys = sorted(raw_key for raw_key in source_selection if _normalize_source_key(raw_key) not in known_keys)
    if unknown_keys:
        unknown_text = ", ".join(unknown_keys)
        raise ValueError(f"Fuentes desconocidas en source_selection: {unknown_text}")

    filtered_sources: list[tuple[str, str, Path]] = []
    for source_slug, source_name, source_dir in ordered_sources:
        include_source = _resolve_source_inclusion(source_slug, source_name, selection_by_key)
        if include_source:
            filtered_sources.append((source_slug, source_name, source_dir))

    return filtered_sources


def _normalize_source_selection(source_selection: Mapping[str, bool]) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    for raw_key, include_source in source_selection.items():
        normalized[_normalize_source_key(raw_key)] = bool(include_source)
    return normalized


def _known_source_keys(definitions, ordered_sources: list[tuple[str, str, Path]]) -> set[str]:
    known_keys: set[str] = set()
    for definition in definitions:
        known_keys.update(_source_key_aliases(definition.config.slug, definition.config.name))
    for source_slug, source_name, _ in ordered_sources:
        known_keys.update(_source_key_aliases(source_slug, source_name))
    return known_keys


def _resolve_source_inclusion(
    source_slug: str,
    source_name: str,
    selection_by_key: Mapping[str, bool],
) -> bool:
    matched_values = {
        selection_by_key[alias]
        for alias in _source_key_aliases(source_slug, source_name)
        if alias in selection_by_key
    }
    if len(matched_values) > 1:
        raise ValueError(f"Configuracion conflictiva para la fuente {source_name}")
    if matched_values:
        return matched_values.pop()
    return True


def _source_key_aliases(source_slug: str, source_name: str) -> set[str]:
    return {
        _normalize_source_key(source_slug),
        _normalize_source_key(source_name),
        _normalize_source_key(source_slug.replace("_", " ")),
    }


def _normalize_source_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    without_marks = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(without_marks.casefold().replace("_", " ").split())


def _dated_directories(source_dir: Path) -> list[tuple[Path, date]]:
    directories: list[tuple[Path, date]] = []
    for child in source_dir.iterdir():
        if not child.is_dir():
            continue
        parsed_date = _parse_dated_directory_name(child.name)
        if parsed_date is None:
            continue
        directories.append((child, parsed_date))
    return sorted(directories, key=lambda item: (item[1], item[0].name))


def _article_pages(date_dir: Path) -> list[Path]:
    html_pages = [path for path in date_dir.glob("*.html") if path.is_file()]
    return sorted(html_pages, key=_article_sort_key)


def _article_sort_key(article_path: Path) -> tuple[int, str]:
    try:
        return (int(article_path.stem), article_path.name)
    except ValueError:
        return (10**9, article_path.name)


def _parse_dated_directory_name(name: str) -> date | None:
    match = _DATED_DIRECTORY_PATTERN.match(name)
    if match is None:
        return None
    year, month, day = map(int, match.groups())
    return date(year, month, day)


def _extract_original_url(soup: BeautifulSoup) -> str:
    for button in soup.find_all("button"):
        if "Ver en web original" not in button.get_text(" ", strip=True):
            continue
        onclick = button.get("onclick", "")
        match = _ORIGINAL_URL_PATTERN.search(onclick)
        if match is not None:
            return match.group("url").strip()

    for script in soup.find_all("script"):
        script_text = script.string or script.get_text("\n", strip=False)
        if not script_text:
            continue
        match = _SHARE_URL_PATTERN.search(script_text)
        if match is not None:
            return match.group("url").strip()

    return ""


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())