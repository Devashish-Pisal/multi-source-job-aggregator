import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from config.path_config import RAW_FOLDER_PATH, REJECTED_FOLDER_PATH, LOGS_FOLDER_PATH, DATABASE_FILE_PATH
from config.common_config import common_config
from sources.stepstone_scraper import StepstoneScraper
from sources.indeed_scraper import IndeedScraper
from sources.xing_scraper import XingScraper
from sources.study_smarter_scraper import StudySmarterScraper
from sources.linkedin_scraper import LinkedInScraper
from utils.util import load_embedding_model_and_keyword_embeddings
from utils.throttle import delay_between_sources
from utils.db import init_db, upsert_stage1_jobs, jobs_pending_judge, db_summary
from judge.llm_judge import judge_pending_jobs

SCRAPER_CLASSES = {
    "stepstone": StepstoneScraper,
    "study_smarter": StudySmarterScraper,
    "indeed": IndeedScraper,
    "xing": XingScraper,
    "linkedin": LinkedInScraper, # last, so other boards win duplicates
}

JOB_CSV_COLUMNS = ["title", "url", "title_score", "matched_keyword", "platform"]
DESCRIPTION_CSV_COLUMNS = ["id", "title", "url", "platform", "description_status", "original_id", "note", "dedup_key", "description_source", "company", "location", "employment_type", "date_posted", "description_chars"]
STAGE2_STATUS_LABELS = {"ok": "ok", "duplicate": "duplicate", "expired": "expired", "failed": "failed", "pending": "retry next run"}
DIVIDER = "=" * 100
TOP_N = 20


def enabled_scrapers() -> dict:
    scrapers = {}
    for name, scraper_class in SCRAPER_CLASSES.items():
        if common_config[f"use_{name}_scraper"]:
            scrapers[name] = scraper_class
    return scrapers


def save_csv(rows: list[dict], columns: list[str], folder: Path, filename: str):
    if not rows:
        logger.info(f"[main] No rows for {filename}, CSV not written")
        return None
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / filename
    pd.DataFrame(rows, columns=columns).to_csv(file_path, encoding="utf-8", index=False)
    logger.info(f"[main] Wrote {len(rows)} rows to {file_path}")
    return file_path


def run_stage_1(run_timestamp: str, run: dict):
    logger.info("[main] Stage 1: search pages")
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    logger.info("[main] Embedding model loaded.")
    accepted_jobs = []
    for index, (name, scraper_class) in enumerate(enabled_scrapers().items()):
        scraper = scraper_class(embedding_model, keyword_embeddings)
        outcome = "completed"
        try:
            if index > 0:
                delay_between_sources(common_config)
            scraper.run_scraper()
        except KeyboardInterrupt:
            outcome = "interrupted"
            logger.warning(f"[main] Interrupted during '{name}', saving what was collected and skipping the other sources.")
        except Exception:
            outcome = "failed"
            logger.exception(f"[main] '{name}' scraper failed, saving what it collected and going on with the next source.")

        accepted = scraper.query_matched_emb_accepted_jobs
        rejected = scraper.query_matched_emb_rejected_jobs
        accepted_jobs += accepted
        for entry in scraper.query_yield:
            yield_entry = dict(entry)
            yield_entry["source"] = name
            yield_entry["location"] = entry["location"].split(",")[0].strip() # "Mannheim, Baden-Württemberg" -> "Mannheim"
            run["yield"].append(yield_entry)
        untitled = 0
        for job in rejected:
            if job["title"] is None:
                untitled += 1
        run["stage1"][name] = {"outcome": outcome, "accepted": len(accepted), "rejected": len(rejected), "untitled": untitled}
        run["files"].append(save_csv(accepted, JOB_CSV_COLUMNS, RAW_FOLDER_PATH, f"{name}_jobs_{run_timestamp}.csv"))
        run["files"].append(save_csv(rejected, JOB_CSV_COLUMNS, REJECTED_FOLDER_PATH, f"{name}_rejected_{run_timestamp}.csv"))
        if outcome == "interrupted":
            break
    run["db"] = upsert_stage1_jobs(accepted_jobs)


def description_csv_row(job: dict) -> dict:
    row = {}
    for column in DESCRIPTION_CSV_COLUMNS:
        row[column] = job.get(column)
    row["original_id"] = job.get("original_id") or "" # avoids 14.0 in the csv
    if job.get("description"):
        row["description_chars"] = len(job["description"])
    else:
        row["description_chars"] = 0
    return row


