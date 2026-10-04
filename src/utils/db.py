import json
import sqlite3
from contextlib import closing
from datetime import date

from loguru import logger

from config import path_config
from config.stage2_config import stage2_config
from deduplication.normalize import normalize_title, normalize_company, normalize_location, normalize_description, build_dedup_key, tidy_text, description_similarity
from utils.util import normalize_job_url

SCHEMA_VERSION = 3 # bump on schema changes
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    other_urls TEXT NOT NULL DEFAULT '[]',
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    title_score REAL NOT NULL CHECK (typeof(title_score) = 'real'),
    date_added TEXT NOT NULL,
    company TEXT,
    location TEXT,
    employment_type TEXT,
    date_posted TEXT,
    description TEXT,
    description_source TEXT,
    description_status TEXT NOT NULL DEFAULT 'pending' CHECK (description_status IN ('pending', 'ok', 'expired', 'failed')),
    description_attempts INTEGER NOT NULL DEFAULT 0,
    dedup_key TEXT,
    judge_model TEXT,
    fit_score INTEGER,
    judge_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_platform_status ON jobs (platform, description_status);
CREATE INDEX IF NOT EXISTS idx_jobs_dedup_key ON jobs (dedup_key);
"""
FIT_BUCKETS = ["85-100", "60-84", "30-59", "0-29"]


def _connect() -> sqlite3.Connection:
    db_path = path_config.DATABASE_FILE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    has_jobs_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'jobs'").fetchone()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if has_jobs_table and version != SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(f"{db_path} has schema version {version}, this code expects {SCHEMA_VERSION} -- move it aside (e.g. to app_backup_<date>.db) and a fresh database is created on the next run")
    conn.executescript(SCHEMA)
    if not has_jobs_table:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return conn


def init_db() -> None:
    with closing(_connect()):
        logger.info(f"[db] Using {path_config.DATABASE_FILE_PATH}")


def upsert_stage1_jobs(jobs: list[dict]) -> tuple[int, int]:
    new_count = 0
    known_count = 0
    today = date.today().isoformat()
    with closing(_connect()) as conn:
        folded_urls = {row[0] for row in conn.execute("SELECT value FROM jobs, json_each(jobs.other_urls)")}
        for job in jobs:
            url = normalize_job_url(job["url"])
            if url in folded_urls: # duplicate seen before
                known_count += 1
                continue
            cursor = conn.execute(
                "INSERT INTO jobs (url, platform, title, title_score, date_added) VALUES (?, ?, ?, ?, ?) ON CONFLICT (url) DO NOTHING",
                (url, job["platform"], tidy_text(job["title"]), float(job["title_score"]), today),
            )
            if cursor.rowcount:
                new_count += 1
            else:
                known_count += 1
                conn.execute("UPDATE jobs SET description_status = 'pending', description_attempts = 0 WHERE url = ? AND description_status IN ('expired', 'failed')", (url,))
        conn.commit()
    return new_count, known_count


def jobs_pending_description(platform: str, limit: int) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE platform = ? AND description_status = 'pending' ORDER BY title_score DESC, id DESC LIMIT ?",
            (platform, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _find_original(conn: sqlite3.Connection, job_id: int, dedup_key: str | None, company_key: str, description: str) -> tuple[int | None, str | None]:
    if not dedup_key:
        return None, None
    exact = conn.execute("SELECT id FROM jobs WHERE dedup_key = ? AND id != ? AND description_status = 'ok' ORDER BY id LIMIT 1", (dedup_key, job_id)).fetchone()
    if exact:
        return exact["id"], "same key"
    prefix = f"{company_key}|"
    best_id, best_score = None, stage2_config["dedup"]["description_similarity"]
    candidates = conn.execute("SELECT id, description FROM jobs WHERE substr(dedup_key, 1, ?) = ? AND id != ? AND description_status = 'ok'", (len(prefix), prefix, job_id))
    for candidate in candidates:
        score = description_similarity(description, candidate["description"])
        if score >= best_score:
            best_id, best_score = candidate["id"], score
    return (best_id, f"same company, description similarity {best_score:.2f}") if best_id else (None, None)


def save_description(job_id: int, fields: dict) -> dict:
    stored = {
        "company": tidy_text(fields.get("company")) or None,
        "location": normalize_location(fields.get("location")) or None,
        "employment_type": (fields.get("employment_type") or "").lower() or None,
        "date_posted": fields.get("date_posted"),
        "description": normalize_description(fields["description"]),
        "description_source": fields["description_source"],
    }
    company_key = normalize_company(stored["company"])
    with closing(_connect()) as conn:
        row = conn.execute("SELECT url, title, other_urls FROM jobs WHERE id = ?", (job_id,)).fetchone()
        stored["dedup_key"] = build_dedup_key(company_key, normalize_title(row["title"]), stored["location"])
        original_id, match = _find_original(conn, job_id, stored["dedup_key"], company_key, stored["description"])
        if original_id:
            original_urls = json.loads(conn.execute("SELECT other_urls FROM jobs WHERE id = ?", (original_id,)).fetchone()[0])
            merged_urls = list(dict.fromkeys(original_urls + [row["url"]] + json.loads(row["other_urls"])))
            conn.execute("UPDATE jobs SET other_urls = ? WHERE id = ?", (json.dumps(merged_urls), original_id))
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            stored.update(description_status="duplicate", original_id=original_id, match=match)
        else:
            stored["description_status"] = "ok"
            conn.execute(
                """UPDATE jobs SET company = :company, location = :location, employment_type = :employment_type, date_posted = :date_posted,
                       description = :description, description_source = :description_source, dedup_key = :dedup_key,
                       description_status = 'ok', description_attempts = description_attempts + 1
                   WHERE id = :id""",
                {**stored, "id": job_id},
            )
        conn.commit()
    return stored


def mark_description_expired(job_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE jobs SET description_status = 'expired', description_attempts = description_attempts + 1 WHERE id = ?", (job_id,))
        conn.commit()


def record_description_failure(job_id: int, max_attempts: int) -> str:
    with closing(_connect()) as conn:
        conn.execute("UPDATE jobs SET description_attempts = description_attempts + 1 WHERE id = ?", (job_id,))
        conn.execute("UPDATE jobs SET description_status = 'failed' WHERE id = ? AND description_attempts >= ?", (job_id, max_attempts))
        conn.commit()
        return conn.execute("SELECT description_status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]


def jobs_pending_judge() -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE description_status = 'ok' AND judge_model IS NULL ORDER BY title_score DESC, id").fetchall()
    return [dict(row) for row in rows]


def save_verdict(job_id: int, model: str, fit_score: int, judge_json: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE jobs SET judge_model = ?, fit_score = ?, judge_json = ? WHERE id = ?", (model, fit_score, judge_json, job_id))
        conn.commit()


def db_summary(top_n: int) -> dict:
    with closing(_connect()) as conn:
        buckets = dict(conn.execute(
            """SELECT CASE WHEN fit_score >= 85 THEN '85-100' WHEN fit_score >= 60 THEN '60-84' WHEN fit_score >= 30 THEN '30-59' ELSE '0-29' END, COUNT(*)
               FROM jobs WHERE fit_score IS NOT NULL GROUP BY 1"""
        ).fetchall())
        return {
            "total": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "folded_urls": conn.execute("SELECT COUNT(*) FROM jobs, json_each(jobs.other_urls)").fetchone()[0],
            "per_platform": dict(conn.execute("SELECT platform, COUNT(*) FROM jobs GROUP BY platform ORDER BY platform").fetchall()),
            "per_status": dict(conn.execute("SELECT description_status, COUNT(*) FROM jobs GROUP BY description_status ORDER BY description_status").fetchall()),
            "judged": conn.execute("SELECT COUNT(*) FROM jobs WHERE fit_score IS NOT NULL").fetchone()[0],
            "awaiting_judge": conn.execute("SELECT COUNT(*) FROM jobs WHERE description_status = 'ok' AND judge_model IS NULL").fetchone()[0],
            "fit_buckets": {bucket: buckets.get(bucket, 0) for bucket in FIT_BUCKETS},
            "top_jobs": [dict(row) for row in conn.execute(
                "SELECT id, fit_score, title, company, location, platform, date_added, url FROM jobs WHERE fit_score IS NOT NULL ORDER BY fit_score DESC, title_score DESC LIMIT ?",
                (top_n,),
            )],
        }
