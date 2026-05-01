import time
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class Crawler:
    def __init__(
        self,
        start_url: str,
        politeness_window: float = 6.0,
        timeout: int = 10,
    ) -> None:
        self.start_url = start_url
        self.politeness_window = politeness_window
        self.timeout = timeout

        self.visited: set[str] = set()
        self.pages: dict[str, str] = {}

    def normalise_url(self, url: str) -> str:
        """Remove fragments and normalise URL formatting."""
        clean_url, _ = urldefrag(url)

        parsed = urlparse(clean_url)

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        path = parsed.path or "/"

        return f"{scheme}://{netloc}{path}"

    def is_same_host(self, url: str) -> bool:
        """Restrict crawling to the original host."""
        return (
            urlparse(url).netloc.lower()
            == urlparse(self.start_url).netloc.lower()
        )

    def extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract valid same-host links from a page."""
        soup = BeautifulSoup(html, "html.parser")

        links = []

        for tag in soup.find_all("a", href=True):
            absolute_url = urljoin(base_url, tag["href"])

            absolute_url = self.normalise_url(absolute_url)

            if self.is_same_host(absolute_url):
                links.append(absolute_url)

        return links

    def crawl(self) -> dict[str, str]:
        """Crawl pages using breadth-first traversal."""
        queue = deque([self.normalise_url(self.start_url)])

        while queue:
            url = queue.popleft()

            if url in self.visited:
                continue

            print(f"Crawling {url}")

            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()

                html = response.text

                self.visited.add(url)
                self.pages[url] = html

                links = self.extract_links(html, url)

                for link in links:
                    if link not in self.visited:
                        queue.append(link)

                time.sleep(self.politeness_window)

            except requests.RequestException as error:
                print(f"Failed to crawl {url}: {error}")

        return self.pages
