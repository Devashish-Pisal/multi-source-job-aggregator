import re
import unicodedata

from utils.util import GENDER_NOISE_WORDS, GENDER_SUFFIX_PATTERN, INVISIBLE_CHARS_PATTERN, words_regex

# (m/w/d), (w|m|d), (mwd), (f/m/x) and the gender words
GENDER_TAG_PATTERN = re.compile(r"\(\s*(?:[mwfdx]\s*[/|,*.-]?\s*){2,4}\)" + "|" + words_regex(GENDER_NOISE_WORDS))
LEGAL_FORMS_PATTERN = re.compile(
    r"\b(?:gmbh|mbh|ag|se|kgaa|kg|ohg|gbr|ug|haftungsbeschränkt|e v|ev|ltd|limited|inc|llc|plc|corp|co|deutschland|germany|group|gruppe|holding)\b"
)
NO_CITY = ["bundesweit", "deutschlandweit", "deutschland", "germany", "remote", "home office", "homeoffice", "home-office", "mobile office", "mobiles arbeiten"]
FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def clean_invisible(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return INVISIBLE_CHARS_PATTERN.sub("", text)


def _collapse(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tidy_text(text) -> str:
    if not text:
        return ""
    return _collapse(clean_invisible(text))


def normalize_title(title) -> str:
    if not title:
        return ""
    text = clean_invisible(title).lower()
    text = GENDER_SUFFIX_PATTERN.sub("", text)
    text = GENDER_TAG_PATTERN.sub(" ", text)
    text = re.sub(r"[^\w\s+#.]|_", " ", text)
    text = re.sub(r"(?<!\w)\.|\.(?!\w)", " ", text)  # keep dots inside words only (node.js)
    return _collapse(text)


def normalize_company(company) -> str:
    if not company:
        return ""
    text = clean_invisible(company).lower()
    text = re.sub(r"[^\w\s]|_", " ", text)
    text = _collapse(text)
    text = LEGAL_FORMS_PATTERN.sub(" ", text)
    return _collapse(text)


def normalize_location(location) -> str:
    if not location:
        return ""
    parts = []
    for part in re.split(r"[|,;]", clean_invisible(location).lower()):
        part = re.sub(r"\d+", " ", part)
        part = re.sub(r"[^\w\s-]|_|(?<!\w)-|-(?!\w)", " ", part)
        part = _collapse(part)
        if part and part not in parts:
            parts.append(part)
    return " | ".join(parts)


def first_city(location) -> str:
    if not location:
        return ""
    city = location.split(" | ")[0]
    if city in NO_CITY:
        return ""
    return city


def normalize_description(description: str) -> str:
    text = clean_invisible(description).replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_dedup_key(company, title, location):
    if not company or not title:
        return None
    key = f"{company}|{title}|{first_city(location)}"
    return key.translate(FOLD) # nußloch = nussloch


def _shingles(text: str, size: int = 5) -> set:
    words = re.findall(r"\w+", text.lower())
    shingles = set()
    count = max(len(words) - size + 1, 1)
    for i in range(count):
        shingles.add(" ".join(words[i:i + size]))
    return shingles


def description_containment(first: str, second: str) -> float:
    first_shingles = _shingles(first)
    second_shingles = _shingles(second)
    shared = first_shingles & second_shingles
    # divided by the smaller text, so a short teaser inside the full ad counts
    return len(shared) / min(len(first_shingles), len(second_shingles))
