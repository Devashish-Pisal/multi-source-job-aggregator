import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from config.path_config import RAW_FOLDER_PATH, REJECTED_FOLDER_PATH, LOGS_FOLDER_PATH, DATABASE_FILE_PATH
from config.scraper_common_config import scraper_common_config
from sources.stepstone_scraper import StepstoneScraper
from sources.indeed_scraper import IndeedScraper
from sources.xing_scraper import XingScraper
from sources.study_smarter_scraper import StudySmarterScraper
from utils.util import load_embedding_model_and_keyword_embeddings
from utils.throttle import delay_between_sources
from utils.db import init_db, upsert_stage1_jobs, jobs_pending_judge, db_summary
from utils.llm_judge import judge_pending_jobs

SCRAPER_CLASSES = {
    "stepstone": StepstoneScraper,
    "study_smarter": StudySmarterScraper,
    "indeed": IndeedScraper,
    "xing": XingScraper,
}

JOB_CSV_COLUMNS = ["title", "url", "title_score", "matched_keyword", "platform"]
DESCRIPTION_CSV_COLUMNS = ["id", "title", "url", "platform", "description_status", "original_id", "match", "dedup_key", "description_source", "company", "location", "employment_type", "date_posted", "description_chars"]
STAGE2_STATUS_LABELS = {"ok": "ok", "duplicate": "duplicate", "expired": "expired", "failed": "failed", "pending": "retry next run"}
DIVIDER = "=" * 100
TOP_N = 20


def enabled_scrapers() -> dict:
    return {name: scraper_class for name, scraper_class in SCRAPER_CLASSES.items() if scraper_common_config[f"use_{name}_scraper"]}


def save_csv(rows: list[dict], columns: list[str], folder: Path, filename: str) -> Path | None:
    if not rows:
        logger.info(f"[main] No rows for {filename}, CSV not written")
        return None
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    pd.DataFrame(rows, columns=columns).to_csv(file_path, encoding="utf-8", index=False)
    logger.info(f"[main] Wrote {len(rows)} rows to {file_path}")
    return file_path


def run_all_scrapers(embedding_model, keyword_embeddings, run_timestamp: str, run: dict) -> list[dict]:
    accepted_jobs = []
    for index, (name, scraper_class) in enumerate(enabled_scrapers().items()):
        scraper = scraper_class(embedding_model, keyword_embeddings)
        outcome = "completed"
        try:
            if index > 0:
                delay_between_sources(scraper_common_config)
            scraper.run_scraper()
        except KeyboardInterrupt:
            outcome = "interrupted"
            logger.warning(f"[main] Interrupted during '{name}' -- saving what was collected so far and skipping the remaining sources.")
        except Exception:
            outcome = "failed"
            logger.exception(f"[main] '{name}' scraper failed -- saving what it collected before the failure and continuing with the remaining sources.")
        accepted, rejected = scraper.query_matched_emb_accepted_jobs, scraper.query_matched_emb_rejected_jobs
        accepted_jobs += accepted
        run["yield"] += scraper.query_yield
        run["stage1"][name] = {"outcome": outcome, "accepted": len(accepted), "rejected": len(rejected), "untitled": sum(1 for job in rejected if job["title"] is None)}
        run["files"] += [save_csv(accepted, JOB_CSV_COLUMNS, RAW_FOLDER_PATH, f"{name}_jobs_{run_timestamp}.csv"),
                         save_csv(rejected, JOB_CSV_COLUMNS, REJECTED_FOLDER_PATH, f"{name}_rejected_{run_timestamp}.csv")]
        if outcome == "interrupted":
            break
    return accepted_jobs


def description_csv_row(job: dict) -> dict:
    row = {column: job.get(column) for column in DESCRIPTION_CSV_COLUMNS}
    row["original_id"] = job.get("original_id") or "" # avoids 14.0 in the csv
    row["description_chars"] = len(job["description"]) if job.get("description") else 0
    return row


def run_description_scrapers(run_timestamp: str, run: dict) -> None:
    for index, (name, scraper_class) in enumerate(enabled_scrapers().items()):
        scraper = scraper_class()
        outcome = "completed"
        try:
            if index > 0:
                delay_between_sources(scraper_common_config)
            scraper.run_description_scraper()
        except KeyboardInterrupt:
            outcome = "interrupted"
            logger.warning(f"[main] Interrupted during '{name}' description scraping -- pages finished so far are in the DB; skipping the remaining sources.")
        except Exception:
            outcome = "failed"
            logger.exception(f"[main] '{name}' description scraper failed -- pages finished before the failure are in the DB; continuing with the remaining sources.")
        jobs = scraper.description_scraped_jobs
        run["stage2"][name] = {"outcome": outcome, "visited": len(jobs), "statuses": Counter(job["description_status"] for job in jobs)}
        run["files"].append(save_csv([description_csv_row(job) for job in jobs], DESCRIPTION_CSV_COLUMNS, RAW_FOLDER_PATH, f"{name}_descriptions_{run_timestamp}.csv"))
        if outcome == "interrupted":
            break


