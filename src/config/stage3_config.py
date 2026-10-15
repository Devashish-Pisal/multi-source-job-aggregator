from config.path_config import PROFILE_FOLDER_PATH

stage3_config = {
    "system_prompt_path": PROFILE_FOLDER_PATH / "system_prompt.md", # copy of system_prompt.example.md
    "resume_path": PROFILE_FOLDER_PATH / "resume.md", # copy of resume.example.md
    "max_description_chars": 5000, # cut before judging
    "search_area": {"latitude": 49.4875, "longitude": 8.4660, "radius_km": 100}, # Mannheim, farther postings are not judged
    "verdict": {
        "empty_details_below": 40, # details cleared below this fit
        "max_fit_with_missing_must_haves": {"count": 2, "fit": 84}, # 2+ missing must-haves cap the score
    },
    "llm": {
        # provider, key and models live in .env
        "temperature": 0.0, # None if the model rejects it
        "max_tokens": 3200, # 120b needs ~2350, groq allows 8k tokens/min
        "response_format": "json_schema", # or "json_object" / None
        "per_model": { # overrides per model name
            "nvidia/nemotron-3-super-120b-a12b:free": {"max_tokens": 12000}, # reasons a lot
            "qwen/qwen3.8-27b": {"max_tokens": 1500}, # needs ~1k
        },
        "timeout_seconds": 180, # nemotron needs ~100 s for 12000 tokens
        "max_consecutive_failures": 3,
        "delay_between_calls": {"min_seconds": 2.0, "max_seconds": 3.0},
        "rate_limit_retries": 3, # retries on HTTP 429
        "connection_error_pause_seconds": 10, # one retry after a dropped connection
        "rate_limit_pause_seconds": 60, # when the provider gives no wait time
        "rate_limit_max_wait_seconds": 120, # longer means daily limit, next model
    },
}
