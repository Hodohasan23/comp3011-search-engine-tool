# comp3011-search-engine-tool

A full-stack information retrieval system built from scratch in Python. Crawls `quotes.toscrape.com`, builds a positional inverted index, and retrieves ranked results from a command-line shell.

```
121 tests · 99% coverage · MyPy · Ruff · GitHub Actions CI
```

---

## Quickstart

```bash
git clone https://github.com/Hodohasan23/comp3011-search-engine-tool.git
cd comp3011-search-engine-tool
python -m pip install -r requirements.txt
python -m src.main
```

```
> build
> find good friends
> find "good friends"
> find good friends --ranking tfidf
> find indiffrence
> print indifference
> quit
```

---

## Features

| Category | Feature |
|---|---|
| **Crawling** | Polite BFS, configurable delay (default 6 s), robots.txt, retry + exponential backoff, same-host restriction, URL normalisation, non-HTML rejection |
| **Indexing** | Positional inverted index, stop-word filtering, case-insensitive tokenisation, document-length tracking, schema versioning, JSON persistence |
| **Retrieval** | Boolean AND, BM25, TF-IDF, runtime ranking selection, positional phrase queries, did-you-mean suggestions, search result snippets |
| **Engineering** | 121 tests, 99% coverage, MyPy, Ruff, GitHub Actions CI, fully mocked HTTP suite |

---

## Sample session

```
> build
Crawling https://quotes.toscrape.com/ ...
Built index for 214 pages with 4445 unique terms and 36821 tokens.
Saved to data/index.json. Build completed in 1302.47 seconds.

> find "good friends"
2 result(s) for '"good friends"' using bm25:
  [3.589] https://quotes.toscrape.com/tag/contentment/page/1/
      ... viewing tag contentment good friends good books sleepy conscience ...
  [2.936] https://quotes.toscrape.com/tag/friendship/
      ... unhappy marriage good friends good books sleepy conscience ...

> find indiffrence
No pages match 'indiffrence'.
Did you mean:
  indifference instead of indiffrence

> print indifference
{
  "https://quotes.toscrape.com/tag/indifference/page/1/": {
    "tf": 3,
    "positions": [14, 28, 61]
  }
}
```

---

## Architecture

```
                        ┌─────────────────┐
                        │   src/main.py   │
                        │ argparse · REPL │
                        │ CLI · commands  │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
        ┌───────────▼──┐             ┌────────▼────────┐
        │ src/crawler  │             │ data/index.json │
        │ polite BFS   │             │ versioned index │
        │ robots.txt   │             └────────┬────────┘
        │ retries      │                      │ load
        └──────┬───────┘                      │
               │ {url: html}                  │
               ▼                              ▼
        ┌──────────────────────────────────────────┐
        │              src/indexer.py              │
        │  visible text extraction · tokenisation  │
        │  stop-word filtering · schema versioning │
        │  term → URL → {tf, positions}            │
        │  doc_lengths · doc_tokens · JSON save    │
        └──────────────────┬───────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │              src/search.py               │
        │  AND retrieval · phrase search           │
        │  BM25Ranker · TFIDFRanker                │
        │  did-you-mean · snippet generation       │
        │  QueryProcessor · Levenshtein distance   │
        └──────────────────────────────────────────┘
```

**Data flow — build:** `main.py` → `crawler.py` fetches pages → `indexer.py` tokenises and indexes → saves to `data/index.json`.

**Data flow — find:** `main.py` → `search.py` queries index → ranker scores candidates → ranked results with snippets returned to shell.

The crawler returns `{url: html}` and has no knowledge of how pages get indexed. The ranker knows only how to score candidate URLs. `main.py` is a thin shell — both crawler and search engine are constructor-injectable so the entire test suite runs without a network connection.

---

## Index format

A single versioned UTF-8 JSON file:

```json
{
  "version": 1,
  "doc_lengths": {
    "https://quotes.toscrape.com/": 82
  },
  "doc_tokens": {
    "https://quotes.toscrape.com/": ["life", "change", "world", "..."]
  },
  "terms": {
    "indifference": {
      "https://quotes.toscrape.com/tag/indifference/page/1/": {
        "tf": 3,
        "positions": [14, 28, 61]
      }
    }
  }
}
```

`positions` are 0-based token offsets after stop-word removal — they power both phrase queries and snippet extraction. `doc_tokens` stores the full token sequence per page so snippets can be generated without re-parsing HTML. `doc_lengths` feeds BM25 document-length normalisation.

---

## Ranking

### BM25 (default)

```
score = Σ  IDF(t) · tf · (k1 + 1) / (tf + k1 · (1 − b + b · dl/avgdl))

IDF(t) = log(1 + (N − df + 0.5) / (df + 0.5))
k1 = 1.5,  b = 0.75
```

Document-length normalisation makes BM25 outperform raw TF-IDF on short pages — a high-frequency term on a short page scores differently to the same frequency on a long one.

### TF-IDF

```
score = Σ  (1 + log tf) · (log((N+1)/(df+1)) + 1)
```

Sub-linear TF dampens repeated terms. Smoothed IDF avoids division by zero.

Switch at runtime:

```
> ranking tfidf
> find good friends --ranking bm25
```

---

## Phrase queries

Positional posting intersection (Manning §2.4.1). For a phrase `[t0, t1, ..., tn]`:

