import os
import re
import requests
import pandas as pd
from box import Box
from pprint import pprint
from loguru import logger
from dotenv import load_dotenv
from config.path_config import RAW_FOLDER_PATH, PROCESSED_FOLDER_PATH, DUPLICATES_FOLDER_PATH
from utils.util import generate_deduplication_key


class Adzuna:
    def __init__(self, common_config:dict):
        self.common_config = common_config
        self.ADZUNA_APP_ID = None
        self.ADZUNA_APP_KEY = None
        self.request_params = None
        self.iter_params = None
        self.result = None
        self._load_adzuna_secrets()


    def _load_adzuna_secrets(self):
        """
        Extract secret environment variables from .env file
        :return: None
        """
        if self.common_config["use_adzuna_api"]:
            logger.info("Using adzuna api!")
            self.ADZUNA_APP_ID = None
            self.ADZUNA_APP_KEY = None
            try:
                load_dotenv()
                self.ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
                self.ADZUNA_APP_KEY = os.environ.get("ADZUNA_API_KEY")
                logger.info("Adzuna secret credentials loaded successfully.")
            except Exception:
                logger.exception("Unable to load Adzuna secret credentials!")


    def execute_query(self):
        """
        Combines all methods from the class together and executes all of them in clean pipeline manner.
        :return: None
        """
        self._construct_request_and_iter_params()
        self._make_requests()
        self._save_csv_file()


    def _construct_request_and_iter_params(self):
        """
        Creates request parameters to send with requests and creates iteration parameters to inject in request parameters one by one.
        :return: None
        """
        common_config = Box(self.common_config)
        request_params = {
            "app_id": self.ADZUNA_APP_ID,
            "app_key": self.ADZUNA_APP_KEY,
            "results_per_page": common_config.results_per_page,
            "what": None, # It is iteration variable, it will be set during making request
        }
        if not common_config.remote:
            request_params["where"] = None # It is iteration variable, it will be set during making request
            request_params["distance"] = common_config.distance
        if common_config.full_time:
            request_params["full_time"] = "1"
        if common_config.part_time:
            request_params["part_time"] = "1"
        self.request_params = request_params
        iter_params = {
            "countries" : [self._get_country_code_mappings()[country] for country in common_config.country],
            "cities": list(common_config.city),
            "search_terms": list(common_config.search_keywords),
        }
        self.iter_params = iter_params
        logger.info(f"Adzuna iter params are : {iter_params}")


    def _make_requests(self):
        """
        Make multiple requests to adzuna by iterating over self.iter_params
        :return: None
        """
        countries = self.iter_params["countries"]
        cities = self.iter_params["cities"]
        search_terms = self.iter_params["search_terms"]
        request_params = self.request_params
        result = {
            "area": [],
            "company": [],
            "title": [],
            "source": [],
            "redirect_url": [],
            "description": [],
            "deduplication_key": []
        }
        for country in countries:
            for city in cities:
                for term in search_terms:
                    request_url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{self.common_config['page_number']}"
                    if not self.common_config["remote"]:
                        request_params["where"] = city
                        request_params["what"] = term
                        response = requests.get(url=request_url, params=request_params, headers=self._get_adzuna_request_headers())
                        if response.status_code != 200:
                            logger.error(f"Status: {response.status_code}")
                            logger.error(f"Response: {response.text}")
                            logger.error(f"URL: {response.url}")
                            logger.error(f"Params: {request_params}")
                        else:
                            data = response.json()
                            output = data["results"]
                            for dictionary in output:
                                title = dictionary["title"].strip().lower()
                                company = dictionary["company"]["display_name"].strip().lower()
                                location = dictionary["location"]["area"][-1]
                                dedup_key = generate_deduplication_key(title, company, location)
                                result["area"].append(", ".join([item.strip().lower() for item in dictionary["location"]["area"]]))
                                result["company"].append(company)
                                result["title"].append(title)
                                result["source"].append("adzuna")
                                result["redirect_url"].append(dictionary["redirect_url"])
                                result["description"].append(self._get_normalized_job_description(dictionary["description"]))
                                result["deduplication_key"].append(dedup_key)
                    else:
                        raise ValueError("Remote job search for adzuna is not implemented yet!")
        self.result = pd.DataFrame(result)


    def _save_csv_file(self):
        """
        Saves raw CSV files of adzuna job postings in folder data/raw.
        :return: None
        """
        file_path = os.path.join(RAW_FOLDER_PATH,"adzuna_" + self.common_config["output_filename"])
        self.result.to_csv(file_path, encoding="utf-8", index=False)
        logger.info(f"Raw output data with {len(self.result)} entries is stored at location {file_path}")


    @staticmethod
    def _get_normalized_job_description(description:str):
        normalized = re.sub(r"\s+", " ", description).strip().lower()
        normalized = normalized[0:490] # Removing last 10 chars (description contains "..." at the end)
        return normalized


    @staticmethod
    def _get_adzuna_request_headers():
        """
        Gives headers to pass in the API request
        :return:
        """
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        return headers


    @staticmethod
    def _get_country_code_mappings():
        """
        Maps country names with their ISO 8601 country codes
        :return: Mapping of country names with their ISO 8601 country codes
        """
        country_code_mapping = {
            "united kingdom": "gb",
            "united states": "us",
            "austria": "at",
            "australia": "au",
            "belgium": "be",
            "brazil": "br",
            "canada": "ca",
            "switzerland": "ch",
            "germany": "de",
            "spain": "es",
            "france": "fr",
            "india": "in",
            "italy": "it",
            "mexico": "mx",
            "netherlands": "nl",
            "new zealand": "nz",
            "poland": "pl",
            "singapore": "sg",
            "south africa": "za",
        }
        return country_code_mapping


