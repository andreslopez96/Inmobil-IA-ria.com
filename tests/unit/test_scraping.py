import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from inmobil_iaria.config import AppConfig
from inmobil_iaria.sources.idealista_browser import (
    IdealistaBrowserSource,
    _major_version,
    discover_new_ids,
    scrape_report_assets,
)


def _search_html(*ids):
    articles = "".join(f'<article data-element-id="{value}"></article>' for value in ids)
    return f'<main class="listing-items">{articles}</main>'


def _detail_html(property_id=900):
    return f"""
    <span class="main-info__title-main">Piso luminoso {property_id}</span>
    <span class="main-info__title-minor">Centro, Zaragoza</span>
    <span class="txt-bold">125.000 €</span>
    <div class="details-property-feature-one">
      <li>80 m² construidos</li><li>3 habitaciones</li><li>2 baños</li>
    </div>
    <div class="details-property-feature-two"><li>Piscina</li></div>
    <picture class="first-image"><img src="cover.jpg"></picture>
    """


class _ImageElement:
    def screenshot(self, path):
        Path(path).write_bytes(b"fake-png")
        return True


class _Browser:
    def __init__(self, pages):
        self.pages = pages
        self.page_source = ""
        self.visited = []
        self.closed = False

    def get(self, url):
        self.visited.append(url)
        self.page_source = next(
            html for fragment, html in self.pages.items() if fragment in url
        )

    def find_element(self, by, selector):
        if by == "css selector":
            return _ImageElement()
        raise LookupError(selector)

    def quit(self):
        self.closed = True


class ScrapingTests(unittest.TestCase):
    def test_extracts_chrome_and_driver_major_versions(self):
        self.assertEqual(_major_version("Google Chrome 152.0.7977.83"), 152)
        self.assertEqual(
            _major_version("ChromeDriver 153.0.8010.36 (abcdef)"), 153
        )

    def test_returns_none_for_unknown_output(self):
        self.assertIsNone(_major_version("Chrome no disponible"))

    @patch("inmobil_iaria.sources.idealista_browser.time.sleep", return_value=None)
    def test_discovers_recent_ids_until_known_ids_are_consecutive(self, _sleep):
        browser = _Browser(
            {"pagina-1.htm": _search_html(900, 1, 901, 2, 3, 4)}
        )

        result = discover_new_ids(
            browser,
            {"1", "2", "3", "4"},
            repeat_limit=3,
        )

        self.assertEqual(result, ["900", "901"])
        self.assertEqual(len(browser.visited), 1)

    @patch("inmobil_iaria.sources.idealista_browser.time.sleep", return_value=None)
    def test_browser_source_scrapes_only_the_new_ids_and_closes(self, _sleep):
        with TemporaryDirectory() as directory:
            config = replace(
                AppConfig.from_env(Path(directory)), known_id_repeat_limit=2
            )
            browser = _Browser(
                {
                    "pagina-1.htm": _search_html(900, 1, 2),
                    "/inmueble/900/": _detail_html(900),
                }
            )
            source = IdealistaBrowserSource(
                config,
                browser_factory=lambda *_args, **_kwargs: browser,
            )

            properties = source.collect_new({1, 2})

        self.assertEqual([item.id for item in properties], [900])
        self.assertEqual(properties[0].Titulo, "Piso luminoso 900")
        self.assertTrue(browser.closed)

    @patch("inmobil_iaria.sources.idealista_browser.time.sleep", return_value=None)
    def test_scrapes_title_and_cover_only_for_selected_ids(self, _sleep):
        with TemporaryDirectory() as directory:
            config = AppConfig.from_env(Path(directory))
            browser = _Browser({"/inmueble/900/": _detail_html(900)})

            titles = scrape_report_assets(
                config,
                [900],
                browser_factory=lambda *_args, **_kwargs: browser,
            )

            cover = config.paths.reports / "900" / "cover.png"
            self.assertEqual(titles, {900: "Piso luminoso 900"})
            self.assertTrue(cover.exists())
            self.assertTrue(browser.closed)


if __name__ == "__main__":
    unittest.main()
