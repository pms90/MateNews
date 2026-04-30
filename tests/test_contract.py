from __future__ import annotations

import argparse
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from matenews.cli import handle_build
from matenews.domain.dates import file_date_name, frontend_date
from matenews.domain.models import Article, RunConfig, SourceBatch, SourceConfig
from matenews.domain.paths import resolve_previous_edition_url
from matenews.fetchers.http import HttpClient
from matenews.pipeline.runner import build_site, fetch_source_batches
from matenews.publish import default_commit_message, sync_site_directory
from matenews.render.site import render_article_page, render_index_sections
from matenews.sources.lanacion import LanacionSource
from matenews.sources.letrap import LetraPSource
from matenews.sources.registry import get_source_definitions


ARGENTINA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
FIXED_NOW = datetime(2026, 4, 21, 12, 0, tzinfo=ARGENTINA_TZ)
REPO_ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_http_client_get_does_not_sleep_for_generic_requests(self) -> None:
        client = HttpClient()
        response = MagicMock()
        response.raise_for_status.return_value = None
        client.session.get = MagicMock(return_value=response)

        with patch("matenews.fetchers.http.time.sleep") as sleep_mock:
            client.get("https://example.com")

        sleep_mock.assert_not_called()
        client.session.get.assert_called_once_with("https://example.com", timeout=30.0)

    def test_http_client_get_article_applies_base_delay_plus_jitter(self) -> None:
        client = HttpClient()
        response = MagicMock()
        response.raise_for_status.return_value = None
        client.session.get = MagicMock(return_value=response)

        with patch("matenews.fetchers.http.random.uniform", return_value=0.07) as uniform_mock:
            with patch("matenews.fetchers.http.time.sleep") as sleep_mock:
                client.get_article("https://example.com/nota")

        uniform_mock.assert_called_once_with(0.05, 0.1)
        sleep_mock.assert_called_once()
        self.assertAlmostEqual(sleep_mock.call_args.args[0], 0.12)
        client.session.get.assert_called_once_with("https://example.com/nota", timeout=30.0)

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
                site_url="https://pms90.github.io/MateNews",
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

    def test_build_removes_source_directories_older_than_seven_days(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "site"
            config = RunConfig(
                output_dir=output_dir,
                templates_dir=REPO_ROOT / "templates",
                assets_dir=REPO_ROOT / "assets",
                site_url="https://pms90.github.io/MateNews",
            )
            batch = SourceBatch(
                source=SourceConfig(name="Infobae", slug="infobae", homepage_url="https://www.infobae.com"),
                articles=[Article(title="Titulo.", url="https://example.com", text="Texto local.")],
            )

            old_current_dir = output_dir / "infobae" / "2026-04-13-Lunes"
            retained_current_dir = output_dir / "infobae" / "2026-04-14-Martes"
            old_archived_dir = output_dir / "prev" / "infobae" / "2026-04-13-Lunes"
            retained_archived_dir = output_dir / "prev" / "infobae" / "2026-04-14-Martes"
            old_current_dir.mkdir(parents=True)
            retained_current_dir.mkdir(parents=True)
            old_archived_dir.mkdir(parents=True)
            retained_archived_dir.mkdir(parents=True)
            (old_current_dir / "1.html").write_text("old", encoding="utf-8")
            (retained_current_dir / "1.html").write_text("keep", encoding="utf-8")
            (old_archived_dir / "1.html").write_text("old", encoding="utf-8")
            (retained_archived_dir / "1.html").write_text("keep", encoding="utf-8")

            build_site([batch], config=config, now=FIXED_NOW)

            self.assertFalse(old_current_dir.exists())
            self.assertTrue(retained_current_dir.exists())
            self.assertFalse(old_archived_dir.exists())
            self.assertTrue(retained_archived_dir.exists())

    def test_fetch_source_batches_logs_sources_and_articles(self) -> None:
        class DummySource:
            def __init__(self) -> None:
                self.config = SourceConfig(name="Diario de prueba", slug="diario_prueba", homepage_url="https://example.com")

            def fetch(self, client):
                return SourceBatch(
                    source=self.config,
                    articles=[Article(title="Nota 1"), Article(title="Nota 2")],
                )

        with patch("matenews.pipeline.runner.get_source_instances", return_value=[DummySource()]):
            with self.assertLogs("matenews.pipeline.runner", level="INFO") as captured:
                fetch_source_batches(ignore_schedule=True)

        output = "\n".join(captured.output)
        self.assertIn("Recuperando diario Diario de prueba (https://example.com)", output)
        self.assertIn("Diario Diario de prueba: 2 articulos recuperados", output)
        self.assertIn("Articulo recuperado [Diario de prueba] Nota 1", output)
        self.assertIn("Articulo recuperado [Diario de prueba] Nota 2", output)

    def test_previous_edition_url_uses_sibling_path_inside_prev(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "site"
            config = RunConfig(
                output_dir=output_dir,
                templates_dir=REPO_ROOT / "templates",
                assets_dir=REPO_ROOT / "assets",
                site_url="https://pms90.github.io/MateNews",
            )
            prev_dir = output_dir / "prev"
            prev_dir.mkdir(parents=True)
            (prev_dir / "2026-04-21-Martes.html").write_text("prev", encoding="utf-8")
            (prev_dir / "2026-04-22-Miercoles.html").write_text("prev", encoding="utf-8")

            self.assertEqual(
                resolve_previous_edition_url(config, "2026-04-22-Miercoles.html"),
                "prev/2026-04-21-Martes.html",
            )
            self.assertEqual(
                resolve_previous_edition_url(
                    config,
                    "2026-04-22-Miercoles.html",
                    inside_prev_dir=True,
                ),
                "2026-04-21-Martes.html",
            )

    def test_build_reuses_cached_section_for_unscheduled_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "site"
            config = RunConfig(
                output_dir=output_dir,
                templates_dir=REPO_ROOT / "templates",
                assets_dir=REPO_ROOT / "assets",
                site_url="https://pms90.github.io/MateNews",
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

    def test_letra_p_registration_and_url_filter(self) -> None:
        definitions = get_source_definitions()
        self.assertIn("letra_p", {definition.config.slug for definition in definitions})

        source = LetraPSource(
            SourceConfig(
                name="Letra P",
                slug="letra_p",
                homepage_url="https://www.letrap.com.ar/",
                base_url="https://www.letrap.com.ar",
            )
        )

        self.assertTrue(
            source._is_article_url(
                "https://www.letrap.com.ar/politica/la-grieta-y-la-interna-del-gobierno-convirtieron-el-homenaje-al-papa-francisco-un-campo-batalla-n5423312"
            )
        )
        self.assertFalse(source._is_article_url("https://www.letrap.com.ar/seccion/politica"))
        self.assertFalse(source._is_article_url("https://www.letrap.com.ar/region/buenos-aires"))

    def test_handle_build_fetches_selected_but_renders_cached_sections(self) -> None:
        args = argparse.Namespace(
            sources=["letra_p"],
            output_dir="site",
            site_url="https://pms90.github.io/MateNews",
            all_sources=False,
        )

        with patch("matenews.pipeline.runner.fetch_source_batches", return_value=[] ) as fetch_mock:
            with patch("matenews.pipeline.runner.build_site") as build_mock:
                result = handle_build(args)

        self.assertEqual(result, 0)
        fetch_mock.assert_called_once_with(selected_slugs={"letra_p"}, ignore_schedule=False)
        _, build_kwargs = build_mock.call_args
        self.assertIn("config", build_kwargs)
        self.assertNotIn("selected_slugs", build_kwargs)

    def test_la_nacion_registration_and_url_filter(self) -> None:
        definitions = get_source_definitions()
        self.assertIn("la_nacion", {definition.config.slug for definition in definitions})

        source = LanacionSource(
            SourceConfig(
                name="La Nación",
                slug="la_nacion",
                homepage_url="https://www.lanacion.com.ar/",
                base_url="https://www.lanacion.com.ar",
            )
        )

        self.assertTrue(
            source._is_article_url(
                "https://www.lanacion.com.ar/politica/el-gobierno-denuncio-a-dos-periodistas-por-grabar-en-los-pasillos-de-la-casa-rosada-nid22042026/"
            )
        )
        self.assertFalse(source._is_article_url("https://www.lanacion.com.ar/politica/"))
        self.assertFalse(source._is_article_url("https://www.lanacion.com.ar/tema/gobierno/"))


if __name__ == "__main__":
    unittest.main()