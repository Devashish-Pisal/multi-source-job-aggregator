sss_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://talents.studysmarter.de/jobs/?keyword={keywords}&page_number=1&job_listing_type=&job_listing_category=&job_listing_tag=&job_listing_company_size=&job_listing_industry=&job_listing_seniority_level=&is_remote_position=&city={location}&radius={radius}&isResetClicked=false&easy_apply=&salary_min=&salary_max=&job_age={job_age}&premium_only=",
    "location_radius_pairs" : {
        # Allowed radius lengths for study smarter are : 1, 10, 20, 30, 40, 50
        # non-overlapping tiles within ~150 km of Mannheim, only page 1 is read; a radius is limited by its neighbour
        "Mannheim": 30, # + Heidelberg, Ludwigshafen, Worms, Speyer, Walldorf
        "Darmstadt": 10, # 45 km
        "Kaiserslautern": 20, # 52 km
        "Karlsruhe": 20, # 54 km, + Ettlingen, Bruchsal
        "Mainz": 10, # 58 km, Wiesbaden at the edge
        "Heilbronn": 20, # 66 km, + Neckarsulm
        "Frankfurt am Main": 10, # 71 km, + Offenbach, Eschborn
        "Stuttgart": 20, # 95 km, + Böblingen, Ludwigsburg, Esslingen
        "Saarbrücken": 20, # 110 km
        "Würzburg": 20, # 112 km
        # more cities, still non-overlapping (Tübingen and Pforzheim have no room next to Stuttgart / Karlsruhe)
        #"Gießen": 20,
        #"Koblenz": 20,
        #"Aschaffenburg": 20,
        # inside the Mannheim circle; add one only if the run summary shows full first pages
        #"Heidelberg": 20, # + Walldorf, Sandhausen
        #"Speyer": 10, # + Hockenheim, Schifferstadt
        #"Worms": 10,
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
    },
    "job_age": 30, # 1, 7, 30; weekly runs 7, catch-up 30

    # selectors
    "cookie_button": None, # no cookie banner
    "search_page": {
        "results_container": "div[class*='results__jobs']",
        "cards_container": "div[class='c-job-cards']", # not visible = no results
        "cards": "div[class='c-job-card ']", # trailing space is real
        "title": "div[class*='c-job-card'] h4[class*='c-job-card__title']",
        "card_link": "a",
    },
    "detail_page": {
        "wait_for": "main",
        "description": ["[class*='job-description']", "[class*='c-job-detail']", "main"], # 'main' is the noisy last resort
        "company": ["[class*='c-job-detail__company']"],
        "location": ["[class*='c-job-detail__location']"],
        "junk_lines": ["Impressum"],
        "footer_markers": [],
        "expired_signatures": ["nicht mehr verfügbar", "no longer available", "page not found", "seite nicht gefunden", "ist abgelaufen"],
    },
}
