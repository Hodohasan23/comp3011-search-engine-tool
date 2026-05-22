"""
Performance benchmarks for COMP3011 Search Engine Tool.
Run from the repo root: python benchmarks/benchmark.py
"""

import statistics
import tempfile
import time

from src.indexer import InvertedIndex, html_to_tokens
from src.search import SearchEngine


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def make_index(num_docs: int, tokens_per_doc: int) -> InvertedIndex:
    vocab = [f"word{i}" for i in range(500)]
    index = InvertedIndex()
    for doc_id in range(num_docs):
        tokens = [vocab[(doc_id + i) % len(vocab)] for i in range(tokens_per_doc)]
        html = "<p>" + " ".join(tokens) + "</p>"
        index.add_document(f"https://example.com/page/{doc_id}/", html)
    return index


def bench(label: str, fn, runs: int = 20) -> float:
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    mean = statistics.mean(times)
    stdev = statistics.stdev(times)
    print(f"  {label:<50} {mean:>7.3f} ms  ±{stdev:.3f}")
    return mean


# ──────────────────────────────────────────────
# Benchmarks
# ──────────────────────────────────────────────

def benchmark_tokenisation():
    print("\n── Tokenisation ──────────────────────────────────────")
    short = "<p>" + " ".join(f"word{i}" for i in range(50)) + "</p>"
    long_ = "<p>" + " ".join(f"word{i}" for i in range(500)) + "</p>"

    bench("tokenise  50-token page  (stop-words off)", lambda: html_to_tokens(short))
    bench("tokenise  50-token page  (stop-words on) ", lambda: html_to_tokens(short, remove_stopwords=True))
    bench("tokenise 500-token page  (stop-words off)", lambda: html_to_tokens(long_))
    bench("tokenise 500-token page  (stop-words on) ", lambda: html_to_tokens(long_, remove_stopwords=True))


def benchmark_indexing():
    print("\n── Indexing ──────────────────────────────────────────")
    vocab = [f"word{i}" for i in range(500)]

    for num_docs, tpd in [(50, 50), (100, 50), (200, 50), (200, 100)]:
        pages = {
            f"https://example.com/page/{d}/": "<p>" + " ".join(
                vocab[(d + i) % len(vocab)] for i in range(tpd)
            ) + "</p>"
            for d in range(num_docs)
        }

        def run(p=pages):
            idx = InvertedIndex()
            for url, html in p.items():
                idx.add_document(url, html)

        bench(f"index {num_docs:>3} docs × {tpd:>3} tokens/doc", run)


def benchmark_save_load():
    print("\n── Save / Load ───────────────────────────────────────")
    import os

    with tempfile.TemporaryDirectory() as tmp:
        for num_docs in [50, 100, 200]:
            index = make_index(num_docs, 50)
            path = os.path.join(tmp, f"index_{num_docs}.json")

            bench(f"save  {num_docs}-doc index", lambda p=path, i=index: i.save(p))
            bench(f"load  {num_docs}-doc index", lambda p=path: InvertedIndex.load(p))

            size_kb = os.path.getsize(path) / 1024
            print(f"  {'  → file size':50} {size_kb:.1f} KB")


def benchmark_search():
    print("\n── Search ────────────────────────────────────────────")

    for num_docs in [50, 100, 200]:
        index = make_index(num_docs, 50)
        engine = SearchEngine(index)
        print(f"\n  [{num_docs} docs]")

        bench("find single term              ", lambda e=engine: e.find("word0"))
        bench("find two-term AND             ", lambda e=engine: e.find("word0 word1"))
        bench("find phrase query             ", lambda e=engine: e.find('"word0 word1"'))
        bench("find unknown term             ", lambda e=engine: e.find("zzzzz"))
        bench("find unknown + did-you-mean   ", lambda e=engine: e.find("wrod0"))
        bench("find single term (tfidf)      ", lambda: SearchEngine(index, ranking_method="tfidf").find("word0"))


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("COMP3011 Search Engine — Performance Benchmarks")
    print("=" * 58)
    print("Each measurement: mean ± stdev over 20 runs (synthetic data)")

    benchmark_tokenisation()
    benchmark_indexing()
    benchmark_save_load()
    benchmark_search()

    print("\n── Notes ─────────────────────────────────────────────")
    print("  Crawl time is dominated by the 6 s politeness window, not CPU.")
    print("  All query operations complete well under 50 ms on real index data.")