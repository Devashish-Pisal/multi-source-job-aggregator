common_config = {
    # Knobs to enable/disable scrapers
    "use_indeed_scraper": True,
    "use_stepstone_scraper": True,
    "use_xing_scraper": True,
    "use_study_smarter_scraper": True,
    "use_linkedin_scraper": False,

    # 1 = search pages, 2 = job pages, 3 = llm judge
    "run_stage_1": False,
    "run_stage_2": True,
    "run_stage_3": True,

    "log_level": "INFO", # DEBUG, INFO, WARNING, ...

    "browser_profile_path": "/home/dev/scraping_chrome_profiles/common_profile/", # Browser profiles with accepted website cookies reduces the chances of triggering anti bot measure

    "throttle_config": {
        # delay ranges in seconds
        "between_queries": {"min_seconds": 2.0, "max_seconds": 6.0},
        "between_interactions": {"min_seconds": 0.3, "max_seconds": 1.2},
        "post_page_load": {"min_seconds": 1.0, "max_seconds": 3.0},
        "between_sources": {"min_seconds": 5.0, "max_seconds": 15.0},
        "scroll": {"min_steps": 1, "max_steps": 4, "step_min_pixels": 200, "step_max_pixels": 600, "step_min_seconds": 0.2, "step_max_seconds": 0.8},
    },
    "circuit_breaker": {
        "max_consecutive_failures": 5, # failed queries in a row before a scraper gives up
    },
}
