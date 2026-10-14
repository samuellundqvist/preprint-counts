# preprint-counts

Monthly counts of new papers on arXiv in every subject class of an archive,
counted by the month arXiv announced them, with an interactive page to explore
them. The repository holds the data for mathematics (`math.*`, January 2018 to
September 2026). The same scripts build the counts for other archives such as
computer science (`cs.*`).

Thank you to arXiv for use of its open access interoperability. This project
was not reviewed or approved by, nor does it necessarily express or reflect the
policies or opinions of, arXiv.

## What is counted

- Every paper with a category in the archive is fetched from the
  [arXiv API](https://info.arxiv.org/help/api/index.html).
- Each paper is counted once, under its **primary** category, in the month arXiv
  **announced** it. That month is the `YYMM` at the start of the identifier:
  `2609.01234` was announced in September 2026. Replacement versions keep their
  identifier and are not counted again.
- arXiv fixes the identifier when a paper goes out, so a paper held for
  moderation counts in the month it is released. A month's count is final once
  the month has ended.
- The API can only be searched by submission date, so the raw data is organised
  by v1-submission month. It starts in November 2017, two months before the
  first month shown, to catch papers submitted earlier and announced later.
- `aggregate.py` refuses to write unless every submission month has exactly the
  number of papers the API reported for it (`raw/manifest.tsv`).
- The page calls a class rising or falling only when its last twelve months
  differ from the twelve before by more than twice the counting noise,
  2√(a + b) for the two totals a and b. Smaller changes are reported as flat.

## Files

| Path | Contents |
|---|---|
| `config.py` | Archive, month range and paths shared by every script |
| `arxiv_api.py` | The only code that sends requests to arXiv; enforces the rate limit |
| `harvest.py` | Fetches submission months from the API |
| `repair.py` | Refetches a month day by day when the month-wide query does not add up |
| `pack.py` | Folds fetched months into the compressed archive |
| `aggregate.py` | Counts papers per month and class; writes the CSVs and `viz_data.json` |
| `update_page.py` | Puts the counts into the page |
| `categories.tsv` | Names of all subject classes, from arXiv's [category taxonomy](https://arxiv.org/category_taxonomy) |
| `data/math/raw/papers_2017-11_2026-09.jsonl.gz` | One line per paper (391,193 papers): identifier, v1 date, last-updated date, primary category, all categories |
| `data/math/raw/manifest.tsv` | Papers per submission month, as the API reported them |
| `data/math/arxiv_math_primary.csv` | Papers per announcement month and class, by primary category |
| `data/math/arxiv_math_anycat.csv` | The same, counting cross-listed papers in every class they list |
| `data/math/viz_data.json` | The data embedded in the page |
| `data/math/arxiv_math_submissions.html` | The page; open it in a browser |

The scripts need Python 3.8 or later and nothing outside the standard library.

## Rebuilding the page from the included data

```sh
python3 aggregate.py --write
python3 update_page.py
```

## Adding a month

Run this after month M has ended, with M-5 standing for the month five months
before M:

1. Set `HI = "M"` in `config.py`.
2. `python3 harvest.py M-5 M-4 M-3 M-2 M-1 M`. The five months before M are
   fetched again because papers submitted then can be announced in M. In 2026
   about 5% of a month's papers were announced a month or more after
   submission. For every month the harvest reports as INCOMPLETE, run
   `python3 repair.py <month>`.
3. `python3 pack.py --write`
4. `python3 aggregate.py --write`
5. `python3 update_page.py`

## Other archives

Set `ARXIV_ARCHIVE` to the archive's prefix for every command. Each archive gets
its own folder under `data/`. For computer science:

```sh
export ARXIV_ARCHIVE=cs
python3 harvest.py             # every submission month from 2017-11 to HI
python3 repair.py 2025-03 ...  # each month the harvest reports as INCOMPLETE
python3 pack.py --write
python3 aggregate.py --write
python3 update_page.py         # writes data/cs/arxiv_cs_submissions.html
```

- This works for archives with subject classes: `math`, `cs`, `stat`, `eess`,
  `econ`, `q-bio`, `q-fin`, `physics`, `astro-ph`, `cond-mat` and `nlin`.
  Archives without classes, such as `hep-th` or `quant-ph`, need a different query.
- A full harvest of a large archive makes many requests and, at one request
  every three seconds, takes a long time. Larger months fail the page check more
  often. `repair.py` then queries one day at a time and splits a busy day into
  smaller windows until each fits in a single response.
- The page takes the archive's name and prefix from the data. Its note on
  `math.IT`, `math.MP` and `math.GM` is shown only for mathematics.
- Some classes are aliases stored under another archive, so they never appear
  as a primary category in their own: `cs.NA` is `math.NA`, `cs.SY` is
  `eess.SY`, `math.IT` is `cs.IT`, `math.MP` is `math-ph`, `stat.TH` is
  `math.ST` and `q-fin.EC` is `econ.GN`.
- The page title for an archive is set in `TITLES` in `config.py`.

## Using the arXiv API

The scripts follow arXiv's [terms of use for its APIs](https://info.arxiv.org/help/api/tou.html):

- Every request goes through `arxiv_api.get()`, which allows at most one request
  every three seconds over a single connection. A lock file shared by all
  scripts and archives makes this hold across processes on one machine. arXiv
  counts all machines under your control together, so run harvests from one
  machine only, and don't remove the limiter.
- The metadata is free to use under
  [CC0](https://creativecommons.org/publicdomain/zero/1.0/). If you publish a
  page built with these scripts, keep the acknowledgement in its footer, and
  follow arXiv's [name and logo guidelines](https://info.arxiv.org/brand/brand-guidelines.html):
  don't present your project as connected to or endorsed by arXiv.

## Licence

The code is released under the MIT licence (see `LICENSE`). The data in `data/`
and `categories.tsv` is derived from arXiv metadata and is released, like that
metadata, under CC0 1.0.
