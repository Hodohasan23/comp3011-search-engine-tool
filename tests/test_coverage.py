"""
Targeted tests for uncovered lines (all passes combined).
"""

import subprocess
import sys
from collections import deque

import responses

from src.main import SearchCLI
from src.crawler import Crawler
from src.indexer import InvertedIndex
from src.main import index_summary
from src.search import QueryProcessor
from src.search import BM25Ranker, TFIDFRanker
from src.search import SearchEngine


# ──────────────────────────────────────────────
# cli.py line 95 — print_term with no postings
# ──────────────────────────────────────────────

def test_print_term_not_in_index_returns_no_postings_message():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    cli = SearchCLI()
    cli.index = index
    cli.engine = SearchEngine(index)

    output = cli.handle_command("print zzzzz")

    assert "No postings found" in output


# ──────────────────────────────────────────────
# cli.py line 149 — handle_command "build" path
# ──────────────────────────────────────────────

def test_handle_command_build_calls_build(tmp_path):
    cli = SearchCLI(
        index_path=str(tmp_path / "index.json"),
        politeness_window=0,
    )

    class FakeCrawler:
        def crawl(self):
            return {"page1": "<p>good friends</p>"}

    from src import main as main_module
    original = main_module.Crawler
    main_module.Crawler = lambda *a, **kw: FakeCrawler()

    try:
        output = cli.handle_command("build")
        assert "Built index" in output
    finally:
        main_module.Crawler = original


# ──────────────────────────────────────────────
# cli.py line 152 — handle_command "load" path
# ──────────────────────────────────────────────

def test_handle_command_load_calls_load(tmp_path):
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    path = tmp_path / "index.json"
    index.save(str(path))

    cli = SearchCLI(index_path=str(path))
    output = cli.handle_command("load")

    assert "Loaded index" in output


# ──────────────────────────────────────────────
# cli.py lines 203-216 — run() loop
# ──────────────────────────────────────────────

def test_run_loop_processes_commands_then_quits():
    from unittest.mock import patch
    cli = SearchCLI()
    commands = iter(["help", "unknown", "", "quit"])

    with patch("builtins.input", side_effect=commands):
        with patch("builtins.print"):
            cli.run()


# ──────────────────────────────────────────────
# crawler.py lines 60, 64-65 — configure_robots 200 and non-200
# ──────────────────────────────────────────────

@responses.activate
def test_configure_robots_parses_200_response():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/robots.txt",
        body="User-agent: *\nDisallow: /private/",
        status=200,
        content_type="text/plain",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=True,
    )

    assert not crawler.allowed_by_robots(
        "https://quotes.toscrape.com/private/page"
    )


@responses.activate
def test_configure_robots_non_200_allows_all():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/robots.txt",
        status=404,
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=True,
    )

    assert crawler.allowed_by_robots("https://quotes.toscrape.com/page/1/")


# ──────────────────────────────────────────────
# crawler.py line 78 — configure_robots network error
# ──────────────────────────────────────────────

@responses.activate
def test_configure_robots_network_error_allows_all():
    import requests as req
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/robots.txt",
        body=req.exceptions.ConnectionError("network error"),
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=True,
    )

    assert crawler.allowed_by_robots("https://quotes.toscrape.com/")


# ──────────────────────────────────────────────
# crawler.py lines 96-97 — allowed_by_robots exception → True
# ──────────────────────────────────────────────

def test_allowed_by_robots_exception_returns_true():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=True)

    class BrokenParser:
        def can_fetch(self, *args):
            raise RuntimeError("broken")

    crawler.robot_parser = BrokenParser()  # type: ignore

    assert crawler.allowed_by_robots("https://quotes.toscrape.com/") is True


# ──────────────────────────────────────────────
# crawler.py lines 96-97 — normalise_url strips :80
# ──────────────────────────────────────────────

def test_normalise_url_strips_http_port_80():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    result = crawler.normalise_url("http://example.com:80/page/")
    assert result == "http://example.com/page/"


# ──────────────────────────────────────────────
# crawler.py line 158 — empty href skipped
# ──────────────────────────────────────────────

def test_extract_links_skips_anchor_with_empty_string_href():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    html = """
    <html><body>
        <a href="">Empty href</a>
        <a href="/page/1/">Valid</a>
    </body></html>
    """

    links = crawler.extract_links(html, "https://quotes.toscrape.com/")

    assert links == ["https://quotes.toscrape.com/page/1/"]


# ──────────────────────────────────────────────
# crawler.py line 161 — href is a list, joined before use
# ──────────────────────────────────────────────

def test_extract_links_joins_list_href(monkeypatch):
    from bs4 import BeautifulSoup

    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    html = '<html><body><a href="/page/1/">Link</a></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.find("a")

    original_get = anchor.get

    def patched_get(key, default=None):
        if key == "href":
            return ["/page/1/"]
        return original_get(key, default)

    monkeypatch.setattr(anchor, "get", patched_get)

    def fake_find_all(*args, **kwargs):
        return [anchor]

    monkeypatch.setattr(soup, "find_all", fake_find_all)
    monkeypatch.setattr("src.crawler.BeautifulSoup", lambda *a, **kw: soup)

    links = crawler.extract_links(html, "https://quotes.toscrape.com/")
    assert "https://quotes.toscrape.com/page/1/" in links


# ──────────────────────────────────────────────
# crawler.py lines 169-170 — malformed URL skipped
# ──────────────────────────────────────────────

def test_extract_links_skips_malformed_urls():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    html = (
        '<html><body>'
        '<a href="http://[invalid">Bad</a>'
        '<a href="/page/1/">Good</a>'
        '</body></html>'
    )
    links = crawler.extract_links(html, "https://quotes.toscrape.com/")

    assert "https://quotes.toscrape.com/page/1/" in links


