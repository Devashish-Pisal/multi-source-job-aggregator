stepstone_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.stepstone.de/jobs/{keywords}/in-{location}?radius={radius}&action=facet_selected%3bage%3bage_1&ag=age_{job_age}&searchOrigin=Resultlist_top-search",
    "location_radius_pairs" : {
        # Allowed radius lengths for stepstone are : 5, 10, 20, 30, 40, 50, 75, 100
        "Mannheim": 30,
        "Heidelberg": 20,
        "Ludwigshafen Am Rhein": 20,
        "Walldorf": 20,
        #"Karlsruhe": 20,
        #"Kaiserslautern": 20,
        #"Darmstadt": 20,
        #"Frankfurt Am Main": 20,
        #"Stuttgart": 20,

        # Small cities near Mannheim
        "Worms": 5,
        "Frankenthal (Pfalz)": 5,
        # "Maxdorf": 5,
        # "Limburgerhof": 5,
        # "Schifferstadt": 5,
        "Speyer": 5,
        # "Hockenheim": 5,
        # "Rheinau": 5,
        # "Schwetzingen": 5,
        # "Sandhausen": 5,
        # "Viernheim": 5,
        "Weinheim": 5,
    },
    "job_age": 7, # Allowed number of days old job for stepstone is (1, 7)
}