def run_stage_2(run_timestamp: str, run: dict):
    logger.info("[main] Stage 2: job pages")
    for index, (name, scraper_class) in enumerate(enabled_scrapers().items()):
        scraper = scraper_class()
        outcome = "completed"
        try:
            if index > 0:
                delay_between_sources(common_config)
            scraper.run_description_scraper()
        except KeyboardInterrupt:
            outcome = "interrupted"
            logger.warning(f"[main] Interrupted during '{name}' job pages, finished pages are in the DB, skipping the other sources.")
        except Exception:
            outcome = "failed"
            logger.exception(f"[main] '{name}' job pages failed, finished pages are in the DB, going on with the next source.")

        jobs = scraper.description_scraped_jobs
        statuses = {}
        for job in jobs:
            status = job["description_status"]
            statuses[status] = statuses.get(status, 0) + 1
        run["stage2"][name] = {"outcome": outcome, "visited": len(jobs), "statuses": statuses}
        csv_rows = []
        for job in jobs:
            csv_rows.append(description_csv_row(job))
        run["files"].append(save_csv(csv_rows, DESCRIPTION_CSV_COLUMNS, RAW_FOLDER_PATH, f"{name}_descriptions_{run_timestamp}.csv"))
        if outcome == "interrupted":
            break


def run_stage_3(run: dict):
    logger.info("[main] Stage 3: llm judge")
    judged, failed, stop_reason = judge_pending_jobs()
    run["stage3"] = {"judged": judged, "failed": failed, "stop_reason": stop_reason, "awaiting": len(jobs_pending_judge())}


def yield_by(entries: list[dict], field: str) -> list:
    # jobs found per keyword (or location), and how many of them only it found
    finders = {}
    for entry in entries:
        for url in entry["accepted_urls"]:
            if url not in finders:
                finders[url] = set()
            finders[url].add(entry[field])
    found = {}
    only = {}
    for values in finders.values():
        for value in values:
            found[value] = found.get(value, 0) + 1
            if len(values) == 1:
                only[value] = only.get(value, 0) + 1
    rows = []
    for entry in entries:
        value = entry[field]
        row = (value, found.get(value, 0), only.get(value, 0))
        if row not in rows:
            rows.append(row)
    rows.sort(key=lambda row: (-row[2], -row[1], row[0]))
    return rows


def yield_table(entries: list[dict], field: str) -> list:
    sources = []
    for entry in entries:
        if entry["source"] not in sources:
            sources.append(entry["source"])
    per_source = {}
    for entry in entries:
        key = (entry[field], entry["source"])
        if key not in per_source:
            per_source[key] = set()
        per_source[key].update(entry["accepted_urls"])

    header = f"  {field:<34}"
    for source in sources:
        header += f"{source[:12]:>14}"
    lines = [header + f"{'total':>7}{'only':>6}"]
    for value, found, only in yield_by(entries, field):
        line = f"  {value:<34}"
        for source in sources:
            line += f"{len(per_source.get((value, source), [])):>14}"
        lines.append(line + f"{found:>7}{only:>6}")
    return lines


def per_model(counts: dict) -> str:
    if not counts:
        return ""
    parts = []
    for model, count in counts.items():
        parts.append(f"{model} {count}")
    return " (" + ", ".join(parts) + ")"


def log_job_lines(jobs: list[dict]):
    for job in jobs:
        logger.info(f"  {job['fit_score']:>3} | {job['title']} | {job['company']} | {job['location']} | {job['platform']}")
        logger.info(f"        {job['url']}")


