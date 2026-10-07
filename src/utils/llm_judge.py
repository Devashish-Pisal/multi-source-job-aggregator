import json
import os
import re
import sys
import time
from itertools import count
from pathlib import Path
from typing import Literal, get_origin
from urllib.parse import urlparse

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI, AuthenticationError, PermissionDeniedError, NotFoundError, RateLimitError
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from config.path_config import PROJECT_ROOT
from config.scraper_common_config import scraper_common_config
from config.stage2_config import stage2_config
from utils.db import jobs_pending_judge, save_verdict
from utils.throttle import delay_between_llm_calls
from utils.search_area import outside_search_area

RESPONSE_FORMAT_MODES = ("json_schema", "json_object", None)
REQUEST_KEYS = ("temperature", "max_tokens", "response_format") # what per_model may override
LOCATION_FILTER = "location filter" # judge_model of jobs outside stage2_config["search_area"]
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.S)
CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.S)
PLACEHOLDER = r"unspecified|not specified|not stated|not mentioned|n/?a|none|unknown|nicht angegeben|keine angabe"
PLACEHOLDER_FULL = re.compile(rf"\s*(?:{PLACEHOLDER})\.?\s*", re.I)
PLACEHOLDER_PAREN = re.compile(rf"\s*\((?:{PLACEHOLDER})\)", re.I)
DAILY_LIMIT_PATTERN = re.compile(r"per[ -]day|daily", re.I) # groq "tokens per day", openrouter "free-models-per-day"


class DailyLimitReached(Exception):
    pass


def _lowercase(value):
    return value.strip().lower() if isinstance(value, str) else value


def _work_model(value):
    text = value.strip().lower() if isinstance(value, str) else ""
    remote = re.search(r"remote|home.?office|mobil", text)
    onsite = re.search(r"onsite|on-site|vor ort|präsenz|büro|office", re.sub(r"home.?office", "", text))
    if "hybrid" in text or (remote and onsite):
        return "hybrid"
    return "remote" if remote else "onsite" if onsite else "unspecified" # also "" and the posting's own wording


def _blank_placeholders(value):
    if isinstance(value, list):
        return [item for item in (_blank_placeholders(v) for v in value) if item != ""]
    if isinstance(value, str):
        return "" if PLACEHOLDER_FULL.fullmatch(value) else PLACEHOLDER_PAREN.sub("", value).strip() # "paid (unspecified)" -> "paid"
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequiredLanguage(StrictModel):
    language: str
    level: Literal["basic", "good", "fluent", "native", "unspecified"]

    _lowercase_level = field_validator("level", mode="before")(_lowercase)


class Requirements(StrictModel):
    must_have: list[str]
    nice_to_have: list[str]
    tech_stack: list[str]
    keywords: list[str]
    education: list[str]
    soft_skills: list[str]
    experience: list[str]

    _blank = field_validator("must_have", "nice_to_have", "tech_stack", "keywords", "education", "soft_skills", "experience", mode="before")(_blank_placeholders)


class RoleAndCompany(StrictModel):
    responsibilities: list[str]
    team: str
    company_summary: str
    projects: list[str]
    learning: list[str]
    prospects: str

    _blank = field_validator("responsibilities", "team", "company_summary", "projects", "learning", "prospects", mode="before")(_blank_placeholders)


class Company(StrictModel):
    industry: str
    products: list[str]
    values: list[str]
    size: str
    benefits: list[str]

    _blank = field_validator("industry", "products", "values", "size", "benefits", mode="before")(_blank_placeholders)


class Logistics(StrictModel):
    start_date: str
    duration: str
    hours_per_week: str
    work_model: str # free text for the provider, so "" or the posting's wording cannot fail the call
    salary: str
    application_deadline: str

    _work_model = field_validator("work_model", mode="after")(_work_model) # stored as onsite / hybrid / remote / unspecified
    _blank = field_validator("start_date", "duration", "hours_per_week", "salary", "application_deadline", mode="before")(_blank_placeholders)


class JobDetails(StrictModel):
    requirements: Requirements
    role: RoleAndCompany
    company: Company
    logistics: Logistics


class JobVerdict(StrictModel):
    fit_score: int
    employment_type: Literal["full_time", "part_time", "working_student", "internship", "thesis", "dual_study", "apprenticeship", "freelance", "other"]
    level_ok: bool
    required_languages: list[RequiredLanguage]
    matched_skills: list[str]
    missing_must_haves: list[str]
    reason: str
    details: JobDetails

    _lowercase_employment_type = field_validator("employment_type", mode="before")(_lowercase)
    _blank = field_validator("matched_skills", "missing_must_haves", mode="before")(_blank_placeholders)

    @field_validator("fit_score", mode="before")
    @classmethod
    def clamp_fit_score(cls, value):
        return max(0, min(100, round(float(value))))


