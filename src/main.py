import time
import pandas as pd
from loguru import logger
from datetime import datetime
from pprint import pprint
from config.path_config import RAW_FOLDER_PATH, DUPLICATES_FOLDER_PATH, PROCESSED_FOLDER_PATH
from config.scraper_common_config import scraper_common_config
from src.sources.stepstone_scraper import StepstoneScraper
from src.sources.indeed_scraper import IndeedScraper
from src.sources.xing_scraper import XingScraper
from src.sources.study_smarter_scraper import StudySmarterScraper
from src.utils.util import load_embedding_model_and_keyword_embeddings, normalize_job_url
from src.utils.throttle import delay_between_sources

# Browser scrapers only -- the REST API sources (Adzuna/Arbeitsamt/Arbeitnow/Findwork)
# use a different, currently-inactive pipeline (config/common_config.py +
# src/utils/validate_config.py) and are intentionally not wired in here.
SCRAPER_CLASSES = {
    "stepstone": StepstoneScraper,
    "study_smarter": StudySmarterScraper,
    "indeed": IndeedScraper,
    "xing": XingScraper,
}


def run_all_scrapers(embedding_model, keyword_embeddings) -> dict[str, tuple[list[dict], list[dict]]]:
    """
    Runs each scraper sequentially -- never in parallel, since concurrent
    persistent browser profiles would fight over the same profile lock, and
    hitting several sites at once is itself a less human-like traffic
    pattern. One scraper's total failure (e.g. a locked profile directory
    left over from a crashed prior run, or a missing Chrome install) is
    caught here so it can't take down the sources that still work.
    """
    results = {}
    source_names = list(SCRAPER_CLASSES.keys())
    for index, name in enumerate(source_names):
        scraper = SCRAPER_CLASSES[name](embedding_model, keyword_embeddings)
        try:
            scraper.run_scraper()
            results[name] = (scraper.query_matched_emb_accepted_jobs, scraper.query_matched_emb_rejected_jobs)
        except Exception:
            logger.exception(f"[main] '{name}' scraper failed entirely -- continuing with the remaining sources.")
            results[name] = ([], [])
        if index < len(source_names) - 1:
            delay_between_sources(scraper_common_config)
    return results


def merge_and_rank(accepted_job_lists: list[list[dict]]) -> tuple[list[dict], list[dict]]:
    """
    Combines accepted jobs from every source, ranks by relevance score
    descending, and drops exact-normalized-URL duplicates -- pre-sorting
    first means the first (kept) copy of any duplicate is always the
    highest-scoring one.

    This is exact-URL dedup only. The same job cross-posted under a
    different URL on another board isn't caught here: that needs
    company/location fields this pipeline doesn't extract yet, and is
    already documented as separate, DB-backed future work in the repo's own
    intersource_dedup_pipeline.txt.
    """
    all_jobs = [job for jobs in accepted_job_lists for job in jobs]
    all_jobs.sort(key=lambda job: job["title_keyword_emd_match_score"], reverse=True)

    seen_urls = set()
    unique_jobs = []
    duplicate_jobs = []
    for job in all_jobs:
        key = normalize_job_url(job["url"])
        if key in seen_urls:
            duplicate_jobs.append(job)
        else:
            seen_urls.add(key)
            unique_jobs.append(job)
    return unique_jobs, duplicate_jobs


JOB_CSV_COLUMNS = ["title", "url", "title_keyword_emd_match_score", "job_posting_platform", "rejection_reason"]


def save_jobs_csv(jobs: list[dict], folder, filename: str) -> None:
    # Explicit columns so a 0-row source (e.g. fully blocked this run) still
    # writes a header -- an empty-but-labeled CSV is distinguishable from a
    # write that silently failed; a headerless blank file isn't.
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    pd.DataFrame(jobs, columns=JOB_CSV_COLUMNS).to_csv(file_path, encoding="utf-8", index=False)
    logger.info(f"[main] Wrote {len(jobs)} rows to {file_path}")


def main():
    start = time.time()
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    logger.info("[main] Embedding model loaded.")

    results = run_all_scrapers(embedding_model, keyword_embeddings)

    # Per-source debug/tuning visibility: every accepted + rejected job this run,
    # with rejection_reason distinguishing them (None = accepted).
    for source_name, (accepted, rejected) in results.items():
        save_jobs_csv(accepted + rejected, RAW_FOLDER_PATH, f"{source_name}_jobs.csv")

    accepted_lists = [accepted for accepted, _rejected in results.values()]
    unique_jobs, duplicate_jobs = merge_and_rank(accepted_lists)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    save_jobs_csv(unique_jobs, PROCESSED_FOLDER_PATH, f"ranked_jobs_{timestamp}.csv")
    save_jobs_csv(duplicate_jobs, DUPLICATES_FOLDER_PATH, f"duplicates_{timestamp}.csv")

    duration_minutes = (time.time() - start) / 60
    logger.info(f"[main] Pipeline complete in {duration_minutes:.2f} minutes.")

    print("=" * 130)
    print(f"FINAL RESULT: {len(unique_jobs)} unique jobs (ranked by relevance, {len(duplicate_jobs)} duplicates dropped)")
    print(f"Saved to: {PROCESSED_FOLDER_PATH / f'ranked_jobs_{timestamp}.csv'}")
    print("=" * 130)
    pprint(unique_jobs[:20])


if __name__ == "__main__":
    main()
