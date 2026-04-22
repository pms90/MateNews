from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from matenews.domain.dates import file_date_name, frontend_date
from matenews.domain.models import Article, RunConfig, SourceBatch, SourceConfig
from matenews.pipeline.runner import build_site
from matenews.publish import default_commit_message, sync_site_directory
from matenews.render.site import render_article_page, render_index_sections


ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
FIXED_NOW = datetime(2026, 4, 21, 12, 0, tzinfo=ARGENTINA_TZ)
REPO_ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_date_contract_matches_notebook(self) -> None:
        self.assertEqual(file_date_name(FIXED_NOW), "2026-04-21-Martes")
        self.assertEqual(frontend_date(FIXED_NOW), "Martes 21 abril 2026")

    def test_sections_link_to_local_article_when_text_exists(self) -> None:
        batch = SourceBatch(
            source=SourceConfig(name="Infobae", slug="infobae", homepage_url="https://www.infobae.com"),
            articles=[Article(title="Titulo.", url="https://example.com/nota", text="Parrafo uno.")],
        )

        rendered = render_index_sections([batch], FIXED_NOW)

        self.assertIn('href="infobae/2026-04-21-Martes/1.html"', rendered)
        self.assertIn('1) Titulo.', rendered)

    def test_article_template_receives_title_url_and_text(self) -> None:
        template = (REPO_ROOT / "templates" / "noticia.html").read_text(encoding="utf-8")
        article = Article(
            title="Titulo de prueba.",
            url="https://example.com/nota",
            text="Primer parrafo.\n\nSegundo parrafo.",
        )

        rendered = render_article_page(template, article)

        self.assertIn("<title>Titulo de prueba.</title>", rendered)
        self.assertIn("<p>Primer parrafo.</p><p>Segundo parrafo.</p>", rendered)
        self.assertIn("https://example.com/nota", rendered)

    def test_build_writes_current_and_archived_local_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "site"
            config = RunConfig(
                output_dir=output_dir,
                templates_dir=REPO_ROOT / "templates",
                assets_dir=REPO_ROOT / "assets",
                site_url="https://matenews.github.io/MateNews",
            )
            batch = SourceBatch(
                source=SourceConfig(name="Infobae", slug="infobae", homepage_url="https://www.infobae.com"),
                articles=[Article(title="Titulo.", url="https://example.com", text="Texto local.")],
            )

            build_site([batch], config=config, now=FIXED_NOW)

            self.assertTrue((output_dir / "index.html").exists())
            self.assertTrue((output_dir / "prev" / "2026-04-21-Martes.html").exists())
            self.assertTrue((output_dir / "infobae" / "2026-04-21-Martes" / "1.html").exists())
            self.assertTrue((output_dir / "prev" / "infobae" / "2026-04-21-Martes" / "1.html").exists())
            self.assertTrue((output_dir / "infobae" / "index_section.html").exists())

    def test_build_reuses_cached_section_for_unscheduled_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "site"
            config = RunConfig(
                output_dir=output_dir,
                templates_dir=REPO_ROOT / "templates",
                assets_dir=REPO_ROOT / "assets",
                site_url="https://matenews.github.io/MateNews",
            )
            source = SourceConfig(
                name="El Cohete a la Luna",
                slug="el_cohete_a_la_luna",
                homepage_url="https://www.elcohetealaluna.com",
                day_codes=("Do", "Lu"),
            )
            monday = datetime(2026, 4, 20, 12, 0, tzinfo=ARGENTINA_TZ)
            tuesday = datetime(2026, 4, 21, 12, 0, tzinfo=ARGENTINA_TZ)
            monday_batch = SourceBatch(
                source=source,
                articles=[Article(title="Titulo lunes.", url="https://example.com", text="Texto lunes.")],
            )

            build_site([monday_batch], config=config, now=monday, selected_slugs={source.slug})
            build_site([], config=config, now=tuesday, selected_slugs={source.slug})

            tuesday_index = (output_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("Titulo lunes.", tuesday_index)
            self.assertIn("el_cohete_a_la_luna/2026-04-20-Lunes/1.html", tuesday_index)

    def test_sync_site_directory_replaces_target_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_dir = temp_root / "site"
            target_dir = temp_root / "docs"
            (source_dir / "prev").mkdir(parents=True)
            (source_dir / "index.html").write_text("home", encoding="utf-8")
            (source_dir / "prev" / "a.html").write_text("prev", encoding="utf-8")

            target_dir.mkdir()
            (target_dir / "stale.txt").write_text("old", encoding="utf-8")

            synchronized = sync_site_directory(source_dir, target_dir)

            self.assertEqual(synchronized, 2)
            self.assertTrue((target_dir / "index.html").exists())
            self.assertTrue((target_dir / "prev" / "a.html").exists())
            self.assertFalse((target_dir / "stale.txt").exists())

    def test_default_commit_message_is_stable(self) -> None:
        now = datetime(2026, 4, 22, 15, 45, 0)
        self.assertEqual(default_commit_message(now), "Publish MateNews site 2026-04-22 15:45:00")


if __name__ == "__main__":
    unittest.main()