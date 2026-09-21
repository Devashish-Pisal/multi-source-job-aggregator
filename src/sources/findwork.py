import os
import re
import requests
import pandas as pd
from box import Box
from pprint import pprint
from loguru import logger
from time import sleep
from dotenv import load_dotenv
from config.path_config import RAW_FOLDER_PATH, PROCESSED_FOLDER_PATH, DUPLICATES_FOLDER_PATH
from src.utils.util import generate_deduplication_key
from bs4 import BeautifulSoup
from cleantext import clean

class FindWork:
    def __init__(self, common_config:dict):
        self.common_config = common_config
        self.FINDWORK_APP_KEY = None
        self.request_params = None
        self.iter_params = None
        self.result = None
        self._load_findwork_secrets()


    def _load_findwork_secrets(self):
        """
        Extract secret environment variables from .env file
        :return: None
        """
        if self.common_config["use_findwork_api"]:
            logger.info("Using findwork api!")
            self.FINDWORK_APP_KEY = None
            try:
                load_dotenv()
                self.FINDWORK_APP_KEY = os.environ.get("FINDWORK_API_KEY")
                logger.info("Findwork secret credentials loaded successfully.")
            except Exception:
                logger.exception("Unable to load Findwork secret credentials!")


    def execute_query(self):
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
            "search": None, # It is iteration variable, it will be set during making request
            "order_by": "relevance",
            "page": common_config.page_number,
        }
        if not common_config.remote:
            request_params["location"] = None # It is iteration variable, it will be set during making request
            request_params["remote"] = False
        if common_config.full_time:
            request_params["employment_type"] = "full time"
        if common_config.part_time:
            request_params["employment_type"] = "contract"
        self.request_params = request_params
        if len(common_config.country) > 1 or common_config.country[0] != "germany":
            raise ValueError("Currently Findwork API only integrated for 'country'= ['germany']. "
                             "Either in common_config set 'use_findwork_api' = False or provide only one country 'germany' in country list.")
        iter_params = {
            "cities": list(common_config.city),
            "search_terms": list(common_config.search_keywords),
        }
        self.iter_params = iter_params
        logger.info(f"Findwork iter params are : {iter_params}")


    def _make_requests(self):
        """
        Make multiple requests to findwork by iterating over self.iter_params
        :return: None
        """
        request_url = "https://findwork.dev/api/jobs/"
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

        for city in cities:
            for term in search_terms:
                if not self.common_config["remote"]:
                    request_params["location"] = city
                    request_params["search"] = term
                    sleep(5)
                    logger.info("Sleeping for 5 seconds to avoid api request throttle.")
                    response = requests.get(url=request_url, params=request_params, headers=self._get_findwork_request_headers())
                    if response.status_code != 200:
                        logger.error(f"Status: {response.status_code}")
                        logger.error(f"Response: {response.text}")
                        logger.error(f"URL: {response.url}")
                        logger.error(f"Params: {request_params}")
                    else:
                        data = response.json()
                        output = data["results"]
                        for dictionary in output:
                            title = dictionary["role"].strip().lower()
                            company = dictionary["company_name"].strip().lower()
                            location = dictionary["location"].split(",")[0].strip().lower()        # 'location': 'Berlin, Germany',
                            dedup_key = generate_deduplication_key(title, company, location)
                            result["area"].append(dictionary["location"].strip().lower())
                            result["company"].append(company)
                            result["title"].append(title)
                            result["source"].append("findwork")
                            result["redirect_url"].append(dictionary["url"])
                            result["description"].append(self._get_normalized_job_description(dictionary["text"]))
                            result["deduplication_key"].append(dedup_key)
                else:
                    raise ValueError("Remote job search for findwork is not implemented yet!")
        self.result = pd.DataFrame(result)


    def _save_csv_file(self):
        """
        Saves raw CSV files of findwork job postings in folder data/raw.
        :return: None
        """
        file_path = os.path.join(RAW_FOLDER_PATH,"findwork_" + self.common_config["output_filename"])
        self.result.to_csv(file_path, encoding="utf-8", index=False)
        logger.info(f"Raw output data with {len(self.result)} entries is stored at location {file_path}")


    def _get_findwork_request_headers(self):
        """
        Gives headers to pass in the API request
        :return:
        """
        headers = {
            'Authorization': f"Token {self.FINDWORK_APP_KEY}",
            'Accept': "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        return headers


    @staticmethod
    def _get_normalized_job_description(description:str):
        text = BeautifulSoup(description, "html.parser").get_text()
        text = clean(text, normalize_whitespace=True, lower=True, no_line_breaks=True, no_emoji=True)
        return text


"""
ONE EXAMPLE FROM results list

{'company_name': 'Lane One',
  'company_num_employees': None,
  'date_posted': '2026-04-01T04:00:00Z',
  'employment_type': 'full time',
  'id': 'MdVLAZn',
  'keywords': ['ai'],
  'location': 'Berlin, Germany',
  'logo': 'https://berlinstartupjobs.com/wp-content/plugins/startup-jobs/inc/../images/company-placeholder.svg',
  'remote': False,
  'role': 'AI Partner Success Manager (m/w/d) // Lane One',
  'source': 'Berlinstartupjobs',
  'text': 'Verändere, wie die Welt arbeitet.\n'
          '\n'
          'KI-Agenten automatisieren schon heute ganze Geschäftsprozesse — im '
          'Vertrieb, im Support, in der Logistik, im Gesundheitswesen. In '
          'jeder Branche, in jeder Abteilung. Das ist keine Zukunftsvision. '
          'Das passiert jetzt. Und wir stehen erst am Anfang einer '
          'Transformation, die so grundlegend ist wie die Einführung des '
          'Internets.\n'
          '\n'
          'Bei Lane One bauen wir die Plattform, auf der Unternehmen ihre '
          'eigenen KI-Agenten erstellen und unter eigener Marke an ihre Kunden '
          'verkaufen.\n'
          '\n'
          'Deine Rolle dabei: Du machst unsere Partner erfolgreich. Jeder '
          'Partner, den du befähigst, bringt KI-Agenten in dutzende, hunderte, '
          'tausende Unternehmen. Du multiplizierst den Impact. Du veränderst '
          'nachhaltig, wie Menschen arbeiten.\n'
          '\n'
          '<strong>Aufgaben</strong>\n'
          '\n'
          'Was du tust? Denken wie ein Geschäftsführer — handeln wie ein '
          'Partner!\n'
          '\n'
          'Du versetzt dich in jeden einzelnen unserer Partner rein. Du '
          'verstehst sein Geschäftsmodell, seine Kunden, seine Branche, seine '
          'Herausforderungen.\n'
          '\n'
          'Du denkst nicht in Features — du denkst in Geschäftschancen. Wo '
          'kann ein KI-Agent echten Wert schaffen? Welches Produkt lässt sich '
          'daraus bauen? Wie wird daraus ein skalierbares Business für den '
          'Partner?\n'
          '\n'
          '<strong>Den 30-Tage-Erfolgssprint führen:</strong>\n'
          '<ul>\n'
          ' \t<li>Du analysierst das Geschäft des Partners und identifizierst '
          'die wirkungsvollsten Einsatzmöglichkeiten für KI-Agenten</li>\n'
          ' \t<li>Du entwickelst gemeinsam mit Partnern das Geschäftsmodell '
          'und die Go-to-Market-Strategie sowie erste POCs oder '
          'KI-Agenten</li>\n'
          ' \t<li>Du trainierst den Partner auf der Plattform — so '
          'tiefgreifend, dass er danach möglichst eigenständig agieren '
          'kann</li>\n'
          ' \t<li>Du sorgst dafür, dass am Ende von 30 Tagen ein '
          'funktionierender, wertschöpfender Agent live ist</li>\n'
          '</ul>\n'
          '<strong>Partner langfristig zum Erfolg führen:</strong>\n'
          '<ul>\n'
          ' \t<li>Du bleibst nach dem Sprint der strategische Sparringspartner '
          'an der Seite des Partners</li>\n'
          ' \t<li>Du challengst, berätst und inspirierst — wie ein Co-Pilot '
          'für das KI-Business des Partners</li>\n'
          ' \t<li>Du erkennst neue Chancen im Geschäft des Partners, bevor er '
          'sie selbst sieht</li>\n'
          ' \t<li>Du räumst Hindernisse aus dem Weg und findest pragmatische '
          'Lösungen</li>\n'
          ' \t<li>Du bringst Partner-Feedback strukturiert ins Team zurück, '
          'damit Produkt und Plattform besser werden</li>\n'
          '</ul>\n'
          '<strong>Qualifikation</strong>\n'
          '\n'
          '<strong>Kern-Skills:</strong>\n'
          '<ul>\n'
          ' \t<li>Unternehmerisches Denken: Du kannst dich in die Perspektive '
          'eines Geschäftsführers versetzen — du verstehst Geschäftsmodelle, '
          'Kundenbedürfnisse und wie man Mehrwert schafft</li>\n'
          ' \t<li>Kommunikationsstärke: Du kannst mit Geschäftsführern, '
          'Vertriebsleitern und technischen Ansprechpartnern auf Augenhöhe '
          'sprechen und komplexe Themen einfach erklären</li>\n'
          ' \t<li>Empathie und Beziehungsaufbau: Du hörst zu, verstehst die '
          'echten Probleme und baust Vertrauen auf</li>\n'
          ' \t<li>Getting-Shit-Done-Mentalität: Du findest den einfachsten Weg '
          'zum Ziel — kein Overengineering, keine Ausreden</li>\n'
          ' \t<li>Problemlösungskompetenz: Du siehst Hindernisse als Aufgaben, '
          'nicht als Blocker</li>\n'
          '</ul>\n'
          '<strong>Technisches Verständnis:</strong>\n'
          '<ul>\n'
          ' \t<li>Du weißt, wie REST-APIs funktionieren, kannst API-Calls '
          'lesen und debuggen</li>\n'
          ' \t<li>Grundlegende Programmierkenntnisse</li>\n'
          ' \t<li>Erfahrung mit AI Tools: Du nutzt KI-Tools souverän im '
          'Arbeitsalltag und verstehst, wie sie Prozesse beschleunigen</li>\n'
          ' \t<li>Du wirst die Person, die unsere Plattform am besten versteht '
          '— und die Partner befähigt, die besten Agenten zu bauen</li>\n'
          '</ul>\n'
          'Sprachen: Deutsch und Englisch fließend\n'
          '\n'
          '<strong>Nice-to-haves:</strong>\n'
          '<ul>\n'
          ' \t<li>Erfahrung im Partner Success, Customer Success oder '
          'Consulting</li>\n'
          ' \t<li>Erfahrung mit SaaS-Plattformen oder im '
          'KI/Automatisierungs-Umfeld</li>\n'
          '</ul>\n'
          '<strong>Benefits</strong>\n'
          '<ul>\n'
          ' \t<li>Technologische Herausforderung: Arbeite an einem '
          'hochrelevanten Produkt und löse komplexe Probleme an der '
          'Schnittstelle von KI, Sprache und Cloud-Infrastruktur.</li>\n'
          ' \t<li>Attraktives Vergütungspaket: Wir bieten ein kompetitives '
          'Gehalt (50.000 € – 70.000 € p.a.) inklusive virtueller '
          'Mitarbeiterbeteiligung (VSOP).</li>\n'
          ' \t<li>Flexibilität: Anstelle von Stechuhren setzen wir auf '
          'Vertrauen, flexible Arbeitszeiten und Remote-Working.</li>\n'
          ' \t<li>Weiterentwicklung: Nutze dein jährliches Budget für '
          'Weiterbildungen, Konferenzen oder Kurse, um dich persönlich und '
          'fachlich weiterzuentwickeln.</li>\n'
          ' \t<li>Weitere Benefits: Urban Sports Club, JobRad, regelmäßige '
          'Teamevents und eine offene Feedbackkultur, in der wir gemeinsam '
          'lernen.</li>\n'
          '</ul>\n'
          '<strong>Was dich erwartet</strong>\n'
          '<ul>\n'
          ' \t<li>Echtes Startup: Wir sind 6 Leute — 3 Gründer, 2 Entwickler, '
          '1 Werkstudent. Du bist nicht irgendein Rädchen. Du baust diese '
          'Funktion auf.</li>\n'
          ' \t<li>Ownership vom ersten Tag: Du übernimmst Verantwortung, '
          'triffst Entscheidungen, gestaltest mit.</li>\n'
          ' \t<li>Direkter Impact: Jeder Partner, den du zum Fliegen bringst, '
          'verändert die Arbeitswelt für hunderte Unternehmen und tausende '
          'Menschen.</li>\n'
          '</ul>\n'
          'Schick uns eine kurze Nachricht, warum du diese Rolle willst, und '
          'was du in den ersten 30 Tagen tun würdest. Kein '
          'Anschreiben-Template, kein Roman — zeig uns, wie du denkst.',
  'url': 'https://findwork.dev/MdVLAZn/ai-partner-success-manager-mwd-lane-one-at-lane-one'},
"""