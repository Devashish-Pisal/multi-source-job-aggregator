linkedin_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.linkedin.com/jobs/search?keywords={keywords}&location={location}&distance={radius}&f_TPR={job_age}&sortBy=DD", # guest search, newest first
    "location_radius_pairs": {
        # Allowed radius lengths for linkedin are (miles, 1 mi = 1.6 km) : 0 (the place only), 5, 10, 25, 50
        # one big circle while guests get so few page loads; page 1 holds 60 jobs
        "Mannheim, Baden-Württemberg, Deutschland": 50, # 80 km, + Frankfurt, Darmstadt, Mainz, Karlsruhe, Heilbronn, Kaiserslautern
        # non-overlapping tiles within ~150 km of Mannheim, only page 1 is read; a radius is limited by its neighbour
        #"Mannheim, Baden-Württemberg, Deutschland": 25, # 40 km, + Heidelberg, Ludwigshafen, Worms, Speyer, Walldorf
        #"Darmstadt, Hessen, Deutschland": 0, # 45 km
        #"Kaiserslautern, Rheinland-Pfalz, Deutschland": 5, # 52 km
        #"Karlsruhe, Baden-Württemberg, Deutschland": 5, # 54 km
        #"Mainz, Rheinland-Pfalz, Deutschland": 10, # 58 km, + Wiesbaden
        #"Heilbronn, Baden-Württemberg, Deutschland": 0, # 66 km
        #"Frankfurt am Main, Hessen, Deutschland": 10, # 71 km, + Offenbach, Eschborn
        #"Stuttgart, Baden-Württemberg, Deutschland": 25, # 95 km, + Böblingen, Ludwigsburg, Esslingen, Tübingen, Pforzheim
        #"Saarbrücken, Saarland, Deutschland": 25, # 110 km
        #"Würzburg, Bayern, Deutschland": 25, # 112 km
        # more cities, still non-overlapping
        #"Gießen, Hessen, Deutschland": 10,
        #"Koblenz, Rheinland-Pfalz, Deutschland": 25,
        #"Aschaffenburg, Bayern, Deutschland": 10,
        # inside the Mannheim circle; add one only if the run summary shows full first pages
        #"Heidelberg, Baden-Württemberg, Deutschland": 10, # + Walldorf, Sandhausen
        #"Ludwigshafen am Rhein, Rheinland-Pfalz, Deutschland": 5,
        #"Speyer, Rheinland-Pfalz, Deutschland": 5,
        #"Worms, Rheinland-Pfalz, Deutschland": 5,
        #"Weinheim, Baden-Württemberg, Deutschland": 5,
        #"Walldorf, Baden-Württemberg, Deutschland": 5,
    },
    "job_age": "r1209600", # seconds: r86400 = 1 day, r604800 = 7 days, r1209600 = 14 days, r2592000 = 30 days; weekly runs r604800
    # guests get a sign-in wall after a few dozen page loads, so few and slow ones
    "search_keywords": ["Werkstudent Digitalisierung", "Werkstudent Automatisierung", "Werkstudent Data Science", "Praktikum Data Analytics", "Intern AI"], # None = the common list
    "between_queries": {"min_seconds": 20.0, "max_seconds": 40.0}, # None = the common pace
    "max_detail_pages": 20, # posting pages per run, None = max_detail_pages_per_platform in stage2_config
    "between_detail_pages": {"min_seconds": 10.0, "max_seconds": 20.0}, # None = the stage-2 pace

    # selectors
    "cookie_button": "button[action-type='DENY']", # reject button
    "modal_dismiss_button": "button.contextual-sign-in-modal__modal-dismiss:visible", # sign-in popup
    "search_page": {
        "results_container": "ul.jobs-search__results-list",
        "cards": "ul.jobs-search__results-list div.base-search-card[data-entity-urn^='urn:li:jobPosting:']",
        "title": "h3.base-search-card__title",
    },
    "detail_page": {
        "wait_for": ".show-more-less-html__markup", # no JSON-LD on linkedin
        "description": [".show-more-less-html__markup"],
        "company": ["a.topcard__org-name-link", "span.topcard__flavor"],
        "location": ["span.topcard__flavor.topcard__flavor--bullet"], # "Köln, Nordrhein-Westfalen, Deutschland"
        "date_posted": ["span.posted-time-ago__text"], # "Vor 1 Woche"
        "junk_lines": [],
        "footer_markers": [],
        "expired_signatures": ["no longer accepting applications", "nimmt keine bewerbungen mehr an", "bewerbungen werden nicht mehr angenommen", "seite nicht gefunden"], # lowercase, the first three unverified
    },
}
