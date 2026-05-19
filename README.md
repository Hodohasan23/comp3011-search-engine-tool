# COMP3011 Search Engine Tool

![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-72%20passing-success)
![Coverage](https://img.shields.io/badge/coverage-93%25-success)
![MyPy](https://img.shields.io/badge/mypy-passing-blue)
![Ruff](https://img.shields.io/badge/ruff-passing-blue)

A feature-rich command-line search engine implemented in Python for COMP3011 Web Services and Web Data.

The system crawls and indexes pages from `quotes.toscrape.com`, builds a positional inverted index, and supports ranked retrieval through BM25 and TF-IDF scoring models. The project emphasises robust crawling, modular architecture, positional retrieval, ranking abstraction, automated testing, and software engineering quality.

---

## Features

### Crawling

- Breadth-first crawler
- Configurable politeness delay
- Retry and exponential backoff handling
- robots.txt support
- Same-host restriction
- URL normalisation
- Duplicate-link filtering
- External-link exclusion
- Non-HTML content rejection

### Indexing

- Positional inverted index
- Term frequencies and token positions
- Stop-word filtering
- Case-insensitive tokenisation
- Persistent JSON index storage
- Index schema versioning
- Document-length tracking
- Snippet-ready token storage

### Search & Retrieval

- Boolean AND retrieval
- BM25 ranking
- TF-IDF ranking
- Runtime ranking selection
- Positional phrase queries
- Did-you-mean suggestions
- Search-result snippets
- Full-word matching
- Deterministic ranking order

### Software Engineering

- 72 automated tests
- 93% total coverage
- MyPy static type checking
- Ruff linting
- GitHub Actions CI pipeline
- Fully mocked HTTP test suite
- Modular architecture
- Dependency-isolated testing

---

## Installation

Clone the repository:

```bash
git clone https://github.com/Hodohasan23/comp3011-search-engine-tool.git
cd comp3011-search-engine-tool
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

---

## Quick Start

Run the CLI:

```bash
python -m src.main
```

Build the search index:

```
build
```

Load a previously-built index:

```
load
```

Quit the shell:

```
quit
```

---

## Example Usage

### Multi-word retrieval

```
find good friends
```

### Phrase queries

```
find "good friends"
```

### Ranking selection

```
find good friends --ranking bm25
find good friends --ranking tfidf
```

### Did-you-mean suggestions

```
find indiffrence
```

### Inspect postings

```
print indifference
```

---

## Example Output

```
> find "good friends"

10 result(s) for '"good friends"' using bm25:

[3.589] https://quotes.toscrape.com/tag/contentment/page/1/
    ... viewing tag contentment good friends good books sleepy conscience ...

[2.936] https://quotes.toscrape.com/tag/friendship/
    ... unhappy marriage good friends good books sleepy conscience ...
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          src/main.py                                │
│                argparse entry point + CLI startup                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           src/cli.py                                │
│        build / load / print / find / ranking / help / quit           │
└───────────────┬───────────────────────┬─────────────────────────────┘
                │                       │
        build   ▼                       ▼  load
┌─────────────────────────┐   ┌───────────────────────────────────────┐
│     src/crawler.py      │   │        data/index.json                 │
│ polite BFS crawl        │   │ versioned persistent index             │
│ robots.txt              │   └──────────────────┬────────────────────┘
│ retries + backoff       │                      │
│ URL normalisation       │                      │
└─────────────┬───────────┘                      │
              │ raw HTML pages                   │
              ▼                                  │
┌─────────────────────────┐                      │
│   src/html_parser.py    │                      │
│ visible text extraction │                      │
│ tokenisation            │                      │
│ stop-word filtering     │                      │
└─────────────┬───────────┘                      │
              │ tokens                           │
              ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    src/inverted_index.py                            │
│ term → URL → {tf, positions}                                        │
│ doc_lengths + doc_tokens + schema versioning                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    src/search_engine.py                             │
│ Boolean AND retrieval                                               │
│ positional phrase search                                            │
│ did-you-mean suggestions                                            │
│ snippet generation                                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         src/ranker.py                               │
│ BM25Ranker / TFIDFRanker / runtime ranking selection                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
comp3011-search-engine-tool/
├── src/
│   ├── cli.py
│   ├── crawler.py
│   ├── html_parser.py
│   ├── inverted_index.py
│   ├── main.py
│   ├── metrics.py
│   ├── query_processor.py
│   ├── ranker.py
│   └── search_engine.py
│
├── tests/
│   ├── test_cli.py
│   ├── test_crawler.py
│   ├── test_inverted_index.py
│   ├── test_query_processor.py
│   ├── test_ranker.py
│   └── test_search_engine.py
│
├── data/
├── docs/
├── .github/workflows/
├── README.md
├── technical_log.md
├── requirements.txt
├── pyproject.toml
└── pytest.ini
```

---

## Ranking Models

### BM25

The engine implements Okapi BM25 ranking with configurable `k1` and `b` parameters. BM25 balances term frequency, inverse document frequency, and document-length normalisation to improve retrieval quality over naive frequency-based ranking.

### TF-IDF

A second retrieval pipeline implements TF-IDF scoring using inverse document frequency weighting.

The ranking abstraction layer allows runtime switching between retrieval models:

```
find artificial intelligence --ranking bm25
find artificial intelligence --ranking tfidf
```

---

## Phrase Queries

The engine supports true positional phrase matching. Queries such as:

```
find "good friends"
```

only return documents where the tokens occur consecutively. This is implemented through positional posting intersection using stored token offsets inside the inverted index.

---

## Testing

Run the full test suite:

```bash
python -m pytest --cov=src --cov-report=term-missing
```

Run static analysis:

```bash
python -m mypy src
```

Run linting:

```bash
python -m ruff check src tests
```

| Metric   | Result  |
| -------- | ------- |
| Tests    | 72      |
| Coverage | 93%     |
| MyPy     | Passing |
| Ruff     | Passing |

---

## Design Decisions

### Why a positional inverted index?

Positions allow phrase queries, snippet generation, proximity-aware retrieval, and future ranking extensions, rather than only simple keyword presence.

### Why JSON persistence?

JSON storage is human-readable, portable, easy to debug, and coursework-friendly, while still supporting schema evolution through explicit versioning.

### Why both BM25 and TF-IDF?

Implementing multiple ranking models allows comparative retrieval evaluation and demonstrates separation between indexing and ranking concerns.

---

## Limitations

- Crawling is single-threaded
- Tokenisation is ASCII-oriented
- No stemming or lemmatisation
- No distributed indexing
- No semantic/vector retrieval
- No PageRank or link-analysis stage

These were intentionally excluded to prioritise correctness, robustness, and retrieval quality within coursework scope.

---

## Technologies

- Python 3.12
- requests
- BeautifulSoup4
- pytest / pytest-cov
- responses
- Ruff
- MyPy

---

## References

- Manning, Raghavan & Schütze — *Introduction to Information Retrieval*
- Python Requests Documentation
- BeautifulSoup Documentation
- COMP3011 Lecture Material

---

## Repository

[https://github.com/Hodohasan23/comp3011-search-engine-tool](https://github.com/Hodohasan23/comp3011-search-engine-tool)