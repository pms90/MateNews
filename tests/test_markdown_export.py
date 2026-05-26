from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from matenews.export.markdown import export_weekly_markdown, parse_article_page


class MarkdownExportTests(unittest.TestCase):
    def test_parse_article_page_extracts_title_url_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            article_path = Path(temp_dir) / "1.html"
            article_path.write_text(
                """
                <html>
                  <body>
                    <div id="texto">
                      <h1>Titulo de prueba</h1>
                      <p>Primer parrafo.</p>
                      <p>Segundo parrafo.</p>
                    </div>
                    <button class="btnL" onclick="window.location.href='https://example.com/nota'">Ver en web original</button>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )

            note = parse_article_page(
                article_path,
                published_on=date(2026, 5, 13),
                date_label="2026-05-13-Miercoles",
                source_slug="infobae",
                source_name="Infobae",
            )

            self.assertEqual(note.title, "Titulo de prueba")
            self.assertEqual(note.original_url, "https://example.com/nota")
            self.assertEqual(note.content, "Primer parrafo.\n\nSegundo parrafo.")

    def test_export_weekly_markdown_orders_dates_and_excludes_prev(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            docs_dir = repo_root / "docs"
            output_path = repo_root / "weekly_md" / "semana_actual.md"

            self._write_article(
                docs_dir / "infobae" / "2026-05-13-Miercoles" / "2.html",
                title="Infobae dos",
                url="https://example.com/infobae-2",
                paragraphs=["Contenido infobae 2."],
            )
            self._write_article(
                docs_dir / "infobae" / "2026-05-12-Martes" / "1.html",
                title="Infobae uno",
                url="https://example.com/infobae-1",
                paragraphs=["Contenido infobae 1."],
            )
            self._write_article(
                docs_dir / "pagina_12" / "2026-05-13-Miercoles" / "1.html",
                title="Pagina 12 uno",
                url="https://example.com/pagina-12-1",
                paragraphs=["Contenido pagina 12 1."],
            )
            self._write_article(
              docs_dir / "pagina_12" / "2026-05-12-Martes" / "2.html",
              title="Pagina 12 dos",
              url="https://example.com/pagina-12-2",
              paragraphs=["Contenido pagina 12 2."],
            )
            self._write_article(
                docs_dir / "prev" / "infobae" / "2026-05-11-Lunes" / "1.html",
                title="No debe aparecer",
                url="https://example.com/no",
                paragraphs=["Contenido previo."],
            )

            summary = export_weekly_markdown(docs_dir=docs_dir, output_path=output_path)
            markdown_text = output_path.read_text(encoding="utf-8")

            self.assertEqual(summary.note_count, 4)
            self.assertEqual(summary.date_count, 2)
            self.assertEqual(summary.source_count, 2)
            self.assertNotIn("No debe aparecer", markdown_text)
            self.assertLess(markdown_text.index("## 2026-05-12-Martes"), markdown_text.index("## 2026-05-13-Miercoles"))
            first_date_block = markdown_text.split("## 2026-05-13-Miercoles", maxsplit=1)[0]
            self.assertLess(first_date_block.index("### Infobae"), first_date_block.index("### P\u00e1gina 12"))
            self.assertIn("#### Infobae uno", markdown_text)
            self.assertIn("https://example.com/infobae-1", markdown_text)
            self.assertIn("#### Pagina 12 dos", markdown_text)
            self.assertIn("Contenido pagina 12 1.", markdown_text)

    def test_export_weekly_markdown_filters_sources_with_boolean_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            docs_dir = repo_root / "docs"
            output_path = repo_root / "weekly_md" / "semana_actual.md"

            self._write_article(
                docs_dir / "infobae" / "2026-05-13-Miercoles" / "1.html",
                title="Infobae uno",
                url="https://example.com/infobae-1",
                paragraphs=["Contenido infobae 1."],
            )
            self._write_article(
                docs_dir / "pagina_12" / "2026-05-13-Miercoles" / "1.html",
                title="Pagina 12 uno",
                url="https://example.com/pagina-12-1",
                paragraphs=["Contenido pagina 12 1."],
            )

            summary = export_weekly_markdown(
                docs_dir=docs_dir,
                output_path=output_path,
                source_selection={"Infobae": True, "Página 12": False},
            )
            markdown_text = output_path.read_text(encoding="utf-8")

            self.assertEqual(summary.note_count, 1)
            self.assertEqual(summary.source_count, 1)
            self.assertIn("### Infobae", markdown_text)
            self.assertNotIn("### Página 12", markdown_text)
            self.assertNotIn("Contenido pagina 12 1.", markdown_text)

    def _write_article(self, article_path: Path, *, title: str, url: str, paragraphs: list[str]) -> None:
        article_path.parent.mkdir(parents=True, exist_ok=True)
        article_path.write_text(
            """
            <html>
              <body>
                <div id="texto">
                  <h1>{title}</h1>
                  {paragraphs}
                </div>
                <button class="btnL" onclick="window.location.href='{url}'">Ver en web original</button>
              </body>
            </html>
            """.format(
                title=title,
                url=url,
                paragraphs="".join(f"<p>{paragraph}</p>" for paragraph in paragraphs),
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()