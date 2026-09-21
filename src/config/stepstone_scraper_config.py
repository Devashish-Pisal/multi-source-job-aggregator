stepstone_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.stepstone.de/jobs/{keywords}/in-{location}?radius={radius}&action=facet_selected%3bage%3bage_1&ag=age_{job_age}&searchOrigin=Resultlist_top-search",
    "location_radius_pairs" : {
        # Allowed radius lengths for stepstone are : 5, 10, 20, 30, 40, 50, 75, 100
        # Non-overlapping tiles: only page 1 of each query is read, so nested circles return the same page again
        "Mannheim": 20, # covers Ludwigshafen, Frankenthal, Weinheim, Viernheim, Schwetzingen
        "Heidelberg": 20, # covers Walldorf, Sandhausen
        "Speyer": 10, # covers Hockenheim, Schifferstadt, Limburgerhof
        "Worms": 10,
        # Inside a tile above; uncomment only if that tile saturates (page 1 full)
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
    "job_age": 7, # Allowed values: 1, 7 (site maximum). Weekly cadence: 7

    # Selectors (both stages). Extraction logic stays in stepstone_scraper.py; only the strings live here.
    "cookie_button": "button[id='ccmgt_explicit_accept']", # not verified yet; stage 2 clicks it if visible, stage 1 still has its TODO; None disables
    "search_page": {
        "results_container": "div[class*='res-'][data-genesis-element='BASE']",
        "hit_counter": "[data-resultlist-offers-numbers]",
        "hit_counter_attribute": "data-resultlist-offers-main-displayed", # number of real hits on page 1 (excludes recommendations)
        "links": "a[href*='/stellenangebote']",
    },
    "detail_page": {
        "wait_for": "[data-at='job-ad-content']",
        "description": ["[data-at='job-ad-content']"],
        "company": ["[data-at='header-company-name']"],
        "location": ["[data-at='metadata-location']"],
        "expired_signatures": ["nicht mehr verfügbar", "nicht mehr aktiv", "ist abgelaufen", "no longer available", "wurde deaktiviert"],
    },
}
