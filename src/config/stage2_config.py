from config.path_config import PROFILE_FOLDER_PATH

stage2_config = {
    "system_prompt_path": PROFILE_FOLDER_PATH / "system_prompt.md", # copy of system_prompt.example.md
    "resume_path": PROFILE_FOLDER_PATH / "resume.md", # copy of resume.example.md
    "max_detail_pages_per_platform": 150, # per run, best titles first
    "max_description_attempts": 2, # then the job is marked failed
    "max_description_chars": 6000, # longer descriptions are cut before judging
    "max_posting_age_days": 60, # older postings are marked expired and not judged
    "throttle": {
        "between_detail_pages": {"min_seconds": 3.0, "max_seconds": 8.0},
    },
    "dedup": {
        "description_containment": 0.90, # same company + this much of the shorter ad inside the other = same job
    },
    "llm": {
        # provider, key and model are in .env
        "temperature": 0.0, # None if the model rejects it
        "max_tokens": 1500, # counts against Groq's token limits; calls used ~1200
        "response_format": "json_schema", # or "json_object" / None
        "timeout_seconds": 120,
        "max_consecutive_failures": 3,
        "delay_between_calls": {"min_seconds": 2.0, "max_seconds": 3.0},
        "rate_limit_retries": 3, # on HTTP 429, wait and try the same job again
        "rate_limit_pause_seconds": 60, # when the provider gives no wait time
        "rate_limit_max_wait_seconds": 120, # a longer wait means the daily limit, so the pass stops
    },
}
