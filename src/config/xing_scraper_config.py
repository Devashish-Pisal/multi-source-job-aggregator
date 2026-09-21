xing_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.xing.com/jobs/search/ki?keywords={keywords}&location={location}&radius={radius}&sincePeriod={job_age}",
    "location_radius_pairs" : {
        # Allowed radius lengths for xing are : 0, 10, 20, 50, 70, 100, 200
        # Non-overlapping tiles: only page 1 of each query is read, so nested circles return the same page again
        "Mannheim": 20, # covers Ludwigshafen, Frankenthal, Weinheim, Viernheim, Schwetzingen
        "Heidelberg": 20, # covers Walldorf, Sandhausen
        "Speyer": 10, # covers Hockenheim, Schifferstadt, Limburgerhof
        "Worms": 10,
        # Inside a tile above; uncomment only if that tile saturates (page 1 full)
        #"Ludwigshafen am Rhein": 20,
        #"Walldorf": 20,
        #"Frankenthal": 10,
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
    "job_age": "LAST_MONTH", # Allowed values: LAST_24_HOURS, LAST_WEEK, LAST_MONTH. Weekly cadence: LAST_WEEK. Catch-up after a pause: LAST_MONTH

    # Selectors (both stages). Extraction logic stays in xing_scraper.py; only the strings live here.
    "cookie_button": "button[data-action-type='accept'][id='accept']", # accept button
    "search_page": {
        "results_container": "div[class*='container__Container']",
        "cards": "div[class*='container__Container'] > div > ol[class*='results-styles'] > li > article[data-xds='Card']",
        "card_link": "a", # the card's click overlay; title comes from its aria-label
    },
    "detail_page": {
        "wait_for": "main",
        "description": ["[data-testid='job-description']", "main"], # guesses; 'main' is the noisy last resort
        "company": ["[data-testid='job-company-name']"],
        "location": ["[data-testid='job-location']"],
        "expired_signatures": ["nicht mehr verfügbar", "nicht mehr online", "ist abgelaufen", "no longer available", "wurde deaktiviert"],
    },
}
