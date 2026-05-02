from src.query_processor import QueryProcessor


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