"""
EXAMPLE OF ONE OUTPUT RESPONSE DICTIONARY

{'__CLASS__': 'Adzuna::API::Response::Job',
 'adref': 'eyJhbGciOiJIUzI1NiJ9.eyJpIjoiNTY5MDUxMTc1MiIsInMiOiJZSnhIS2IweThSR2xNN1libWNubFl3In0.nTFainf-d4HGQIImRmQER5598s8GE5EZySoyW2jDgzc',
 'category': {'__CLASS__': 'Adzuna::API::Response::Category',
              'label': 'IT-Stellen',
              'tag': 'it-jobs'},
 'company': {'__CLASS__': 'Adzuna::API::Response::Company',
             'display_name': 'Stiftung Kirchliches Rechenzentrum '
                             'Südwestdeutschland'},
 'created': '2026-04-05T10:59:33Z',
 'description': 'Deine Mission - Du entwickelst das datengetriebene Herz '
                'unserer Services Als Python Developer bist Du der Experte für '
                'die Konzeption, Entwicklung und Optimierung unserer '
                'datenintensiven Anwendungen. Dein Fokus liegt auf der '
                'Implementierung performanter Backend-Services und der '
                'Sicherstellung geschäftskritischer ETL-Prozesse. Aufgaben '
                'Schwerpunkt Backend-Entwicklung: Du designst, implementierst '
                'und wartest skalierbare Backend-Services und APIs, primär '
                'unter Verwendung von Python und FastAPI. ITS…',
 'id': '5690511752',
 'latitude': 49.09022,
 'location': {'__CLASS__': 'Adzuna::API::Response::Location',
              'area': ['Deutschland',
                       'Baden-Württemberg',
                       'Karlsruhe (Kreis)',
                       'Eggenstein-Leopoldshafen'],
              'display_name': 'Eggenstein-Leopoldshafen, Karlsruhe (Kreis)'},
 'longitude': 8.42763,
 'redirect_url': 'https://www.adzuna.de/land/ad/5690511752?se=YJxHKb0y8RGlM7YbmcnlYw&utm_medium=api&utm_source=4aaad539&v=E37BB83202C894B8CC7213F8ED57FA21456AFEBB',
 'salary_is_predicted': '0',
 'title': 'Python-Entwickler Plattformbetrieb & Datenflussoptimierung (m/w/d)'}
"""