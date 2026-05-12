import re

from bs4 import BeautifulSoup


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "hers", "him", "his", "i", "if", "in", "into",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours",
    "she", "should", "so", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "was",
    "we", "were", "what", "when", "where", "which", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours",
}


def extract_visible_text(html: str) -> str:
    """Extract visible searchable text from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    return soup.get_text(" ", strip=True)


def tokenize(text: str, remove_stopwords: bool = False) -> list[str]:
    """Convert text into lowercase alphanumeric tokens."""
    tokens = TOKEN_PATTERN.findall(text.lower())

    if remove_stopwords:
        return [token for token in tokens if token not in STOPWORDS]

    return tokens


def html_to_tokens(html: str, remove_stopwords: bool = False) -> list[str]:
    """Convert HTML into clean searchable tokens."""
    return tokenize(
        extract_visible_text(html),
        remove_stopwords=remove_stopwords,
    )
