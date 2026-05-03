from src.inverted_index import InvertedIndex
from src.metrics import Timer, index_summary


def test_index_summary_counts_documents_terms_and_tokens():
    index = InvertedIndex()
    index.add_document("page1", "<p>good friends</p>")
    index.add_document("page2", "<p>good books</p>")

    summary = index_summary(index)

    assert summary["documents"] == 2
    assert summary["vocabulary_size"] == 3
    assert summary["total_tokens"] == 4


def test_timer_returns_elapsed_time():
    timer = Timer()

    timer.start()
    timer.stop()

    assert timer.elapsed() >= 0