1. Find URLs containing all terms.
2. For each URL, shift each term's position set by its phrase offset: `{p − offset}`.
3. Intersect all shifted sets — non-empty intersection means consecutive occurrence.

```
> find "good friends"          # phrase only
> find "good friends" matter   # phrase AND free term
```

---

## Did-you-mean

When a query returns no results, each unrecognised token is passed through the spelling suggestion engine:

1. Pre-filter vocabulary by length (`|len(vocab) − len(query)| ≤ 2`).
2. Compute Levenshtein edit distance against candidates.
3. Return the closest match within distance 2, breaking ties alphabetically.

---

## Design decisions

| Decision | Chosen | Alternatives considered | Rationale |
|---|---|---|---|
| Index storage | Single JSON file | SQLite, pickle, Whoosh | Brief requires a single file; human-readable; trivially portable; schema evolution via version field |
| Document IDs | Full URLs | Integer doc IDs | Readable in output and debugging; no lookup table needed; index fits in memory at this scale |
| Crawler frontier | `collections.deque` | `list.pop(0)`, `set` | O(1) at both ends; preserves BFS order; `seen` set deduplicates before enqueue |
| Tokeniser | `re.findall("[a-z0-9]+")` | NLTK, `str.split` | No extra dependency; matches brief; fast; handles punctuation and case in one step |
| Stop-words | Inline list | NLTK, sklearn, none | Brief requires stop-word removal; inline avoids dependency; query example words deliberately kept |
| Ranking | BM25 default + TF-IDF | Unranked, BM25 only | BM25 is stronger on short documents; exposing both allows runtime comparison; satisfies 80–100 rubric band |
| Politeness | Injectable `sleep` callable | Hard-coded `time.sleep(6)` | Tests pass `sleep=lambda t: None`; full suite runs in under 7 s without waiting |
| HTTP mocking | `responses` library | `unittest.mock.patch` | Less brittle; richer response objects; deterministic offline suite |
| Search semantics | AND across terms | OR | Brief's `find good friends` example implies AND; matches user expectation for a precision-oriented tool |
| Phrase positions | Stored in index | Re-parsed on query | Avoids re-parsing HTML at query time; enables snippet extraction from the same structure |

---

## Testing

```bash
python -m pytest --cov=src --cov-report=term-missing
python -m mypy src
python -m ruff check src tests
```

| Metric | Result |
|---|---|
| Tests | 121 |
| Coverage | 99% |
| MyPy | Passing |
| Ruff | Passing |
| HTTP | Fully mocked via `responses` |
| Runtime | ~7 s |

**Crawler** — URL normalisation (port, case, fragment, default ports), link extraction (relative, absolute, mailto, javascript, empty href, malformed HTML), BFS deduplication, external-host skip, max-pages cap, 404, 500-then-200 retry recovery, ConnectionError, Timeout, all-retries-fail, non-HTML skip, politeness window, robots.txt (disallow, 404 allow-all, network failure allow-all).

**Indexer** — tokenisation, stop-word filtering, position tracking, document-length tracking, boilerplate stripping, empty documents, unknown terms, JSON round-trip, schema version rejection.

**Search** — single-word, multi-word AND, empty query, whitespace query, stop-word-only query, duplicate terms, phrase match, phrase non-match, phrase + free term intersection, BM25/TF-IDF scoring, did-you-mean, snippet generation, empty index early return.

**CLI** — all four commands, ranking selection, inline `--ranking` flag, unknown command, missing arguments, missing index, did-you-mean display, REPL loop (quit, exit, help, blank, unknown, error trapping).

---

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP client for crawling (recommended by brief §1.c) |
| `beautifulsoup4` | HTML parsing and visible text extraction (recommended by brief §1.c) |
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `responses` | HTTP mocking for offline, deterministic tests |
| `ruff` | Linting and style enforcement |
| `mypy` | Static type checking |

---

## Project structure

```
comp3011-search-engine-tool/
├── src/
│   ├── __init__.py
│   ├── crawler.py      polite BFS crawler
│   ├── indexer.py      tokenisation, inverted index, JSON persistence
│   ├── search.py       retrieval, ranking, phrase search, snippets
│   └── main.py         argparse entry point, CLI, REPL
├── tests/
│   ├── test_cli.py
│   ├── test_crawler.py
│   ├── test_html_parser.py
│   ├── test_inverted_index.py
│   ├── test_main.py
│   ├── test_metrics.py
│   ├── test_query_processor.py
│   ├── test_ranker.py
│   ├── test_search_engine.py
│   ├── test_additional.py
│   └── test_coverage.py
├── benchmarks/
│   └── benchmark.py
├── data/
├── .github/workflows/
├── README.md
├── technical_log.md
├── requirements.txt
├── pyproject.toml
└── pytest.ini
```

---

## Limitations

- Single-threaded crawler — re-crawl is always a full re-fetch
- ASCII tokenisation — curly quotes stripped, non-Latin scripts unsupported
- No stemming or lemmatisation
- No PageRank or link-graph analysis
- Stop-word list is binary — no weighted or context-sensitive filtering

All intentionally excluded to stay within coursework scope and prioritise correctness over completeness.

---

## References

- Manning, Raghavan & Schütze — *Introduction to Information Retrieval* (Cambridge, 2008), ch. 1–6
- [Python Requests documentation](https://docs.python-requests.org/)
- [Beautiful Soup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [responses library](https://github.com/getsentry/responses)
- COMP3011 lecture slides 9–12