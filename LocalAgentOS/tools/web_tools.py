"""tools/web_tools.py — Headless Chrome browsing and scraping via Selenium."""
from __future__ import annotations
import logging
from typing import Any

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from config import SELENIUM_HEADLESS, SELENIUM_PAGE_LOAD_TIMEOUT_S, SELENIUM_TIMEOUT_S

logger = logging.getLogger(__name__)


class WebTool:
    """Headless Chrome-based web browsing and scraping."""

    def __init__(self) -> None:
        self._driver: webdriver.Chrome | None = None

    def _get_driver(self) -> webdriver.Chrome:
        if self._driver is None:
            opts = Options()
            if SELENIUM_HEADLESS:
                opts.add_argument("--headless=new")
            for arg in ["--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
                        "--disable-extensions","--blink-settings=imagesEnabled=false","--window-size=1280,800"]:
                opts.add_argument(arg)
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=opts)
            self._driver.set_page_load_timeout(SELENIUM_PAGE_LOAD_TIMEOUT_S)
            logger.info("Chrome WebDriver started")
        return self._driver

    def quit(self) -> None:
        if self._driver:
            self._driver.quit()
            self._driver = None

    def navigate(self, url: str) -> str:
        """Navigate to url and return rendered HTML. Returns empty string on timeout."""
        driver = self._get_driver()
        try:
            driver.get(url)
        except TimeoutException:
            logger.warning("Page load timeout for %s — returning empty", url)
            return ""
        return driver.page_source

    def get_text(self, url: str) -> str:
        """Navigate to url and return clean visible text."""
        html = self.navigate(url)
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script","style","nav","footer","header","aside"]):
            tag.decompose()
        lines = [ln for ln in soup.get_text(separator="\n", strip=True).splitlines() if ln.strip()]
        return "\n".join(lines)

    def find_elements(self, css_selector: str) -> list[dict[str, str]]:
        """Return text/attributes of all elements matching css_selector."""
        driver = self._get_driver()
        elements = driver.find_elements(By.CSS_SELECTOR, css_selector)
        return [{"tag": el.tag_name, "text": el.text.strip()[:500],
                 "href": el.get_attribute("href") or "", "id": el.get_attribute("id") or ""}
                for el in elements]

    def click_element(self, css_selector: str, timeout: int = SELENIUM_TIMEOUT_S) -> None:
        driver = self._get_driver()
        el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
        el.click()

    def fill_input(self, css_selector: str, value: str) -> None:
        driver = self._get_driver()
        el = driver.find_element(By.CSS_SELECTOR, css_selector)
        el.clear()
        el.send_keys(value)

    def execute_js(self, script: str, *args: Any) -> Any:
        return self._get_driver().execute_script(script, *args)

    def current_url(self) -> str:
        return self._get_driver().current_url

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "web_tools",
            "description": "Browse websites, scrape text and structured data, fill forms, click elements, execute JavaScript.",
            "keywords": ["web","browser","scrape","crawl","url","navigate","html","javascript","form","search","internet","page"],
        }
