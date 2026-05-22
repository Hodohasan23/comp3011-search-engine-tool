# Technical Log — COMP3011 Search Engine Tool

This log records the engineering decisions behind each component, problems I ran into during development, how I fixed them, and what I ruled out. It sits alongside the README rather than in it — the README explains what the system does; this explains why it was built this way.

---

## 1. Requirements re-read

Before writing any code I extracted the constraints that actually shape architecture:

- Target: `https://quotes.toscrape.com/` — ~213 pages, all on one host.
- Politeness: ≥ 6 s between requests (brief §1.b).
- Index must store per-term, per-page statistics: at minimum frequency and position.
- Search must be case-insensitive and full-word (`friends ≠ friendship`).
- CLI must support `build`, `load`, `print <word>`, `find <query>`.

Rubric weights that shaped priority ordering:

| Component | Weight | Implication |
|---|---|---|
| Testing & coverage | 20% | ≥ 85% line coverage, edge cases, mocked HTTP — non-negotiable |
| Search functionality | 12% | Multi-word AND, ranking — needs to work correctly |
| GenAI critical evaluation | 15% | Covered in the video — not a code concern |
| Version control | 5% | Regular, meaningful commits throughout |

The testing weight being the single largest category meant I wrote tests alongside implementation, not after.

---

## 2. Module breakdown

I split the work into four modules matching the brief's structure exactly:

```
src/crawler.py    HTTP + BFS crawler
src/indexer.py    tokenisation, data structure, persistence, schema
src/search.py     query logic, ranking, phrase search, did-you-mean, snippets
src/main.py       argparse entry point, CLI, REPL
```

The key separation: the crawler returns `{url: html}` and has no knowledge of how that HTML gets indexed. The ranker knows only how to score a set of candidate URLs; it has no knowledge of how candidates were selected. This made unit testing each module independently straightforward.

---

## 3. Crawler

### URL normalisation

Deduplication breaks if the same page has two representations. Rules applied in order:

1. Resolve relative URLs against the base with `urljoin`.
2. Strip fragments with `urldefrag` — `#section` is client-side only.
3. Lowercase scheme and host — HTTP semantics treat these as case-insensitive.
4. Drop default ports — `:80` on http and `:443` on https are semantically identical to no port.
5. Empty path becomes `/`.

I considered normalising query parameters (sorting keys, dropping UTM tags) but `quotes.toscrape.com` uses clean paths with no query strings, so this would have added complexity for zero gain.

### Frontier

`collections.deque` for the queue. `list.pop(0)` is O(n) — pointless when an O(1) alternative exists. Deduplication uses a separate `seen: set[str]` keyed by normalised URL. The seen set filters duplicates *before* they enter the queue, not after they are dequeued — this avoids queuing the same URL N times and then skipping it N-1 times.

### Politeness

```python
def wait_for_politeness(self) -> None:
    if self.last_request_time is None:
        return
    elapsed = time.monotonic() - self.last_request_time
    remaining = self.politeness_window - elapsed
    if remaining > 0:
        self.sleep(remaining)
```

`sleep` is constructor-injected. Tests pass `lambda t: None`. The suite runs in under 7 seconds without waiting 6 seconds per mock request. `time.monotonic` is preferred over `time.time` because it is unaffected by system clock adjustments.

The alternative — `time.sleep(6)` unconditionally after every fetch — oversleeps when the request itself takes several seconds. The implementation above waits exactly as long as needed to maintain the gap.

### Retry and back-off

| Status / exception | Behaviour |
|---|---|
| 200 + `text/html` | Accept, return HTML |
| 200 + other content-type | Reject, return `None`, record in `failed` |
| 4xx | Permanent failure, no retry |
| 5xx / `RequestException` | Retry up to `max_retries`, exponential back-off (`backoff` multiplier) |
| All retries exhausted | Return `None`, record `"Maximum retries exceeded"` |

Back-off sleep goes through the same injected callable so tests stay fast.

### Problems encountered

**`User-Agent` not being set.** First attempt used `session.headers.setdefault(...)` which silently kept the requests library's default because `User-Agent` is pre-populated. Fixed by direct assignment. Added a test that reads the header back to prevent regression.

**Retry tests slow.** Back-off was using `time.sleep` directly. Fixed by passing `backoff=0` in test helpers that don't need realistic delays.