def blank(model: type[BaseModel]) -> dict:
    values = {}
    for name, field in model.model_fields.items():
        if isinstance(field.annotation, type) and issubclass(field.annotation, BaseModel):
            values[name] = blank(field.annotation)
        else:
            values[name] = [] if get_origin(field.annotation) is list else "unspecified" if get_origin(field.annotation) is Literal else ""
    return model.model_validate(values).model_dump()


def apply_verdict_rules(verdict: JobVerdict) -> dict:
    rules = stage2_config["verdict"]
    result = verdict.model_dump()
    cap = rules["max_fit_with_missing_must_haves"]
    if cap and len(result["missing_must_haves"]) >= cap["count"] and result["fit_score"] > cap["fit"]:
        logger.debug(f"[LLM Judge] fit {result['fit_score']} capped at {cap['fit']}: {len(result['missing_must_haves'])} must-haves missing")
        result["fit_score"] = cap["fit"]
    if result["fit_score"] < rules["empty_details_below"]:
        result["details"] = blank(JobDetails)
    return result


def location_verdict(reason: str) -> dict:
    return JobVerdict(fit_score=0, employment_type="other", level_ok=False, required_languages=[], matched_skills=[], missing_must_haves=[],
                      reason=reason, details=JobDetails(**blank(JobDetails))).model_dump()


def strict_json_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, list):
            return [inline(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return inline(definitions[node["$ref"].rsplit("/", 1)[-1]])
        result = {}
        for key, value in node.items():
            if key == "title":
                continue
            result[key] = {name: inline(prop) for name, prop in value.items()} if key == "properties" else inline(value)
        return result

    return inline(schema)


VERDICT_SCHEMA = strict_json_schema(JobVerdict)


def request_settings(model: str) -> dict:
    llm = stage2_config["llm"]
    override = llm["per_model"].get(model, {})
    unknown = set(override) - set(REQUEST_KEYS)
    if unknown:
        raise ValueError(f"stage2_config['llm']['per_model']['{model}'] has unknown keys {sorted(unknown)}, allowed: {', '.join(REQUEST_KEYS)}")
    settings = {key: override.get(key, llm[key]) for key in REQUEST_KEYS}
    if settings["response_format"] not in RESPONSE_FORMAT_MODES:
        raise ValueError(f"response_format for '{model}' must be one of {RESPONSE_FORMAT_MODES}, not {settings['response_format']!r}")
    return settings


def load_judges() -> list[dict]:
    load_dotenv(PROJECT_ROOT / ".env")
    judges = []
    for number in count(1):
        prefix = "LLM_" if number == 1 else f"LLM_{number}_" # LLM_*, then LLM_2_*, LLM_3_*, ...
        names = [prefix + name for name in ("BASE_URL", "API_KEY", "MODEL")]
        base_url, api_key, models = (os.environ.get(name) for name in names)
        if number > 1 and not base_url:
            break
        missing = [name for name, value in zip(names, (base_url, api_key, models)) if not value]
        if missing:
            raise RuntimeError(f"{', '.join(missing)} not set in {PROJECT_ROOT / '.env'}")
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=stage2_config["llm"]["timeout_seconds"], max_retries=0) # we handle 429s ourselves
        for model in filter(None, (name.strip() for name in models.split(","))):
            judges.append({"client": client, "model": model, "settings": request_settings(model), "provider": urlparse(base_url).netloc, "env": prefix + "*"})
    if not judges:
        raise RuntimeError(f"LLM_MODEL in {PROJECT_ROOT / '.env'} names no model")
    unmatched = set(stage2_config["llm"]["per_model"]) - {judge["model"] for judge in judges}
    if unmatched:
        logger.warning(f"[LLM Judge] stage2_config['llm']['per_model'] names models that are not in .env: {', '.join(sorted(unmatched))}")
    return judges


def load_profile_text(config_key: str) -> str:
    path = Path(stage2_config[config_key])
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found -- copy {path.with_name(path.stem + '.example.md')} to {path.name} and adapt it (path set by stage2_config['{config_key}'])")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{path} is empty")
    return text


