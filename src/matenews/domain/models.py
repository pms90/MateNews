from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DAY_CODES = ("Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do")


@dataclass(slots=True, frozen=True)
class SourceConfig:
    name: str
    slug: str
    homepage_url: str
    base_url: str = ""
    limit: int = 16
    day_codes: tuple[str, ...] = DEFAULT_DAY_CODES
    enabled: bool = True


@dataclass(slots=True)
class Article:
    title: str
    url: str = ""
    text: str = ""
    description: str = ""
    author: str = ""

    @property
    def has_local_page(self) -> bool:
        return bool(self.text.strip())


@dataclass(slots=True)
class SourceBatch:
    source: SourceConfig
    articles: list[Article] = field(default_factory=list)


@dataclass(slots=True)
class RunConfig:
    output_dir: Path = Path("site")
    templates_dir: Path = Path("templates")
    assets_dir: Path = Path("assets")
    site_url: str = "https://pms90.github.io/MateNews"
    keep_prev_count: int = 3