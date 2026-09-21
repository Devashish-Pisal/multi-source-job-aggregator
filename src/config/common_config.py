
config =  {

    # User query setting
    "country": ["germany"],                     # List of countries to search for job listings (case-insensitive) [CURRENTLY ONLY SUPPORTED FOR 'GERMANY']
    "city": ["mannheim"],                       # List of cities to search for job listings (case-insensitive)
    "distance": 40,                             # In kilometers
    "remote": False,                            # If set "True", then "city", "distance" fields will be ignored completely.
    "full_time": False,
    "part_time": False,
    "search_keywords": [                        # Synonymes of search terms (at the end results for all terms will be merged and duplicated will be removed) (case-insensitive)
        "Werkstudent KI",
        """
        "Software Developer Working Student",
        "Software Development Intern",
        "Junior Software Engineer Part-Time",
        "Werkstudent Softwareentwicklung",
        "Praktikum Softwareentwicklung",
        "Junior Softwareentwickler Teilzeit",
        "Werkstudent Webentwicklung",
        "Backend Developer Working Student",
        "Java Developer Intern",
        "Python Developer Part-Time",
        "Werkstudent Backend Entwicklung",
        "Praktikum Java Entwicklung",
        "Werkstudent Python Entwicklung",
        """
    ],
    "output_filename": "jobs.csv",              # Currently only .csv output file formate is supported
    "keywords_job_title_must_include": [],      # Job title will always include at least one keyword from the list (OR operation)
    "keywords_job_title_must_exclude": [],      # Job title will never include any keyword from the list (AND operation)
    


    # Developer setting
    "use_adzuna_api": True,
    "use_arbeitsamt_api": True,
    "use_arbeitnow_api": True,
    "use_findwork_api": True,                   # Developer focussed platform
    "max_pages": 1,
    "page_number": 1,
    "results_per_page": 250,
    "output_format": ".csv"                     # Currently only .csv output file format is supported
}
