import argparse
import json
import shlex
from pathlib import Path
from time import perf_counter

from src.crawler import Crawler
from src.indexer import InvertedIndex
from src.search import SearchEngine


DEFAULT_START_URL = "https://quotes.toscrape.com/"
DEFAULT_INDEX_PATH = "data/index.json"
DEFAULT_RANKING_METHOD = "bm25"


class Timer:
    """Small utility for measuring build time."""

    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None

    def start(self) -> None:
        """Start timing."""
        self.start_time = perf_counter()

    def stop(self) -> None:
        """Stop timing."""
        self.end_time = perf_counter()

    def elapsed(self) -> float:
        """Return elapsed seconds, or 0 if the timer is incomplete."""
        if self.start_time is None or self.end_time is None:
            return 0.0

        return self.end_time - self.start_time


def index_summary(index: InvertedIndex, index_path: str | None = None) -> dict:
    """Return simple statistics about the built index."""
    summary = {
        "documents": len(index.doc_lengths),
        "vocabulary_size": len(index.terms),
        "total_tokens": sum(index.doc_lengths.values()),
    }

    # Include file size only when the index has already been saved.
    if index_path is not None and Path(index_path).exists():
        summary["index_size_bytes"] = Path(index_path).stat().st_size

    return summary


class SearchCLI:
    """Interactive command-line interface for the search engine."""

    def __init__(
        self,
        start_url: str = DEFAULT_START_URL,
        index_path: str = DEFAULT_INDEX_PATH,
        politeness_window: float = 6.0,
        ranking_method: str = DEFAULT_RANKING_METHOD,
    ) -> None:
        self.start_url = start_url
        self.index_path = index_path
        self.politeness_window = politeness_window
        self.ranking_method = ranking_method

        # These are initialised after build/load.
        self.index: InvertedIndex | None = None
        self.engine: SearchEngine | None = None

    def build(self) -> str:
        """Crawl pages, build the index, save it, and report metrics."""
        timer = Timer()
        timer.start()

        crawler = Crawler(
            self.start_url,
            politeness_window=self.politeness_window,
        )
        pages = crawler.crawl()

        index = InvertedIndex()

        # Convert each crawled HTML page into indexed postings.
        for url, html in pages.items():
            index.add_document(url, html)

        index.save(self.index_path)
        timer.stop()

        self.index = index
        self.engine = SearchEngine(index, ranking_method=self.ranking_method)

        summary = index_summary(index, self.index_path)

        return (
            f"Built index for {summary['documents']} pages "
            f"with {summary['vocabulary_size']} unique terms "
            f"and {summary['total_tokens']} tokens.\n"
            f"Saved to {self.index_path} "
            f"({summary.get('index_size_bytes', 0)} bytes).\n"
            f"Build completed in {timer.elapsed():.2f} seconds."
        )

    def load(self) -> str:
        """Load a previously saved index from disk."""
        self.index = InvertedIndex.load(self.index_path)
        self.engine = SearchEngine(
            self.index,
            ranking_method=self.ranking_method,
        )

        return f"Loaded index from {self.index_path}"

    def set_ranking_method(self, ranking_method: str) -> str:
        """Change ranking method and rebuild the search engine view."""
        ranking_method = ranking_method.lower()

        if ranking_method not in {"bm25", "tfidf"}:
            return "Unknown ranking method. Use 'bm25' or 'tfidf'."

        self.ranking_method = ranking_method

        # If an index is already loaded, refresh the engine with the new ranker.
        if self.index is not None:
            self.engine = SearchEngine(
                self.index,
                ranking_method=self.ranking_method,
            )

        return f"Ranking method set to {self.ranking_method}"

    def print_term(self, term: str) -> str:
        """Return the posting list for a single term as formatted JSON."""
        if self.engine is None:
            return "No index loaded. Run build or load first."

        postings = self.engine.print_term(term)

        if not postings:
            return f"No postings found for '{term}'."

        return json.dumps(postings, indent=2)

    def find(self, query: str) -> str:
        """Run a search query and format ranked results for the terminal."""
        if self.engine is None:
            return "No index loaded. Run build or load first."

        results = self.engine.find(query)

        if not results:
            suggestions = self.engine.suggest_terms(query)

            if suggestions:
                suggestion_lines = [
                    f"No pages match '{query}'.",
                    "Did you mean:",
                ]

                for original, suggestion in suggestions.items():
                    suggestion_lines.append(
                        f"  {suggestion} instead of {original}"
                    )

                return "\n".join(suggestion_lines)

            return f"No pages match '{query}'."

        lines = [
            f"{len(results)} result(s) for '{query}' "
            f"using {self.ranking_method}:"
        ]

        query_terms = self.engine.query_processor.clean_query(query)

        for url, score in results:
            snippet = self.engine.snippet(url, query_terms)

            lines.append(f"  [{score:.3f}] {url}")

            # Snippets make it clear why the URL matched the query.
            if snippet:
                lines.append(f"      ... {snippet} ...")

        return "\n".join(lines)

    def handle_command(self, line: str) -> str:
        """Parse and execute one REPL command."""
        # posix=False preserves quoted phrases for phrase-search handling.
        parts = shlex.split(line, posix=False)

        if not parts:
            return ""

        command = parts[0].lower()
        args = parts[1:]

        if command == "build":
            return self.build()

        if command == "load":
            return self.load()

        if command == "ranking":
            if not args:
                return f"Current ranking method: {self.ranking_method}"
            return self.set_ranking_method(args[0])

        if command == "print":
            if not args:
                return "Usage: print <word>"
            return self.print_term(args[0])

        if command == "find":
            if not args:
                return "Usage: find <query>"

            # Optional inline ranking override:
            # find good friends --ranking tfidf
            if "--ranking" in args:
                ranking_index = args.index("--ranking")

                if ranking_index + 1 >= len(args):
                    return "Missing ranking method. Use bm25 or tfidf."

                ranking_method = args[ranking_index + 1]
                del args[ranking_index : ranking_index + 2]

                ranking_output = self.set_ranking_method(ranking_method)

                if ranking_output.startswith("Unknown"):
                    return ranking_output

            return self.find(" ".join(args))

        if command == "help":
            return (
                "Commands:\n"
                "  build                         crawl site, build index, save it\n"
                "  load                          load saved index\n"
                "  ranking [bm25|tfidf]          view or change ranking method\n"
                "  print <word>                  show postings for one word\n"
                "  find <query>                  find pages matching query terms\n"
                "  find <query> --ranking tfidf  run query with TF-IDF ranking\n"
                "  find <query> --ranking bm25   run query with BM25 ranking\n"
                "  quit / exit                   leave the shell"
            )

        if command in {"quit", "exit"}:
            raise SystemExit

        return f"Unknown command: {command}"

    def run(self) -> None:
        """Start the interactive REPL."""
        print("COMP3011 Search Engine Tool")
        print("Type 'help' for commands or 'quit' to exit.")

        while True:
            try:
                line = input("> ")
                output = self.handle_command(line)

                if output:
                    print(output)

            except SystemExit:
                print("bye.")
                break


def main() -> None:
    """Parse command-line options and start the CLI."""
    parser = argparse.ArgumentParser(description="COMP3011 Search Engine Tool")

    parser.add_argument(
        "--start-url",
        default=DEFAULT_START_URL,
        help="Website URL to crawl",
    )

    parser.add_argument(
        "--index-path",
        default=DEFAULT_INDEX_PATH,
        help="Path to save/load the index JSON file",
    )

    parser.add_argument(
        "--politeness-window",
        type=float,
        default=6.0,
        help="Delay between requests in seconds",
    )

    parser.add_argument(
        "--ranking",
        default=DEFAULT_RANKING_METHOD,
        choices=["bm25", "tfidf"],
        help="Default ranking method",
    )

    args = parser.parse_args()

    cli = SearchCLI(
        start_url=args.start_url,
        index_path=args.index_path,
        politeness_window=args.politeness_window,
        ranking_method=args.ranking,
    )

    cli.run()


if __name__ == "__main__":
    main()