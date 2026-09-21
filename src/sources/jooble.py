import json
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


import http.client

load_dotenv()
host = 'jooble.org'
key = os.getenv("JOOBLE_API_KEY")

connection = http.client.HTTPConnection(host)
#request headers
headers = {"Content-type": "application/json"}
#json query
body = '{ "keywords": "python developer", "location": "germany"}'
connection.request('POST','/api/' + key, body, headers)
response = connection.getresponse()
print(response.status, response.reason)
data = json.loads(response.read().decode("utf-8"))
print(data)
pprint(data["jobs"])
exit()



"""
200 OK
{'totalCount': 20, 'jobs': [{'title': 'Praktikant Software Engineer - Web Backend (w/m/x)', 'location': 'Germany', 'snippet': '&nbsp;...dich?\r\n Du unterstützt bei der Weiterentwicklung unserer unternehmensinternen Webapplikationsplattform mit Angular im Frontend und <b>Python </b>im Backend. \r\n Gemeinsam mit unserem internationalen Team gestaltest du neue Features und trägst zur Optimierung bestehender Lösungen...&nbsp;', 'salary': '', 'source': 'ev.careers', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-3467250242468632040', 'company': 'BMW Group', 'updated': '2026-05-12T00:00:00.0000000', 'id': -3467250242468632040}, {'title': 'AI & ML Developer', 'location': 'Germany', 'snippet': '&nbsp;...Title: Independent Contractor – AI & ML <b>Developer </b>(Remote).\n About 20four7VA \r\n20four7VA is a global leader in providing virtual staffing...&nbsp;&nbsp;...AI automation tools. \r\n Technologies & Tools \r\n Programming: <b>Python,</b> Django, Flask \r\n AI/ML: OpenAI API, Hugging Face Transformers,...&nbsp;', 'salary': '', 'source': 'hubstaff.com', 'type': '', 'link': 'https://jooble.org/jdp/4099517956178006872', 'company': '20four7va', 'updated': '2026-05-24T17:09:51.2770000', 'id': 4099517956178006872}, {'title': 'Machine Learning Software Engineer', 'location': 'Germany', 'snippet': "&nbsp;...to build the software and infrastructure foundation for our ML <b>developments </b>\r\n We're Looking For Someone Who Has \r\n~ Experience with the...&nbsp;&nbsp;...using modern software practices \r\n~ Fluency in C++, or fluency in <b>Python </b>with intermediate experience in C++\r\n~ Deep understanding of...&nbsp;", 'salary': '$600 per month', 'source': 'ev.careers', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/7886566773197798235', 'company': 'Applied Intuition', 'updated': '2026-06-02T00:00:00.0000000', 'id': 7886566773197798235}, {'title': 'Senior Cloud Engineer', 'location': 'Germany', 'snippet': '&nbsp;...and monitoring  : monitor application and system performance, <b>develop </b>automated monitors, and troubleshoot production issues \r\n Disaster...&nbsp;&nbsp;...Scripting and programming  : strong skills in languages like <b>Python </b>and Bash \r\n DevOps  : experience with DevOps practices and tools...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-2976788512761650800', 'company': 'Crypto Finance', 'updated': '2026-05-18T00:00:00.0000000', 'id': -2976788512761650800}, {'title': 'Senior AI Platform Engineer (f/m/x)', 'location': 'Germany', 'snippet': '&nbsp;...in advancing the Data & AI transformation at the BMW Group by <b>developing </b>state-of-the-art AI platform solutions to train, run, and continuously...&nbsp;&nbsp;...AI and proficiency in modern programming languages such as <b>Python,</b> Node.js/Nest.js, Java/Kotlin, or Go, as well as API...&nbsp;', 'salary': '', 'source': 'ev.careers', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/852098258954709671', 'company': 'BMW Group', 'updated': '2026-05-17T00:00:00.0000000', 'id': 852098258954709671}, {'title': 'DevOps Engineer - Infrastructure', 'location': 'Germany', 'snippet': '&nbsp;...a highly scalable, secure, and automated platform that enables <b>developers </b>to deploy and run services reliably across multiple regions. You...&nbsp;&nbsp;...for automation and troubleshooting; experience with Golang or <b>Python </b>is a plus. \r\n WHAT WE OFFER: \r\n Competitive salary coupled with...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/6560329202587069335', 'company': 'Impossible Cloud', 'updated': '2026-05-15T00:00:00.0000000', 'id': 6560329202587069335}, {'title': 'MLOps Engineer - Implementation (f/m/x)', 'location': 'Germany', 'snippet': '&nbsp;...lineage, and approval gates from experiment to production. \r\n You <b>develop </b>and maintain model compilation and optimisation pipelines...&nbsp;&nbsp;...of hands-on ML infrastructure or MLOps experience. \r\n~ Strong <b>Python </b>skills; experience with hermetic build systems (e.g., Bazel) is...&nbsp;', 'salary': '', 'source': 'ev.careers', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-7867418511919640166', 'company': 'BMW Group', 'updated': '2026-05-17T00:00:00.0000000', 'id': -7867418511919640166}, {'title': 'Software Engineer (f/m/d)', 'location': 'Germany', 'snippet': ' At Upvest, we are on a  mission to make investing as easy as spending money  . Upvest empowers businesses to offer a wide range of investment products and the best experience in the field of capital market investment and retirement planning. Upvest’s Investment API is ...', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/1092807693719857472', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': 1092807693719857472}, {'title': 'Platform Engineer (Bare Metal) - Entry to Mid-level', 'location': 'Germany', 'snippet': ' ABOUT US:  Impossible Cloud is a fast-growing B2B cloud company headquartered in Hamburg, Germany. We have built a cloud object storage solution comparable to AWS S3, purpose-built and optimised for AI and compute workloads. Our commercial hyper-growth speaks for itself...', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/589731188326891508', 'company': 'Impossible Cloud', 'updated': '2026-05-15T00:00:00.0000000', 'id': 589731188326891508}, {'title': 'Trainee Software Engineer (f/m/d)', 'location': 'Germany', 'snippet': "&nbsp;...s both easy and effective. \r\n You'll be placed into a working Product Engineering tribe in Berlin, London or Tallinn, where you'll <b>develop </b>real-world engineering skills in direct partnership with senior members of Upvest's world-class engineering team. \r\n Throughout the...&nbsp;", 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-1933368956005446336', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': -1933368956005446336}, {'title': 'Senior Machine Learning Engineer/ Research Scientist', 'location': 'Germany', 'snippet': '&nbsp;...verified with World ID, and more new Orb verifications take place each week. World App is already among the most used wallets globally. <b>Developers </b>are integrating World ID to build safer online experiences and create spaces where real people can participate, earn, and be...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/3158532154918147539', 'company': 'World', 'updated': '2026-05-29T02:16:33.5300000', 'id': 3158532154918147539}, {'title': 'Platform Engineer - Distributed Systems / Decentralise Cloud', 'location': 'Germany', 'snippet': '&nbsp;...As an experienced (Sr / Staff / Principal) Platform Engineer, you will design and implement the technical architecture and enable <b>developers </b>to deploy services seamlessly on a scalable platform that supports the core components of the business. \r\n WHAT YOU WILL DO:...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/5198892179686365911', 'company': 'Impossible Cloud', 'updated': '2026-05-15T00:00:00.0000000', 'id': 5198892179686365911}, {'title': 'Senior Operations Manager für das Altersvorsorgedepot (f/m/d)', 'location': 'Germany', 'snippet': '&nbsp;...in der Prozessautomatisierung. \r\n Sicherer Umgang mit Datenvisualisierungstools sowie Programmier- und Skriptsprachen wie SQL und <b>Python.</b> \r\n Praktische Kenntnisse in Workflow-Automatisierung (z. B. n8n) sowie in der Anwendung moderner KI-Lösungen wie Claude oder vergleichbaren...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/7821241021317466234', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': 7821241021317466234}, {'title': 'IT Support Engineer', 'location': 'Germany', 'snippet': '&nbsp;...critical vulnerabilities, triage alerts to whitelist or escalate, and <b>develop </b>USB policies aligned with ISO procedures. \r\n Run the full...&nbsp;&nbsp;...(Grafana, Loki, or equivalent) and scripting ability in <b>Python </b>or Bash for troubleshooting and log parsing. \r\n~ Structured, precise...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-2945558638824401523', 'company': 'Impossible Cloud', 'updated': '2026-05-15T00:00:00.0000000', 'id': -2945558638824401523}, {'title': 'Senior TechOps & Automation Engineer (f/m/d)', 'location': 'Germany', 'snippet': '&nbsp;...Terraform is a plus, particularly in the context of infrastructure-as-code \r\n Knowledge of scripting languages or our tech stack (Golang, <b>Python,</b> Docker, k8s) is a plus, but not a requirement \r\n Excellent communication and task management skills \r\n Based in or willing to...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/4364847297300043160', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': 4364847297300043160}, {'title': 'Senior Liquidity Risk Manager (f/m/d)', 'location': 'Germany', 'snippet': '&nbsp;...Technical & Modeling Skills:  Hands-on experience building or operating quantitative risk models and cash flow forecasting tools (SQL/<b>Python </b>skills are a plus). \r\n Project & Cross-Functional Power:  Proven track record of driving complex projects across domains like IT...&nbsp;', 'salary': '€20k per year', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-1102055589309873122', 'company': 'Upvest', 'updated': '2026-06-03T06:59:03.8500000', 'id': -1102055589309873122}, {'title': 'Brokerage Operations Associate (f/m/d)', 'location': 'Germany', 'snippet': '&nbsp;...trading platforms, market data tools (like Bloomberg), and order management systems. Proficiency in data tools (e.g., Excel, SQL, or <b>Python)</b> is a strong plus. \r\n Communication:  Fluency in English is required; German is a strong plus. \r\n How we Upvest in you: \r\n Impact-...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-5635080695685171909', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': -5635080695685171909}, {'title': 'High Potential Program - AI and Automation', 'location': 'Germany', 'snippet': '&nbsp;...your journey to become a global ambassador of the company. Help <b>develop </b>and maintain our internal AI tool stack and automation strategy...&nbsp;&nbsp;...(n8n, Make, Zapier) - familiarity with prompt engineering, <b>Python </b>scripting, or API integrations is a plus \r\n A strong communicator...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Internship', 'link': 'https://jooble.org/jdp/-6269313989225921539', 'company': 'Impossible Cloud', 'updated': '2026-05-15T00:00:00.0000000', 'id': -6269313989225921539}, {'title': 'Senior Operations Manager for Altersvorsorgedepot (f/m/d)', 'location': 'Germany', 'snippet': '&nbsp;...part of a team \r\n It’s great if you have: \r\n Experience in data analysis and process automation using data visualization tools, SQL, <b>Python,</b> or similar \r\n Several years of relevant work experience with Riesterrente (former german pension product)\r\n How we Upvest in you:...&nbsp;', 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-2702612218058475409', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': -2702612218058475409}, {'title': 'Security Engineering Lead (m/f/d)', 'location': 'Germany', 'snippet': "&nbsp;...programme management. \r\n In a past life, you have shipped backend code in production, and you're comfortable in  Go  (preferred), <b>Python,</b> or another modern backend language. \r\n Regulatory fluency.  Working knowledge of  DORA, MaRisk, BAIT, ISO 27001 . You can change audit...&nbsp;", 'salary': '', 'source': 'decentrajobs.com', 'type': 'Full-time', 'link': 'https://jooble.org/jdp/-401619617937500235', 'company': 'Upvest', 'updated': '2026-05-15T00:00:00.0000000', 'id': -401619617937500235}]}
[{'company': 'BMW Group',
  'id': -3467250242468632040,
  'link': 'https://jooble.org/jdp/-3467250242468632040',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...dich?\r\n'
             ' Du unterstützt bei der Weiterentwicklung unserer '
             'unternehmensinternen Webapplikationsplattform mit Angular im '
             'Frontend und <b>Python </b>im Backend. \r\n'
             ' Gemeinsam mit unserem internationalen Team gestaltest du neue '
             'Features und trägst zur Optimierung bestehender '
             'Lösungen...&nbsp;',
  'source': 'ev.careers',
  'title': 'Praktikant Software Engineer - Web Backend (w/m/x)',
  'type': 'Full-time',
  'updated': '2026-05-12T00:00:00.0000000'},
 {'company': '20four7va',
  'id': 4099517956178006872,
  'link': 'https://jooble.org/jdp/4099517956178006872',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...Title: Independent Contractor – AI & ML <b>Developer '
             '</b>(Remote).\n'
             ' About 20four7VA \r\n'
             '20four7VA is a global leader in providing virtual '
             'staffing...&nbsp;&nbsp;...AI automation tools. \r\n'
             ' Technologies & Tools \r\n'
             ' Programming: <b>Python,</b> Django, Flask \r\n'
             ' AI/ML: OpenAI API, Hugging Face Transformers,...&nbsp;',
  'source': 'hubstaff.com',
  'title': 'AI & ML Developer',
  'type': '',
  'updated': '2026-05-24T17:09:51.2770000'},
 {'company': 'Applied Intuition',
  'id': 7886566773197798235,
  'link': 'https://jooble.org/jdp/7886566773197798235',
  'location': 'Germany',
  'salary': '$600 per month',
  'snippet': '&nbsp;...to build the software and infrastructure foundation for '
             'our ML <b>developments </b>\r\n'
             " We're Looking For Someone Who Has \r\n"
             '~ Experience with the...&nbsp;&nbsp;...using modern software '
             'practices \r\n'
             '~ Fluency in C++, or fluency in <b>Python </b>with intermediate '
             'experience in C++\r\n'
             '~ Deep understanding of...&nbsp;',
  'source': 'ev.careers',
  'title': 'Machine Learning Software Engineer',
  'type': 'Full-time',
  'updated': '2026-06-02T00:00:00.0000000'},
 {'company': 'Crypto Finance',
  'id': -2976788512761650800,
  'link': 'https://jooble.org/jdp/-2976788512761650800',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...and monitoring  : monitor application and system '
             'performance, <b>develop </b>automated monitors, and troubleshoot '
             'production issues \r\n'
             ' Disaster...&nbsp;&nbsp;...Scripting and programming  : strong '
             'skills in languages like <b>Python </b>and Bash \r\n'
             ' DevOps  : experience with DevOps practices and tools...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Senior Cloud Engineer',
  'type': 'Full-time',
  'updated': '2026-05-18T00:00:00.0000000'},
 {'company': 'BMW Group',
  'id': 852098258954709671,
  'link': 'https://jooble.org/jdp/852098258954709671',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...in advancing the Data & AI transformation at the BMW '
             'Group by <b>developing </b>state-of-the-art AI platform '
             'solutions to train, run, and continuously...&nbsp;&nbsp;...AI '
             'and proficiency in modern programming languages such as '
             '<b>Python,</b> Node.js/Nest.js, Java/Kotlin, or Go, as well as '
             'API...&nbsp;',
  'source': 'ev.careers',
  'title': 'Senior AI Platform Engineer (f/m/x)',
  'type': 'Full-time',
  'updated': '2026-05-17T00:00:00.0000000'},
 {'company': 'Impossible Cloud',
  'id': 6560329202587069335,
  'link': 'https://jooble.org/jdp/6560329202587069335',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...a highly scalable, secure, and automated platform that '
             'enables <b>developers </b>to deploy and run services reliably '
             'across multiple regions. You...&nbsp;&nbsp;...for automation and '
             'troubleshooting; experience with Golang or <b>Python </b>is a '
             'plus. \r\n'
             ' WHAT WE OFFER: \r\n'
             ' Competitive salary coupled with...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'DevOps Engineer - Infrastructure',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'BMW Group',
  'id': -7867418511919640166,
  'link': 'https://jooble.org/jdp/-7867418511919640166',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...lineage, and approval gates from experiment to '
             'production. \r\n'
             ' You <b>develop </b>and maintain model compilation and '
             'optimisation pipelines...&nbsp;&nbsp;...of hands-on ML '
             'infrastructure or MLOps experience. \r\n'
             '~ Strong <b>Python </b>skills; experience with hermetic build '
             'systems (e.g., Bazel) is...&nbsp;',
  'source': 'ev.careers',
  'title': 'MLOps Engineer - Implementation (f/m/x)',
  'type': 'Full-time',
  'updated': '2026-05-17T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': 1092807693719857472,
  'link': 'https://jooble.org/jdp/1092807693719857472',
  'location': 'Germany',
  'salary': '',
  'snippet': ' At Upvest, we are on a  mission to make investing as easy as '
             'spending money  . Upvest empowers businesses to offer a wide '
             'range of investment products and the best experience in the '
             'field of capital market investment and retirement planning. '
             'Upvest’s Investment API is ...',
  'source': 'decentrajobs.com',
  'title': 'Software Engineer (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Impossible Cloud',
  'id': 589731188326891508,
  'link': 'https://jooble.org/jdp/589731188326891508',
  'location': 'Germany',
  'salary': '',
  'snippet': ' ABOUT US:  Impossible Cloud is a fast-growing B2B cloud company '
             'headquartered in Hamburg, Germany. We have built a cloud object '
             'storage solution comparable to AWS S3, purpose-built and '
             'optimised for AI and compute workloads. Our commercial '
             'hyper-growth speaks for itself...',
  'source': 'decentrajobs.com',
  'title': 'Platform Engineer (Bare Metal) - Entry to Mid-level',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': -1933368956005446336,
  'link': 'https://jooble.org/jdp/-1933368956005446336',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...s both easy and effective. \r\n'
             " You'll be placed into a working Product Engineering tribe in "
             "Berlin, London or Tallinn, where you'll <b>develop "
             '</b>real-world engineering skills in direct partnership with '
             "senior members of Upvest's world-class engineering team. \r\n"
             ' Throughout the...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Trainee Software Engineer (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'World',
  'id': 3158532154918147539,
  'link': 'https://jooble.org/jdp/3158532154918147539',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...verified with World ID, and more new Orb verifications '
             'take place each week. World App is already among the most used '
             'wallets globally. <b>Developers </b>are integrating World ID to '
             'build safer online experiences and create spaces where real '
             'people can participate, earn, and be...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Senior Machine Learning Engineer/ Research Scientist',
  'type': 'Full-time',
  'updated': '2026-05-29T02:16:33.5300000'},
 {'company': 'Impossible Cloud',
  'id': 5198892179686365911,
  'link': 'https://jooble.org/jdp/5198892179686365911',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...As an experienced (Sr / Staff / Principal) Platform '
             'Engineer, you will design and implement the technical '
             'architecture and enable <b>developers </b>to deploy services '
             'seamlessly on a scalable platform that supports the core '
             'components of the business. \r\n'
             ' WHAT YOU WILL DO:...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Platform Engineer - Distributed Systems / Decentralise Cloud',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': 7821241021317466234,
  'link': 'https://jooble.org/jdp/7821241021317466234',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...in der Prozessautomatisierung. \r\n'
             ' Sicherer Umgang mit Datenvisualisierungstools sowie '
             'Programmier- und Skriptsprachen wie SQL und <b>Python.</b> \r\n'
             ' Praktische Kenntnisse in Workflow-Automatisierung (z. B. n8n) '
             'sowie in der Anwendung moderner KI-Lösungen wie Claude oder '
             'vergleichbaren...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Senior Operations Manager für das Altersvorsorgedepot (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Impossible Cloud',
  'id': -2945558638824401523,
  'link': 'https://jooble.org/jdp/-2945558638824401523',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...critical vulnerabilities, triage alerts to whitelist or '
             'escalate, and <b>develop </b>USB policies aligned with ISO '
             'procedures. \r\n'
             ' Run the full...&nbsp;&nbsp;...(Grafana, Loki, or equivalent) '
             'and scripting ability in <b>Python </b>or Bash for '
             'troubleshooting and log parsing. \r\n'
             '~ Structured, precise...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'IT Support Engineer',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': 4364847297300043160,
  'link': 'https://jooble.org/jdp/4364847297300043160',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...Terraform is a plus, particularly in the context of '
             'infrastructure-as-code \r\n'
             ' Knowledge of scripting languages or our tech stack (Golang, '
             '<b>Python,</b> Docker, k8s) is a plus, but not a requirement \r\n'
             ' Excellent communication and task management skills \r\n'
             ' Based in or willing to...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Senior TechOps & Automation Engineer (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': -1102055589309873122,
  'link': 'https://jooble.org/jdp/-1102055589309873122',
  'location': 'Germany',
  'salary': '€20k per year',
  'snippet': '&nbsp;...Technical & Modeling Skills:  Hands-on experience '
             'building or operating quantitative risk models and cash flow '
             'forecasting tools (SQL/<b>Python </b>skills are a plus). \r\n'
             ' Project & Cross-Functional Power:  Proven track record of '
             'driving complex projects across domains like IT...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Senior Liquidity Risk Manager (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-06-03T06:59:03.8500000'},
 {'company': 'Upvest',
  'id': -5635080695685171909,
  'link': 'https://jooble.org/jdp/-5635080695685171909',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...trading platforms, market data tools (like Bloomberg), '
             'and order management systems. Proficiency in data tools (e.g., '
             'Excel, SQL, or <b>Python)</b> is a strong plus. \r\n'
             ' Communication:  Fluency in English is required; German is a '
             'strong plus. \r\n'
             ' How we Upvest in you: \r\n'
             ' Impact-...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Brokerage Operations Associate (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Impossible Cloud',
  'id': -6269313989225921539,
  'link': 'https://jooble.org/jdp/-6269313989225921539',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...your journey to become a global ambassador of the '
             'company. Help <b>develop </b>and maintain our internal AI tool '
             'stack and automation strategy...&nbsp;&nbsp;...(n8n, Make, '
             'Zapier) - familiarity with prompt engineering, <b>Python '
             '</b>scripting, or API integrations is a plus \r\n'
             ' A strong communicator...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'High Potential Program - AI and Automation',
  'type': 'Internship',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': -2702612218058475409,
  'link': 'https://jooble.org/jdp/-2702612218058475409',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...part of a team \r\n'
             ' It’s great if you have: \r\n'
             ' Experience in data analysis and process automation using data '
             'visualization tools, SQL, <b>Python,</b> or similar \r\n'
             ' Several years of relevant work experience with Riesterrente '
             '(former german pension product)\r\n'
             ' How we Upvest in you:...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Senior Operations Manager for Altersvorsorgedepot (f/m/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'},
 {'company': 'Upvest',
  'id': -401619617937500235,
  'link': 'https://jooble.org/jdp/-401619617937500235',
  'location': 'Germany',
  'salary': '',
  'snippet': '&nbsp;...programme management. \r\n'
             ' In a past life, you have shipped backend code in production, '
             "and you're comfortable in  Go  (preferred), <b>Python,</b> or "
             'another modern backend language. \r\n'
             ' Regulatory fluency.  Working knowledge of  DORA, MaRisk, BAIT, '
             'ISO 27001 . You can change audit...&nbsp;',
  'source': 'decentrajobs.com',
  'title': 'Security Engineering Lead (m/f/d)',
  'type': 'Full-time',
  'updated': '2026-05-15T00:00:00.0000000'}]
"""