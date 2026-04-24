import re

from bs4 import BeautifulSoup


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def extract_visible_text(html: str) -> str:
    """Extract visible page text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    return soup.get_text(" ", strip=True)


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase alphanumeric tokens."""
    return TOKEN_PATTERN.findall(text.lower())


def html_to_tokens(html: str) -> list[str]:
    """Convert HTML into clean searchable tokens."""
    return tokenize(extract_visible_text(html))
