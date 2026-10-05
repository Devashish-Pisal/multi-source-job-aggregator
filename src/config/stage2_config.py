from config.path_config import PROFILE_FOLDER_PATH

stage2_config = {
    "system_prompt_path": PROFILE_FOLDER_PATH / "system_prompt.md", # copy of system_prompt.example.md
    "resume_path": PROFILE_FOLDER_PATH / "resume.md", # copy of resume.example.md
    "max_detail_pages_per_platform": 150, # per run, best titles first
    "max_description_attempts": 2, # then the job is marked failed
    "max_description_chars": 5000, # longer descriptions are cut before judging (keeps the prompt under ~4.5k tokens)
    "max_posting_age_days": 60, # older postings are marked expired and not judged
    "throttle": {
        "between_detail_pages": {"min_seconds": 3.0, "max_seconds": 8.0},
    },
    "dedup": {
        "description_containment": 0.90, # same company + this much of the shorter ad inside the other = same job
    },
    "llm": {
        # provider, key and models are in .env (LLM_*, LLM_2_*, ... tried in order)
        "temperature": 0.0, # None if the model rejects it
        "max_tokens": 3200, # 120b needs ~2350; prompt + this must fit 8k tokens/min
        "response_format": "json_schema", # or "json_object" / None
        "per_model": { # temperature / max_tokens / response_format for single models, named as in .env
            "nvidia/nemotron-3-super-120b-a12b:free": {"max_tokens": 8000}, # long reasoning; openrouter has no tokens/min cap
        },
        "timeout_seconds": 120,
        "max_consecutive_failures": 3,
        "delay_between_calls": {"min_seconds": 2.0, "max_seconds": 3.0},
        "rate_limit_retries": 3, # on HTTP 429, wait and try the same job again
        "rate_limit_pause_seconds": 60, # when the provider gives no wait time
        "rate_limit_max_wait_seconds": 120, # a longer wait means the daily limit, so the next model takes over
    },
}
