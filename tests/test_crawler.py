import responses

from src.crawler import Crawler


@responses.activate
def test_crawler_fetches_page():
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

    pages = crawler.crawl()

    assert "https://quotes.toscrape.com/" in pages


def test_normalise_url_removes_fragment():
    crawler = Crawler(
        "https://quotes.toscrape.com/",
        obey_robots=False,
    )

    url = crawler.normalise_url(
        "https://quotes.toscrape.com/page/1/#section"
    )

    assert url == "https://quotes.toscrape.com/page/1/"


def test_same_host_validation():
    crawler = Crawler(
        "https://quotes.toscrape.com/",
        obey_robots=False,
    )

    assert crawler.is_same_host(
        "https://quotes.toscrape.com/page/2/"
    )

    assert not crawler.is_same_host(
        "https://google.com/"
    )


@responses.activate
def test_crawler_ignores_external_links():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/",
        body="""
        <html>
            <body>
                <a href="https://google.com/">Google</a>
            </body>
        </html>
        """,
        status=200,
        content_type="text/html",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
    )

    crawler.crawl()

    assert len(crawler.pages) == 1


@responses.activate
def test_fetch_retries_then_succeeds():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/",
        status=503,
        content_type="text/html",
    )

    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/",
        body="<html><body>Success</body></html>",
        status=200,
        content_type="text/html",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
        backoff=0,
    )

    html = crawler.fetch("https://quotes.toscrape.com/")

    assert html is not None
    assert "Success" in html


def test_allowed_by_robots_returns_boolean():
    crawler = Crawler("https://quotes.toscrape.com/")

    assert isinstance(
        crawler.allowed_by_robots("https://quotes.toscrape.com/"),
        bool,
    )

@responses.activate
def test_fetch_returns_none_for_404():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/missing",
        status=404,
        content_type="text/html",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
    )

    result = crawler.fetch(
        "https://quotes.toscrape.com/missing"
    )

    assert result is None


@responses.activate
def test_fetch_skips_non_html_content():
    responses.add(
        responses.GET,
        "https://quotes.toscrape.com/file.pdf",
        body="PDF",
        status=200,
        content_type="application/pdf",
    )

    crawler = Crawler(
        "https://quotes.toscrape.com/",
        politeness_window=0,
        obey_robots=False,
    )

    result = crawler.fetch(
        "https://quotes.toscrape.com/file.pdf"
    )

    assert result is None


def test_normalise_url_drops_default_ports():
    crawler = Crawler(
        "https://quotes.toscrape.com/",
        obey_robots=False,
    )

    result = crawler.normalise_url(
        "HTTPS://Quotes.toscrape.com:443/page/1/"
    )

    assert result == "https://quotes.toscrape.com/page/1/"


def test_extract_links_removes_duplicates():
    crawler = Crawler(
        "https://quotes.toscrape.com/",
        obey_robots=False,
    )

    html = """
    <html>
        <body>
            <a href="/page/1/">One</a>
            <a href="/page/1/">Duplicate</a>
        </body>
    </html>
    """

    links = crawler.extract_links(
        html,
        "https://quotes.toscrape.com/",
    )

    assert len(links) == 1


def test_allowed_by_robots_false_when_disallowed():
    crawler = Crawler(
        "https://quotes.toscrape.com/",
        obey_robots=False,
    )

    crawler.robot_parser.parse([
        "User-agent: *",
        "Disallow: /private/",
    ])

    crawler.obey_robots = True

    assert not crawler.allowed_by_robots(
        "https://quotes.toscrape.com/private/page"
    )