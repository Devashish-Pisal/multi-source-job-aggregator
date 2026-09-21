indeed_scraper_config = {
    "use_headless_mode": False,
    "BASE_URL": "https://de.indeed.com/jobs?q={keywords}&l={location}&fromage={job_age}&radius={radius}",
    "location_radius_pairs": {
        # Allowed radius lengths for indeed are : 0, 5, 10, 15, 25, 35, 40, 50, 100
        # Big cities
        "Mannheim, Baden-Württemberg": 35,
        "Heidelberg, Baden-Württemberg": 25,
        "Ludwigshafen am Rhein, Rheinland-Pfalz": 25,
        "Walldorf, Baden-Württemberg": 25,
        #"Karlsruhe, Baden-Württemberg": 25,
        #"Kaiserslautern, Rheinland-Pfalz": 25,
        #"Darmstadt, Hessen": 25,
        #"Frankfurt am Main, Hessen": 25,
        #"Stuttgart, Baden-Württemberg": 25,

        # Small cities near Mannheim
        "Worms, Rheinland-Pfalz": 5,
        "Frankenthal, Rheinland-Pfalz": 5,
        #"Maxdorf, Rheinland-Pfalz": 5,
        #"Rheingönheim, Rheinland-Pfalz": 5,
        #"Limburgerhof, Rheinland-Pfalz": 5,
        #"Schifferstadt, Rheinland-Pfalz": 5,
        "Speyer, Rheinland-Pfalz": 5,
        #"Hockenheim, Baden-Württemberg": 5,
        #"Rheinau, Baden-Württemberg": 5,
        #"Schwetzingen, Baden-Württemberg": 5,
        #"Sandhausen, Baden-Württemberg": 5,
        #"Handschuhsheim, Baden-Württemberg": 5,
        #"Viernheim, Hessen": 5,
        "Weinheim, Baden-Württemberg": 5,
    },
    "job_age": 14,  # Allowed number of days old job for indeed is (1, 3, 7, 14)
}