linkedin_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.linkedin.com/jobs/search?keywords={keywords}&location={location}&distance={radius}&f_TPR={job_age}&sortBy=DD", # guest search, newest first
    "location_radius_pairs": {
        # Allowed radius lengths for linkedin are (miles) : 0, 5, 10, 25, 50
        # one big circle, guests get few page loads
        "Mannheim, Baden-Württemberg, Deutschland": 50, # 80 km, up to Frankfurt and Karlsruhe
        # ten hubs around Mannheim, for later
        #"Mannheim, Baden-Württemberg, Deutschland": 25, # 40 km, + Heidelberg, Ludwigshafen, Worms, Speyer, Walldorf
        #"Darmstadt, Hessen, Deutschland": 0, # 45 km
        #"Kaiserslautern, Rheinland-Pfalz, Deutschland": 5, # 52 km
        #"Karlsruhe, Baden-Württemberg, Deutschland": 5, # 54 km
        #"Mainz, Rheinland-Pfalz, Deutschland": 10, # 58 km, + Wiesbaden
        #"Heilbronn, Baden-Württemberg, Deutschland": 0, # 66 km
        #"Frankfurt am Main, Hessen, Deutschland": 10, # 71 km, + Offenbach, Eschborn
        #"Stuttgart, Baden-Württemberg, Deutschland": 25, # 95 km, + Böblingen, Ludwigsburg, Esslingen
        #"Saarbrücken, Saarland, Deutschland": 25, # 110 km
        #"Würzburg, Bayern, Deutschland": 25, # 112 km
        # more cities, still non-overlapping
        #"Gießen, Hessen, Deutschland": 10,
        #"Koblenz, Rheinland-Pfalz, Deutschland": 25,
        #"Aschaffenburg, Bayern, Deutschland": 10,
        # inside the Mannheim circle, only if page 1 fills up
        #"Heidelberg, Baden-Württemberg, Deutschland": 10, # + Walldorf, Sandhausen
        #"Ludwigshafen am Rhein, Rheinland-Pfalz, Deutschland": 5,
        #"Speyer, Rheinland-Pfalz, Deutschland": 5,
        #"Worms, Rheinland-Pfalz, Deutschland": 5,
        #"Weinheim, Baden-Württemberg, Deutschland": 5,
        #"Walldorf, Baden-Württemberg, Deutschland": 5,
    },
    "job_age": "r1209600", # r86400 = 1 day, r604800 = 7 (weekly), r1209600 = 14, r2592000 = 30
    # guests hit a sign-in wall quickly, so fewer and slower queries
    "search_keywords": ["Werkstudent Digitalisierung", "Werkstudent Automatisierung", "Werkstudent Data Science", "Praktikum Data Analytics", "Intern AI"], # None = the common list
    "between_queries": {"min_seconds": 20.0, "max_seconds": 40.0}, # None = the common pace
    "max_detail_pages": 20, # None = the stage-2 limit
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
        "expired_signatures": ["no longer accepting applications", "nimmt keine bewerbungen mehr an", "bewerbungen werden nicht mehr angenommen", "seite nicht gefunden"], # lowercase, partly unverified
    },
}