def build_messages(system_prompt: str, resume: str, job: dict, response_format: str | None) -> list[dict]:
    description = job["description"]
    max_chars = stage2_config["max_description_chars"]
    if len(description) > max_chars:
        logger.warning(f"[LLM Judge] Description of {job['url']} has {len(description)} chars, cutting to {max_chars} before judging")
        description = description[:max_chars]
    user_content = (
        f"Job title: {job.get('title') or 'unknown'}\n"
        f"Company: {job.get('company') or 'unknown'}\n"
        f"Location: {job.get('location') or 'unknown'}\n"
        f"Posted: {job.get('date_posted') or 'unknown'}\n"
        f"Source: {job['platform']} {job['url']}\n\n"
        f'Job description:\n"""\n{description}\n"""'
    )
    system_content = f'{system_prompt}\n\nCandidate résumé:\n"""\n{resume}\n"""'
    if response_format != "json_schema":
        system_content += f"\n\nRespond with one JSON object that matches this JSON schema:\n{json.dumps(VERDICT_SCHEMA, ensure_ascii=False)}"
    return [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]


def response_format_param(mode: str | None) -> dict | None:
    if mode == "json_schema":
        return {"type": "json_schema", "json_schema": {"name": "job_verdict", "schema": VERDICT_SCHEMA, "strict": True}}
    if mode == "json_object":
        return {"type": "json_object"}
    return None


def parse_verdict(text: str) -> JobVerdict:
    cleaned = CODE_FENCE_PATTERN.sub("", THINK_BLOCK_PATTERN.sub("", text).strip())
    match = JSON_OBJECT_PATTERN.search(cleaned)
    if not match:
        raise ValueError(f"no JSON object in the model response: {text[:200]!r}")
    try:
        return JobVerdict.model_validate_json(match.group(0))
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(str(part) for part in error['loc']) or 'reply'}: {error['msg']}" for error in exc.errors()[:3])
        raise ValueError(f"verdict does not match the schema ({exc.error_count()} errors): {problems}") from None


def judge_job(judge: dict, system_prompt: str, resume: str, job: dict) -> dict:
    settings = judge["settings"]
    kwargs = {"model": judge["model"], "messages": build_messages(system_prompt, resume, job, settings["response_format"])}
    if settings["temperature"] is not None:
        kwargs["temperature"] = settings["temperature"]
    if settings["max_tokens"] is not None:
        kwargs["max_tokens"] = settings["max_tokens"]
    response_format = response_format_param(settings["response_format"])
    if response_format:
        kwargs["response_format"] = response_format
    completion = judge["client"].chat.completions.create(**kwargs)
    choice = completion.choices[0]
    if completion.usage:
        logger.debug(f"[LLM Judge] Tokens: prompt={completion.usage.prompt_tokens} completion={completion.usage.completion_tokens}")
    if choice.finish_reason == "length":
        raise ValueError(f"response cut off at max_tokens={settings['max_tokens']} (raise it in stage2_config['llm'], or for this model in 'per_model')")
    return apply_verdict_rules(parse_verdict(choice.message.content or ""))


def rate_limit_wait(exc: RateLimitError) -> float | None:
    headers = exc.response.headers if exc.response is not None else {}
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        pass
    try:
        reset = float(headers.get("x-ratelimit-reset"))
        return max(0.0, reset / 1000 - time.time()) if reset > 1e12 else reset # openrouter sends epoch ms
    except (TypeError, ValueError):
        pass
    match = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", str(exc))
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds)
    return None


def judge_with_rate_limit_pauses(judge: dict, system_prompt: str, resume: str, job: dict) -> dict:
    llm = stage2_config["llm"]
    for attempt in range(llm["rate_limit_retries"] + 1):
        try:
            return judge_job(judge, system_prompt, resume, job)
        except RateLimitError as exc:
            wait = rate_limit_wait(exc)
            if DAILY_LIMIT_PATTERN.search(str(exc)) or (wait or 0) > llm["rate_limit_max_wait_seconds"]:
                raise DailyLimitReached(str(exc).strip().splitlines()[0]) from None
            if attempt == llm["rate_limit_retries"]:
                raise
            wait = llm["rate_limit_pause_seconds"] if wait is None else wait
            logger.info(f"[LLM Judge] Rate limit hit on '{judge['model']}', waiting {wait:.0f} s as asked, then retrying '{job['title']}'")
            time.sleep(wait + 1)


