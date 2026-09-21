import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI, AuthenticationError, PermissionDeniedError, NotFoundError

from config.path_config import PROJECT_ROOT
from config.stage2_config import stage2_config
from utils.db import jobs_pending_judge, save_verdict
from utils.throttle import delay_between_llm_calls

SYSTEM_PROMPT = """You screen job postings for one specific candidate: a university student in Germany looking for a student position (Werkstudent / Working Student, Praktikum / Internship or similar) in the field shown by the résumé below. Judge each posting using only the résumé and the posting text. Be strict about stated hard requirements and honest about gaps.

fit_score guide (0-100):
- 85-100: student-level position, topic squarely in the candidate's field, stated must-have requirements met.
- 60-84: student-level position, topic close to the candidate's field, at most minor gaps.
- 30-59: student-level position but the topic is off, or a hard requirement is clearly not met (e.g. fluent German required while the résumé shows none), or the level is doubtful.
- 0-29: not a student position (regular full-time, senior, Ausbildung) or an unrelated field.

Respond with a single JSON object and nothing else, with exactly these keys:
- "fit_score": integer 0-100
- "employment_type": one of "werkstudent", "praktikum", "thesis", "full_time", "other"
- "level_ok": true if the posting is a student-level position the candidate can apply for
- "language_requirement": one of "de", "en", "both", "unspecified" -- the working language(s) the posting asks for
- "german_level": one of "none", "basic", "fluent" -- the German level the posting requires
- "matched_skills": list of the candidate's skills that the posting asks for
- "missing_must_haves": list of stated must-have requirements the résumé does not show
- "hours_or_duration": hours per week, duration or start date if stated, else ""
- "reason": at most two sentences explaining the score"""

VERDICT_KEYS = {"fit_score", "employment_type", "level_ok", "language_requirement", "german_level", "matched_skills", "missing_must_haves", "hours_or_duration", "reason"}
CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.S)


def load_llm_settings() -> tuple[OpenAI, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    settings = {name: os.environ.get(name) for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")}
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} not set in {PROJECT_ROOT / '.env'}")
    client = OpenAI(base_url=settings["LLM_BASE_URL"], api_key=settings["LLM_API_KEY"], timeout=stage2_config["llm"]["timeout_seconds"])
    return client, settings["LLM_MODEL"]


def load_resume() -> str:
    path = Path(stage2_config["resume_path"])
    if not path.is_file():
        raise FileNotFoundError(f"résumé not found at {path} (plain text or markdown; path set by stage2_config['resume_path'])")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"résumé file {path} is empty")
    return text


def build_messages(resume: str, job: dict) -> list[dict]:
    description = job["description"]
    max_chars = stage2_config["max_description_chars"]
    if len(description) > max_chars:
        logger.warning(f"[LLM Judge] Description of {job['url']} has {len(description)} chars, cutting to {max_chars} before judging")
        description = description[:max_chars]
    user_content = (
        f"Job title: {job.get('title') or 'unknown'}\n"
        f"Company: {job.get('company') or 'unknown'}\n"
        f"Location: {job.get('location') or 'unknown'}\n"
        f"Employment type from the posting metadata: {job.get('employment_type') or 'unspecified'}\n"
        f"Posted: {job.get('date_posted') or 'unknown'}\n"
        f"Source: {job['platform']} {job['url']}\n\n"
        f'Job description:\n"""\n{description}\n"""'
    )
    system_content = f'{SYSTEM_PROMPT}\n\nCandidate résumé:\n"""\n{resume}\n"""'
    return [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]


