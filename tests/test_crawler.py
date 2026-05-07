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