def log_run_summary(run: dict, run_timestamp: str, minutes: float):
    logger.info(DIVIDER)
    logger.info(f"RUN SUMMARY  {run_timestamp}  ({minutes:.1f} min)")
    logger.info(DIVIDER)
    disabled = []
    for name in SCRAPER_CLASSES:
        if name not in enabled_scrapers():
            disabled.append(name)
    if disabled:
        logger.info(f"Disabled sources: {', '.join(disabled)}")

    # stage 1
    if not common_config["run_stage_1"]:
        logger.info("Stage 1 | skipped (run_stage_1 is False)")
    for name, stats in run["stage1"].items():
        untitled = ""
        if stats["untitled"]:
            untitled = f" ({stats['untitled']} without a title)"
        logger.info(f"Stage 1 | {name:<13} | {stats['outcome']:<11} | accepted {stats['accepted']:>3} | rejected {stats['rejected']:>3}{untitled}")
    if run["db"]:
        logger.info(f"Stage 1 | database      | {run['db'][0]} new jobs, {run['db'][1]} already known")
    sources = []
    for entry in run["yield"]:
        if entry["source"] not in sources:
            sources.append(entry["source"])
    for source in sources:
        results = []
        for entry in run["yield"]:
            if entry["source"] == source:
                results.append(entry["results"])
        average = sum(results) / len(results)
        logger.info(f"Stage 1 | {source:<13} | page 1 results per query: avg {average:.0f}, max {max(results)}, empty {results.count(0)} of {len(results)}")
    for field in ("keyword", "location"):
        if run["yield"]:
            logger.info(f"Stage 1 | {field} yield (accepted jobs per site | total | found by no other {field}):")
            for line in yield_table(run["yield"], field):
                logger.info(line)

    # stage 2
    if not common_config["run_stage_2"]:
        logger.info("Stage 2 | skipped (run_stage_2 is False)")
    for name, stats in run["stage2"].items():
        counts = []
        for status, label in STAGE2_STATUS_LABELS.items():
            count = stats["statuses"].get(status, 0)
            if count:
                counts.append(f"{label} {count}")
        line = f"Stage 2 | {name:<13} | {stats['outcome']:<11} | {stats['visited']} detail pages"
        if counts:
            line += ": " + ", ".join(counts)
        logger.info(line)

    # stage 3
    if not common_config["run_stage_3"]:
        logger.info("Stage 3 | skipped (run_stage_3 is False)")
    if run["stage3"]:
        judge = run["stage3"]
        model_counts = {}
        for job in judge["judged"]:
            model_counts[job["judge_model"]] = model_counts.get(job["judge_model"], 0) + 1
        model_counts = dict(sorted(model_counts.items(), key=lambda item: item[1], reverse=True))
        line = f"Stage 3 | {len(judge['judged'])} judged{per_model(model_counts)}, {judge['awaiting']} awaiting a verdict"
        if judge["failed"]:
            line += f" ({judge['failed']} failed calls)"
        if judge["stop_reason"]:
            line += f" -- stopped early: {judge['stop_reason']}"
        logger.info(line)
        top = sorted(judge["judged"], key=lambda job: job["fit_score"], reverse=True)[:TOP_N]
        if top:
            logger.info(f"Top {len(top)} jobs judged in this run (fit | title | company | location | platform):")
            log_job_lines(top)

    for path in run["files"]:
        if path:
            logger.info(f"File    | {path}")


def log_db_summary():
    try:
        summary = db_summary(TOP_N)
    except Exception as exc:
        logger.error(f"[main] Database summary unavailable: {exc}")
        return
    logger.info(DIVIDER)
    logger.info(f"DATABASE SUMMARY  {DATABASE_FILE_PATH}")
    logger.info(DIVIDER)

    platforms = []
    for platform, count in summary["per_platform"].items():
        platforms.append(f"{platform} {count}")
    logger.info(f"Jobs         | {summary['total']} total | {', '.join(platforms)} | {summary['folded_urls']} duplicate URLs folded into kept jobs")

    statuses = []
    for status, count in summary["per_status"].items():
        statuses.append(f"{status} {count}")
    logger.info("Descriptions | " + ", ".join(statuses))

    buckets = []
    for bucket, count in summary["fit_buckets"].items():
        buckets.append(f"{bucket}: {count}")
    logger.info(f"Judge        | {summary['judged']} judged{per_model(summary['per_judge_model'])}, {summary['awaiting_judge']} awaiting a verdict | fit {', '.join(buckets)}")

    if summary["top_jobs"]:
        logger.info(f"Top {len(summary['top_jobs'])} jobs in the database (fit | title | company | location | platform):")
        log_job_lines(summary["top_jobs"])
    logger.info(DIVIDER)


def main():
    logger.remove()
    start = time.time()
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(LOGS_FOLDER_PATH / "{time:YYYY-MM-DD_HH-mm-ss}.log", retention="15 day", level=common_config["log_level"]) # for file
    logger.add(sys.stderr,level=common_config["log_level"]) # for console
    run = {"stage1": {}, "yield": [], "db": None, "stage2": {}, "stage3": None, "files": []}
    try:
        init_db()
        if common_config["run_stage_1"]:
            run_stage_1(run_timestamp, run)
        else:
            logger.info("[main] Stage 1 skipped (run_stage_1 is False).")

        if common_config["run_stage_2"]:
            run_stage_2(run_timestamp, run)
        else:
            logger.info("[main] Stage 2 skipped (run_stage_2 is False).")

        if common_config["run_stage_3"]:
            run_stage_3(run)
        else:
            logger.info("[main] Stage 3 skipped (run_stage_3 is False).")
    finally:
        log_run_summary(run, run_timestamp, (time.time() - start) / 60)
        log_db_summary()


if __name__ == "__main__":
    main()
