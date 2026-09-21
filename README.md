# Multi-Source Job Aggregator ![Status](https://img.shields.io/badge/status-under--development-red)

Scrapes student-level job postings (Werkstudent / Praktikum / Working Student / Intern) from several German job boards in one run, scores every job title against a configurable topic vocabulary with a sentence-embedding model, then visits the matching postings, stores their descriptions in a local SQLite database and lets an LLM of your choice judge each one against your résumé. The result is one CSV ranked by fit; between weekly runs only new postings are scraped and judged.

<p align="center">
  <img src="assets/multi-source-job-aggregation_high-level-pipeline.png" width="700">
</p>

### The problems it solves
- No need to repeat the same searches on different job boards. Edit the config once and let the project do the job-board hopping for you.
- No need to try every synonym by hand (Python Entwickler, Python Developer, Python Software Developer, …). List the phrasings once; the embedding match collapses them.
- No need to open every posting. Each description is scraped once, judged once against your résumé and remembered, so a weekly run only processes what is new.

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

**Stage 1 – title search**

1. For every enabled site, `location tiles × search keywords` search URLs are built, shuffled, and visited one by one in a persistent Google Chrome profile (real Chrome, cookies kept between runs, human-like random delays and scrolling).
2. Only the first results page of each query is read (no pagination). Every job title on it is cleaned (employment type, gender codes and contract noise stripped), embedded with `BAAI/bge-m3` and compared against the `match_keywords` vocabulary; titles scoring at or above `embedding_match_config.threshold` are accepted, the rest are kept as rejected with a reason so the threshold can be tuned.
3. Results of every source are written to `data/raw/` as soon as that source finishes, then all accepted jobs are merged, ranked by score, de-duplicated by URL and stored in `data/database/app.db`. A URL already seen in an earlier run is only marked as seen again.

**Stage 2 – description and résumé judge**

4. For every accepted URL without a description yet (best title score first, at most `max_detail_pages_per_platform` per site and run) the posting page is opened in the same Chrome profile. Title, company, location, employment type, date and description are taken from the page's `JobPosting` JSON-LD block, with CSS selectors as fallback; expired postings are marked and skipped. Every page is saved to the database immediately.
5. Each stored description is sent, together with your résumé, to the LLM configured in `.env` (any OpenAI-compatible endpoint: OpenRouter, Groq, OpenAI, Anthropic, …). The model returns a JSON verdict (fit score 0–100, employment type, whether the level fits, language requirement, matched skills, missing must-haves, a short reason) which is stored next to the description. The final CSV lists all judged jobs by fit score and flags the ones first seen in this run.

Safety valves: a single failing query or page is skipped, not fatal; a site that starts blocking (CAPTCHA / "access denied" page, or several failures in a row) trips a circuit breaker that aborts *that* scraper and keeps what it had collected; a posting page that fails twice is left alone; the judge stops on a bad API key or model name and after several failed calls in a row; `Ctrl-C` keeps everything saved so far.

## Setup

Requirements: Python 3.12+, Google Chrome installed (Playwright drives your installed Chrome, no `playwright install` needed).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then:

1. Set `browser_profile_path` in `src/config/scraper_common_config.py` to a directory Chrome may use as its profile. Visit the job sites once in that profile and accept their cookie banners; a warmed-up profile is what keeps the anti-bot checks quiet.
2. Save your résumé as plain text or markdown at `data/resume/resume.md` (or change `resume_path` in `src/config/stage2_config.py`). `data/` is gitignored.
3. Create `.env` in the repo root (copy `.env.example`) with the LLM endpoint:

```
LLM_BASE_URL=https://openrouter.ai/api/v1   # or https://api.groq.com/openai/v1, https://api.openai.com/v1, ...
LLM_API_KEY=...
LLM_MODEL=...                                # the provider's model id
```

Switching providers means changing these three lines, nothing else.

## Run

```bash
python src/main.py
```

`run_stage_1` / `run_stage_2` in `src/config/scraper_common_config.py` switch either stage off. Stage 2 alone scrapes and judges whatever is still pending in the database – useful after changing the prompt or the model (set `rejudge_when_model_changes` to re-score everything with a new model).

`src/` is the import root. To run a single scraper on its own (stage 1 then stage 2 for that site) or only the judge pass:

```bash
PYTHONPATH=src python src/sources/indeed_scraper.py    # Windows: set PYTHONPATH=src
PYTHONPATH=src python src/utils/llm_judge.py
```

