indeed_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://de.indeed.com/jobs?q={keywords}&l={location}&fromage={job_age}&radius={radius}&sort=date", # newest first
    "location_radius_pairs": {
        # Allowed radius lengths for indeed are : 0, 5, 10, 15, 25, 35, 40, 50, 100
        # non-overlapping tiles within ~150 km of Mannheim, only page 1 is read; a radius is limited by its neighbour
        "Mannheim, Baden-Württemberg": 25, # + Heidelberg, Ludwigshafen, Worms, Speyer, Walldorf
        "Darmstadt, Hessen": 10, # 45 km
        "Kaiserslautern, Rheinland-Pfalz": 25, # 52 km
        "Karlsruhe, Baden-Württemberg": 25, # 54 km, + Ettlingen, Bruchsal
        "Mainz, Rheinland-Pfalz": 10, # 58 km, Wiesbaden at the edge
        "Heilbronn, Baden-Württemberg": 15, # 66 km, + Neckarsulm
        "Frankfurt am Main, Hessen": 15, # 71 km, + Offenbach, Eschborn, Bad Homburg
        "Stuttgart, Baden-Württemberg": 25, # 95 km, + Böblingen, Ludwigsburg, Esslingen
        "Saarbrücken, Saarland": 25, # 110 km
        "Würzburg, Bayern": 25, # 112 km
        # more cities, still non-overlapping (Tübingen and Pforzheim have no room next to Stuttgart / Karlsruhe)
        #"Gießen, Hessen": 25,
        #"Koblenz, Rheinland-Pfalz": 25,
        #"Aschaffenburg, Bayern": 15,
        # inside the Mannheim circle; add one only if the run summary shows full first pages
        #"Heidelberg, Baden-Württemberg": 15, # + Walldorf, Sandhausen
        #"Speyer, Rheinland-Pfalz": 10, # + Hockenheim, Schifferstadt
        #"Worms, Rheinland-Pfalz": 10,
        #"Weinheim, Baden-Württemberg": 10,
        #"Ludwigshafen am Rhein, Rheinland-Pfalz": 25,
        #"Walldorf, Baden-Württemberg": 25,
        #"Frankenthal, Rheinland-Pfalz": 5,
        #"Maxdorf, Rheinland-Pfalz": 5,
        #"Rheingönheim, Rheinland-Pfalz": 5,
        #"Limburgerhof, Rheinland-Pfalz": 5,
        #"Schifferstadt, Rheinland-Pfalz": 5,
        #"Hockenheim, Baden-Württemberg": 5,
        #"Rheinau, Baden-Württemberg": 5,
        #"Schwetzingen, Baden-Württemberg": 5,
        #"Sandhausen, Baden-Württemberg": 5,
        #"Handschuhsheim, Baden-Württemberg": 5,
        #"Viernheim, Hessen": 5,
    },
    "job_age": 14, # 1, 3, 7, 14; weekly runs 7, catch-up 14
    # indeed shows a security check after ~30 quick queries, so fewer and slower ones
    "search_keywords": ["Werkstudent Digitalisierung", "Werkstudent KI", "Werkstudent Data Science", "Werkstudent Data Analytics", "Intern AI"], # None = the common list
    "between_queries": {"min_seconds": 20.0, "max_seconds": 40.0}, # None = the common pace
    "max_detail_pages": None, # posting pages per run, None = max_detail_pages_per_platform in stage2_config
    "between_detail_pages": None, # None = the stage-2 pace

    # selectors
    "cookie_button": "button[id='onetrust-reject-all-handler']", # reject-all button
    "search_page": {
        "results_container": "div[class*='jobsearch-LeftPane']",
        "no_results": "div[class*='jobsearch-NoResult-messageContainer']",
        "cards": "#mosaic-provider-jobcards a[data-jk][id^='job_']", # organic results, ads are sj_...
        "title": "span[id^='jobTitle-']", # full title in its title attribute
    },
    "detail_page": {
        "wait_for": "[data-testid='viewjob-job-content']", # JSON-LD is waited for too
        "description": ["[data-testid='viewjob-job-content']", "#jobDescriptionText"], # first match wins
        "company": ["[data-testid='inlineHeader-companyName']", "[data-company-name='true']"],
        "location": ["[data-testid='inlineHeader-companyLocation']", "[data-testid='job-location']"],
        "junk_lines": [],
        "footer_markers": [],
        "expired_signatures": ["stellenanzeige ist abgelaufen", "job has expired", "nicht mehr verfügbar", "no longer available"], # lowercase
    },
}
