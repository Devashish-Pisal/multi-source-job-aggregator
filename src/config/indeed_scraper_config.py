indeed_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://de.indeed.com/jobs?q={keywords}&l={location}&fromage={job_age}&radius={radius}&sort=date", # newest first
    "location_radius_pairs": {
        # Allowed radius lengths for indeed are : 0, 5, 10, 15, 25, 35, 40, 50, 100
        # non-overlapping tiles, only page 1 is read
        "Mannheim, Baden-Württemberg": 40, # + Ludwigshafen, Viernheim, Schwetzingen
        # "Heidelberg, Baden-Württemberg": 15, # + Walldorf, Sandhausen
        # step 2: add these once step 1 runs clean
        #"Speyer, Rheinland-Pfalz": 10, # + Hockenheim, Schifferstadt
        #"Worms, Rheinland-Pfalz": 10,
        #"Weinheim, Baden-Württemberg": 10, # edge of the Mannheim tile
        # inside a tile above, only if its page 1 is full
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
        # Farther cities
        #"Karlsruhe, Baden-Württemberg": 25,
        #"Kaiserslautern, Rheinland-Pfalz": 25,
        #"Darmstadt, Hessen": 25,
        #"Frankfurt am Main, Hessen": 25,
        #"Stuttgart, Baden-Württemberg": 25,
    },
    "job_age": 14, # 1, 3, 7, 14; weekly runs 7, catch-up 14

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
        "expired_signatures": ["stellenanzeige ist abgelaufen", "job has expired", "nicht mehr verfügbar", "no longer available"], # lowercase
    },
}
