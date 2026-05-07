import logging
import time
from collections import deque
from collections.abc import Callable
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "COMP3011-SearchEngineBot/1.0"
RETRYABLE_STATUS_CODES = {502, 503, 504}


class Crawler:
    def __init__(
        self,
        start_url: str,
        politeness_window: float = 6.0,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff: float = 1.5,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        obey_robots: bool = True,
    ) -> None:
        self.start_url = self.normalise_url(start_url)
        self.politeness_window = max(0.0, politeness_window)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.sleep = sleep
        self.obey_robots = obey_robots

        self.host = urlparse(self.start_url).netloc
        self.visited: set[str] = set()
        self.pages: dict[str, str] = {}
        self.failed: dict[str, str] = {}
        self.disallowed: list[str] = []
        self.last_request_time: float | None = None

        self.robot_parser = RobotFileParser()
        self.configure_robots()

    def configure_robots(self) -> None:
        if not self.obey_robots:
            return

        parsed = urlparse(self.start_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            response = self.session.get(robots_url, timeout=self.timeout)

            if response.status_code == 200:
                self.robot_parser.parse(response.text.splitlines())
            else:
                self.robot_parser.parse([])

        except requests.RequestException:
            self.robot_parser.parse([])

    def normalise_url(self, url: str, base_url: str | None = None) -> str:
        if base_url is not None:
            url = urljoin(base_url, url)

        url, _ = urldefrag(url.strip())
        parsed = urlparse(url)

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]

        if scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        path = parsed.path or "/"

        return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))

    def is_same_host(self, url: str) -> bool:
        return urlparse(url).netloc.lower() == self.host.lower()

    def allowed_by_robots(self, url: str) -> bool:
        if not self.obey_robots:
            return True

        try:
            return self.robot_parser.can_fetch(DEFAULT_USER_AGENT, url)
        except Exception:
            return True

    def wait_for_politeness(self) -> None:
        if self.last_request_time is None:
            return

        elapsed = time.monotonic() - self.last_request_time
        remaining = self.politeness_window - elapsed

        if remaining > 0:
            self.sleep(remaining)

    def fetch(self, url: str) -> str | None:
        wait = self.backoff

        for attempt in range(self.max_retries):
            self.wait_for_politeness()

            try:
                response = self.session.get(url, timeout=self.timeout)
                self.last_request_time = time.monotonic()

                content_type = response.headers.get("Content-Type", "")

                if response.status_code == 200:
                    if content_type and "html" not in content_type:
                        self.failed[url] = f"Non-HTML content: {content_type}"
                        return None

                    return response.text

                if 400 <= response.status_code < 500:
                    self.failed[url] = f"HTTP {response.status_code}"
                    return None

                if response.status_code in RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "Retryable HTTP %s for %s",
                        response.status_code,
                        url,
                    )

            except requests.RequestException as error:
                self.last_request_time = time.monotonic()
                self.failed[url] = str(error)

            if attempt < self.max_retries - 1:
                self.sleep(wait)
                wait *= self.backoff

        self.failed[url] = "Maximum retries exceeded"
        return None

    def extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")

            if not href:
                continue

            if isinstance(href, list):
                href = " ".join(href)

            if href.startswith(("mailto:", "javascript:", "tel:")):
                continue

            try:
                normalised = self.normalise_url(href, base_url)

            except ValueError:
                continue

            if self.is_same_host(normalised):
                links.append(normalised)

        return list(dict.fromkeys(links))

    def crawl(self, max_pages: int | None = None) -> dict[str, str]:
        self.visited.clear()
        self.pages.clear()
        self.failed.clear()
        self.disallowed.clear()

        queue: deque[str] = deque([self.start_url])
        seen: set[str] = {self.start_url}

        while queue:
            if max_pages is not None and len(self.pages) >= max_pages:
                break

            url = queue.popleft()

            if url in self.visited:
                continue

            if not self.allowed_by_robots(url):
                self.disallowed.append(url)
                continue

            print(f"Crawling {url}")

            html = self.fetch(url)

            self.visited.add(url)

            if html is None:
                continue

            self.pages[url] = html

            for link in self.extract_links(html, url):
                if link not in seen:
                    seen.add(link)
                    queue.append(link)

        return self.pages
