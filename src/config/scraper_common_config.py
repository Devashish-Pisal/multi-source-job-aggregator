from pathlib import Path

scraper_common_config = {
    # Knobs to enable/disable scrapers
    "use_indeed_scraper": True,
    "use_stepstone_scraper": True,
    "use_xing_scraper": True,
    "use_study_smarter_scraper": True,

    # 1 = search pages, 2 = job pages + judge
    "run_stage_1": True,
    "run_stage_2": True,

    "log_level": "INFO", # DEBUG, INFO, WARNING, ...

    "browser_profile_path": "/home/dev/scraping_chrome_profiles/common_profile/", # Browser profiles with accepted website cookies reduces the chances of triggering anti bot measure
    "embedding_match_config": {
        "sentence_embedding_model": "BAAI/bge-m3", # model is used to compare the 'query keyword' and 'job title' match and to filter false positives
        "threshold": 0.43, # to filter non-relevant (or less relevant) job listings
    },
    # title must contain one of these words, [] turns it off; a trailing * also matches longer forms
    "title_required_words": [
        "werkstudent*", "werkstudierende*", "working student", "working students",
        "praktik*", "pflichtpraktik*", "praxissemester",
        "intern", "interns", "internship*",
        "thesis", "masterthesis", "bachelorthesis", "abschlussarbeit", "masterarbeit", "bachelorarbeit", "masterand*", "bachelorand*",
        "studentisch*", "student", "students", "studentin", "studenten", "hiwi", "hilfskraft",
    ],
    # titles with one of these words are rejected, [] turns it off
    "title_excluded_words": [
        "sales", "vertrieb", "kundenservice", "customer support", "customer service", "business development", "key account",
        "phd", "doktorand*", "initiativbewerbung", "unsolicited", "schülerpraktikum", "orientierungspraktikum", "chief of staff",
    ],
    "throttle_config": {
        # delay ranges in seconds
        "between_queries": {"min_seconds": 2.0, "max_seconds": 6.0},
        "between_interactions": {"min_seconds": 0.3, "max_seconds": 1.2},
        "post_page_load": {"min_seconds": 1.0, "max_seconds": 3.0},
        "between_sources": {"min_seconds": 5.0, "max_seconds": 15.0},
        "scroll": {"min_steps": 1, "max_steps": 4, "step_min_pixels": 200, "step_max_pixels": 600, "step_min_seconds": 0.2, "step_max_seconds": 0.8},
    },
    "circuit_breaker": {
        "max_consecutive_failures": 5, # failed queries in a row before a scraper gives up
    },

    # sent to the sites; each one costs a page load per location, so keep it short
    "search_keywords": [
        "Werkstudent KI",
        "Werkstudent Data Science",
        "Werkstudent Data Analytics",
        "Werkstudent Data Engineering",
        "Werkstudent Automatisierung",
        "Werkstudent Digitalisierung",
        "Praktikum Data Science",
        "Praktikum Data Analytics",
        "Praktikum Data Engineering",
        "Working Student Data Engineering",
        "Intern AI",
    ],

    # titles are scored against these topics (never sent to a site)
    "match_keywords": [
        # automation / digitalisation
        "Automatisierung",
        "Prozessautomatisierung",
        "Automation",
        "Process Automation",
        "Intelligent Automation",
        "Business Automation",
        "Digitalisierung",
        "Digitale Transformation",
        "Digital Transformation",
        # ai / data
        "KI",
        "AI",
        "Künstliche Intelligenz",
        "Artificial Intelligence",
        "Machine Learning",
        "Maschinelles Lernen",
        "Generative AI",
        "LLM",
        "NLP",
        "Data Science",
        "Data Analytics",
        "Data Analyst",
        "Data Engineering",
        "Business Intelligence",
    ],
}












