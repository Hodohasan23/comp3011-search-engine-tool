from src.search import QueryProcessor


def test_clean_query_tokenises_words():
    processor = QueryProcessor()

    assert processor.clean_query(
        "Good FRIENDS!!!"
    ) == ["good", "friends"]


def test_phrase_query_detection():
    processor = QueryProcessor()

    assert processor.is_phrase_query('"good friends"')
    assert not processor.is_phrase_query("good friends")


def test_extract_phrase_terms():
    processor = QueryProcessor()

    assert processor.extract_phrase_terms(
        '"Good Friends"'
    ) == ["good", "friends"]

def test_levenshtein_distance():
    processor = QueryProcessor()

    assert processor.levenshtein_distance("good", "good") == 0
    assert processor.levenshtein_distance("good", "goof") == 1


def test_suggest_term_returns_closest_match():
    processor = QueryProcessor()

    suggestion = processor.suggest_term(
        "indiffrence",
        {"good", "friends", "indifference"},
    )

    assert suggestion == "indifference"


def test_suggest_term_returns_none_for_known_term():
    processor = QueryProcessor()

    assert processor.suggest_term("good", {"good", "friends"}) is None
