# Multi-Source Job Aggregator ![Status](https://img.shields.io/badge/status-under--development-red)

Scrapes student-level job postings (Werkstudent / Praktikum / Working Student / Intern) from several German job boards in one run, scores every title against a configurable topic vocabulary with a sentence-embedding model, and writes one ranked, de-duplicated CSV.

<p align="center">
  <img src="assets/multi-source-job-aggregation_high-level-pipeline.png" width="700">
</p>

### The two problems it solves
- No need to repeat the same searches on different job boards. Edit the config once and let the project do the job-board hopping for you.
- No need to try every synonym by hand (Python Entwickler, Python Developer, Python Software Developer, …). List the phrasings once; the embedding match collapses them.

## Sources

| Source | Type | Status |
|--------|------|--------|
| Indeed (`de.indeed.com`) | Playwright browser scraper | active |
| Xing Jobs | Playwright browser scraper | active |
| Stepstone | Playwright browser scraper | active |
| StudySmarter Talents | Playwright browser scraper | active |
| Adzuna, Arbeitsagentur, Findwork, Jooble | REST APIs | inactive – older pipeline under `src/sources/`, not wired into `main.py` |

Each browser scraper can be switched on or off with the `use_<site>_scraper` knobs in `src/config/scraper_common_config.py`.

## How a run works

1. For every enabled site, `location tiles × search keywords` search URLs are built, shuffled, and visited one by one in a persistent Google Chrome profile (real Chrome, cookies kept between runs, human-like random delays and scrolling).
2. Only the first results page of each query is read (no pagination). Every job title on it is cleaned (employment type, gender codes and contract noise stripped), embedded with `BAAI/bge-m3` and compared against the `match_keywords` vocabulary; titles scoring at or above `embedding_match_config.threshold` are accepted, the rest are kept as rejected with a reason so the threshold can be tuned.
3. Results of every source are written to `data/raw/` as soon as that source finishes, then all accepted jobs are merged, ranked by score and de-duplicated by URL into `data/processed/`.

Safety valves: a single failing query is skipped, not fatal; a site that starts blocking (CAPTCHA / "access denied" page, or several failed queries in a row) trips a circuit breaker that aborts *that* scraper and keeps what it had collected; `Ctrl-C` saves everything collected so far before stopping.

## Setup

Requirements: Python 3.12+, Google Chrome installed (Playwright drives your installed Chrome, no `playwright install` needed).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then set `browser_profile_path` in `src/config/scraper_common_config.py` to a directory Chrome may use as its profile. Visit the job sites once in that profile and accept their cookie banners; a warmed-up profile is what keeps the anti-bot checks quiet.

## Run

```bash
python src/main.py
```

`src/` is the import root. To run a single scraper on its own (each has an `if __name__ == "__main__":` block):

```bash
PYTHONPATH=src python src/sources/indeed_scraper.py    # Windows: set PYTHONPATH=src
```

In PyCharm, mark `src` as *Sources Root* once and every run configuration works without the variable.

The first run downloads the embedding model (~2 GB). A full run over all four sites is ~300 queries, roughly 50 minutes with the default throttling.

## Configuration

`src/config/scraper_common_config.py` (shared by all scrapers):

| Key | Meaning |
|-----|---------|
| `use_<site>_scraper` | enable / disable a source |
| `browser_profile_path` | persistent Chrome profile directory |
| `search_keywords` | phrasings sent to the sites – keep this list short, every entry costs one page load per location tile |
| `match_keywords` | vocabulary that scraped titles are scored against – never sent to a site, keep it broad |
| `embedding_match_config` | sentence-embedding model and the acceptance `threshold` |
| `throttle_config` | random delay ranges between queries, interactions, page loads and sources, plus scroll behaviour |
| `circuit_breaker.max_consecutive_failures` | failed queries in a row before a scraper aborts |

`src/config/<site>_scraper_config.py` (one per site):

| Key | Meaning |
|-----|---------|
| `BASE_URL` | search URL template |
| `location_radius_pairs` | location tiles to query. Tiles should not overlap – with page 1 only, nested circles return the same page again. Allowed radii differ per site and are listed in each file |
| `job_age` | posting age filter. Allowed values, the weekly-cadence value and the catch-up value are in each file's comment |
| `use_headless_mode` | keep `False` for Indeed, Xing and Stepstone – they block headless browsers |

## Output

| File | Content |
|------|---------|
| `data/raw/<source>_jobs_<run timestamp>.csv` | every title seen on that source: accepted rows have `rejection_reason` empty, rejected rows say why (`below_threshold`, `title_extraction_failed`) – use these to tune the threshold and the keyword lists |
| `data/processed/ranked_jobs_<run timestamp>.csv` | accepted jobs from all sources, ranked by score, URL-de-duplicated |
| `data/duplicates/duplicates_<run timestamp>.csv` | the copies dropped by the URL de-duplication |

Columns: `title, url, title_keyword_emd_match_score, job_posting_platform, rejection_reason`.

## Roadmap

- Stage 2: visit every accepted URL, scrape the job description and match it against a résumé; the title stage is deliberately permissive (no employment-level filtering) because the description decides that far better.
- Persist seen jobs between runs (`data/database/app.db` is reserved for this) so a weekly run reports only new postings and cross-source duplicates can be merged on company/location rather than URL.
- Wire "newest first" sorting for Xing, Stepstone and StudySmarter (Indeed already sorts by date), and add per-query yield logging to find saturated or useless queries.
- Pagination, if page 1 turns out to be too little.

> **Project Status:** work in progress — ongoing development.