"""
ALL KEYWORDS: 


    "search_keywords" :  [
    # search keywords will be dynamically normalized/adjusted by every scraper at runtime (keep default format, every words first letter capitalized, e.g Working Student Python)
        # ==========================================================
        # 1. AUTOMATION / DIGITALIZATION (Highest Priority)
        # ==========================================================
        # German
        "Werkstudent Automatisierung",
        "Werkstudent Prozessautomatisierung",
        "Werkstudent Softwareautomatisierung",
        "Werkstudent Digitalisierung",
        "Werkstudent Digitale Transformation",
        "Werkstudent Prozessdigitalisierung",
        "Werkstudent Intelligent Automation",
        "Werkstudent Business Automation",
        "Werkstudent KI Automatisierung",
        "Werkstudent Automatisierungstechnik",
        "Werkstudent Digitalisierungsprojekte",
        "Werkstudent Digitale Lösungen",
        "Werkstudent Innovation",
        "Werkstudent Digital Innovation",
        # English
        "Working Student Automation",
        "Working Student Process Automation",
        "Working Student Intelligent Automation",
        "Working Student Business Automation",
        "Working Student Digital Transformation",
        "Working Student Digitalization",
        "Working Student Digital Solutions",
        "Working Student Automation Engineer",
        "Working Student Automation Developer",
        "Working Student Software Automation",
        "Working Student Innovation",
        "Working Student Digital Innovation",
        # Internship variants
        "Praktikum Automatisierung",
        "Praktikum Digitalisierung",
        "Praktikum Digitale Transformation",
        "Intern Automation",
        "Intern Digital Transformation",
        # ==========================================================
        # 2. AI / LLM / MACHINE LEARNING (Second Highest Priority)
        # ==========================================================
        # German
        "Werkstudent KI",
        "Werkstudent Künstliche Intelligenz",
        "Werkstudent Generative KI",
        "Werkstudent Generative AI",
        "Werkstudent LLM",
        "Werkstudent AI",
        "Werkstudent AI Engineer",
        "Werkstudent KI Entwicklung",
        "Werkstudent AI Entwicklung",
        "Werkstudent KI Softwareentwicklung",
        "Werkstudent Machine Learning",
        "Werkstudent Maschinelles Lernen",
        "Werkstudent NLP",
        "Werkstudent Prompt Engineering",
        "Werkstudent AI Software Engineer",
        "Werkstudent Applied AI",
        "Werkstudent AI Solutions",
        # English
        "Working Student AI",
        "Working Student AI Engineer",
        "Working Student Artificial Intelligence",
        "Working Student Machine Learning",
        "Working Student ML Engineer",
        "Working Student Generative AI",
        "Working Student LLM",
        "Working Student NLP",
        "Working Student Applied AI",
        "Working Student AI Developer",
        "Working Student AI Software Engineer",
        "Working Student AI Solutions",
        "Working Student AI Applications",
        "Working Student Prompt Engineering",
        # Internship variants
        "Praktikum KI",
        "Praktikum Künstliche Intelligenz",
        "Praktikum Machine Learning",
        "Praktikum AI",
        "Intern AI",
        "Intern Machine Learning",
        "Intern LLM",
        "Intern Generative AI",
        # ==========================================================
        # 3. PYTHON / BACKEND (Third Highest Priority)
        # ==========================================================
        # German
        "Werkstudent Python",
        "Werkstudent Python Entwickler",
        "Werkstudent Python Entwicklung",
        "Werkstudent Python Backend",
        "Werkstudent Backend",
        "Werkstudent Backend Entwickler",
        "Werkstudent Backend Entwicklung",
        "Werkstudent Softwareentwickler Python",
        "Werkstudent Softwareentwicklung Python",
        "Werkstudent API Entwicklung",
        "Werkstudent FastAPI",
        "Werkstudent REST API",
        "Werkstudent Webentwicklung Python",
        # English
        "Working Student Python",
        "Working Student Python Developer",
        "Working Student Python Backend",
        "Working Student Backend Developer",
        "Working Student Backend Engineer",
        "Working Student Software Engineer Python",
        "Working Student Software Developer Python",
        "Working Student API Developer",
        "Working Student FastAPI",
        "Working Student REST API",
        # Internship variants
        "Praktikum Python",
        "Praktikum Backend",
        "Intern Python Developer",
        "Intern Backend Developer",
        # ==========================================================
        # 4. RESEARCH / COMPUTER VISION (Lower Priority)
        # ==========================================================
        # German
        "Werkstudent Computer Vision",
        "Werkstudent Bildverarbeitung",
        "Werkstudent Deep Learning",
        "Werkstudent OCR",
        "Werkstudent Dokumentenanalyse",
        "Werkstudent Vision AI",
        "Werkstudent Multimodale KI",
        "Werkstudent AI Research",
        "HiWi KI",
        "HiWi Machine Learning",
        "HiWi Computer Vision",
        "Wissenschaftliche Hilfskraft KI",
        # English
        "Working Student Computer Vision",
        "Working Student Vision AI",
        "Working Student Deep Learning",
        "Working Student OCR",
        "Working Student Image Processing",
        "Working Student Document AI",
        "Working Student AI Research",
        "Working Student Applied Research",
        "Research Assistant AI",
        "Student Research Assistant AI",
        # Internship variants
        "Praktikum Computer Vision",
        "Intern Computer Vision",
        "Intern Deep Learning",
        # ==========================================================
        # 5. DATA SCIENCE / ANALYTICS
        # ==========================================================
        # German
        "Werkstudent Data Science",
        "Werkstudent Data Scientist",
        "Werkstudent Datenwissenschaft",
        "Werkstudent Data Analytics",
        "Werkstudent Datenanalyse",
        "Werkstudent Data Analyst",
        "Werkstudent Business Analytics",
        "Werkstudent Business Intelligence",
        "Werkstudent BI",
        "Werkstudent Data Engineering",
        "Werkstudent Data Engineer",
        "Werkstudent Big Data",
        "Werkstudent Data Mining",
        "Werkstudent Statistik",
        "Werkstudent Statistische Analyse",
        "Werkstudent Predictive Analytics",
        "Werkstudent Datenmodellierung",
        "Werkstudent SQL",
        "Werkstudent Python Data",
        "Werkstudent Analytics",
        
        # English
        "Working Student Data Science",
        "Working Student Data Scientist",
        "Working Student Data Analytics",
        "Working Student Data Analyst",
        "Working Student Analytics",
        "Working Student Business Analytics",
        "Working Student Business Intelligence",
        "Working Student BI",
        "Working Student Data Engineering",
        "Working Student Data Engineer",
        "Working Student Big Data",
        "Working Student Data Mining",
        "Working Student Predictive Analytics",
        "Working Student Statistical Analysis",
        "Working Student Statistics",
        "Working Student Data Modeling",
        "Working Student SQL",
        "Working Student Python Data",
        "Working Student Data Platform",
        "Working Student Data Solutions",
        
        # Internship variants
        "Praktikum Data Science",
        "Praktikum Data Scientist",
        "Praktikum Data Analytics",
        "Praktikum Data Analyst",
        "Praktikum Business Intelligence",
        "Praktikum Data Engineering",
        "Praktikum Data Engineer",
        "Praktikum Big Data",
        "Praktikum Analytics",
        "Intern Data Science",
        "Intern Data Scientist",
        "Intern Data Analytics",
        "Intern Data Analyst",
        "Intern Business Intelligence",
        "Intern Data Engineering",
        "Intern Data Engineer",
        "Intern Big Data",
        "Intern Analytics",
        "Intern Predictive Analytics",
    ], 
    
"""