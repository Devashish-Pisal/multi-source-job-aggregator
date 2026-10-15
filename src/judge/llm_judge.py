import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Literal, get_origin
from urllib.parse import urlparse

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI, APIConnectionError, APITimeoutError, AuthenticationError, PermissionDeniedError, NotFoundError, RateLimitError
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from config.path_config import PROJECT_ROOT
from config.common_config import common_config
from config.stage3_config import stage3_config
from utils.db import jobs_pending_judge, save_verdict
from utils.throttle import delay_between_llm_calls
from utils.util import short_error
from judge.search_area import outside_search_area

RESPONSE_FORMAT_MODES = ("json_schema", "json_object", None)
REQUEST_KEYS = ("temperature", "max_tokens", "response_format") # what per_model may override
LOCATION_FILTER = "location filter" # judge_model of jobs outside stage3_config["search_area"]
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
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _work_model(value):
    if isinstance(value, str):
        text = value.strip().lower()
    else:
        text = ""
    remote = re.search(r"remote|home.?office|mobil", text)
    without_home_office = re.sub(r"home.?office", "", text)
    onsite = re.search(r"onsite|on-site|vor ort|präsenz|büro|office", without_home_office)
    if "hybrid" in text or (remote and onsite):
        return "hybrid"
    if remote:
        return "remote"
    if onsite:
        return "onsite"
    return "unspecified" # also "" and the posting's own wording


def _blank_placeholders(value):
    if isinstance(value, list):
        items = []
        for item in value:
            item = _blank_placeholders(item)
            if item != "":
                items.append(item)
        return items
    if isinstance(value, str):
        if PLACEHOLDER_FULL.fullmatch(value):
            return ""
        return PLACEHOLDER_PAREN.sub("", value).strip() # "paid (unspecified)" -> "paid"
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequiredLanguage(StrictModel):
    language: str
    level: Literal["basic", "good", "fluent", "native", "unspecified"]

    @field_validator("level", mode="before")
    @classmethod
    def lowercase_level(cls, value):
        return _lowercase(value)


class Requirements(StrictModel):
    must_have: list[str]
    nice_to_have: list[str]
    tech_stack: list[str]
    keywords: list[str]
    education: list[str]
    soft_skills: list[str]
    experience: list[str]

    @field_validator("must_have", "nice_to_have", "tech_stack", "keywords", "education", "soft_skills", "experience", mode="before")
    @classmethod
    def remove_placeholders(cls, value):
        return _blank_placeholders(value)


class RoleAndCompany(StrictModel):
    responsibilities: list[str]
    team: str
    company_summary: str
    projects: list[str]
    learning: list[str]
    prospects: str

    @field_validator("responsibilities", "team", "company_summary", "projects", "learning", "prospects", mode="before")
    @classmethod
    def remove_placeholders(cls, value):
        return _blank_placeholders(value)


class Company(StrictModel):
    industry: str
    products: list[str]
    values: list[str]
    size: str
    benefits: list[str]

    @field_validator("industry", "products", "values", "size", "benefits", mode="before")
    @classmethod
    def remove_placeholders(cls, value):
        return _blank_placeholders(value)


class Logistics(StrictModel):
    start_date: str
    duration: str
    hours_per_week: str
    work_model: str # free text, normalised below
    salary: str
    application_deadline: str

    @field_validator("work_model", mode="after")
    @classmethod
    def normalise_work_model(cls, value):
        return _work_model(value) # stored as onsite / hybrid / remote / unspecified

    @field_validator("start_date", "duration", "hours_per_week", "salary", "application_deadline", mode="before")
    @classmethod
    def remove_placeholders(cls, value):
        return _blank_placeholders(value)


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

    @field_validator("employment_type", mode="before")
    @classmethod
    def lowercase_employment_type(cls, value):
        return _lowercase(value)

    @field_validator("matched_skills", "missing_must_haves", mode="before")
    @classmethod
    def remove_placeholders(cls, value):
        return _blank_placeholders(value)

    @field_validator("fit_score", mode="before")
    @classmethod
    def clamp_fit_score(cls, value):
        return max(0, min(100, round(float(value))))


