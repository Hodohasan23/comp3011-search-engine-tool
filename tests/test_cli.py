from src.cli import SearchCLI
from src.inverted_index import InvertedIndex
from src.search_engine import SearchEngine


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
