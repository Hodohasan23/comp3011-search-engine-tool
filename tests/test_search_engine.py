from src.indexer import InvertedIndex
from src.search import SearchEngine


def test_find_single_word_query():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>bad weather</p>")

    engine = SearchEngine(index)

    results = engine.find("good")

    assert results[0][0] == "page1"


def test_find_multi_word_query_uses_and_semantics():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books</p>")

    engine = SearchEngine(index)

    results = engine.find("good friends")

    assert len(results) == 1
    assert results[0][0] == "page1"


def test_find_empty_query_returns_empty_list():
    index = InvertedIndex()
    engine = SearchEngine(index)

    assert engine.find("") == []


def test_find_missing_word_returns_empty_list():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")

    engine = SearchEngine(index)

    assert engine.find("missing") == []


def test_print_term_returns_postings():
    index = InvertedIndex()
    index.add_document("page1", "<p>good good friends</p>")

    engine = SearchEngine(index)

    result = engine.print_term("good")

    assert result["page1"]["tf"] == 2
    assert result["page1"]["positions"] == [0, 1]

def test_phrase_search_matches_consecutive_terms():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends matter</p>")
    index.add_document("page2", "<p>good books and friends</p>")

    engine = SearchEngine(index)

    results = engine.find('"good friends"')

    assert len(results) == 1
    assert results[0][0] == "page1"


def test_phrase_search_rejects_non_consecutive_terms():
    index = InvertedIndex()
    index.add_document("page1", "<p>good books and friends</p>")

    engine = SearchEngine(index)

    assert engine.find('"good friends"') == []

def test_snippet_returns_context_around_query_term():
    index = InvertedIndex()
    index.add_document(
        "page1",
        "<p>alpha beta gamma good friends delta epsilon zeta</p>",
    )

    engine = SearchEngine(index)

    snippet = engine.snippet("page1", ["good"], window=2)

    assert "gamma good friends" in snippet
