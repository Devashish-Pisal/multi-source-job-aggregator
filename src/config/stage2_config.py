stage2_config = {
    "max_detail_pages_per_platform": 150, # per run, best titles first
    "max_description_attempts": 3, # then the job is marked failed
    "max_posting_age_days": 60, # older postings are marked expired and not judged
    "throttle": {
        "between_detail_pages": {"min_seconds": 3.0, "max_seconds": 8.0},
        "after_connection_error": {"min_seconds": 90.0, "max_seconds": 150.0}, # stepstone drops connections when it wants a break
    },
    "dedup": {
        "description_containment": 0.90, # same company + this overlap = same job
    },
}
