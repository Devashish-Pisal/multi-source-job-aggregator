import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI, AuthenticationError, PermissionDeniedError, NotFoundError, RateLimitError
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from config.path_config import PROJECT_ROOT
from config.scraper_common_config import scraper_common_config
from config.stage2_config import stage2_config
from utils.db import jobs_pending_judge, save_verdict
from utils.throttle import delay_between_llm_calls

RESPONSE_FORMAT_MODES = ("json_schema", "json_object", None)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.S)
CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.S)
PLACEHOLDER = r"unspecified|not specified|not stated|not mentioned|n/?a|none|unknown|nicht angegeben|keine angabe"
PLACEHOLDER_FULL = re.compile(rf"\s*(?:{PLACEHOLDER})\.?\s*", re.I)
PLACEHOLDER_PAREN = re.compile(rf"\s*\((?:{PLACEHOLDER})\)", re.I)


class DailyLimitReached(Exception):
    pass


def _lowercase(value):
    return value.strip().lower() if isinstance(value, str) else value


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

    _blank = field_validator("must_have", "nice_to_have", "tech_stack", "keywords", mode="before")(_blank_placeholders)


class RoleAndCompany(StrictModel):
    responsibilities: list[str]
    team: str
    company_summary: str

    _blank = field_validator("responsibilities", "team", "company_summary", mode="before")(_blank_placeholders)


class Logistics(StrictModel):
    start_date: str
    duration: str
    hours_per_week: str
    work_model: Literal["onsite", "hybrid", "remote", "unspecified"]
    salary: str
    application_deadline: str

    _lowercase_work_model = field_validator("work_model", mode="before")(_lowercase)
    _blank = field_validator("start_date", "duration", "hours_per_week", "salary", "application_deadline", mode="before")(_blank_placeholders)


class JobDetails(StrictModel):
    requirements: Requirements
    role: RoleAndCompany
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


def load_llm_settings() -> tuple[OpenAI, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = {name: os.environ.get(name) for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} not set in {PROJECT_ROOT / '.env'}")
    client = OpenAI(base_url=settings["LLM_BASE_URL"], api_key=settings["LLM_API_KEY"], timeout=stage2_config["llm"]["timeout_seconds"], max_retries=0) # we handle 429s ourselves
    return client, settings["LLM_MODEL"]


def load_profile_text(config_key: str) -> str:
    path = Path(stage2_config[config_key])
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found -- copy {path.with_name(path.stem + '.example.md')} to {path.name} and adapt it (path set by stage2_config['{config_key}'])")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{path} is empty")
    return text


def build_messages(system_prompt: str, resume: str, job: dict) -> list[dict]:
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
    if stage2_config["llm"]["response_format"] != "json_schema":
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


def judge_job(client: OpenAI, model: str, system_prompt: str, resume: str, job: dict) -> dict:
    llm = stage2_config["llm"]
    kwargs = {"model": model, "messages": build_messages(system_prompt, resume, job)}
    if llm["temperature"] is not None:
        kwargs["temperature"] = llm["temperature"]
    if llm["max_tokens"] is not None:
        kwargs["max_tokens"] = llm["max_tokens"]
    response_format = response_format_param(llm["response_format"])
    if response_format:
        kwargs["response_format"] = response_format
    completion = client.chat.completions.create(**kwargs)
    choice = completion.choices[0]
    if completion.usage:
        logger.debug(f"[LLM Judge] Tokens: prompt={completion.usage.prompt_tokens} completion={completion.usage.completion_tokens}")
    if choice.finish_reason == "length":
        raise ValueError(f"response cut off at max_tokens={llm['max_tokens']} (raise stage2_config['llm']['max_tokens'])")
    return parse_verdict(choice.message.content or "").model_dump()


def rate_limit_wait(exc: RateLimitError) -> float | None:
    retry_after = exc.response.headers.get("retry-after") if exc.response is not None else None
    try:
        return float(retry_after)
    except (TypeError, ValueError):
        pass
    match = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", str(exc))
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds)
    return None


def judge_with_rate_limit_pauses(client: OpenAI, model: str, system_prompt: str, resume: str, job: dict) -> dict:
    llm = stage2_config["llm"]
    for attempt in range(llm["rate_limit_retries"] + 1):
        try:
            return judge_job(client, model, system_prompt, resume, job)
        except RateLimitError as exc:
            wait = rate_limit_wait(exc)
            if "per day" in str(exc).lower() or (wait or 0) > llm["rate_limit_max_wait_seconds"]:
                raise DailyLimitReached(str(exc).strip().splitlines()[0]) from None
            if attempt == llm["rate_limit_retries"]:
                raise
            wait = llm["rate_limit_pause_seconds"] if wait is None else wait
            logger.info(f"[LLM Judge] Rate limit hit, waiting {wait:.0f} s as asked, then retrying '{job['title']}'")
            time.sleep(wait + 1)


def judge_pending_jobs() -> tuple[list[dict], int, str | None]:
    llm = stage2_config["llm"]
    judged = []
    failed = 0
    stop_reason = None
    try:
        if llm["response_format"] not in RESPONSE_FORMAT_MODES:
            raise ValueError(f"stage2_config['llm']['response_format'] must be one of {RESPONSE_FORMAT_MODES}, not {llm['response_format']!r}")
        client, model = load_llm_settings()
        system_prompt = load_profile_text("system_prompt_path")
        resume = load_profile_text("resume_path")
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        logger.error(f"[LLM Judge] Skipping the judge pass: {exc}")
        return judged, failed, f"skipped: {exc}"
    pending = jobs_pending_judge()
    logger.info(f"[LLM Judge] {len(pending)} descriptions to judge with '{model}' at {client.base_url}")
    consecutive_failures = 0
    try:
        for job in pending:
            try:
                verdict = judge_with_rate_limit_pauses(client, model, system_prompt, resume, job)
                verdict_json = json.dumps(verdict, ensure_ascii=False)
                save_verdict(job["id"], model, verdict["fit_score"], verdict["employment_type"], verdict_json)
                job.update(judge_model=model, fit_score=verdict["fit_score"], employment_type=verdict["employment_type"], judge_json=verdict_json)
                judged.append(job)
                logger.info(f"[LLM Judge] fit={verdict['fit_score']:>3} level_ok={verdict['level_ok']} type={verdict['employment_type']} '{job['title']}' at '{job.get('company')}' -- {verdict['reason']} | URL: {job['url']}")
                consecutive_failures = 0
            except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                stop_reason = "the provider rejected the configuration"
                logger.error(f"[LLM Judge] Aborting the judge pass -- {stop_reason} ({type(exc).__name__}: {exc}). Check LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env; {len(pending) - len(judged)} jobs stay pending.")
                break
            except DailyLimitReached as exc:
                stop_reason = "daily token limit reached"
                logger.error(f"[LLM Judge] Stopping the judge pass -- {stop_reason} ({exc}). {len(pending) - len(judged)} jobs stay pending; run `python src/utils/llm_judge.py` once the limit resets.")
                break
            except Exception as exc:
                failed += 1
                consecutive_failures += 1
                error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                logger.warning(f"[LLM Judge] Judging failed ({consecutive_failures}/{llm['max_consecutive_failures']} consecutive): {error} | '{job['title']}' | URL: {job['url']}")
                if consecutive_failures >= llm["max_consecutive_failures"]:
                    stop_reason = f"{consecutive_failures} failures in a row"
                    logger.error(f"[LLM Judge] Aborting the judge pass after {stop_reason}; {len(pending) - len(judged)} jobs stay pending for the next run.")
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