def yield_by(entries: list[dict], field: str) -> list[tuple[str, int, int]]:
    finders = {}
    for entry in entries:
        for url in entry["accepted_urls"]:
            finders.setdefault(url, set()).add(entry[field])
    found, only = Counter(), Counter()
    for values in finders.values():
        for value in values:
            found[value] += 1
            only[value] += len(values) == 1
    return sorted(((value, found[value], only[value]) for value in {entry[field] for entry in entries}), key=lambda row: (-row[2], -row[1], row[0]))


def log_job_lines(jobs: list[dict]) -> None:
    for job in jobs:
        logger.info(f"  {job['fit_score']:>3} | {job['title']} | {job['company']} | {job['location']} | {job['platform']}")
        logger.info(f"        {job['url']}")


def log_run_summary(run: dict, run_timestamp: str, minutes: float) -> None:
    logger.info(DIVIDER)
    logger.info(f"RUN SUMMARY  {run_timestamp}  ({minutes:.1f} min)")
    logger.info(DIVIDER)
    disabled = [name for name in SCRAPER_CLASSES if name not in enabled_scrapers()]
    if disabled:
        logger.info(f"Disabled sources: {', '.join(disabled)}")
    if not scraper_common_config["run_stage_1"]:
        logger.info("Stage 1 | skipped (run_stage_1 is False)")
    for name, stats in run["stage1"].items():
        untitled = f" ({stats['untitled']} without a title)" if stats["untitled"] else ""
        logger.info(f"Stage 1 | {name:<13} | {stats['outcome']:<11} | accepted {stats['accepted']:>3} | rejected {stats['rejected']:>3}{untitled}")
    if run["db"]:
        logger.info(f"Stage 1 | database      | {run['db'][0]} new jobs, {run['db'][1]} already known")
    for field in ("keyword", "location"):
        rows = yield_by(run["yield"], field)
        if rows:
            logger.info(f"Stage 1 | {field} yield (accepted jobs | found by no other {field}):")
            for value, found, only in rows:
                logger.info(f"  {value:<40} {found:>4} | {only:>4}")
    if not scraper_common_config["run_stage_2"]:
        logger.info("Stage 2 | skipped (run_stage_2 is False)")
    for name, stats in run["stage2"].items():
        counts = ", ".join(f"{label} {stats['statuses'][status]}" for status, label in STAGE2_STATUS_LABELS.items() if stats["statuses"][status])
        logger.info(f"Stage 2 | {name:<13} | {stats['outcome']:<11} | {stats['visited']} detail pages{': ' + counts if counts else ''}")
    if run["judge"]:
        judge = run["judge"]
        logger.info(f"Judge   | {len(judge['judged'])} judged, {judge['failed']} failed, {judge['awaiting']} awaiting a verdict")
        top = sorted(judge["judged"], key=lambda job: job["fit_score"], reverse=True)[:TOP_N]
        if top:
            logger.info(f"Top {len(top)} jobs judged in this run (fit | title | company | location | platform):")
            log_job_lines(top)
    for path in run["files"]:
        if path:
            logger.info(f"File    | {path}")


def log_db_summary() -> None:
    try:
        summary = db_summary(TOP_N)
    except Exception as exc:
        logger.error(f"[main] Database summary unavailable: {exc}")
        return
    logger.info(DIVIDER)
    logger.info(f"DATABASE SUMMARY  {DATABASE_FILE_PATH}")
    logger.info(DIVIDER)
    logger.info(f"Jobs         | {summary['total']} total | " + ", ".join(f"{platform} {count}" for platform, count in summary["per_platform"].items()) + f" | {summary['folded_urls']} duplicate URLs folded into kept jobs")
    logger.info("Descriptions | " + ", ".join(f"{status} {count}" for status, count in summary["per_status"].items()))
    logger.info(f"Judge        | {summary['judged']} judged, {summary['awaiting_judge']} awaiting a verdict | fit " + ", ".join(f"{bucket}: {count}" for bucket, count in summary["fit_buckets"].items()))
    if summary["top_jobs"]:
        logger.info(f"Top {len(summary['top_jobs'])} jobs in the database (fit | title | company | location | platform):")
        log_job_lines(summary["top_jobs"])
    logger.info(DIVIDER)


def main():
    logger.remove()
    start = time.time()
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(LOGS_FOLDER_PATH / "{time:YYYY-MM-DD_HH-mm-ss}.log", retention="15 day", level=scraper_common_config["log_level"]) # for file
    logger.add(sys.stderr,level=scraper_common_config["log_level"]) # for console
    run = {"stage1": {}, "yield": [], "db": None, "stage2": {}, "judge": None, "files": []}
    try:
        init_db()
        if scraper_common_config["run_stage_1"]:
            embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
            logger.info("[main] Embedding model loaded.")
            accepted_jobs = run_all_scrapers(embedding_model, keyword_embeddings, run_timestamp, run)
            run["db"] = upsert_stage1_jobs(accepted_jobs)
        else:
            logger.info("[main] Stage 1 skipped (run_stage_1 is False).")

        if scraper_common_config["run_stage_2"]:
            run_description_scrapers(run_timestamp, run)
            judged, failed = judge_pending_jobs()
            run["judge"] = {"judged": judged, "failed": failed, "awaiting": len(jobs_pending_judge())}
        else:
            logger.info("[main] Stage 2 skipped (run_stage_2 is False).")
    finally:
        log_run_summary(run, run_timestamp, (time.time() - start) / 60)
        log_db_summary()


if __name__ == "__main__":
    main()