def blank(model) -> dict:
    # empty values for every field of a model, used for "no details"
    values = {}
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            values[name] = blank(annotation)
        elif get_origin(annotation) is list:
            values[name] = []
        elif get_origin(annotation) is Literal:
            values[name] = "unspecified"
        else:
            values[name] = ""
    return model.model_validate(values).model_dump()


def apply_verdict_rules(verdict: JobVerdict) -> dict:
    rules = stage3_config["verdict"]
    result = verdict.model_dump()
    cap = rules["max_fit_with_missing_must_haves"]
    if cap and len(result["missing_must_haves"]) >= cap["count"] and result["fit_score"] > cap["fit"]:
        logger.debug(f"[LLM Judge] fit {result['fit_score']} capped at {cap['fit']}: {len(result['missing_must_haves'])} must-haves missing")
        result["fit_score"] = cap["fit"]
    if result["fit_score"] < rules["empty_details_below"]:
        result["details"] = blank(JobDetails)
    return result


def location_verdict(reason: str) -> dict:
    details = JobDetails(**blank(JobDetails))
    verdict = JobVerdict(fit_score=0, employment_type="other", level_ok=False, required_languages=[], matched_skills=[],
                         missing_must_haves=[], reason=reason, details=details)
    return verdict.model_dump()


def inline_refs(node, definitions):
    # puts every "$ref" definition in place and drops the "title" keys
    if isinstance(node, list):
        items = []
        for item in node:
            items.append(inline_refs(item, definitions))
        return items
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        return inline_refs(definitions[name], definitions)
    result = {}
    for key, value in node.items():
        if key == "title":
            continue
        if key == "properties":
            # property names stay, also a property called "title"
            properties = {}
            for name, prop in value.items():
                properties[name] = inline_refs(prop, definitions)
            result[key] = properties
        else:
            result[key] = inline_refs(value, definitions)
    return result


def strict_json_schema(model) -> dict:
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})
    return inline_refs(schema, definitions)


VERDICT_SCHEMA = strict_json_schema(JobVerdict)


def request_settings(model: str) -> dict:
    llm = stage3_config["llm"]
    override = llm["per_model"].get(model, {})
    unknown = []
    for key in override:
        if key not in REQUEST_KEYS:
            unknown.append(key)
    if unknown:
        raise ValueError(f"stage3_config['llm']['per_model']['{model}'] has unknown keys {sorted(unknown)}, allowed: {', '.join(REQUEST_KEYS)}")
    settings = {}
    for key in REQUEST_KEYS:
        settings[key] = override.get(key, llm[key])
    if settings["response_format"] not in RESPONSE_FORMAT_MODES:
        raise ValueError(f"response_format for '{model}' must be one of {RESPONSE_FORMAT_MODES}, not {settings['response_format']!r}")
    return settings


def load_judges() -> list[dict]:
    load_dotenv(PROJECT_ROOT / ".env")
    judges = []
    number = 1
    while True:
        # LLM_*, then LLM_2_*, LLM_3_*, ...
        if number == 1:
            prefix = "LLM_"
        else:
            prefix = f"LLM_{number}_"
        base_url = os.environ.get(prefix + "BASE_URL")
        api_key = os.environ.get(prefix + "API_KEY")
        models = os.environ.get(prefix + "MODEL")
        if number > 1 and not base_url:
            break
        missing = []
        if not base_url:
            missing.append(prefix + "BASE_URL")
        if not api_key:
            missing.append(prefix + "API_KEY")
        if not models:
            missing.append(prefix + "MODEL")
        if missing:
            raise RuntimeError(f"{', '.join(missing)} not set in {PROJECT_ROOT / '.env'}")
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=stage3_config["llm"]["timeout_seconds"], max_retries=0) # we handle 429s ourselves
        for model in models.split(","):
            model = model.strip()
            if model:
                judges.append({"client": client, "model": model, "settings": request_settings(model), "provider": urlparse(base_url).netloc, "env": prefix + "*"})
        number += 1
    if not judges:
        raise RuntimeError(f"LLM_MODEL in {PROJECT_ROOT / '.env'} names no model")

    model_names = []
    for judge in judges:
        model_names.append(judge["model"])
    unmatched = []
    for name in stage3_config["llm"]["per_model"]:
        if name not in model_names:
            unmatched.append(name)
    if unmatched:
        logger.warning(f"[LLM Judge] stage3_config['llm']['per_model'] names models that are not in .env: {', '.join(sorted(unmatched))}")
    return judges


