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
}