---

## 4. Indexing

### Data structure

```python
terms: dict[str, dict[str, Posting]]   # term → url → {tf, positions}
doc_lengths: dict[str, int]            # url → token count
doc_tokens: dict[str, list[str]]       # url → full token list
```

URLs are used directly as document identifiers rather than integer IDs. Integer IDs reduce JSON size by roughly half (no repeated URLs in every posting), but require a lookup table on every retrieval operation. At 213 pages the index fits comfortably in memory either way, and URL keys make the JSON directly readable for debugging and marking.

`doc_tokens` stores the full token sequence per page. This is the main space cost beyond the inverted index itself, but it means snippet generation never has to re-parse HTML at query time.

### Tokenisation

```python
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

def tokenize(text: str, remove_stopwords: bool = False) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    if remove_stopwords:
        return [t for t in tokens if t not in STOPWORDS]
    return tokens
```

`[a-z0-9]+` rather than `\w+` because `\w` matches unicode letters. That sounds helpful but means `café` becomes one token and `cafe` becomes another — they never match. The corpus is ASCII. The brief asks for case-insensitive full-word matching, which this implements exactly.

No stemming. The brief explicitly requires `friends ≠ friendship`. Stemming would collapse them.

Stop-words are removed at **index time** for two reasons: it reduces the index size by roughly 30%, and it makes position numbers consistent between index and query. The trade-off is that stop-words cannot appear in phrase queries — `find "to be"` returns nothing because both tokens were removed. This is documented in the README and is standard IR practice.

### Boilerplate stripping

Before tokenising, BeautifulSoup decomposes `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, and `<aside>`. Text is extracted from `soup.body` only — not the full document — to prevent `<title>` content leaking into the index.

**Problem:** First version extracted from the full document. Every page on `quotes.toscrape.com` has `<title>Quotes to Scrape</title>`, which gave `quotes` and `scrape` a document frequency of N (one per page). They appeared in every result and dominated snippet output. Fixed by restricting extraction to `soup.body`. Regression test added.

### Schema versioning

The index JSON includes `"version": 1`. `InvertedIndex.load()` raises `ValueError` on any other value. This prevents silent data corruption if the schema changes between builds. The test suite includes a test for version rejection.

---

## 5. Ranking

### Why BM25 as default

BM25 and TF-IDF both satisfy the rubric's 80–100 band requirement for ranking. I implemented both because:

1. BM25 is strictly better on short documents due to document-length normalisation. A high-frequency term on a 20-token page scores differently to the same frequency on a 200-token page.
2. Exposing both at runtime demonstrates that indexing and ranking are cleanly separated — you can swap the ranker without touching the index.
3. The rubric names TF-IDF explicitly. Having it as an alternative means I satisfy that criterion while defaulting to the stronger model.

### BM25

```
score = Σ  IDF(t) · tf · (k1 + 1) / (tf + k1 · (1 − b + b · dl/avgdl))
IDF(t) = log(1 + (N − df + 0.5) / (df + 0.5))
k1 = 1.5,  b = 0.75
```

The `(N − df + 0.5) / (df + 0.5)` form rather than the simpler `log(N/df)` avoids problems when `df = 0` and weights terms that appear in all documents near zero.

### TF-IDF

```
score = Σ  (1 + log tf) · (log((N+1)/(df+1)) + 1)
```

Sub-linear TF (log form) dampens the impact of keyword repetition. Smoothed IDF keeps scores finite when `df = 0`.

### Ranker factory

```python
def create_ranker(index: InvertedIndex, method: str = "bm25") -> Ranker:
    if method == "bm25":
        return BM25Ranker(index)
    if method == "tfidf":
        return TFIDFRanker(index)
    raise ValueError(f"Unknown ranking method: {method}")