def load_profile_text(config_key: str) -> str:
    path = Path(stage3_config[config_key])
    if not path.is_file():
        example = path.with_name(path.stem + ".example.md")
        raise FileNotFoundError(f"{path} not found -- copy {example} to {path.name} and fill it in")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{path} is empty")
    return text


def build_messages(system_prompt: str, resume: str, job: dict, response_format) -> list[dict]:
    description = job["description"]
    max_chars = stage3_config["max_description_chars"]
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
        # without json_schema mode the model only sees the schema in the prompt
        system_content += f"\n\nRespond with one JSON object that matches this JSON schema:\n{json.dumps(VERDICT_SCHEMA, ensure_ascii=False)}"
    return [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]


def response_format_param(mode):
    if mode == "json_schema":
        return {"type": "json_schema", "json_schema": {"name": "job_verdict", "schema": VERDICT_SCHEMA, "strict": True}}
    if mode == "json_object":
        return {"type": "json_object"}
    return None


def parse_verdict(text: str) -> JobVerdict:
    cleaned = THINK_BLOCK_PATTERN.sub("", text).strip()
    cleaned = CODE_FENCE_PATTERN.sub("", cleaned)
    match = JSON_OBJECT_PATTERN.search(cleaned)
    if not match:
        raise ValueError(f"no JSON object in the model response: {text[:200]!r}")
    try:
        return JobVerdict.model_validate_json(match.group(0))
    except ValidationError as exc:
        problems = []
        for error in exc.errors()[:3]:
            field = ".".join(str(part) for part in error["loc"]) or "reply"
            problems.append(f"{field}: {error['msg']}")
        raise ValueError(f"verdict does not match the schema ({exc.error_count()} errors): {'; '.join(problems)}")


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
        raise ValueError(f"response cut off at max_tokens={settings['max_tokens']}")
    verdict = parse_verdict(choice.message.content or "")
    return apply_verdict_rules(verdict)


def rate_limit_wait(exc: RateLimitError):
    headers = {}
    if exc.response is not None:
        headers = exc.response.headers
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):
        pass
    try:
        reset = float(headers.get("x-ratelimit-reset"))
        if reset > 1e12: # openrouter sends epoch ms
            return max(0.0, reset / 1000 - time.time())
        return reset
    except (TypeError, ValueError):
        pass
    match = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", str(exc)) # groq: "try again in 1m2.5s"
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    return None


def judge_with_rate_limit_pauses(judge: dict, system_prompt: str, resume: str, job: dict) -> dict:
    llm = stage3_config["llm"]
    reconnected = False
    for attempt in range(llm["rate_limit_retries"] + 1):
        last_attempt = attempt == llm["rate_limit_retries"]
        try:
            return judge_job(judge, system_prompt, resume, job)
        except APIConnectionError as exc:
            # retry a dropped connection once, a timeout just means a slow model
            if isinstance(exc, APITimeoutError) or reconnected or last_attempt:
                raise
            reconnected = True
            logger.info(f"[LLM Judge] Connection error on '{judge['model']}', retrying '{job['title']}' in {llm['connection_error_pause_seconds']} s")
            time.sleep(llm["connection_error_pause_seconds"])
        except RateLimitError as exc:
            wait = rate_limit_wait(exc)
            if DAILY_LIMIT_PATTERN.search(str(exc)):
                raise DailyLimitReached(short_error(exc))
            if wait is not None and wait > llm["rate_limit_max_wait_seconds"]:
                raise DailyLimitReached(short_error(exc))
            if last_attempt:
                raise
            if wait is None:
                wait = llm["rate_limit_pause_seconds"]
            logger.info(f"[LLM Judge] Rate limit hit on '{judge['model']}', waiting {wait:.0f} s as asked, then retrying '{job['title']}'")
            time.sleep(wait + 1)


