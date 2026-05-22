# GenAI Reflection — COMP3011 CW2

**Author:** Hodo Hassan  
**Tool:** Claude (Anthropic), accessed via claude.ai  
**Declaration:** Claude was used as a pair-programmer throughout the build. All design decisions, verification, and testing strategy were my own. Every line of code in this submission is code I can explain and defend.

---

The most honest thing I can say about working with AI on this project is that it changed *where* the difficulty was, not how much difficulty there was. Implementation got faster. Understanding got harder to force myself to do. This reflection is about the specific moments where that tension produced something worth learning from.

---

### The title leak — a bug that only exists in the data

The indexer's first version used `BeautifulSoup(html).get_text()` to extract visible page text before tokenising. Claude wrote it. I read it. It looked correct. It is wrong in a way that is invisible unless you look at what the index actually contains.

Every page on `quotes.toscrape.com` has the same `<title>Quotes to Scrape</title>`. Default BeautifulSoup extraction walks the entire DOM including `<head>`, so the words `quotes` and `scrape` were indexed on every single page — document frequency equal to 214, the total number of crawled pages. In BM25 and TF-IDF, terms with `df ≈ N` have an IDF close to zero and should be near-invisible in rankings. But they were appearing in every snippet window and dominating `print` output because they saturated `doc_tokens`.

The fix was restricting extraction to `soup.body`. Five minutes. The lesson took longer. No unit test caught this because my synthetic HTML had no `<title>` tags. The problem surfaced only when I ran the full crawl and printed the top terms by document frequency. `quotes: df=214`. That number should not exist for a content term. The only reason I recognised that it was wrong was that I understood what document frequency is *for*.

This is the thing AI cannot do: it has no runtime. It cannot generate a real crawl, look at the resulting distribution, and notice that two words appear in every document. That empirical loop — generate data, measure, ask whether the numbers make sense — is entirely outside what an AI assistant can initiate. I had to bring it myself.

---

### The User-Agent bug — correct-looking code, wrong behaviour

The crawler's first version registered its custom User-Agent with:

```python
session.headers.setdefault("User-Agent", self.user_agent)
```

This is idiomatic defensive Python. It is also a no-op. `requests.Session` ships pre-populated with `User-Agent: python-requests/x.y`, so `setdefault` finds the key already present and does nothing. My custom agent never left the machine.

The bug was invisible from reading the code. It surfaced because I wrote a test that asserted on the actual header value after construction — not just that the constructor ran, but that the observable effect happened. That choice was mine. Claude's default test generation tends to check control flow and exception handling. It does not naturally ask "does the thing I claimed to do actually happen at the system boundary?" Writing that question into a test requires knowing that the system boundary exists and that the internal logic and external effect can diverge.

After I found it, the fix was one word: `update` instead of `setdefault`. But the finding mechanism — checking observable outputs — is a habit I now apply everywhere, and I did not have it before.

---

### Scope conservatism — when AI's caution is the wrong answer

The first plan Claude produced did not include BM25, phrase queries, or did-you-mean suggestions. The brief does not require any of them. Claude read the requirements, identified the mandatory features, and planned for exactly those. The rubric's 80–100 band explicitly names "advanced features beyond requirements" including ranking and query suggestions — but Claude treated this as aspirational rather than something to ship.

I overrode it three times. Each time, Claude implemented the feature correctly and quickly. The issue was never capability. It was that Claude's training pulls it toward conservative scope: do what is asked, flag everything else as future work. That is reasonable advice for a production system. It is the wrong advice for a coursework submission where the assessment criteria reward going beyond the brief.

The lesson here is specific to how RLHF-trained assistants behave: they have been rewarded for hedging, so faced with an ambiguous goal they will anchor on the minimum viable interpretation. **Knowing when to overrule that conservatism is a skill. It requires reading the rubric yourself, forming your own view of what the goal actually is, and being willing to push back.** Claude cannot tell you when its own caution is miscalibrated. You have to notice that yourself.

---

### Defensive code I did not ask for — and what I did about it

Inside `extract_links` there is a guard for `href` attributes that arrive as Python lists rather than strings — a BeautifulSoup edge case with multi-valued HTML attributes. Claude added it without being asked. It is also correct: the edge case exists, and without the guard the URL normaliser crashes on certain malformed pages.

I kept it. But I spent time understanding it before I did: specifically, which HTML attributes BeautifulSoup returns as lists, why, and what the HTML specification says about multi-valued attributes. That took ten minutes. The alternative — shipping defensive code without understanding what it is defending against — means you cannot reason about whether the defence is sufficient, whether it introduces its own bugs, or whether it is even necessary. In this case it is fine. In a larger system, unexamined defensive code is how subtle errors survive review for months.

The habit I took from this: any time Claude added something I had not asked for, I stopped and traced it back to a specific failure mode before moving on. This slowed me down. It also meant I understood every part of the system by the time I had to explain it.

---

### Understanding BM25 — the gap between using and knowing

Claude implemented BM25 correctly in about two minutes. I understood why it has the shape it does in about two hours, after reading Robertson & Zaragoza (2009) and Manning §11.

The formula's IDF term — `log(1 + (N − df + 0.5) / (df + 0.5))` — uses that specific form rather than the simpler `log(N/df)` to avoid numerical instability when `df` approaches zero or N. The `k1` and `b` parameters control term frequency saturation and document-length penalty respectively; the standard values are empirically derived from TREC benchmark collections, not analytically optimal. None of that is in the code. Claude did not explain it unprompted.

This is the gap that AI collaboration creates and that I think is the most important thing to name honestly: **Claude collapsed the time between seeing BM25 and shipping BM25. It did not collapse the time between shipping it and understanding it.** For this coursework, where I have to explain every design decision in a five-minute video, closing that gap was not optional. For someone less careful, it would be easy to submit a system built on formulas you cannot derive and data structures you cannot justify. The code would look the same. The understanding would not be there.

---

### What I would do differently

**Start with the verification script.** A script that checks top terms by document frequency, confirms that boilerplate words have `df = 0`, and runs sample queries against known expected outputs would have caught the `<title>` leak in the first test crawl. I built it late. It should have been the first thing.

**Override scope conservatism on day one.** I knew from reading the rubric that phrase queries and did-you-mean were worth implementing. I waited for Claude to suggest them. It did not. I should have put them in the plan before writing a single line of code.

**Read the relevant Manning chapters before approving AI's data structure proposals.** Claude's index structure was correct. I approved it, then read Manning §1–2, then understood why it was correct. The right order is the reverse. It would not have changed the code. It would have changed how quickly I could defend the code.

---

### What this actually taught me

AI made me faster at building. It did not make me a better IR engineer on its own. Every significant insight in this project came from a moment where AI was insufficient: the `<title>` leak surfaced from looking at real data, the `User-Agent` bug surfaced from testing observable outputs, the BM25 understanding came from reading Manning. Claude was the thing I was working with. The engineering judgment was the thing I had to bring myself.

I think that is the honest answer to what GenAI changes about learning. It removes friction from implementation and adds friction to understanding, because the understanding now has to be forced — it no longer emerges naturally from the struggle of writing the code. That is a trade worth making if you know it is happening. It is a trap if you do not.