sss_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://talents.studysmarter.de/jobs/?keyword={keywords}&page_number=1&job_listing_type=&job_listing_category=&job_listing_tag=&job_listing_company_size=&job_listing_industry=&job_listing_seniority_level=&is_remote_position=&city={location}&radius={radius}&isResetClicked=false&easy_apply=&salary_min=&salary_max=&job_age={job_age}&premium_only=",
    "location_radius_pairs" : {
        # Allowed radius lengths for study smarter are : 1, 10, 20, 30, 40, 50
        "Mannheim": 40,
        "Heidelberg": 30,
        "Ludwigshafen": 30,
        "Walldorf": 20,
        #"Karlsruhe": 20,
        #"Kaiserslautern": 20,
        #"Darmstadt": 20,
        #"Frankfurt am Main": 20,
        #"Stuttgart": 20,

        # Small cities near Mannheim
        "Worms": 10,
        "Frankenthal (Pfalz)": 10,
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
    "job_age": 30, # Allowed number of days old job for study smarter is (1, 7, 30)
}