def next_judge(judges: list[dict], current: int, reason: str, detail: str, used_up: dict) -> int:
    judge = judges[current]
    if reason not in used_up:
        used_up[reason] = []
    used_up[reason].append(judge["model"])
    if current + 1 < len(judges):
        following = f"switching to '{judges[current + 1]['model']}' ({judges[current + 1]['provider']})"
    else:
        following = "no model left"
    hint = ""
    if reason == "rejected":
        hint = f"; check {judge['env']} in .env"
    logger.warning(f"[LLM Judge] '{judge['model']}' ({judge['provider']}): {reason} ({detail}){hint} -- {following}")
    return current + 1


def judge_pending_jobs():
    llm = stage3_config["llm"]
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
    model_texts = []
    for judge in judges:
        text = f"'{judge['model']}' ({judge['provider']}"
        for key, value in llm["per_model"].get(judge["model"], {}).items():
            text += f", {key} {value}"
        model_texts.append(text + ")")
    logger.info(f"[LLM Judge] {len(pending)} descriptions to judge; models in order: " + ", ".join(model_texts))

    current = 0 # index of the model in use
    used_up = {} # reason -> models that cannot be used any more
    consecutive_failures = 0
    try:
        for job in pending:
            outside = outside_search_area(job.get("location"))
            if outside:
                verdict = location_verdict(f"Outside the search area: {outside}.")
                verdict_json = json.dumps(verdict, ensure_ascii=False)
                save_verdict(job["id"], LOCATION_FILTER, 0, verdict["employment_type"], verdict["reason"], verdict_json)
                job.update(judge_model=LOCATION_FILTER, fit_score=0, employment_type=verdict["employment_type"], judge_json=verdict_json)
                judged.append(job)
                logger.info(f"[LLM Judge] Not judged, {outside}: '{job['title']}' at '{job.get('company')}' | URL: {job['url']}")
                continue

            # the same job goes to the next model when one is used up
            while current < len(judges):
                judge = judges[current]
                try:
                    verdict = judge_with_rate_limit_pauses(judge, system_prompt, resume, job)
                except DailyLimitReached as exc:
                    current = next_judge(judges, current, "daily limit", str(exc), used_up)
                    continue
                except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                    current = next_judge(judges, current, "rejected", f"{type(exc).__name__}: {short_error(exc)}", used_up)
                    continue
                except Exception as exc:
                    failed += 1
                    consecutive_failures += 1
                    error = short_error(exc)
                    logger.warning(f"[LLM Judge] Judging failed on '{judge['model']}' ({consecutive_failures}/{llm['max_consecutive_failures']} in a row): {error} | '{job['title']}' | URL: {job['url']}")
                    if consecutive_failures >= llm["max_consecutive_failures"]:
                        current = next_judge(judges, current, "failing", f"{consecutive_failures} failures in a row", used_up)
                        consecutive_failures = 0
                    break # this job stays pending
                verdict_json = json.dumps(verdict, ensure_ascii=False)
                save_verdict(job["id"], judge["model"], verdict["fit_score"], verdict["employment_type"], verdict["reason"], verdict_json)
                job.update(judge_model=judge["model"], fit_score=verdict["fit_score"], employment_type=verdict["employment_type"], judge_json=verdict_json)
                judged.append(job)
                logger.info(f"[LLM Judge] fit={verdict['fit_score']:>3} level_ok={verdict['level_ok']} type={verdict['employment_type']} '{job['title']}' at '{job.get('company')}' -- {verdict['reason']} | URL: {job['url']}")
                consecutive_failures = 0
                break

            if current == len(judges):
                reasons = []
                for reason, models in used_up.items():
                    reasons.append(f"{reason}: {', '.join(models)}")
                stop_reason = "every model is used up (" + "; ".join(reasons) + ")"
                logger.error(f"[LLM Judge] Stopping the judge pass -- {stop_reason}. {len(pending) - len(judged)} jobs stay pending; run stage 3 again once a limit resets.")
                break
            delay_between_llm_calls(stage3_config)
        if stop_reason is None:
            logger.info(f"[LLM Judge] Judge pass complete: {len(judged)} of {len(pending)} descriptions judged.")
    except KeyboardInterrupt:
        stop_reason = "interrupted"
        logger.warning(f"[LLM Judge] Interrupted -- {len(judged)} verdicts saved so far are kept.")
    return judged, failed, stop_reason


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level=common_config["log_level"])
    judge_pending_jobs()
