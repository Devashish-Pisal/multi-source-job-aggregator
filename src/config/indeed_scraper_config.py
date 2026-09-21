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
}