# comp3011-search-engine-tool

**A command-line search engine built in Python.**
Crawls `quotes.toscrape.com`, builds a positional inverted index, and retrieves ranked results via BM25 and TF-IDF.

```
121 tests · 99% coverage · MyPy · Ruff · GitHub Actions CI
```

---

## What it does

The tool ships four required commands and several features beyond the brief:

| Command | Description |
|---|---|
| `build` | Crawl the site, build the index, save to disk |
| `load` | Load a previously built index |
| `print <word>` | Show the inverted index entry for a word |
| `find <query>` | Retrieve ranked pages matching a query |

Beyond the brief: phrase queries, BM25 and TF-IDF ranking, runtime ranking selection, did-you-mean suggestions, and search result snippets.

---

## Installation

```bash
git clone https://github.com/Hodohasan23/comp3011-search-engine-tool.git
cd comp3011-search-engine-tool
python -m pip install -r requirements.txt
```

---

## Usage

```bash
python -m src.main
```

```
> build
> load
> find good friends
> find "good friends"
> find good friends --ranking tfidf
> find indiffrence
> print indifference
> quit
```

### Phrase queries

Wrap a query in double quotes to match consecutive tokens only:

```
> find "good friends"
2 result(s) for '"good friends"' using bm25:
  [3.589] https://quotes.toscrape.com/tag/contentment/page/1/
      ... viewing tag contentment good friends good books ...
```

### Ranking selection

Switch between BM25 and TF-IDF at runtime:

```
> find good friends --ranking bm25
> find good friends --ranking tfidf
> ranking tfidf
```

### Did-you-mean

When a query returns no results, the engine suggests the closest vocabulary match:

```
> find indiffrence
No pages match 'indiffrence'.
Did you mean:
  indifference instead of indiffrence
```

---

## Architecture

```
src/main.py          argparse entry point
src/cli.py           REPL — build / load / print / find / ranking / quit
src/crawler.py       polite BFS crawler with retries, robots.txt, URL normalisation
src/html_parser.py   visible text extraction, tokenisation, stop-word filtering
src/inverted_index.py  term → URL → {tf, positions}, JSON persistence, schema versioning
src/search_engine.py   AND retrieval, phrase search, did-you-mean, snippet generation
src/ranker.py        BM25Ranker, TFIDFRanker, runtime ranking selection
src/query_processor.py  query cleaning, phrase detection, Levenshtein suggestions
src/metrics.py       index summary, timer
```

---

## Index structure

The index is saved as a single versioned JSON file:

```json
{
  "version": 1,
  "terms": {
    "indifference": {
      "page_url": { "tf": 2, "positions": [14, 37] }
    }
  },
  "doc_lengths": { "page_url": 82 },
  "doc_tokens":  { "page_url": ["quote", "life", ...] }
}
```

Positions power phrase queries and snippet generation. `doc_tokens` stores the full token sequence per document for snippet extraction. `doc_lengths` feeds BM25 document-length normalisation.

---

## Ranking

### BM25

Okapi BM25 with configurable `k1` and `b`. Balances term frequency, inverse document frequency, and document-length normalisation:

```
score = Σ IDF(t) · (tf · (k1 + 1)) / (tf + k1 · (1 - b + b · dl/avgdl))
```

### TF-IDF

Sub-linear TF with smoothed IDF:

```
score = Σ (1 + log tf) · (log((N+1)/(df+1)) + 1)
```

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

The suite is fully offline — all HTTP is mocked via the `responses` library. Edge cases covered include: retry exhaustion, robots.txt disallow, malformed URLs, empty queries, stop-word-only queries, phrase intersection, Levenshtein suggestions, and schema version rejection.

---

## Design decisions

**Positional index over term-presence index.** Storing token offsets enables phrase queries, snippet extraction, and proximity-aware retrieval without a second data structure.

**JSON over SQLite or pickle.** The brief requires a single file. JSON is human-readable, trivially portable, and supports schema evolution through an explicit version field.

**BM25 as default, TF-IDF as alternative.** BM25 outperforms TF-IDF on short documents because of document-length normalisation. Exposing both at runtime demonstrates separation between indexing and ranking and allows direct comparison.

**Set-union deduplication in the frontier.** The crawler tracks `seen` URLs separately from `visited` pages — duplicates are filtered before they enter the queue, not after.

---

## Limitations

- Single-threaded crawling
- ASCII tokenisation only (curly quotes stripped)
- No stemming or lemmatisation
- No PageRank or link-analysis

All intentionally excluded to stay within coursework scope.

---

## Stack

Python 3.12 · requests · BeautifulSoup4 · pytest · pytest-cov · responses · Ruff · MyPy

---

## References

- Manning, Raghavan & Schütze — *Introduction to Information Retrieval* (Cambridge, 2008)
- [Python Requests documentation](https://docs.python-requests.org/)
- [Beautiful Soup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- COMP3011 lecture slides 9–12