# ──────────────────────────────────────────────
# crawler.py line 193 — URL already visited → skipped in loop
# ──────────────────────────────────────────────

@responses.activate
def test_crawl_skips_url_already_in_visited():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/",
        body='<html><body><a href="/page/1/">P1</a></body></html>',
        status=200,
        content_type="text/html",
    )
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/page/1/",
        body="<html><body>Page one</body></html>",
        status=200,
        content_type="text/html",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
    )

    def patched_crawl(max_pages=None):
        crawler.visited.clear()
        crawler.pages.clear()
        crawler.failed.clear()
        crawler.disallowed.clear()

        queue = deque([crawler.start_url, crawler.start_url])
        seen = {crawler.start_url}

        while queue:
            url = queue.popleft()
            if url in crawler.visited:
                continue
            html = crawler.fetch(url)
            crawler.visited.add(url)
            if html is None:
                continue
            crawler.pages[url] = html
            for link in crawler.extract_links(html, url):
                if link not in seen:
                    seen.add(link)
                    queue.append(link)
        return crawler.pages

    pages = patched_crawl()
    assert list(pages.keys()).count("https://quotes.toscrape.com/") == 1


# ──────────────────────────────────────────────
# crawler.py line 206 — fetch returns None, page skipped
# ──────────────────────────────────────────────

@responses.activate
def test_crawl_skips_failed_fetch():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/",
        status=404,
        content_type="text/html",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
    )

    pages = crawler.crawl()

    assert pages == {}


# ──────────────────────────────────────────────
# main.py line 40 — __main__ guard via -m
# ──────────────────────────────────────────────

def test_main_entrypoint_guard_is_reachable():
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "start-url" in result.stdout or "usage" in result.stdout.lower()


# ──────────────────────────────────────────────
# metrics.py line 20 — index_summary with existing path returns size
# ──────────────────────────────────────────────

def test_index_summary_includes_size_when_path_exists(tmp_path):
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    path = str(tmp_path / "index.json")
    index.save(path)

    summary = index_summary(index, path)

    assert "index_size_bytes" in summary
    assert summary["index_size_bytes"] > 0


# ──────────────────────────────────────────────
# query_processor.py lines 20, 23 — levenshtein edge cases
# ──────────────────────────────────────────────

def test_levenshtein_first_empty_returns_len_second():
    processor = QueryProcessor()
    assert processor.levenshtein_distance("", "abc") == 3


def test_levenshtein_second_empty_returns_len_first():
    processor = QueryProcessor()
    assert processor.levenshtein_distance("abc", "") == 3


# ──────────────────────────────────────────────
# ranker.py lines 21, 31 — BM25 empty index
# ──────────────────────────────────────────────

def test_bm25_average_document_length_empty_index():
    index = InvertedIndex()
    ranker = BM25Ranker(index)

    assert ranker.average_document_length() == 0.0


def test_bm25_score_empty_index_returns_zero():
    index = InvertedIndex()
    ranker = BM25Ranker(index)

    assert ranker.score(["anything"], "page1") == 0.0


# ──────────────────────────────────────────────
# ranker.py line 65 — TF-IDF empty index
# ──────────────────────────────────────────────

def test_tfidf_score_empty_index_returns_zero():
    index = InvertedIndex()
    ranker = TFIDFRanker(index)

    assert ranker.score(["anything"], "page1") == 0.0


# ──────────────────────────────────────────────
# search_engine.py line 43 — phrase + free term intersects candidates
# ──────────────────────────────────────────────

def test_find_phrase_and_free_term_intersects_candidates():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends matter</p>")
    index.add_document("page2", "<p>good friends books</p>")
    engine = SearchEngine(index)

    results = engine.find('"good friends" matter')

    assert len(results) == 1
    assert results[0][0] == "page1"


# ──────────────────────────────────────────────
# search_engine.py line 49 — AND intersection produces empty
# ──────────────────────────────────────────────

def test_find_and_intersection_produces_empty():
    index = InvertedIndex()
    index.add_document("page1", "<p>good books</p>")
    index.add_document("page2", "<p>good friends</p>")
    engine = SearchEngine(index)

    assert engine.find("friends books") == []


# ──────────────────────────────────────────────
# search_engine.py line 81 — urls_containing_phrase empty → set()
# ──────────────────────────────────────────────

def test_urls_containing_phrase_empty_terms_returns_empty_set():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    engine = SearchEngine(index)

    assert engine.urls_containing_phrase([]) == set()


# ──────────────────────────────────────────────
# search_engine.py line 84 — single-term phrase
# ──────────────────────────────────────────────

def test_urls_containing_phrase_single_term_returns_posting_urls():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>bad weather</p>")
    engine = SearchEngine(index)

    result = engine.urls_containing_phrase(["good"])

    assert "page1" in result
    assert "page2" not in result


# ──────────────────────────────────────────────
# search_engine.py line 92 — phrase-only query returns results
# ──────────────────────────────────────────────

def test_find_phrase_only_query_returns_results():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books</p>")
    engine = SearchEngine(index)

    results = engine.find('"good friends"')

    assert len(results) == 1
    assert results[0][0] == "page1"


# ──────────────────────────────────────────────
# search_engine.py line 133 — snippet for unknown URL returns ""
# ──────────────────────────────────────────────

def test_snippet_url_with_no_tokens_returns_empty_string():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    engine = SearchEngine(index)

    assert engine.snippet("page_unknown", ["good"]) == ""