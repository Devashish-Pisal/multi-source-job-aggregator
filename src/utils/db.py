import sqlite3
from contextlib import closing

from loguru import logger

from config import path_config
from utils.util import normalize_job_url

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    url_key TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    platform TEXT NOT NULL,
    title TEXT,
    title_score REAL,
    rejection_reason TEXT,
    first_seen_run TEXT NOT NULL,
    last_seen_run TEXT NOT NULL,
    company TEXT,
    location TEXT,
    employment_type TEXT,
    date_posted TEXT,
    description TEXT,
    description_source TEXT,
    description_status TEXT NOT NULL DEFAULT 'pending',
    description_attempts INTEGER NOT NULL DEFAULT 0,
    description_run TEXT,
    judge_model TEXT,
    fit_score INTEGER,
    judge_json TEXT,
    judge_run TEXT,
    user_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_platform_status ON jobs (platform, description_status);
"""


def _connect() -> sqlite3.Connection:
    db_path = path_config.DATABASE_FILE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def init_db() -> None:
    with closing(_connect()):
        logger.info(f"[db] Using {path_config.DATABASE_FILE_PATH}")


def upsert_stage1_jobs(jobs: list[dict], run_timestamp: str) -> tuple[int, int]:
    new_count = 0
    seen_count = 0
    with closing(_connect()) as conn:
        for job in jobs:
            url_key = normalize_job_url(job["url"])
            row = conn.execute("SELECT url_key FROM jobs WHERE url_key = ?", (url_key,)).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO jobs (url_key, url, platform, title, title_score, rejection_reason, first_seen_run, last_seen_run) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (url_key, job["url"], job["job_posting_platform"], job["title"], job["title_keyword_emd_match_score"], job["rejection_reason"], run_timestamp, run_timestamp),
                )
                new_count += 1
            else:
                conn.execute(
                    """UPDATE jobs SET last_seen_run = ?,
                           title = COALESCE(?, title),
                           title_score = COALESCE(?, title_score),
                           rejection_reason = CASE WHEN rejection_reason IS NULL THEN NULL ELSE ? END,
                           description_status = CASE WHEN description_status IN ('expired', 'failed') THEN 'pending' ELSE description_status END,
                           description_attempts = CASE WHEN description_status IN ('expired', 'failed') THEN 0 ELSE description_attempts END
                       WHERE url_key = ?""",
                    (run_timestamp, job["title"], job["title_keyword_emd_match_score"], job["rejection_reason"], url_key),
                )
                seen_count += 1
        conn.commit()
    return new_count, seen_count


def jobs_pending_description(platform: str, limit: int) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE platform = ? AND rejection_reason IS NULL AND description_status = 'pending' ORDER BY title_score DESC, first_seen_run DESC LIMIT ?",
            (platform, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def save_description(url_key: str, fields: dict, run_timestamp: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            """UPDATE jobs SET company = ?, location = ?, employment_type = ?, date_posted = ?, description = ?, description_source = ?,
                   description_status = 'ok', description_attempts = description_attempts + 1, description_run = ?
               WHERE url_key = ?""",
            (fields.get("company"), fields.get("location"), fields.get("employment_type"), fields.get("date_posted"), fields["description"], fields["description_source"], run_timestamp, url_key),
        )
        conn.commit()


def mark_description_expired(url_key: str, run_timestamp: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE jobs SET description_status = 'expired', description_attempts = description_attempts + 1, description_run = ? WHERE url_key = ?",
            (run_timestamp, url_key),
        )
        conn.commit()


def record_description_failure(url_key: str, max_attempts: int) -> str:
    with closing(_connect()) as conn:
        conn.execute("UPDATE jobs SET description_attempts = description_attempts + 1 WHERE url_key = ?", (url_key,))
        conn.execute("UPDATE jobs SET description_status = 'failed' WHERE url_key = ? AND description_attempts >= ?", (url_key, max_attempts))
        conn.commit()
        return conn.execute("SELECT description_status FROM jobs WHERE url_key = ?", (url_key,)).fetchone()[0]


def jobs_pending_judge(model: str, rejudge_when_model_changes: bool) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE description_status = 'ok' AND (judge_model IS NULL OR (? AND judge_model != ?)) ORDER BY title_score DESC, first_seen_run DESC",
            (int(rejudge_when_model_changes), model),
        ).fetchall()
    return [dict(row) for row in rows]


def save_verdict(url_key: str, model: str, fit_score: int, judge_json: str, run_timestamp: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE jobs SET judge_model = ?, fit_score = ?, judge_json = ?, judge_run = ? WHERE url_key = ?",
            (model, fit_score, judge_json, run_timestamp, url_key),
        )
        conn.commit()


def ranked_jobs(min_fit_score: int = 0) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE fit_score IS NOT NULL AND fit_score >= ? ORDER BY fit_score DESC, title_score DESC",
            (min_fit_score,),
        ).fetchall()
    return [dict(row) for row in rows]


def status_counts() -> dict[str, int]:
    with closing(_connect()) as conn:
        counts = {"accepted": conn.execute("SELECT COUNT(*) FROM jobs WHERE rejection_reason IS NULL").fetchone()[0],
                  "rejected": conn.execute("SELECT COUNT(*) FROM jobs WHERE rejection_reason IS NOT NULL").fetchone()[0],
                  "judged": conn.execute("SELECT COUNT(*) FROM jobs WHERE fit_score IS NOT NULL").fetchone()[0]}
        for status, count in conn.execute("SELECT description_status, COUNT(*) FROM jobs WHERE rejection_reason IS NULL GROUP BY description_status"):
            counts[f"description_{status}"] = count
    return counts
