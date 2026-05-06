import json
import shlex

from src.crawler import Crawler
from src.inverted_index import InvertedIndex
from src.search_engine import SearchEngine
from src.metrics import Timer, index_summary


DEFAULT_START_URL = "https://quotes.toscrape.com/"
DEFAULT_INDEX_PATH = "data/index.json"


class SearchCLI:
    def __init__(
        self,
        start_url: str = DEFAULT_START_URL,
        index_path: str = DEFAULT_INDEX_PATH,
        politeness_window: float = 6.0,
    ) -> None:
        self.start_url = start_url
        self.index_path = index_path
        self.politeness_window = politeness_window
        self.index: InvertedIndex | None = None
        self.engine: SearchEngine | None = None

    def build(self) -> str:
        timer = Timer()
        timer.start()

        crawler = Crawler(
            self.start_url,
            politeness_window=self.politeness_window,
        )
        pages = crawler.crawl()

        index = InvertedIndex()

        for url, html in pages.items():
            index.add_document(url, html)

        index.save(self.index_path)

        timer.stop()

        self.index = index
        self.engine = SearchEngine(index)

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
        self.index = InvertedIndex.load(self.index_path)
        self.engine = SearchEngine(self.index)

        return f"Loaded index from {self.index_path}"

    def print_term(self, term: str) -> str:
        if self.engine is None:
            return "No index loaded. Run build or load first."

        postings = self.engine.print_term(term)

        if not postings:
            return f"No postings found for '{term}'."

        return json.dumps(postings, indent=2)

    def find(self, query: str) -> str:
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

        lines = [f"{len(results)} result(s) for '{query}':"]

        for url, score in results:
            lines.append(f"  [{score:.3f}] {url}")

        return "\n".join(lines)

    def handle_command(self, line: str) -> str:
        parts = shlex.split(line)

        if not parts:
            return ""

        command = parts[0].lower()
        args = parts[1:]

        if command == "build":
            return self.build()

        if command == "load":
            return self.load()

        if command == "print":
            if not args:
                return "Usage: print <word>"
            return self.print_term(args[0])

        if command == "find":
            if not args:
                return "Usage: find <query>"
            return self.find(" ".join(args))

        if command == "help":
            return (
                "Commands:\n"
                "  build              crawl site, build index, save it\n"
                "  load               load saved index\n"
                "  print <word>       show postings for one word\n"
                "  find <query>       find pages matching query terms\n"
                "  quit / exit        leave the shell"
            )

        if command in {"quit", "exit"}:
            raise SystemExit

        return f"Unknown command: {command}"

    def run(self) -> None:
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
