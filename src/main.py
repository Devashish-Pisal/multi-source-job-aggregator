import json
import time
import pandas as pd
from loguru import logger
from datetime import datetime
from pprint import pprint
from config.path_config import RAW_FOLDER_PATH, DUPLICATES_FOLDER_PATH, PROCESSED_FOLDER_PATH
from config.scraper_common_config import scraper_common_config
from config.stage2_config import stage2_config
from sources.stepstone_scraper import StepstoneScraper
from sources.indeed_scraper import IndeedScraper
from sources.xing_scraper import XingScraper
from sources.study_smarter_scraper import StudySmarterScraper
from utils.util import load_embedding_model_and_keyword_embeddings, normalize_job_url
from utils.throttle import delay_between_sources
from utils.db import init_db, upsert_stage1_jobs, ranked_jobs, status_counts
from utils.llm_judge import judge_pending_jobs

SCRAPER_CLASSES = {
    "stepstone": StepstoneScraper,
    "study_smarter": StudySmarterScraper,
    "indeed": IndeedScraper,
    "xing": XingScraper,
}

JOB_CSV_COLUMNS = ["title", "url", "title_keyword_emd_match_score", "job_posting_platform", "rejection_reason"]
DESCRIPTION_CSV_COLUMNS = ["title", "url", "job_posting_platform", "description_status", "description_source", "company", "location", "employment_type", "date_posted", "description_chars"]
RANKED_CSV_COLUMNS = ["title", "company", "location", "employment_type", "fit_score", "level_ok", "language_requirement", "german_level", "missing_must_haves", "reason", "job_posting_platform", "url", "first_seen_run", "is_new_this_run"]


def save_csv(rows: list[dict], columns: list[str], folder, filename: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    pd.DataFrame(rows, columns=columns).to_csv(file_path, encoding="utf-8", index=False)
    logger.info(f"[main] Wrote {len(rows)} rows to {file_path}")


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
        save_csv(results[name][0] + results[name][1], JOB_CSV_COLUMNS, RAW_FOLDER_PATH, f"{name}_jobs_{run_timestamp}.csv")
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


def description_csv_row(job: dict) -> dict:
    return {
        "title": job.get("title"),
        "url": job["url"],
        "job_posting_platform": job["platform"],
        "description_status": job.get("description_status"),
        "description_source": job.get("description_source"),
        "company": job.get("company"),
        "location": job.get("location"),
        "employment_type": job.get("employment_type"),
        "date_posted": job.get("date_posted"),
        "description_chars": len(job["description"]) if job.get("description") else 0,
    }


def run_description_scrapers(run_timestamp: str) -> dict[str, list[dict]]:
    results = {}
    for index, (name, scraper_class) in enumerate(SCRAPER_CLASSES.items()):
        scraper = scraper_class()
        interrupted = False
        try:
            if index > 0:
                delay_between_sources(scraper_common_config)
            scraper.run_description_scraper(run_timestamp)
        except KeyboardInterrupt:
            interrupted = True
            logger.warning(f"[main] Interrupted during '{name}' description scraping -- pages finished so far are in the DB; skipping the remaining sources.")
        except Exception:
            logger.exception(f"[main] '{name}' description scraper failed -- pages finished before the failure are in the DB; continuing with the remaining sources.")
        results[name] = scraper.description_scraped_jobs
        save_csv([description_csv_row(job) for job in results[name]], DESCRIPTION_CSV_COLUMNS, RAW_FOLDER_PATH, f"{name}_descriptions_{run_timestamp}.csv")
        if interrupted:
            break
    return results


def ranked_csv_row(job: dict, run_timestamp: str) -> dict:
    verdict = json.loads(job["judge_json"]) if job.get("judge_json") else {}
    return {
        "title": job["title"],
        "company": job.get("company"),
        "location": job.get("location"),
        "employment_type": verdict.get("employment_type") or job.get("employment_type"),
        "fit_score": job["fit_score"],
        "level_ok": verdict.get("level_ok"),
        "language_requirement": verdict.get("language_requirement"),
        "german_level": verdict.get("german_level"),
        "missing_must_haves": "; ".join(verdict.get("missing_must_haves") or []),
        "reason": verdict.get("reason"),
        "job_posting_platform": job["platform"],
        "url": job["url"],
        "first_seen_run": job["first_seen_run"],
        "is_new_this_run": job["first_seen_run"] == run_timestamp,
    }


def main():
    start = time.time()
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_db()

    unique_jobs = []
    if scraper_common_config["run_stage_1"]:
        embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
        logger.info("[main] Embedding model loaded.")
        results = run_all_scrapers(embedding_model, keyword_embeddings, run_timestamp)
        accepted_lists = [accepted for accepted, _ in results.values()]
        rejected_jobs = [job for _, rejected in results.values() for job in rejected]
        unique_jobs, duplicate_jobs = merge_and_rank(accepted_lists)
        save_csv(unique_jobs, JOB_CSV_COLUMNS, PROCESSED_FOLDER_PATH, f"title_ranked_jobs_{run_timestamp}.csv")
        save_csv(duplicate_jobs, JOB_CSV_COLUMNS, DUPLICATES_FOLDER_PATH, f"duplicates_{run_timestamp}.csv")
        new_count, seen_count = upsert_stage1_jobs(unique_jobs + rejected_jobs, run_timestamp)
        logger.info(f"[main] Stage 1 done: {len(unique_jobs)} unique accepted jobs ({len(duplicate_jobs)} URL duplicates dropped); {new_count} URLs never seen before, {seen_count} seen in an earlier run.")
    else:
        logger.info("[main] Stage 1 skipped (run_stage_1 is False).")

    ranked_rows = []
    if scraper_common_config["run_stage_2"]:
        run_description_scrapers(run_timestamp)
        judge_pending_jobs(run_timestamp)
        ranked_rows = [ranked_csv_row(job, run_timestamp) for job in ranked_jobs(stage2_config["llm"]["min_fit_score_to_report"])]
        save_csv(ranked_rows, RANKED_CSV_COLUMNS, PROCESSED_FOLDER_PATH, f"ranked_jobs_{run_timestamp}.csv")
    else:
        logger.info("[main] Stage 2 skipped (run_stage_2 is False).")

    logger.info(f"[main] DB totals: {status_counts()}")
    duration_minutes = (time.time() - start) / 60
    logger.info(f"[main] Pipeline complete in {duration_minutes:.2f} minutes.")

    print("=" * 130)
    if ranked_rows:
        new_count = sum(1 for row in ranked_rows if row["is_new_this_run"])
        print(f"FINAL RESULT: {len(ranked_rows)} jobs ranked by résumé fit ({new_count} first seen in this run)")
        print(f"Saved to: {PROCESSED_FOLDER_PATH / f'ranked_jobs_{run_timestamp}.csv'}")
        print("=" * 130)
        for row in ranked_rows[:20]:
            marker = "NEW" if row["is_new_this_run"] else "   "
            print(f"{row['fit_score']:>3} {marker} {row['title']} | {row['company']} | {row['location']} | {row['job_posting_platform']}")
            print(f"        {row['reason']}")
            print(f"        {row['url']}")
    else:
        print(f"FINAL RESULT: {len(unique_jobs)} unique title-matched jobs, no résumé-ranked rows this run")
        print("=" * 130)
        pprint(unique_jobs[:20])


if __name__ == "__main__":
    main()
