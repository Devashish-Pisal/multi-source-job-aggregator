stepstone_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.stepstone.de/jobs/{keywords}/in-{location}?radius={radius}&action=facet_selected%3bage%3bage_1&ag=age_{job_age}&searchOrigin=Resultlist_top-search",
    "location_radius_pairs" : {
        # Allowed radius lengths for stepstone are : 5, 10, 20, 30, 40, 50, 75, 100
        # non-overlapping tiles, only page 1 is read
        "Mannheim": 40, # + Ludwigshafen, Weinheim, Schwetzingen
        # inside the Mannheim circle; add one only if the run summary shows full first pages
        #"Heidelberg": 20, # + Walldorf, Sandhausen
        #"Speyer": 10, # + Hockenheim, Schifferstadt
        #"Worms": 10,
        # inside a tile above, only if its page 1 is full
        #"Ludwigshafen Am Rhein": 20,
        #"Walldorf": 20,
        #"Frankenthal (Pfalz)": 5,
        #"Weinheim": 5,
        #"Maxdorf": 5,
        #"Limburgerhof": 5,
        #"Schifferstadt": 5,
        #"Hockenheim": 5,
        #"Rheinau": 5,
        #"Schwetzingen": 5,
        #"Sandhausen": 5,
        #"Viernheim": 5,
        # Farther cities
        #"Karlsruhe": 20,
        #"Kaiserslautern": 20,
        #"Darmstadt": 20,
        #"Frankfurt Am Main": 20,
        #"Stuttgart": 20,
    },
    "job_age": 7, # 1 or 7 (max)

    # selectors
    "cookie_button": "button[id='ccmgt_explicit_accept']", # unverified
    "search_page": {
        "results_container": "div[class*='res-'][data-genesis-element='BASE']",
        "hit_counter": "[data-resultlist-offers-numbers]",
        "hit_counter_attribute": "data-resultlist-offers-main-displayed", # real hits, no recommendations
        "links": "a[href*='/stellenangebote']",
    },
    "detail_page": {
        "wait_for": "[data-at='job-ad-content']",
        "description": ["[data-at='job-ad-content']"],
        "company": ["[data-at='header-company-name']"],
        "location": ["[data-at='metadata-location']"],
        "junk_lines": [],
        "footer_markers": [],
        "expired_signatures": ["nicht mehr verfügbar", "nicht mehr aktiv", "ist abgelaufen", "no longer available", "wurde deaktiviert"],
    },
}
