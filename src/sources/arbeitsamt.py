import os
import re
import requests
import base64
import pandas as pd
from box import Box
from pprint import pprint
from loguru import logger
from config.path_config import RAW_FOLDER_PATH, PROCESSED_FOLDER_PATH, DUPLICATES_FOLDER_PATH
from utils.util import generate_deduplication_key


class Arbeitsamt:
    def __init__(self, common_config:dict):
        self.common_config = common_config
        self.request_params = None
        self.iter_params = None
        self.result = None


    def execute_query(self):
        self._construct_request_and_iter_params()
        self._make_request()
        self._save_csv_file()


    def _construct_request_and_iter_params(self):
        common_config = Box(self.common_config)
        request_params = {
            "was": None, # It is iteration variable, it will be set during making request
            "page": common_config.page_number,
            "size": common_config.results_per_page
        }
        if not common_config.remote:
            request_params["wo"] = None # It is iteration variable, it will be set during making request
            request_params["umkreis"] = common_config.distance
        if common_config.full_time:
            request_params["arbeitszeit"] = "vz"
        elif common_config.part_time:
            request_params["arbeitszeit"] = "tz"
        self.request_params = request_params
        if len(common_config.country) > 1 or common_config.country[0] != "germany":
            raise ValueError("Arbeitsamt API only supports 'country'= ['germany']. "
                             "Either in common_config set 'use_arbeitsamt_api' = False or provide only one country 'germany' in country list.")
        iter_params = {
            "cities": list(common_config.city),
            "search_terms": list(common_config.search_keywords)
        }
        self.iter_params = iter_params
        logger.info(f"Arbeitsamt request params are : {request_params}")
        logger.info(f"Arbeitsamt iter params are : {iter_params}")


    def _make_request(self):
        request_url = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
        request_params = self.request_params
        cities = self.iter_params["cities"]
        search_terms = self.iter_params["search_terms"]
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
                    request_params["wo"] = city
                    request_params["was"] = term
                    response = requests.get(url=request_url, params=request_params, headers=self._get_arbeitsamt_request_headers())
                    if response.status_code != 200:
                        logger.error(f"Status: {response.status_code}")
                        logger.error(f"Response: {response.text}")
                        logger.error(f"URL: {response.url}")
                        logger.error(f"Params: {request_params}")
                    else:
                        output = response.json()
                        output = output.get("stellenangebote", [])
                        for item in output:
                            job_description = self._get_normalized_job_description(item["refnr"])
                            title = item["titel"].strip().lower()
                            company = item["arbeitgeber"].strip().lower()
                            location = item["arbeitsort"]["ort"].strip().lower()
                            dedup_key = generate_deduplication_key(title, company, location)
                            area = "germany, " + item["arbeitsort"]["region"].strip().lower() + ", " + location
                            result["area"].append(area)
                            result["company"].append(company)
                            result["title"].append(title)
                            result["source"].append("arbeitsamt")
                            result["redirect_url"].append(item["externeUrl"].strip() if "externeUrl" in item else None)
                            result["description"].append(job_description)
                            result["deduplication_key"].append(dedup_key)
                else:
                    raise ValueError("Remote job search for arbeitsamt is not implemented yet!")
        self.result = pd.DataFrame(result)


    def _save_csv_file(self):
        file_path = os.path.join(RAW_FOLDER_PATH, "arbeitsamt_" + self.common_config["output_filename"])
        self.result.to_csv(file_path, encoding="utf-8", index=False)
        logger.info(f"Raw output data with {len(self.result)} entries is stored at location {file_path}")


    def _get_normalized_job_description(self, ref_id):
        base64_bytes = base64.b64encode(ref_id.encode("utf-8"))
        base64_string = base64_bytes.decode("utf-8")
        description_url = f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{base64_string}"
        response = requests.get(url=description_url, headers=self._get_arbeitsamt_request_headers())
        if response.status_code != 200:
            logger.error(f"Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            logger.error(f"URL: {response.url}")
            return None
        else:
            raw = response.json()["stellenangebotsBeschreibung"]
            description = re.sub(r"\s+", " ", raw).strip().lower()
            description = description[0:490] # Truncating to 490 chars because adzuna doesn't provide complete description. If not truncated to 490 chars fuzzy matching will not work as intended.
            return description



    @staticmethod
    def _get_arbeitsamt_request_headers():
        """
        Gives headers to pass in the API request
        :return:
        """
        headers = {
            "X-API-Key": "jobboerse-jobsuche",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        return headers



"""
# EXAMPLE FROM stellenangebote LIST:

{'aktuelleVeroeffentlichungsdatum': '2026-03-13',
  'arbeitgeber': 'everience Germany GmbH',
  'arbeitsort': {'entfernung': '70',
                 'koordinaten': {'lat': 50.1113194, 'lon': 8.6818977},
                 'land': 'Deutschland',
                 'ort': 'Frankfurt am Main',
                 'plz': '60311',
                 'region': 'Hessen',
                 'strasse': 'null'},
  'beruf': 'Informatiker/in',
  'eintrittsdatum': '2026-03-16',
  'externeUrl': 'https://www.jobexport.de/job/5093758.html?exp=81&cid=d823b609-2612-4a60-8bab-1df2d4844c89',
  'modifikationsTimestamp': '2026-03-13T14:11:33.571',
  'refnr': '13635-d823b609_JB5093758-S',
  'titel': 'Werkstudent IT-Support (m/w/d) - Frankfurt am Main'},
"""

"""
EXAMPLE FROM job description QUERY (returns only one dictionary with 30 keys)
{'aenderungsdatum': '2026-02-27T20:56:26.762',
 'allianzpartnerName': 'Robert Bosch GmbH',
 'allianzpartnerUrl': 'www.bosch.de',
 'arbeitgeberKundennummerHash': 'iZ1qVUSwSUBsMgarpsprvZYrvnsj_BfNcQt_jaCgINA=',
 'arbeitszeitSchichtNachtWochenende': False,
 'arbeitszeitTeilzeitAbend': False,
 'arbeitszeitTeilzeitFlexibel': False,
 'arbeitszeitTeilzeitNachmittag': False,
 'arbeitszeitTeilzeitVormittag': False,
 'arbeitszeitVollzeit': True,
 'chiffrenummer': 'REF274705O',
 'datumErsteVeroeffentlichung': '2026-01-09',
 'eintrittszeitraum': {'von': '2026-02-27'},
 'firma': 'Robert Bosch GmbH',
 'geforderterBildungsabschluss': 'NICHT_RELEVANT',
 'hauptberuf': 'Machine Learning Engineer',
 'istArbeitnehmerUeberlassung': False,
 'istBehinderungGefordert': False,
 'istBetreut': True,
 'istGeringfuegigeBeschaeftigung': False,
 'istPrivateArbeitsvermittlung': False,
 'quereinstiegGeeignet': False,
 'referenznummer': '15986-744000102270615-1-S',
 'stellenangebotsBeschreibung': '\n'
                                '            Willkommen bei Bosch\n'
                                '            Bei Bosch gestalten wir Zukunft '
                                'mit hochwertigen Technologien und '
                                'Dienstleistungen, die Begeisterung wecken und '
                                'das Leben der Menschen verbessern. Unser '
                                'Versprechen an unsere Mitarbeiterinnen und '
                                'Mitarbeiter steht dabei felsenfest: Wir '
                                'wachsen gemeinsam, haben Freude an unserer '
                                'Arbeit und inspirieren uns gegenseitig. '
                                'Willkommen bei Bosch.\n'
                                'Die Robert Bosch GmbH freut sich auf eine '
                                'Bewerbung!\n'
                                '            \n'
                                '            Stellenbeschreibung\n'
                                '            - Während Ihres Praktikums '
                                'entwickeln Sie ein Tool zur automatisierten '
                                'Erstellung technischer Dokumente für '
                                'Entwicklungsfahrzeuge.\n'
                                '- Die Integration von Microsoft-Technologien '
                                'wie Power Automate für '
                                'Workflow-Automatisierung, SharePoint für '
                                'Dokumentenverwaltung, Microsoft Copilot '
                                'Studio für KI-gestützte Textgenerierung '
                                'gehören zu Ihrem Aufgabengebiet.\n'
                                '- Sie integrieren führende KI-Dienste wie '
                                'Microsoft Copilot oder unsere internen '
                                'KI-Lösungen, um die Erstellung und '
                                'Bearbeitung von Inhalten maßgeblich zu '
                                'beschleunigen und zu verbessern.\n'
                                '- Für eine effiziente und konsistente '
                                'Dokumentenerstellung entwickeln und '
                                'implementieren Sie intelligente '
                                'Word-Vorlagen, die sich automatisch mit '
                                'relevanten Daten befüllen lassen.\n'
                                '- Sie gewährleisten die Compliance und '
                                'Datenintegrität in MS Office.\n'
                                '\n'
                                '            Qualifikationen\n'
                                '            - Ausbildung: Studium im Bereich '
                                'Informatik, Wirtschaftsinformatik, Data '
                                'Science oder vergleichbar\n'
                                '- Erfahrungen und Know-how: mit Power '
                                'Automate oder vergleichbare Workflow-Tools; '
                                'Programmierkenntnisse (z. B. Python, C#, oder '
                                'Low-Code-Plattformen); sicher im Umgang mit '
                                'MS Office (SharePoint, Teams)\n'
                                '- Persönlichkeit und Arbeitsweise: '
                                'strukturierte Arbeitsweise und Fähigkeit, '
                                'sich in neue Themen einzuarbeiten\n'
                                '- Arbeitsalltag: Ihre Präsenz vor Ort ist '
                                'erforderlich\n'
                                '- Begeisterung: Interesse an KI-Technologien '
                                'und deren praktischer Anwendung\n'
                                '- Sprachen: sehr gutes Deutsch und gutes '
                                'Englisch\n'
                                '\n'
                                '            Zusätzliche Informationen\n'
                                '            Beginn: nach Absprache\n'
                                ' Dauer: 6 Monate – 10h/Woche (Verlängerung '
                                'nach Absprache möglich)\n'
                                'Voraussetzung für die Werkstudententätigkeit '
                                'ist die Immatrikulation an einer Hochschule. '
                                'Bitte fügen Sie Ihrer Bewerbung Ihren '
                                'Lebenslauf, Ihren aktuellen Notenspiegel, '
                                'eine aktuelle Immatrikulationsbescheinigung '
                                'sowie ggf. eine gültige Arbeits- und '
                                'Aufenthaltserlaubnis bei.\n'
                                'Vielfalt und Inklusion sind für uns keine '
                                'Trends, sondern fest verankert in unserer '
                                'Unternehmenskultur. Daher freuen wir uns über '
                                'alle Bewerbungen: unabhängig von Geschlecht, '
                                'Alter, Behinderung, Religion, ethnischer '
                                'Herkunft oder sexueller Identität.\n'
                                'Work #LikeABosch beginnt hier: Jetzt '
                                'bewerben!\n'
                                '\n'
                                '            \n'
                                '            \n'
                                '\n'
                                '            \n'
                                '            \n'
                                '        ',
 'stellenangebotsTitel': 'Werkstudent in der Entwicklung eines KI-gestützten '
                         'Tools zur Erstellung technischer Dokumente (m/...',
 'stellenangebotsart': 'PRAKTIKUM_TRAINEE',
 'stellenlokationen': [{'adresse': {'land': 'DEUTSCHLAND',
                                    'ort': 'Abstatt',
                                    'plz': '74232',
                                    'region': 'BADEN_WUERTTEMBERG'},
                        'breite': 49.0719876,
                        'laenge': 9.2987458}],
 'verguetungsangabe': 'KEINE_ANGABEN',
 'veroeffentlichungszeitraum': {'von': '2026-01-09'},
 'vertragsdauer': 'KEINE_ANGABE'}
"""