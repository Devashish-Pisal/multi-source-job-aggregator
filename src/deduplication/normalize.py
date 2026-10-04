import re
import unicodedata

from utils.util import GENDER_NOISE_WORDS, GENDER_SUFFIX_PATTERN

INVISIBLE_CHARS_PATTERN = re.compile(r"[­​‌‍⁠﻿]")
GENDER_TAG_PATTERN = re.compile(
    r"\(\s*(?:[mwfdx]\s*[/|,*.-]?\s*){2,4}\)"  # (m/w/d), (w|m|d), (mwd), (f/m/x)
    r"|\b(?:" + "|".join(re.escape(w) for w in sorted(GENDER_NOISE_WORDS, key=len, reverse=True)) + r")\b"
)
LEGAL_FORMS_PATTERN = re.compile(
    r"\b(?:gmbh|mbh|ag|se|kgaa|kg|ohg|gbr|ug|haftungsbeschränkt|e v|ev|ltd|limited|inc|llc|plc|corp|co|deutschland|germany)\b"
)
NO_CITY = {"bundesweit", "deutschlandweit", "deutschland", "germany", "remote", "home office", "homeoffice"}


def clean_invisible(text: str) -> str:
    return INVISIBLE_CHARS_PATTERN.sub("", unicodedata.normalize("NFKC", text))


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tidy_text(text: str | None) -> str:
    return _collapse(clean_invisible(text)) if text else ""


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    text = GENDER_SUFFIX_PATTERN.sub("", clean_invisible(title).lower())
    text = GENDER_TAG_PATTERN.sub(" ", text)
    text = re.sub(r"[^\w\s+#.]|_", " ", text)
    text = re.sub(r"(?<!\w)\.|\.(?!\w)", " ", text)  # keep dots inside words only (node.js)
    return _collapse(text)


def normalize_company(company: str | None) -> str:
    if not company:
        return ""
    text = re.sub(r"[^\w\s]|_", " ", clean_invisible(company).lower())
    return _collapse(LEGAL_FORMS_PATTERN.sub(" ", _collapse(text)))


def normalize_location(location: str | None) -> str:
    if not location:
        return ""
    parts = []
    for part in re.split(r"[|,;]", clean_invisible(location).lower()):
        part = re.sub(r"\d+", " ", part)
        part = re.sub(r"[^\w\s-]|_|(?<!\w)-|-(?!\w)", " ", part)
        part = _collapse(part)
        if part:
            parts.append(part)
    return " | ".join(dict.fromkeys(parts))


def first_city(location: str | None) -> str:
    city = (location or "").split(" | ")[0]
    return "" if city in NO_CITY else city


def normalize_description(description: str) -> str:
    text = clean_invisible(description).replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_dedup_key(company: str | None, title: str | None, location: str | None) -> str | None:
    if not company or not title:
        return None
    return f"{company}|{title}|{first_city(location)}"


def _shingles(text: str, size: int = 5) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + size]) for i in range(max(len(words) - size + 1, 1))}


def description_similarity(first: str, second: str) -> float:
    first_shingles, second_shingles = _shingles(first), _shingles(second)
    return len(first_shingles & second_shingles) / len(first_shingles | second_shingles)
