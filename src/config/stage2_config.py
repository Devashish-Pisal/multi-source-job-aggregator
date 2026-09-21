from config.path_config import DATA_FOLDER_PATH

stage2_config = {
    "resume_path": DATA_FOLDER_PATH / "resume" / "resume.md", # plain text or markdown; data/ is gitignored
    "max_detail_pages_per_platform": 150, # per run, most promising titles first (~10 s per page)
    "max_description_attempts": 2, # a URL whose detail page fails this often is marked failed and not retried
    "max_description_chars": 12000, # longer descriptions are cut before judging (logged)
    "throttle": {
        "between_detail_pages": {"min_seconds": 3.0, "max_seconds": 8.0},
    },
    "llm": {
        # Provider, key and model live in .env (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL); any OpenAI-compatible endpoint works
        "temperature": 0.0, # None to omit the parameter (some reasoning models reject it)
        "max_tokens": 700,
        "use_json_response_format": True, # response_format={"type": "json_object"}; set False for providers that reject it
        "timeout_seconds": 60,
        "max_consecutive_failures": 3, # abort the judge pass after this many failed calls in a row (auth/model errors abort at once)
        "delay_between_calls": {"min_seconds": 0.5, "max_seconds": 2.0},
        "rejudge_when_model_changes": False, # True: jobs judged by another model are judged again with the current one
        "min_fit_score_to_report": 0, # rows below this fit_score are left out of the ranked CSV
    },
}