def parse_verdict(text: str) -> dict:
    cleaned = CODE_FENCE_PATTERN.sub("", text.strip())
    match = JSON_OBJECT_PATTERN.search(cleaned)
    if not match:
        raise ValueError(f"no JSON object in the model response: {text[:200]!r}")
    verdict = json.loads(match.group(0))
    missing = VERDICT_KEYS - verdict.keys()
    if missing:
        raise ValueError(f"verdict is missing keys {sorted(missing)}")
    verdict["fit_score"] = max(0, min(100, round(float(verdict["fit_score"]))))
    level_ok = verdict["level_ok"]
    verdict["level_ok"] = level_ok.strip().lower() in ("true", "yes", "1") if isinstance(level_ok, str) else bool(level_ok)
    for key in ("employment_type", "language_requirement", "german_level"):
        verdict[key] = str(verdict[key] or "").strip().lower()
    for key in ("matched_skills", "missing_must_haves"):
        value = verdict[key]
        verdict[key] = [str(v) for v in value] if isinstance(value, list) else ([str(value)] if value else [])
    for key in ("hours_or_duration", "reason"):
        verdict[key] = str(verdict[key] or "").strip()
    return verdict


def judge_job(client: OpenAI, model: str, resume: str, job: dict) -> dict:
    llm = stage2_config["llm"]
    kwargs = {"model": model, "messages": build_messages(resume, job)}
    if llm["temperature"] is not None:
        kwargs["temperature"] = llm["temperature"]
    if llm["max_tokens"] is not None:
        kwargs["max_tokens"] = llm["max_tokens"]
    if llm["use_json_response_format"]:
        kwargs["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**kwargs)
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        logger.warning(f"[LLM Judge] Response for {job['url']} was cut off at max_tokens={llm['max_tokens']}")
    if completion.usage:
        logger.debug(f"[LLM Judge] Tokens: prompt={completion.usage.prompt_tokens} completion={completion.usage.completion_tokens}")
    return parse_verdict(choice.message.content or "")


def judge_pending_jobs(run_timestamp: str) -> list[dict]:
    llm = stage2_config["llm"]
    judged = []
    try:
        client, model = load_llm_settings()
        resume = load_resume()
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        logger.error(f"[LLM Judge] Skipping the judge pass: {exc}")
        return judged
    pending = jobs_pending_judge(model, llm["rejudge_when_model_changes"])
    logger.info(f"[LLM Judge] {len(pending)} descriptions to judge with '{model}' at {client.base_url}")
    consecutive_failures = 0
    try:
        for index, job in enumerate(pending):
            try:
                verdict = judge_job(client, model, resume, job)
                verdict_json = json.dumps(verdict, ensure_ascii=False)
                save_verdict(job["url_key"], model, verdict["fit_score"], verdict_json, run_timestamp)
                job.update(judge_model=model, fit_score=verdict["fit_score"], judge_json=verdict_json, judge_run=run_timestamp)
                judged.append(job)
                logger.info(f"[LLM Judge] fit={verdict['fit_score']:>3} level_ok={verdict['level_ok']} '{job['title']}' at '{job.get('company')}' -- {verdict['reason']} | URL: {job['url']}")
                consecutive_failures = 0
            except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                logger.error(f"[LLM Judge] Aborting the judge pass -- the provider rejected the configuration ({type(exc).__name__}: {exc}). Check LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env; {len(pending) - index} jobs stay pending.")
                break
            except Exception as exc:
                consecutive_failures += 1
                error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                logger.warning(f"[LLM Judge] Judging failed ({consecutive_failures}/{llm['max_consecutive_failures']} consecutive): {error} | '{job['title']}' | URL: {job['url']}")
                if consecutive_failures >= llm["max_consecutive_failures"]:
                    logger.error(f"[LLM Judge] Aborting the judge pass after {consecutive_failures} failures in a row; {len(pending) - index - 1} jobs stay pending for the next run.")
                    break
            delay_between_llm_calls(stage2_config)
        else:
            logger.info(f"[LLM Judge] Judge pass complete: {len(judged)} of {len(pending)} descriptions judged.")
    except KeyboardInterrupt:
        logger.warning(f"[LLM Judge] Interrupted -- {len(judged)} verdicts saved so far are kept.")
    return judged


if __name__ == "__main__":
    judge_pending_jobs(datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
