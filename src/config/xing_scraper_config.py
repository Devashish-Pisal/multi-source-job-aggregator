xing_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.xing.com/jobs/search/ki?keywords={keywords}&location={location}&radius={radius}&sincePeriod={job_age}",
    "location_radius_pairs" : {
        # Allowed radius lengths for xing are : 0, 10, 20, 50, 70, 100, 200
        # non-overlapping tiles, only page 1 is read
        "Mannheim": 50, # + Ludwigshafen, Weinheim, Schwetzingen
        # inside the Mannheim circle; add one only if the run summary shows full first pages
        #"Heidelberg": 20, # + Walldorf, Sandhausen
        #"Speyer": 10, # + Hockenheim, Schifferstadt
        #"Worms": 10,
        # inside a tile above, only if its page 1 is full
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
    "job_age": "LAST_MONTH", # LAST_24_HOURS, LAST_WEEK, LAST_MONTH; weekly runs LAST_WEEK

    # selectors
    "cookie_button": "button[data-action-type='accept'][id='accept']", # accept button
    "search_page": {
        "results_container": "div[class*='container__Container']",
        "cards": "div[class*='container__Container'] > div > ol[class*='results-styles'] > li > article[data-xds='Card']",
        "card_link": "a", # title is in its aria-label
    },
    "detail_page": {
        "wait_for": "main",
        "description": ["[data-testid='job-description']", "main"], # 'main' is the noisy last resort
        "company": ["[data-testid='job-company-name']"],
        "location": ["[data-testid='job-location']"],
        "junk_lines": ["null", "Jetzt bewerben", "Bewerbung starten mit LinkedIn", "Bitte warten..."], # dropped from descriptions
        "footer_markers": ["Anstellungsart"], # short footer block cut off
        "expired_signatures": ["nicht mehr verfügbar", "nicht mehr online", "ist abgelaufen", "no longer available", "wurde deaktiviert"],
    },
}
