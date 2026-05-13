import json
import shlex

from src.crawler import Crawler
from src.inverted_index import InvertedIndex
from src.metrics import Timer, index_summary
from src.search_engine import SearchEngine


DEFAULT_START_URL = "https://quotes.toscrape.com/"
DEFAULT_INDEX_PATH = "data/index.json"
DEFAULT_RANKING_METHOD = "bm25"


class SearchCLI:
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
        self.index = InvertedIndex.load(self.index_path)
        self.engine = SearchEngine(
            self.index,
            ranking_method=self.ranking_method,
        )

        return f"Loaded index from {self.index_path}"

    def set_ranking_method(self, ranking_method: str) -> str:
        ranking_method = ranking_method.lower()

        if ranking_method not in {"bm25", "tfidf"}:
            return "Unknown ranking method. Use 'bm25' or 'tfidf'."

        self.ranking_method = ranking_method

        if self.index is not None:
            self.engine = SearchEngine(
                self.index,
                ranking_method=self.ranking_method,
            )

        return f"Ranking method set to {self.ranking_method}"

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

        lines = [
            f"{len(results)} result(s) for '{query}' "
            f"using {self.ranking_method}:"
        ]

        query_terms = self.engine.query_processor.clean_query(query)

        for url, score in results:
            snippet = self.engine.snippet(url, query_terms)
            lines.append(f"  [{score:.3f}] {url}")

            if snippet:
                lines.append(f"      ... {snippet} ...")

        return "\n".join(lines)

    def handle_command(self, line: str) -> str:
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
