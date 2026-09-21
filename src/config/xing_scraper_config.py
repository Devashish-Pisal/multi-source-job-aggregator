xing_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://www.xing.com/jobs/search/ki?keywords={keywords}&location={location}&radius={radius}&sincePeriod={job_age}",
    "location_radius_pairs" : {
        # Allowed radius lengths for xing are : 0, 10, 20, 50, 70, 100, 200
        "Mannheim": 50,
        "Heidelberg": 20,
        "Ludwigshafen am Rhein": 20,
        "Walldorf": 20,
        # "Karlsruhe": 20,
        # "Kaiserslautern": 20,
        # "Darmstadt": 20,
        # "Frankfurt am Main": 20,
        # "Stuttgart": 20,

        # Small cities near Mannheim
        "Worms": 10,
        "Frankenthal": 10,
        # "Maxdorf": 10,
        # "Limburgerhof": 10,
        # "Schifferstadt": 10,
        "Speyer": 10,
        # "Hockenheim": 10,
        # "Rheinau": 10,
        # "Schwetzingen": 10,
        # "Sandhausen": 10,
        # "Viernheim": 10,
        "Weinheim": 10,
    },
    "job_age": "LAST_MONTH", # Allowed number of days old job for xing is : LAST_24_HOURS, LAST_WEEK, LAST_MONTH
}
