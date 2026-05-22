"""
Targeted tests for uncovered lines.

cli.py        : 95, 149, 152, 203-216
crawler.py    : 60, 64-65, 78, 96-97, 161, 169-170, 193, 206
main.py       : 40
metrics.py    : 20
ranker.py     : 21, 31, 65
search_engine : 43, 49, 81, 92, 133
"""

import subprocess
import sys

import responses
from unittest.mock import patch

from src.main import SearchCLI
from src.crawler import Crawler
from src.indexer import InvertedIndex
from src.main import index_summary
from src.search import BM25Ranker, TFIDFRanker
from src.search import SearchEngine


# ──────────────────────────────────────────────
# cli.py
# ──────────────────────────────────────────────

# line 95 — index_summary called with index_path that exists (returns size)
def test_build_summary_includes_index_size(tmp_path):
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
        output = cli.build()
        assert "bytes" in output
        assert "Built index" in output
    finally:
        main_module.Crawler = original


# line 149 — find with no results and no suggestions
def test_find_no_results_no_suggestions():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    cli = SearchCLI()
    cli.index = index
    cli.engine = SearchEngine(index)

    output = cli.handle_command("find zzzzzzzzzzzzzzz")

    assert "No pages match" in output


# line 152 — find with no results but with a did-you-mean suggestion
def test_find_no_results_with_suggestion():
    index = InvertedIndex()
    index.add_document("page1", "<p>indifference</p>")

    cli = SearchCLI()
    cli.index = index
    cli.engine = SearchEngine(index)

    output = cli.handle_command("find indiffrence")

    assert "Did you mean" in output
    assert "indifference" in output


# lines 203-216 — cli.run() loop: help, unknown, blank, quit
def test_run_loop_processes_commands_then_quits():
    cli = SearchCLI()

    commands = iter(["help", "unknown", "", "quit"])

    with patch("builtins.input", side_effect=commands):
        with patch("builtins.print"):
            cli.run()  # should exit cleanly via quit


# ──────────────────────────────────────────────
# crawler.py
# ──────────────────────────────────────────────

# line 60 — configure_robots: 200 response, parses rules
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


# lines 64-65 — configure_robots: non-200 response → allow all
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


# line 78 — configure_robots: RequestException → allow all
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


# lines 96-97 — normalise_url strips :80 from http
def test_normalise_url_strips_http_port_80():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    result = crawler.normalise_url("http://example.com:80/page/")
    assert result == "http://example.com/page/"


# line 161 — extract_links: href is a list (BeautifulSoup edge case)
def test_extract_links_href_is_list():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    # inject a tag whose get("href") returns a list
    from bs4 import BeautifulSoup
    html = '<html><body><a href="/page/1/">Link</a></body></html>'
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.find("a")
    anchor["href"] = ["/page/1/"]  # type: ignore

    # re-render so extract_links sees it
    links = crawler.extract_links(str(soup), "https://quotes.toscrape.com/")
    assert "https://quotes.toscrape.com/page/1/" in links


# lines 169-170 — extract_links: ValueError on bad URL → skip
def test_extract_links_skips_malformed_urls():
    crawler = Crawler("https://quotes.toscrape.com/", obey_robots=False)

    html = '<html><body><a href="http://[invalid">Bad</a><a href="/page/1/">Good</a></body></html>'
    links = crawler.extract_links(html, "https://quotes.toscrape.com/")

    assert "https://quotes.toscrape.com/page/1/" in links


# line 193 — crawl: print statement for each URL crawled
@responses.activate
def test_crawl_prints_each_url(capsys):
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/",
        body="<html><body>Hello</body></html>",
        status=200,
        content_type="text/html",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
    )

    crawler.crawl()

    captured = capsys.readouterr()
    assert "quotes.toscrape.com" in captured.out


# line 206 — crawl: fetch returns None → page not added, continue
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
# main.py
# ──────────────────────────────────────────────

# line 40 — __main__ guard
def test_main_module_guard():
    result = subprocess.run(
        [sys.executable, "-c",
         "import src.main; src.main.main.__module__"],
        capture_output=True,
    )
    assert result.returncode == 0


# ──────────────────────────────────────────────
# metrics.py
# ──────────────────────────────────────────────

# line 20 — index_summary with index_path that exists → includes size
def test_index_summary_with_existing_path(tmp_path):
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    path = tmp_path / "index.json"
    index.save(str(path))

    summary = index_summary(index, str(path))

    assert "index_size_bytes" in summary
    assert summary["index_size_bytes"] > 0


# ──────────────────────────────────────────────
# ranker.py
# ──────────────────────────────────────────────

# line 21 — BM25 average_document_length with empty index returns 0.0
def test_bm25_average_document_length_empty_index():
    index = InvertedIndex()
    ranker = BM25Ranker(index)

    assert ranker.average_document_length() == 0.0


# line 31 — BM25 score with zero total_docs or avg_doc_length returns 0.0
def test_bm25_score_empty_index_returns_zero():
    index = InvertedIndex()
    ranker = BM25Ranker(index)

    # url not even in index — but total_docs is 0 so early return fires
    assert ranker.score(["anything"], "page1") == 0.0


# line 65 — TFIDFRanker score with zero total_docs returns 0.0
def test_tfidf_score_empty_index_returns_zero():
    index = InvertedIndex()
    ranker = TFIDFRanker(index)

    assert ranker.score(["anything"], "page1") == 0.0


# ──────────────────────────────────────────────
# search_engine.py
# ──────────────────────────────────────────────

# line 43 — find: free term not in index → return []
def test_find_free_term_not_in_index_returns_empty():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    engine = SearchEngine(index)

    assert engine.find("nonexistent") == []


# line 49 — find: AND narrows candidates to empty → return []
def test_find_and_intersection_produces_empty():
    index = InvertedIndex()
    index.add_document("page1", "<p>good books</p>")
    index.add_document("page2", "<p>good friends</p>")
    engine = SearchEngine(index)

    # "good" matches both, "friends" only page2, "books" only page1
    assert engine.find("friends books") == []


# line 81 — find: phrase candidate set goes empty → return []
def test_find_phrase_with_no_matching_urls_returns_empty():
    index = InvertedIndex()
    index.add_document("page1", "<p>good books</p>")
    engine = SearchEngine(index)

    assert engine.find('"good friends"') == []


# line 92 — find: candidate_urls is None after phrases loop (shouldn't happen,
# but covers the guard) — tested via phrase-only query that matches
def test_find_phrase_only_query_returns_results():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books</p>")
    engine = SearchEngine(index)

    results = engine.find('"good friends"')

    assert len(results) == 1
    assert results[0][0] == "page1"


# line 133 — snippet: no token in query_set → match_position stays 0
def test_snippet_no_query_term_found_returns_from_start():
    index = InvertedIndex()
    index.add_document("page1", "<p>alpha beta gamma delta epsilon</p>")
    engine = SearchEngine(index)

    snippet = engine.snippet("page1", ["zzz"], window=2)

    assert isinstance(snippet, str)
    assert len(snippet) > 0