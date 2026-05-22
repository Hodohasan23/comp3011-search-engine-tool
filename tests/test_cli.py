from pathlib import Path

from src.main import SearchCLI
from src.indexer import InvertedIndex
from src.search import SearchEngine


def make_cli_with_index() -> SearchCLI:
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books</p>")

    cli = SearchCLI()
    cli.index = index
    cli.engine = SearchEngine(index)

    return cli


def test_help_command():
    cli = SearchCLI()

    output = cli.handle_command("help")

    assert "build" in output
    assert "find" in output


def test_blank_command_returns_empty_string():
    cli = SearchCLI()

    assert cli.handle_command("") == ""


def test_unknown_command():
    cli = SearchCLI()

    assert cli.handle_command("unknown") == "Unknown command: unknown"


def test_print_without_loaded_index():
    cli = SearchCLI()

    assert "No index loaded" in cli.handle_command("print good")


def test_find_without_loaded_index():
    cli = SearchCLI()

    assert "No index loaded" in cli.handle_command("find good")


def test_print_missing_argument():
    cli = SearchCLI()

    assert cli.handle_command("print") == "Usage: print <word>"


def test_find_missing_argument():
    cli = SearchCLI()

    assert cli.handle_command("find") == "Usage: find <query>"


def test_print_term_with_loaded_index():
    cli = make_cli_with_index()

    output = cli.handle_command("print good")

    assert "page1" in output
    assert "tf" in output


def test_find_query_with_loaded_index():
    cli = make_cli_with_index()

    output = cli.handle_command("find good friends")

    assert "result(s)" in output
    assert "page1" in output


def test_find_no_results():
    cli = make_cli_with_index()

    output = cli.handle_command("find missing")

    assert "No pages match" in output


def test_quit_raises_system_exit():
    cli = SearchCLI()

    try:
        cli.handle_command("quit")
    except SystemExit:
        assert True
    else:
        assert False

def test_build_creates_index_file(tmp_path):
    cli = SearchCLI(
        index_path=str(tmp_path / "index.json"),
        politeness_window=0,
    )

    class FakeCrawler:
        def crawl(self):
            return {
                "page1": "<p>good friends</p>",
                "page2": "<p>good books</p>",
            }

    from src import main as main_module

    original_crawler = main_module.Crawler
    main_module.Crawler = lambda *args, **kwargs: FakeCrawler()

    try:
        output = cli.build()

        assert "Built index" in output
        assert Path(tmp_path / "index.json").exists()

    finally:
        main_module.Crawler = original_crawler


def test_load_reads_existing_index(tmp_path):
    from src.indexer import InvertedIndex

    index_path = tmp_path / "index.json"

    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.save(str(index_path))

    cli = SearchCLI(index_path=str(index_path))

    output = cli.load()

    assert "Loaded index" in output
    assert cli.engine is not None

def test_find_shows_did_you_mean_suggestion():
    cli = make_cli_with_index()

    output = cli.handle_command("find frends")

    assert "Did you mean" in output
    assert "friends instead of frends" in output

def test_find_supports_tfidf_ranking():
    cli = make_cli_with_index()

    output = cli.handle_command(
        "find friends --ranking tfidf"
    )

    assert "result" in output.lower()

def test_ranking_command_shows_current_method():
    cli = SearchCLI()

    output = cli.handle_command("ranking")

    assert output == "Current ranking method: bm25"


def test_ranking_command_updates_method():
    cli = make_cli_with_index()

    output = cli.handle_command("ranking tfidf")

    assert output == "Ranking method set to tfidf"
    assert cli.ranking_method == "tfidf"


def test_ranking_command_rejects_unknown_method():
    cli = SearchCLI()

    output = cli.handle_command("ranking unknown")

    assert "Unknown ranking method" in output


def test_find_rejects_missing_ranking_method():
    cli = make_cli_with_index()

    output = cli.handle_command("find good --ranking")

    assert "Missing ranking method" in output


def test_find_rejects_unknown_inline_ranking_method():
    cli = make_cli_with_index()

    output = cli.handle_command("find good --ranking unknown")

    assert "Unknown ranking method" in output
