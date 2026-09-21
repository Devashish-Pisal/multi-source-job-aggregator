indeed_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://de.indeed.com/jobs?q={keywords}&l={location}&fromage={job_age}&radius={radius}&sort=date", # newest first: page 1 holds everything posted since the last run while the inflow stays below one page
    "location_radius_pairs": {
        # Allowed radius lengths for indeed are : 0, 5, 10, 15, 25, 35, 40, 50, 100
        # Non-overlapping tiles: only page 1 of each query is read, so nested circles return the same page again
        "Mannheim, Baden-Württemberg": 15, # covers Ludwigshafen, Frankenthal, Viernheim, Schwetzingen
        "Heidelberg, Baden-Württemberg": 15, # covers Walldorf, Sandhausen, Handschuhsheim
        "Speyer, Rheinland-Pfalz": 10, # covers Hockenheim, Schifferstadt, Limburgerhof
        "Worms, Rheinland-Pfalz": 10,
        "Weinheim, Baden-Württemberg": 10, # sits on the edge of the Mannheim tile
        # Inside a tile above; uncomment only if that tile saturates (page 1 full)
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
    "job_age": 14, # Allowed values: 1, 3, 7, 14 (30 is not offered). Weekly cadence: 7. Catch-up after a pause: 14

    # Selectors (both stages). Extraction logic stays in indeed_scraper.py; only the strings live here.
    "cookie_button": "button[id='onetrust-reject-all-handler']", # reject-all button
    "search_page": {
        "results_container": "div[class*='jobsearch-LeftPane']",
        "no_results": "div[class*='jobsearch-NoResult-messageContainer']",
        "cards": "#mosaic-jobResults #mosaic-provider-jobcards ul > li[class*='css']  a[id*='job']", # > div[class*='vjs-highlight']
        "title_fallback": "h2[class*='jobTitle']", # only used when the href carries no ti= parameter
    },
    "detail_page": {
        "wait_for": "#jobDescriptionText", # JSON-LD script is always waited for as well
        "description": ["#jobDescriptionText"], # fallback lists: first selector with text wins
        "company": ["[data-testid='inlineHeader-companyName']", "[data-company-name='true']"],
        "location": ["[data-testid='inlineHeader-companyLocation']", "[data-testid='job-location']"],
        "expired_signatures": ["stellenanzeige ist abgelaufen", "job has expired", "nicht mehr verfügbar", "no longer available"], # lowercase phrases, matched against title + first 5 kB of text
    },
}
