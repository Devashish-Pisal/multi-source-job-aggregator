import time
import pandas as pd
from loguru import logger
from datetime import datetime
from pprint import pprint
from config.path_config import RAW_FOLDER_PATH, DUPLICATES_FOLDER_PATH, PROCESSED_FOLDER_PATH
from config.scraper_common_config import scraper_common_config
from sources.stepstone_scraper import StepstoneScraper
from sources.indeed_scraper import IndeedScraper
from sources.xing_scraper import XingScraper
from sources.study_smarter_scraper import StudySmarterScraper
from utils.util import load_embedding_model_and_keyword_embeddings, normalize_job_url
from utils.throttle import delay_between_sources

SCRAPER_CLASSES = {
    "stepstone": StepstoneScraper,
    "study_smarter": StudySmarterScraper,
    "indeed": IndeedScraper,
    "xing": XingScraper,
}

JOB_CSV_COLUMNS = ["title", "url", "title_keyword_emd_match_score", "job_posting_platform", "rejection_reason"]


def save_jobs_csv(jobs: list[dict], folder, filename: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    pd.DataFrame(jobs, columns=JOB_CSV_COLUMNS).to_csv(file_path, encoding="utf-8", index=False)
    logger.info(f"[main] Wrote {len(jobs)} rows to {file_path}")


def run_all_scrapers(embedding_model, keyword_embeddings, run_timestamp: str) -> dict[str, tuple[list[dict], list[dict]]]:
    results = {}
    for index, (name, scraper_class) in enumerate(SCRAPER_CLASSES.items()):
        scraper = scraper_class(embedding_model, keyword_embeddings)
        interrupted = False
        try:
            if index > 0:
                delay_between_sources(scraper_common_config)
            scraper.run_scraper()
        except KeyboardInterrupt:
            interrupted = True
            logger.warning(f"[main] Interrupted during '{name}' -- saving what was collected so far and skipping the remaining sources.")
        except Exception:
            logger.exception(f"[main] '{name}' scraper failed -- saving what it collected before the failure and continuing with the remaining sources.")
        results[name] = (scraper.query_matched_emb_accepted_jobs, scraper.query_matched_emb_rejected_jobs)
        save_jobs_csv(results[name][0] + results[name][1], RAW_FOLDER_PATH, f"{name}_jobs_{run_timestamp}.csv")
        if interrupted:
            break
    return results


def merge_and_rank(accepted_job_lists: list[list[dict]]) -> tuple[list[dict], list[dict]]:
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


def main():
    start = time.time()
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    logger.info("[main] Embedding model loaded.")

    results = run_all_scrapers(embedding_model, keyword_embeddings, run_timestamp)

    accepted_lists = [accepted for accepted, _ in results.values()]
    unique_jobs, duplicate_jobs = merge_and_rank(accepted_lists)
    save_jobs_csv(unique_jobs, PROCESSED_FOLDER_PATH, f"ranked_jobs_{run_timestamp}.csv")
    save_jobs_csv(duplicate_jobs, DUPLICATES_FOLDER_PATH, f"duplicates_{run_timestamp}.csv")

    duration_minutes = (time.time() - start) / 60
    logger.info(f"[main] Pipeline complete in {duration_minutes:.2f} minutes.")

    print("=" * 130)
    print(f"FINAL RESULT: {len(unique_jobs)} unique jobs (ranked by relevance, {len(duplicate_jobs)} duplicates dropped)")
    print(f"Saved to: {PROCESSED_FOLDER_PATH / f'ranked_jobs_{run_timestamp}.csv'}")
    print("=" * 130)
    pprint(unique_jobs[:20])


if __name__ == "__main__":
    main()
