xing_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.xing.com/jobs/search/ki?keywords={keywords}&location={location}&radius={radius}&sincePeriod={job_age}",
    "location_radius_pairs" : {
        # Allowed radius lengths for xing are : 0, 10, 20, 50, 70, 100, 200
        # ten hubs around Mannheim, circles must not overlap
        "Mannheim": 20, # + Heidelberg, Ludwigshafen, Worms, Speyer
        "Darmstadt": 10, # 45 km
        "Kaiserslautern": 20, # 52 km
        "Karlsruhe": 20, # 54 km, + Ettlingen, Bruchsal
        "Mainz": 10, # 58 km, Wiesbaden at the edge
        "Heilbronn": 20, # 66 km, + Neckarsulm
        "Frankfurt am Main": 10, # 71 km, + Offenbach, Eschborn
        "Stuttgart": 20, # 95 km, + Böblingen, Ludwigsburg, Esslingen
        "Saarbrücken": 20, # 110 km
        "Würzburg": 20, # 112 km
        # more cities, still non-overlapping
        #"Gießen": 20,
        #"Koblenz": 20,
        #"Aschaffenburg": 20,
        # inside the Mannheim circle, only if page 1 fills up
        #"Heidelberg": 20, # + Walldorf, Sandhausen
        #"Speyer": 10, # + Hockenheim, Schifferstadt
        #"Worms": 10,
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
    },
    "job_age": "LAST_MONTH", # LAST_24_HOURS, LAST_WEEK, LAST_MONTH; weekly runs LAST_WEEK
    "search_keywords": None, # None = the common list
    "between_queries": None, # None = the common pace
    "max_detail_pages": None, # None = the stage-2 limit
    "between_detail_pages": None, # None = the stage-2 pace

    # selectors
    "cookie_button": "button[data-action-type='accept'][id='accept']", # accept button
    "search_page": {
        "results_container": "div[class*='container__Container']",
        "cards": "div[class*='container__Container'] > div > ol[class*='results-styles'] > li > article[data-xds='Card']",
        "card_link": "a", # title is in its aria-label
    },
    "detail_page": {
        "wait_for": "[data-testid='expandable-content']", # 'main' appears before the JSON-LD does
        "description": ["[data-testid='expandable-content']"], # 'main' would hold the similar-jobs list
        "company": ["[data-testid='job-details-company-info-name']"],
        "location": ["[data-testid='company-card-location']"],
        "junk_lines": ["null", "Jetzt bewerben", "Bewerbung starten mit LinkedIn", "Bitte warten..."], # dropped from descriptions
        "footer_markers": ["Anstellungsart"], # short footer block cut off
        "expired_signatures": ["nicht mehr verfügbar", "nicht mehr online", "ist abgelaufen", "no longer available", "wurde deaktiviert",
                               "this job ad isn't available", "this job ad isn’t available", "stellenanzeige ist nicht verfügbar"], # lowercase
    },
}
