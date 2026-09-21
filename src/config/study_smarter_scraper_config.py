sss_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://talents.studysmarter.de/jobs/?keyword={keywords}&page_number=1&job_listing_type=&job_listing_category=&job_listing_tag=&job_listing_company_size=&job_listing_industry=&job_listing_seniority_level=&is_remote_position=&city={location}&radius={radius}&isResetClicked=false&easy_apply=&salary_min=&salary_max=&job_age={job_age}&premium_only=",
    "location_radius_pairs" : {
        # Allowed radius lengths for study smarter are : 1, 10, 20, 30, 40, 50
        # Non-overlapping tiles: only page 1 of each query is read, so nested circles return the same page again
        "Mannheim": 20, # covers Ludwigshafen, Frankenthal, Weinheim, Viernheim, Schwetzingen
        "Heidelberg": 20, # covers Walldorf, Sandhausen
        "Speyer": 10, # covers Hockenheim, Schifferstadt, Limburgerhof
        "Worms": 10,
        # Inside a tile above; uncomment only if that tile saturates (page 1 full)
        #"Ludwigshafen": 30,
        #"Walldorf": 20,
        #"Frankenthal (Pfalz)": 10,
        #"Weinheim": 10,
        #"Maxdorf": 10,
        #"Limburgerhof": 10,
        #"Schifferstadt": 10,
        #"Hockenheim": 10,
        #"Rheinau": 10,
        #"Schwetzingen": 10,
        #"Sandhausen": 10,
        #"Viernheim": 10,
        # Farther cities
        #"Karlsruhe": 20,
        #"Kaiserslautern": 20,
        #"Darmstadt": 20,
        #"Frankfurt am Main": 20,
        #"Stuttgart": 20,
    },
    "job_age": 30, # Allowed values: 1, 7, 30. Weekly cadence: 7. Catch-up after a pause: 30

    # Selectors (both stages). Extraction logic stays in study_smarter_scraper.py; only the strings live here.
    "cookie_button": None, # no cookie banner handling; set a selector to have stage 2 click it
    "search_page": {
        "results_container": "div[class*='results__jobs']",
        "cards_container": "div[class='c-job-cards']", # not visible = no results
        "cards": "div[class='c-job-card ']", # trailing space is real
        "title": "div[class*='c-job-card'] h4[class*='c-job-card__title']",
        "card_link": "a",
    },
    "detail_page": {
        "wait_for": "main",
        "description": ["[class*='job-description']", "[class*='c-job-detail']", "main"], # guesses; 'main' is the noisy last resort
        "company": ["[class*='c-job-detail__company']"],
        "location": ["[class*='c-job-detail__location']"],
        "expired_signatures": ["nicht mehr verfügbar", "no longer available", "page not found", "seite nicht gefunden", "ist abgelaufen"],
    },
}