def next_judge(judges: list[dict], current: int, reason: str, detail: str, used_up: dict) -> int:
    judge = judges[current]
    used_up.setdefault(reason, []).append(judge["model"])
    following = f"switching to '{judges[current + 1]['model']}' ({judges[current + 1]['provider']})" if current + 1 < len(judges) else "no model left"
    hint = f"; check {judge['env']} in .env" if reason == "rejected" else ""
    logger.warning(f"[LLM Judge] '{judge['model']}' ({judge['provider']}): {reason} ({detail}){hint} -- {following}")
    return current + 1


def judge_pending_jobs() -> tuple[list[dict], int, str | None]:
    llm = stage2_config["llm"]
    judged = []
    failed = 0
    stop_reason = None
    try:
        judges = load_judges()
        system_prompt = load_profile_text("system_prompt_path")
        resume = load_profile_text("resume_path")
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        logger.error(f"[LLM Judge] Skipping the judge pass: {exc}")
        return judged, failed, f"skipped: {exc}"
    pending = jobs_pending_judge()
    overrides = {judge["model"]: "".join(f", {key} {value}" for key, value in stage2_config["llm"]["per_model"].get(judge["model"], {}).items()) for judge in judges}
    logger.info(f"[LLM Judge] {len(pending)} descriptions to judge; models in order: " + ", ".join(f"'{judge['model']}' ({judge['provider']}{overrides[judge['model']]})" for judge in judges))
    current = 0
    used_up = {}
    consecutive_failures = 0
    try:
        for job in pending:
            outside = outside_search_area(job.get("location"))
            if outside:
                verdict = location_verdict(f"Outside the search area: {outside}.")
                verdict_json = json.dumps(verdict, ensure_ascii=False)
                save_verdict(job["id"], LOCATION_FILTER, 0, verdict["employment_type"], verdict_json)
                job.update(judge_model=LOCATION_FILTER, fit_score=0, employment_type=verdict["employment_type"], judge_json=verdict_json)
                judged.append(job)
                logger.info(f"[LLM Judge] Not judged, {outside}: '{job['title']}' at '{job.get('company')}' | URL: {job['url']}")
                continue
            while current < len(judges): # same job again after a switch
                judge = judges[current]
                try:
                    verdict = judge_with_rate_limit_pauses(judge, system_prompt, resume, job)
                except DailyLimitReached as exc:
                    current = next_judge(judges, current, "daily limit", str(exc), used_up)
                    continue
                except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                    current = next_judge(judges, current, "rejected", f"{type(exc).__name__}: {str(exc).strip().splitlines()[0]}", used_up)
                    continue
                except Exception as exc:
                    failed += 1
                    consecutive_failures += 1
                    error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                    logger.warning(f"[LLM Judge] Judging failed on '{judge['model']}' ({consecutive_failures}/{llm['max_consecutive_failures']} in a row): {error} | '{job['title']}' | URL: {job['url']}")
                    if consecutive_failures >= llm["max_consecutive_failures"]:
                        current = next_judge(judges, current, "failing", f"{consecutive_failures} failures in a row", used_up)
                        consecutive_failures = 0
                    break # this job stays pending
                verdict_json = json.dumps(verdict, ensure_ascii=False)
                save_verdict(job["id"], judge["model"], verdict["fit_score"], verdict["employment_type"], verdict_json)
                job.update(judge_model=judge["model"], fit_score=verdict["fit_score"], employment_type=verdict["employment_type"], judge_json=verdict_json)
                judged.append(job)
                logger.info(f"[LLM Judge] fit={verdict['fit_score']:>3} level_ok={verdict['level_ok']} type={verdict['employment_type']} '{job['title']}' at '{job.get('company')}' -- {verdict['reason']} | URL: {job['url']}")
                consecutive_failures = 0
                break
            if current == len(judges):
                stop_reason = "every model is used up (" + "; ".join(f"{reason}: {', '.join(models)}" for reason, models in used_up.items()) + ")"
                logger.error(f"[LLM Judge] Stopping the judge pass -- {stop_reason}. {len(pending) - len(judged)} jobs stay pending; run `python src/utils/llm_judge.py` once a limit resets.")
                break
            delay_between_llm_calls(stage2_config)
        else:
            logger.info(f"[LLM Judge] Judge pass complete: {len(judged)} of {len(pending)} descriptions judged.")
    except KeyboardInterrupt:
        stop_reason = "interrupted"
        logger.warning(f"[LLM Judge] Interrupted -- {len(judged)} verdicts saved so far are kept.")
    return judged, failed, stop_reason


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level=scraper_common_config["log_level"])
    judge_pending_jobs()