```

`Ranker` is a `Protocol` — both rankers implement `score(query_terms, url) -> float` without inheriting from a base class. This keeps the interface explicit without requiring inheritance.

---

## 6. Search engine

### Find semantics

`find()` takes a raw query string and applies this pipeline:

1. `parse_query()` — extract phrase-quoted substrings, tokenise the remainder as free terms.
2. For free terms: intersect posting sets (AND semantics). Any term with no postings short-circuits to `[]`.
3. For phrases: `urls_containing_phrase()` — positional posting intersection.
4. Intersect phrase results with free-term results.
5. Score each candidate URL, sort descending by score then ascending by URL for determinism.

AND semantics rather than OR because the brief's example `find good friends` clearly expects documents containing both words. OR would return any document containing either term — much noisier for a precision-oriented tool.

### Phrase queries

Positional posting intersection (Manning §2.4.1). For phrase tokens `[t0, t1, ..., tn]`:

1. Intersect posting URLs — candidate must contain every token.
2. For each candidate URL, shift each token's position list by its offset in the phrase: `{p − offset for p in positions}`.
3. Intersect all shifted sets. A non-empty intersection means the tokens appear consecutively.

Why this works: if tokens appear consecutively starting at position `p`, their position lists contain `p, p+1, p+2, ...`. Shifting each by its offset makes all aligned occurrences map to the same value `p`. Non-aligned occurrences produce different values and are filtered out.

### Did-you-mean

When `find()` returns no results, `suggest_terms()` is called on each query token. `QueryProcessor.suggest_term()`:

1. Pre-filter vocabulary: skip any term where `|len(vocab) − len(query)| > max_distance`. This eliminates most vocabulary terms without any DP computation.
2. Compute Levenshtein distance for remaining candidates.
3. Return the closest match within `max_distance=2`, breaking ties alphabetically.

Levenshtein over Soundex because the corpus is literary English text with typical typos (`indiffrence`, `friedns`) — edit distance captures these better than phonetic encoding.

### Snippet generation

```python
def snippet(self, url: str, query_terms: list[str], window: int = 6) -> str:
    tokens = self.index.doc_tokens.get(url, [])
    if not tokens:
        return ""
    query_set = set(query_terms)
    match_position = next(
        (i for i, t in enumerate(tokens) if t in query_set), 0
    )
    start = max(0, match_position - window)
    end = min(len(tokens), match_position + window + 1)
    return " ".join(tokens[start:end])
```

`doc_tokens` stores the pre-tokenised sequence so this is a list slice — no HTML parsing at query time.

---

## 7. Testing strategy

### Structure

Tests live in files mirroring the source modules. Each file tests one module in isolation using only that module's public interface.

### HTTP mocking

All crawler tests use the `responses` library rather than `unittest.mock.patch('requests.get')`. The difference: `responses` intercepts at the transport layer and produces realistic `requests.Response` objects including headers, status codes, and content-type. Patching `requests.get` directly is more brittle — it breaks if the crawler calls `session.get` instead, and it requires constructing mock response objects manually.

The crawler's `sleep` callable is injected so tests can pass `lambda t: None`. Without this, a test with three retries would wait `backoff * 3` seconds. The full suite runs in under 7 seconds.

### Edge cases covered

The cases most likely to lose coverage marks, and how they're covered:

| Edge case | Why it matters | Test |
|---|---|---|
| Empty query | Should return `[]` cleanly, not raise | `test_find_empty_query_returns_empty_list` |
| Stop-word-only query | All tokens filtered, no postings to intersect | `test_find_stop_word_only_query_returns_empty` |
| Phrase with no consecutive match | Positions exist but not adjacent | `test_phrase_search_rejects_non_consecutive_terms` |
| Schema version mismatch | Corrupt or stale index | `test_load_rejects_unsupported_schema_version` |
| All retries exhausted | Network permanently unavailable | `test_fetch_returns_none_after_all_retries_fail` |
| robots.txt disallow | Crawler must respect it | `test_crawl_records_disallowed_url` |
| Non-HTML content | PDF, images must be skipped | `test_fetch_skips_non_html_content` |
| Empty document | Page with no visible text | `test_add_empty_document_does_not_crash` |
| BM25/TF-IDF on empty index | No division-by-zero | `test_bm25_score_empty_index_returns_zero` |

### Coverage result

121 tests, 99% total coverage, all checks passing.

```
Name              Stmts   Miss  Cover
---------------------------------------
src/__init__.py       0      0   100%
src/crawler.py      142      1    99%
src/indexer.py       63      0   100%
src/main.py         148      2    99%
src/search.py       192      0   100%
---------------------------------------
TOTAL               545      3    99%
```

---

## 8. Full crawl — 13 May 2026

Live crawl against `https://quotes.toscrape.com/` with 6 s politeness delay:

| Metric | Value |
|---|---|
| Pages fetched | 214 |
| Failed | 0 |
| Disallowed by robots.txt | 0 |
| Unique terms indexed | 4,445 |
| Total tokens | 36,821 |
| Average tokens per page | 85.2 |
| Index file size | ~694 KB |
| Wall-clock time | ~22 min |

Sample queries against the live index:

| Query | Hits | Notes |
|---|---|---|
| `find indifference` | 11 | Works as expected |
| `find good friends` | 19 | AND semantics |
| `find "good friends"` | 2 | Phrase — consecutive only |
| `find friendship` | 22 | Different result set from `friends` — full-word confirmed |
| `find the` | 0 | Stop-word filtered at index time |
| `find indiffrence` | 0 + suggestion | Did-you-mean returns `indifference` |

`login` and `scrape` both have `df = 0`, confirming the body-only extraction is correctly stripping the site-wide header and title.

---

## 9. Features beyond the brief

The 80–100 rubric band asks for "advanced features beyond requirements." Four were implemented:

**BM25 ranking.** The brief names TF-IDF explicitly; BM25 is an improvement over it on short documents. Both are available at runtime via `--ranking bm25/tfidf`.

**Positional phrase queries.** `find "good friends"` matches only pages where the tokens appear consecutively. The brief does not require this. Implementation uses stored position offsets — the same data structure that powers snippets.

**Did-you-mean suggestions.** When a query returns no results, the engine suggests the closest vocabulary term by Levenshtein distance. The brief does not require this.

**Search result snippets.** Each result shows a window of tokens around the first match. Implemented using `doc_tokens` stored at index time.

---

## 10. Complexity

| Operation | Time complexity | Notes |
|---|---|---|
| `crawl()` | O(N · L) | HTML parse + link extraction per page |
| `add_document()` | O(L) | Tokenise + hash insert per token |
| `save()` / `load()` | O(N · L) | JSON serialise/deserialise |
| `find()` — AND | O(Q · min_df) | Intersect smallest posting set first |
| `find()` — phrase | O(Q · df · P) | P = positions per term per doc |
| `snippet()` | O(W) | W = window size, list slice |
| `suggest_term()` | O(V · \|t\|²) worst case | Pre-filters eliminate most of V |

### Observed numbers (benchmarked on a 2024 MacBook Air, 20 runs each)

| Operation | Mean | Stdev |
|---|---|---|
| Tokenise 50-token page (stop-words off) | 0.064 ms | ±0.038 |
| Tokenise 500-token page (stop-words on) | 0.177 ms | ±0.021 |
| Index 200 docs × 50 tokens | 20.0 ms | ±1.4 |
| Index 200 docs × 100 tokens | 31.4 ms | ±1.9 |
| Save 200-doc index | 84.5 ms | ±3.5 |
| Load 200-doc index | 14.2 ms | ±1.6 |
| Find single term (200 docs, BM25) | 0.005 ms | ±0.002 |
| Find two-term AND (200 docs) | 0.006 ms | ±0.001 |
| Find phrase query (200 docs) | 0.008 ms | ±0.002 |
| Find unknown + did-you-mean | 0.001 ms | ±0.000 |

All search operations are sub-millisecond regardless of index size — the 50-doc and 200-doc timings are nearly identical, confirming the O(df) retrieval is efficient in practice. The crawl is the only slow operation, and that is entirely the 6 s politeness window, not CPU.

Benchmarks reproducible via:

```bash
python -m benchmarks.benchmark
```

---

## 11. Limitations

These were ruled out deliberately, not overlooked:

**Single-threaded crawler.** With a 6 s politeness window the bottleneck is HTTP latency, not CPU. Parallelism would not meaningfully reduce crawl time on this site.

**No conditional GET.** Re-crawling always fetches every page. `If-Modified-Since` would be the right fix for an incremental crawler. Out of scope for a one-shot coursework submission.

**ASCII tokenisation.** `quotes.toscrape.com` uses ASCII text. Unicode-aware tokenisation would change nothing on this corpus and would complicate the `friends ≠ friendship` test cases.

**No stemming.** The brief requires full-word matching. Stemming violates this.

**Binary stop-word list.** A weighted or context-sensitive stop-word list (e.g. BM25's IDF already down-weights high-frequency terms) would be more principled. The inline list is sufficient for this corpus.