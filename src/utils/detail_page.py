import json
import re
from html import unescape

JSON_LD_SCRIPT_PATTERN = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I)
BLOCK_TAG_PATTERN = re.compile(r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|table|section|article|blockquote)\b[^>]*>", re.I)
TAG_PATTERN = re.compile(r"<[^>]+>")


def html_to_text(html: str) -> str:
    text = re.sub(r"</li\s*>", "", html, flags=re.I)
    text = re.sub(r"<li\b[^>]*>", "\n- ", text, flags=re.I)
    text = BLOCK_TAG_PATTERN.sub("\n", text)
    text = TAG_PATTERN.sub(" ", text)
    text = unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


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


def _organization_name(organization) -> str | None:
    if isinstance(organization, dict):
        return organization.get("name") or None
    return organization or None


def _location_text(job_location) -> str | None:
    places = job_location if isinstance(job_location, list) else [job_location]
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
            text = " ".join(str(v) for v in (postal_code, locality) if v) or address.get("streetAddress")
        else:
            text = address or place.get("name")
        if text:
            parts.append(str(text))
    return " | ".join(dict.fromkeys(parts)) or None


def _employment_type_text(employment_type) -> str | None:
    if isinstance(employment_type, list):
        return ", ".join(str(e) for e in employment_type) or None
    return employment_type or None


def parse_job_posting_json_ld(html: str) -> dict | None:
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
            "date_posted": posting.get("datePosted") or None,
            "description": html_to_text(posting.get("description") or "") or None,
        }
    return None


def first_inner_text(page, selectors: list[str], min_chars: int = 1) -> str | None:
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


def detect_expired_page(page, response, text_pattern: re.Pattern) -> str | None:
    try:
        if response is not None and response.status in (404, 410):
            return f"HTTP {response.status}"
        title = page.title()
        if match := text_pattern.search(title.lower()):
            return f"page title '{title}' matches '{match.group(0)}'"
        text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 5000) : ''")
        if match := text_pattern.search(text.lower()):
            return f"page text contains '{match.group(0)}'"
    except Exception:
        return None
    return None
