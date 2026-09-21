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
    "intern",
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


def clean_search_keywords_and_job_title(text: str) -> str:
    text = text.lower()
    for w in NOISE_WORDS:
        text = text.replace(w, " ")
    # remove special characters like (m/w/d)
    text = re.sub(r"\(.*?m.*?w.*?d.*?\)", " ", text)
    # remove leftover brackets and symbols
    text = re.sub(r"[\(\)\|\-_/,:;]", " ", text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


STUDENT_LEVEL_MARKERS = [
    "werkstudent", "working student", "praktikum", "praktikant", "praktikantin",
    "intern", "internship", "hiwi", "wissenschaftliche hilfskraft",
    "student", "studentische hilfskraft", "trainee", "ausbildung", "azubi",
    "dual student", "duales studium",
]

SENIOR_LEVEL_MARKERS = [
    "senior", "sr.", "lead", "principal", "staff", "head of", "manager",
    "director", "vp", "vice president", "chief", "teamlead", "team lead",
    "gruppenleiter", "abteilungsleiter", "expert",
]


def get_employment_level(text: str) -> str:
    """
    Classifies raw text as 'student' (werkstudent/praktikum/intern-level),
    'senior' (lead/manager/director-level), or 'unspecified'.

    Must be called on text BEFORE clean_search_keywords_and_job_title() strips
    these same markers out for topic embedding. That stripping is intentional
    (it lets "Werkstudent KI" and "Working Student AI" embed as the same
    topic), but it also destroys the employment-level signal -- which is why
    level compatibility needs its own check instead of relying on embedding
    similarity alone (a query like "Werkstudent AI" is topically close to a
    "Senior AI Engineer" title, even though the level is wrong).
    """
    lowered = text.lower()
    is_student = any(marker in lowered for marker in STUDENT_LEVEL_MARKERS)
    is_senior = any(marker in lowered for marker in SENIOR_LEVEL_MARKERS)
    if is_student and not is_senior:
        return "student"
    if is_senior and not is_student:
        return "senior"
    return "unspecified"


def is_employment_level_compatible(query_text: str, title_text: str) -> bool:
    """
    Conflict-only gate: rejects only a clear, opposite-level mismatch (e.g.
    query "Werkstudent AI" vs. title "Senior AI Engineer"). A query or title
    with no level marker at all -- the common case, since German postings
    often state level only in the query -- always passes.

    This is deliberately independent of topic (AI, backend, data science,
    ...): it reacts to the same two marker lists regardless of subject, so it
    generalizes to any query/title pair sharing the same student-vs-senior
    pattern instead of hardcoding the one example that motivated it.
    """
    query_level = get_employment_level(query_text)
    title_level = get_employment_level(title_text)
    if query_level == "unspecified" or title_level == "unspecified":
        return True
    return query_level == title_level


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
    """
    Returns (index, score) of the query keyword embedding closest to
    job_title_emb. Returning the index (not just the score) lets callers look
    up the winning keyword's original text -- needed for
    is_employment_level_compatible(), which the score alone can't drive.
    """
    best_index = -1
    max_sim = float("-inf")  # not -sys.float_info.max: that's a float64 finite value that overflows when cast against the float32 embeddings, which numpy warns about on every comparison
    for index, query_emb in enumerate(keywords_embeddings):
        current_sim = compute_cosine_similarity(query_emb, job_title_emb)
        if current_sim > max_sim:
            max_sim = current_sim
            best_index = index
    return best_index, max_sim


def normalize_job_url(url: str) -> str:
    """
    Merge-time dedup key: strips tracking params and URL fragments so the same
    posting reached via different campaign links collapses to one entry.
    Deliberately a small subset of the fuller normalization described in
    db-schema_&_dedup.txt (which also canonicalizes company/location) -- that
    fuller version needs the database this project doesn't have yet.
    """
    tracking_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
    parsed = urlparse(url)
    filtered_query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in tracking_params]
    normalized = parsed._replace(query=urlencode(filtered_query), fragment="")
    return urlunparse(normalized).rstrip("/").lower()


def load_embedding_model_and_keyword_embeddings():
    """
    DRYs up the load-model-then-embed-keywords boilerplate needed by main.py
    and every scraper's standalone __main__ block.
    """
    model = SentenceTransformer(scraper_common_config["embedding_match_config"]["sentence_embedding_model"])
    keyword_embeddings = compute_search_keywords_embeddings(model, scraper_common_config["search_keywords"])
    return model, keyword_embeddings


def get_emb_match_job_dict(title, url, title_keyword_emd_match_score, job_posting_platform, rejection_reason=None):
    output = {
        "title": title,
        "url": url,
        "title_keyword_emd_match_score": title_keyword_emd_match_score,
        "job_posting_platform": job_posting_platform,
        "rejection_reason": rejection_reason,  # None (accepted) | "below_threshold" | "employment_level_mismatch" | "title_extraction_failed"
    }
    return output
