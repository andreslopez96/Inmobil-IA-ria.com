"""Scraper operativo de Idealista con navegador controlado por Selenium."""

from __future__ import annotations

import platform
import random
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from ..config import AppConfig
from ..domain.properties import RawProperty


SEARCH_URL = (
    "https://www.idealista.com/venta-viviendas/zaragoza-zaragoza/"
    "pagina-{page}.htm?ordenado-por=fecha-publicacion-desc"
)


def _major_version(text: str) -> int | None:
    match = re.search(r"\b(\d+)\.\d+\.\d+\.\d+\b", text)
    return int(match.group(1)) if match else None


def _command_version(command: list[str]) -> int | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        return None
    return _major_version(f"{result.stdout} {result.stderr}")


def detect_chrome_major() -> int | None:
    system = platform.system()
    if system == "Darwin":
        commands = [
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "--version",
            ],
            [
                "/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                "--version",
            ],
        ]
    elif system == "Windows":
        commands = [["powershell", "-NoProfile", "-Command", "(Get-Command chrome).Source"]]
    else:
        commands = [
            [executable, "--version"]
            for name in (
                "google-chrome",
                "google-chrome-stable",
                "chromium",
                "chromium-browser",
            )
            if (executable := shutil.which(name))
        ]

    for command in commands:
        version = _command_version(command)
        if version is not None:
            return version
    return None


def _cached_drivers() -> list[Path]:
    home = Path.home()
    candidates = [
        home
        / "Library"
        / "Application Support"
        / "undetected_chromedriver"
        / "undetected_chromedriver",
        home / ".local" / "share" / "undetected_chromedriver" / "undetected_chromedriver",
    ]
    return [path for path in candidates if path.is_file()]


def _remove_incompatible_cached_driver(
    chrome_major: int | None, progress: "Progress"
) -> None:
    if chrome_major is None:
        return
    for driver in _cached_drivers():
        driver_major = _command_version([str(driver), "--version"])
        if driver_major is not None and driver_major != chrome_major:
            progress(
                f"🧹 ChromeDriver {driver_major} no coincide con Chrome "
                f"{chrome_major}; eliminando únicamente el driver en caché"
            )
            driver.unlink()


def _user_agent(chrome_major: int | None = None) -> str:
    system = platform.system()
    platform_token = {
        "Windows": "Windows NT 10.0; Win64; x64",
        "Darwin": "Macintosh; Intel Mac OS X 10_15_7",
    }.get(system, "X11; Linux x86_64")
    return (
        f"Mozilla/5.0 ({platform_token}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{chrome_major or 120}.0.0.0 Safari/537.36"
    )


def create_browser(
    headless: bool = False,
    *,
    progress: "Progress" = print,
):
    import undetected_chromedriver as uc

    chrome_major = detect_chrome_major()
    if chrome_major is None:
        progress("⚠️ No se pudo detectar la versión de Chrome automáticamente")
    else:
        progress(f"🌐 Chrome detectado: versión principal {chrome_major}")
    _remove_incompatible_cached_driver(chrome_major, progress)

    last_error: Exception | None = None
    for attempt in range(2):
        options = uc.ChromeOptions()
        options.add_argument(f"--user-agent={_user_agent(chrome_major)}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-dev-shm-usage")
        if headless:
            options.add_argument("--headless=new")

        arguments: dict[str, object] = {
            "options": options,
            "use_subprocess": True,
        }
        if chrome_major is not None:
            arguments["version_main"] = chrome_major

        try:
            browser = uc.Chrome(**arguments)
            browser.set_page_load_timeout(60)
            return browser
        except Exception as error:
            last_error = error
            if attempt == 1 or "only supports Chrome version" not in str(error):
                raise
            progress("🔄 El driver descargado no coincide; limpiando caché y reintentando")
            for driver in _cached_drivers():
                driver.unlink(missing_ok=True)

    raise RuntimeError("No se pudo iniciar Chrome") from last_error


Progress = Callable[[str], None]


def _silent(_: str) -> None:
    pass


def discover_new_ids(
    browser,
    known: set[str],
    repeat_limit: int = 5,
    *,
    progress: Progress = _silent,
) -> list[str]:
    found: list[str] = []
    repeated = 0
    page = 1
    while repeated < repeat_limit:
        url = SEARCH_URL.format(page=page)
        progress(f"🌍 Rastreando página {page}: {url}")
        browser.get(url)
        time.sleep(random.uniform(8, 15))
        try:
            browser.find_element("xpath", '//*[@id="didomi-notice-agree-button"]').click()
        except Exception:
            pass

        soup = BeautifulSoup(browser.page_source, "lxml")
        listing = soup.find("main", {"class": "listing-items"})
        if listing is None:
            raise RuntimeError(
                "Idealista no devolvio el listado esperado; revisa el navegador o la VPN"
            )
        articles = listing.find_all("article")
        progress(f"🏠 Página {page}: {len(articles)} anuncios encontrados")
        for article in articles:
            property_id = article.get("data-element-id")
            if not property_id:
                continue
            if str(property_id) in known:
                repeated += 1
                progress(
                    f"↩️ ID conocido {property_id} "
                    f"({repeated}/{repeat_limit} consecutivos)"
                )
                if repeated >= repeat_limit:
                    break
            else:
                repeated = 0
                if str(property_id) not in found:
                    found.append(str(property_id))
                    progress(f"➕ Nuevo ID añadido: {property_id}")
        page += 1
        if repeated < repeat_limit:
            time.sleep(random.uniform(5, 10))
    progress(f"✅ Rastreo terminado: {len(found)} IDs nuevos")
    return found


