import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import numpy as np
from sentence_transformers import SentenceTransformer
from config.scraper_common_config import scraper_common_config

def generate_deduplication_key(title:str, company:str, location:str):
    normalized = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}"
    return hashlib.md5(normalized.encode()).hexdigest()


NOISE_WORDS = [
    # employment type
    "werkstudent",
    "working student",
    "praktikum",
    "praktikant",
    "praktikantin",
    "intern",
    "internship",
    "hiwi",
    "student",
    "studentenjob",
    "research assistant",
    "wissenschaftliche hilfskraft",
    # gender / legal
    "m/w/d",
    "w/m/d",
    "m/f/d",
    "f/m/x",
    "m/w/x",
    "w/m/x",
    "m/f/x",
    "f/m/d",
    "all genders",
    "gn",
    # contract / meta
    "full time",
    "part time",
    "teilzeit",
    "vollzeit",
    "remote",
    "hybrid",
    "onsite",
    "home office",
    "befristet",
    "unbefristet",
    # job board noise
    "job id",
    "job-id",
    "ref",
]


NOISE_WORDS_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(NOISE_WORDS, key=len, reverse=True)) + r")\b"
)
GENDER_SUFFIX_PATTERN = re.compile(r"(?<=[a-zäöüß])[/*:_·]in(?:nen)?\b")  # praktikant/in, werkstudent:in, entwickler*innen


def clean_search_keywords_and_job_title(text: str) -> str:
    text = GENDER_SUFFIX_PATTERN.sub("", text.lower())
    text = NOISE_WORDS_PATTERN.sub(" ", text)
    text = re.sub(r"[\(\)\[\]\|\-_/,:;]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


BLOCK_PAGE_TITLE_PATTERN = re.compile(
    r"just a moment|attention required|access denied|zugriff verweigert|verify you are human|are you a human"
    r"|security check|sicherheitsüberprüfung|captcha|blocked|unusual traffic|additional verification"
    r"|zusätzliche verifizierung|request rejected|403 forbidden|too many requests|429"
)
BLOCK_PAGE_TEXT_PATTERN = re.compile(
    r"verify (?:that )?you are (?:a )?human|are you a robot|i'm not a robot|ich bin kein roboter|unusual traffic"
    r"|ungewöhnlichen datenverkehr|complete the security check|access to this page has been denied|access denied"
    r"|zugriff verweigert|too many requests|zu viele anfragen|prove you are human|additional verification required"
)
BLOCK_PAGE_URL_PATTERN = re.compile(r"captcha|/challenge|/blocked|access-denied|/sorry/|/distil_r_captcha")
BLOCK_PAGE_SELECTORS = [
    "#challenge-running",
    "#challenge-form",
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='hcaptcha.com']",
    "iframe[src*='geo.captcha-delivery.com']",
    "#px-captcha",
    "form[action*='captcha']",
]


def detect_block_page(page) -> str | None:
    try:
        title = page.title()
        url = page.url
        if match := BLOCK_PAGE_TITLE_PATTERN.search(title.lower()):
            return f"page title '{title}' matches '{match.group(0)}'"
        if match := BLOCK_PAGE_URL_PATTERN.search(url.lower()):
            return f"page URL {url} matches '{match.group(0)}'"
        for selector in BLOCK_PAGE_SELECTORS:
            if page.locator(selector).count():
                return f"challenge element '{selector}' is on the page (title '{title}')"
        text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 20000) : ''")
        if match := BLOCK_PAGE_TEXT_PATTERN.search(text.lower()):
            return f"page text contains '{match.group(0)}' (title '{title}')"
    except Exception:
        return None
    return None


def compute_search_keywords_embeddings(model, keywords:list[str]):
    output =[]
    for kw in keywords:
        emb = compute_embedding(model, kw)
        output.append(emb)
    return np.array(output)


def compute_embedding(model, job_title:str):
    cleaned = clean_search_keywords_and_job_title(job_title)
    emb = model.encode(cleaned, normalize_embeddings=True)
    return emb


def compute_cosine_similarity(query_emb, job_embs):
    # cosine similarity = dot product (because normalized)
    return job_embs @ query_emb


def find_best_matching_keyword(keywords_embeddings, job_title_emb) -> tuple[int, float]:
    best_index = -1
    max_sim = float("-inf")
    for index, query_emb in enumerate(keywords_embeddings):
        current_sim = compute_cosine_similarity(query_emb, job_title_emb)
        if current_sim > max_sim:
            max_sim = current_sim
            best_index = index
    return best_index, max_sim


def normalize_job_url(url: str) -> str:
    tracking_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
    parsed = urlparse(url)
    filtered_query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in tracking_params]
    normalized = parsed._replace(query=urlencode(filtered_query), fragment="")
    return urlunparse(normalized).rstrip("/").lower()


def load_embedding_model_and_keyword_embeddings():
    model = SentenceTransformer(scraper_common_config["embedding_match_config"]["sentence_embedding_model"])
    keyword_embeddings = compute_search_keywords_embeddings(model, scraper_common_config["match_keywords"])
    return model, keyword_embeddings


def get_emb_match_job_dict(title, url, title_keyword_emd_match_score, job_posting_platform, rejection_reason=None):
    output = {
        "title": title,
        "url": url,
        "title_keyword_emd_match_score": title_keyword_emd_match_score,
        "job_posting_platform": job_posting_platform,
        "rejection_reason": rejection_reason,  # None (accepted) | "below_threshold" | "title_extraction_failed"
    }
    return output
