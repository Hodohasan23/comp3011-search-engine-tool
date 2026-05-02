import argparse

from src.cli import SearchCLI


def main() -> None:
    parser = argparse.ArgumentParser(description="COMP3011 Search Engine Tool")

    parser.add_argument(
        "--start-url",
        default="https://quotes.toscrape.com/",
        help="Website URL to crawl",
    )

    parser.add_argument(
        "--index-path",
        default="data/index.json",
        help="Path to save/load the index JSON file",
    )

    parser.add_argument(
        "--politeness-window",
        type=float,
        default=6.0,
        help="Delay between requests in seconds",
    )

    args = parser.parse_args()

    cli = SearchCLI(
        start_url=args.start_url,
        index_path=args.index_path,
        politeness_window=args.politeness_window,
    )

    cli.run()


if __name__ == "__main__":
    main()