In PyCharm, mark `src` as *Sources Root* once and every run configuration works without the variable.

The first run downloads the embedding model (~2 GB). A full stage-1 run over all four sites is ~300 queries, roughly 50 minutes with the default throttling; stage 2 adds about 10 s per new posting.

## Configuration

`src/config/scraper_common_config.py` (shared by all scrapers):

| Key | Meaning |
|-----|---------|
| `use_<site>_scraper` | enable / disable a source (both stages) |
| `run_stage_1`, `run_stage_2` | run the title search / the description + judge stage |
| `browser_profile_path` | persistent Chrome profile directory |
| `search_keywords` | phrasings sent to the sites – keep this list short, every entry costs one page load per location tile |
| `match_keywords` | vocabulary that scraped titles are scored against – never sent to a site, keep it broad |
| `embedding_match_config` | sentence-embedding model and the acceptance `threshold` |
| `throttle_config` | random delay ranges between queries, interactions, page loads and sources, plus scroll behaviour |
| `circuit_breaker.max_consecutive_failures` | failed queries or pages in a row before a scraper aborts |

`src/config/<site>_scraper_config.py` (one per site):

| Key | Meaning |
|-----|---------|
| `BASE_URL` | search URL template |
| `location_radius_pairs` | location tiles to query. Tiles should not overlap – with page 1 only, nested circles return the same page again. Allowed radii differ per site and are listed in each file |
| `job_age` | posting age filter. Allowed values, the weekly-cadence value and the catch-up value are in each file's comment |
| `use_headless_mode` | keep `False` for Indeed, Xing and Stepstone – they block headless browsers |
| `cookie_button` | cookie-banner button clicked when visible (`None` = no handling) |
| `search_page` | selectors for the results page (stage 1) |
| `detail_page` | selectors and expired-page phrases for the posting page (stage 2); `description` / `company` / `location` are fallback lists, first match wins |

`src/config/stage2_config.py`:

| Key | Meaning |
|-----|---------|
| `resume_path` | plain-text / markdown résumé the judge reads |
| `max_detail_pages_per_platform` | posting pages per site and run; the rest stay pending for the next run |
| `max_description_attempts` | failed page loads before a URL is given up on |
| `max_description_chars` | longer descriptions are cut before judging |
| `throttle.between_detail_pages` | random delay between posting pages |
| `llm.temperature`, `llm.max_tokens`, `llm.use_json_response_format` | request parameters; set to `None` / `False` for providers that reject them |
| `llm.timeout_seconds`, `llm.max_consecutive_failures`, `llm.delay_between_calls` | judge pass safety valves |
| `llm.rejudge_when_model_changes` | re-score jobs that were judged by a different model |
| `llm.min_fit_score_to_report` | rows below this score are left out of the ranked CSV |

`.env`: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (stage 2); `ADZUNA_APP_ID`, `ADZUNA_API_KEY`, `FINDWORK_API_KEY`, `JOOBLE_API_KEY` (inactive REST pipeline only).

## Output

| File | Content |
|------|---------|
| `data/raw/<source>_jobs_<run timestamp>.csv` | every title seen on that source: accepted rows have `rejection_reason` empty, rejected rows say why (`below_threshold`, `title_extraction_failed`) – use these to tune the threshold and the keyword lists |
| `data/raw/<source>_descriptions_<run timestamp>.csv` | every posting page visited in this run: status (`ok`, `expired`, `pending` = failed once, `failed`), which extraction path worked (`json_ld` / `css`), company, location, employment type, date, description length |
| `data/processed/title_ranked_jobs_<run timestamp>.csv` | stage-1 result: accepted jobs from all sources, ranked by title score, URL-de-duplicated |
| `data/processed/ranked_jobs_<run timestamp>.csv` | stage-2 result: all judged jobs ranked by `fit_score`, with the verdict fields and `is_new_this_run` |
| `data/duplicates/duplicates_<run timestamp>.csv` | the copies dropped by the URL de-duplication |
| `data/database/app.db` | SQLite store of every job ever seen: stage-1 score, description, verdict, run timestamps – the source of truth between runs |

## Roadmap

- Cross-source duplicates: merge the same posting from different boards on company + location + title (the fields are stored now).
- Track application status per job (a `user_status` column is reserved).
- Wire "newest first" sorting for Xing, Stepstone and StudySmarter (Indeed already sorts by date), and add per-query yield logging to find saturated or useless queries.
- Pagination, if page 1 turns out to be too little.

> **Project Status:** work in progress — ongoing development.
