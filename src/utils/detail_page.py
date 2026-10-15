import json
import re
from datetime import date, timedelta
from html import unescape

JSON_LD_SCRIPT_PATTERN = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I)
BLOCK_TAG_PATTERN = re.compile(r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|table|section|article|blockquote)\b[^>]*>", re.I)
TAG_PATTERN = re.compile(r"<[^>]+>")
AGE_TEXT_PATTERN = re.compile(r"(\d+)\s*(minute|min|stunde|std|hour|tag|day|woche|week|monat|month|jahr|year)", re.I)
AGE_UNIT_DAYS = {"minute": 0, "min": 0, "stunde": 0, "std": 0, "hour": 0, "tag": 1, "day": 1, "woche": 7, "week": 7, "monat": 30, "month": 30, "jahr": 365, "year": 365}


def expired_pattern(signatures: list[str]):
    escaped = []
    for signature in signatures:
        escaped.append(re.escape(signature.lower()))
    return re.compile("|".join(escaped))


def html_to_text(html: str) -> str:
    text = re.sub(r"</li\s*>", "", html, flags=re.I)
    text = re.sub(r"<li\b[^>]*>", "\n- ", text, flags=re.I)
    text = BLOCK_TAG_PATTERN.sub("\n", text)
    text = TAG_PATTERN.sub(" ", text)
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"(?m)^-\n+(?=\S)", "- ", text) # <li><p> left the dash on its own line
    text = re.sub(r"(?m)^(- .+)\n\n(?=- )", r"\1\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def drop_junk_lines(text: str, detail: dict) -> str:
    junk = []
    for line in detail.get("junk_lines", []):
        junk.append(line.lower())
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.lstrip("-• ").lower() in junk:
            continue
        if stripped == "-" or stripped == "•":
            continue
        lines.append(line)
    # cut a short footer such as xing's "Anstellungsart ... Standort" block
    for marker in detail.get("footer_markers", []):
        last_marker = None
        for index, line in enumerate(lines):
            if line.strip() == marker:
                last_marker = index
        if last_marker is not None and len("\n".join(lines[last_marker:])) < 300:
            lines = lines[:last_marker]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _find_job_posting(data):
    if isinstance(data, dict):
        types = data.get("@type")
        if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
            return data
        for value in data.values():
            if isinstance(value, (dict, list)):
                found = _find_job_posting(value)
                if found:
                    return found
    elif isinstance(data, list):
        for item in data:
            found = _find_job_posting(item)
            if found:
                return found
    return None


def _organization_name(organization):
    if isinstance(organization, dict):
        return organization.get("name") or None
    return organization or None


def _location_text(job_location):
    if isinstance(job_location, list):
        places = job_location
    else:
        places = [job_location]
    parts = []
    for place in places:
        if not isinstance(place, dict):
            if place:
                parts.append(str(place))
            continue
        address = place.get("address")
        if isinstance(address, dict):
            locality = address.get("addressLocality") or address.get("addressRegion")
            postal_code = address.get("postalCode")
            words = []
            if postal_code:
                words.append(str(postal_code))
            if locality:
                words.append(str(locality))
            text = " ".join(words) or address.get("streetAddress")
        else:
            text = address or place.get("name")
        if text:
            parts.append(str(text))
    unique_parts = []
    for part in parts:
        if part not in unique_parts:
            unique_parts.append(part)
    return " | ".join(unique_parts) or None


def _employment_type_text(employment_type):
    if isinstance(employment_type, list):
        types = []
        for item in employment_type:
            types.append(str(item))
        return ", ".join(types) or None
    return employment_type or None


def _date_only(value):
    match = re.match(r"\d{4}-\d{2}-\d{2}", str(value or "").strip())
    if match:
        return match.group(0)
    return None


def date_from_age_text(text):
    match = AGE_TEXT_PATTERN.search(text or "") # "Vor 2 Wochen", "3 days ago"
    if not match:
        return None
    days = int(match.group(1)) * AGE_UNIT_DAYS[match.group(2).lower()]
    return (date.today() - timedelta(days=days)).isoformat()


def parse_job_posting_json_ld(html: str):
    for block in JSON_LD_SCRIPT_PATTERN.findall(html):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        posting = _find_job_posting(data)
        if posting is None:
            continue
        return {
            "title": posting.get("title") or None,
            "company": _organization_name(posting.get("hiringOrganization")),
            "location": _location_text(posting.get("jobLocation")),
            "employment_type": _employment_type_text(posting.get("employmentType")),
            "date_posted": _date_only(posting.get("datePosted")),
            "description": html_to_text(posting.get("description") or "") or None,
        }
    return None


def first_inner_text(page, selectors: list[str], min_chars: int = 1):
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue
            text = locator.first.inner_text().strip()
            if len(text) >= min_chars:
                return text
        except Exception:
            continue
    return None


def detect_expired_page(page, response, text_pattern):
    try:
        if response is not None and response.status in (404, 410):
            return f"HTTP {response.status}"
        title = page.title()
        match = text_pattern.search(title.lower())
        if match:
            return f"page title '{title}' matches '{match.group(0)}'"
        text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 5000) : ''")
        match = text_pattern.search(text.lower())
        if match:
            return f"page text contains '{match.group(0)}'"
    except Exception:
        return None
    return None
