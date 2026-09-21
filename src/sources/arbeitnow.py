from pprint import pprint
import requests
from loguru import logger

from config.common_config import config
from sources.arbeitsamt import Arbeitsamt
from sources.adzuna import Adzuna
from utils.validate_config import ValidateConfig
from sources.findwork import FindWork
"""
ARBEITSAMT_BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",  # required API key header
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0"
}
params = {
    "was": "Werkstudent IT Support",  # keyword search, e.g., job title
    "wo": "Mannheim",              # location
    "page": 1,
    "size": 250,                   # number of results
    "umkreis": 100
}

response = requests.get(ARBEITSAMT_BASE_URL, headers=HEADERS, params=params)

if response.ok:
    data = response.json()
    # ‘stellenangebote’ key holds the job list
    jobs = data.get("stellenangebote", [])
    pprint(jobs)
    print(len(jobs))
else:
    print("Error:", response.status_code, response.text)
"""


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
ARBEITSNOW_BASE_URL = "https://arbeitnow.com/api/job-board-api"
headers = {}
params = {
    "location": "Mannheim"
}

response = requests.get(url=ARBEITSNOW_BASE_URL, headers=headers, params=params)
print("="*100)
print(response.status_code)
print(len(response.text))
pprint(response.json())
"""

"""
url = "https://findwork.dev/api/jobs/"
headers = {
    'Authorization': 'Token XYZ', 
    'Accept': "application/json",
    "User-Agent": "Mozilla/5.0",
}
params = {
    "location": "berlin",
    "search": "werkstudent",
    #"sort_by": "relevance"
}
response = requests.get(url, headers=headers, params=params)
print(response.status_code)
print(response.url)
pprint(response.json()["results"])
exit()
"""

cfg = None
try:
    cfg = ValidateConfig(**config)
    cfg = dict(cfg)
except Exception:
    logger.exception("Config validation failed")
    exit(1)

ad = FindWork(cfg)
ad.execute_query()