def scrape_details(
    browser,
    property_ids: list[str],
    *,
    retry_callback: Callable[[str], None] | None = None,
    progress: Progress = _silent,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total = len(property_ids)
    for position, property_id in enumerate(property_ids, start=1):
        progress(f"🔎 Extrayendo ID {property_id} ({position}/{total})")
        url = f"https://www.idealista.com/inmueble/{property_id}/"
        soup = None
        for attempt in range(2):
            browser.get(url)
            time.sleep(random.uniform(4, 6))
            soup = BeautifulSoup(browser.page_source, "lxml")
            if soup.find("span", {"class": "main-info__title-main"}):
                break
            if attempt == 0 and retry_callback:
                retry_callback(property_id)
        if soup is None:
            continue

        title = soup.find("span", {"class": "main-info__title-main"})
        location = soup.find("span", {"class": "main-info__title-minor"})
        price = soup.find("span", {"class": "txt-bold"})
        basic = soup.find("div", {"class": "details-property-feature-one"})
        extra = soup.find("div", {"class": "details-property-feature-two"})
        if title is None or price is None:
            progress(f"⚠️ No se pudieron extraer los datos del ID {property_id}")
            continue

        rows.append(
            {
                "id": property_id,
                "Titulo": title.get_text(strip=True),
                "Localizacion": (
                    location.get_text(strip=True).split(",")[0] if location else None
                ),
                "Precio": int(
                    price.get_text(strip=True).replace(".", "").replace("€", "")
                ),
                "Caracteristicas_basicas": "; ".join(
                    item.get_text(strip=True) for item in basic.find_all("li")
                )
                if basic
                else None,
                "Caracteristicas_extra": "; ".join(
                    item.get_text(strip=True) for item in extra.find_all("li")
                )
                if extra
                else None,
            }
        )
        progress(f"💾 ID {property_id} preparado para guardar")
    return pd.DataFrame(rows)


class IdealistaBrowserSource:
    """Descubre IDs recientes y extrae los datos de cada anuncio nuevo."""

    name = "idealista_browser"

    def __init__(
        self,
        config: AppConfig,
        *,
        progress: Progress = print,
        browser_factory=None,
    ):
        self.config = config
        self.progress = progress
        self.browser_factory = browser_factory or create_browser

    def collect_new(self, known_ids: set[int]) -> list[RawProperty]:
        browser = self.browser_factory(
            self.config.headless,
            progress=self.progress,
        )
        try:
            known = {str(value) for value in known_ids}
            self.progress(f"📚 IDs ya conocidos: {len(known)}")
            discovered = discover_new_ids(
                browser,
                known,
                repeat_limit=self.config.known_id_repeat_limit,
                progress=self.progress,
            )
            if not discovered:
                return []
            details = scrape_details(browser, discovered, progress=self.progress)
        finally:
            browser.quit()

        if details.empty:
            self.progress("ℹ️ No hay inmuebles nuevos con datos completos")
            return []
        return [
            RawProperty.from_mapping(record)
            for record in details.to_dict(orient="records")
        ]


def browser_source_from_config(
    config: AppConfig,
    *,
    progress: Progress = print,
) -> IdealistaBrowserSource:
    return IdealistaBrowserSource(config, progress=progress)


def scrape_report_assets(
    config: AppConfig,
    property_ids: list[int],
    *,
    progress: Progress = print,
    browser_factory=None,
) -> dict[int, str]:
    """Obtiene título y portada solo de los anuncios aprobados por el usuario."""

    if not property_ids:
        return {}
    factory = browser_factory or create_browser
    browser = factory(config.headless, progress=progress)
    titles: dict[int, str] = {}
    try:
        total = len(property_ids)
        for position, property_id in enumerate(property_ids, start=1):
            progress(f"🖼️ Título y portada del ID {property_id} ({position}/{total})")
            browser.get(f"https://www.idealista.com/inmueble/{property_id}/")
            time.sleep(random.uniform(4, 6))
            soup = BeautifulSoup(browser.page_source, "lxml")
            title = soup.find("span", {"class": "main-info__title-main"})
            if title is not None:
                titles[int(property_id)] = title.get_text(" ", strip=True)

            report_dir = config.paths.reports / str(int(property_id))
            report_dir.mkdir(parents=True, exist_ok=True)
            cover = report_dir / "cover.png"
            temporary_cover = report_dir / ".cover.tmp.png"
            try:
                image = browser.find_element(
                    "css selector", "picture.first-image img"
                )
                if not image.screenshot(str(temporary_cover)):
                    raise RuntimeError("el navegador no pudo capturar la portada")
                temporary_cover.replace(cover)
            except Exception as error:
                temporary_cover.unlink(missing_ok=True)
                progress(f"⚠️ No se pudo guardar la portada del ID {property_id}: {error}")
    finally:
        browser.quit()
    return titles


def run_scraping(
    config: AppConfig,
    *,
    progress: Progress = print,
) -> list[int]:
    """Compatibilidad con llamadas antiguas; usa el mismo workflow de guardado."""

    from ..workflow import collect_new_properties

    return collect_new_properties(
        config.paths,
        browser_source_from_config(config, progress=progress),
    )
