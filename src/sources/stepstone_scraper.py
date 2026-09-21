import random
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from loguru import logger
from playwright.sync_api import sync_playwright

from config.stepstone_scraper_config import stepstone_scraper_config
from config.scraper_common_config import scraper_common_config
from config.stage2_config import stage2_config
from utils.util import (
    compute_embedding,
    get_emb_match_job_dict,
    find_best_matching_keyword,
    load_embedding_model_and_keyword_embeddings,
    detect_block_page,
)
from utils.throttle import delay_after_page_load, delay_between_interactions, delay_between_queries, delay_between_detail_pages, random_scroll
from utils.db import jobs_pending_description, save_description, mark_description_expired, record_description_failure, upsert_stage1_jobs
from utils.detail_page import parse_job_posting_json_ld, first_inner_text, detect_expired_page

STEPSTONE_EXPIRED_PATTERN = re.compile("|".join(re.escape(s.lower()) for s in stepstone_scraper_config["detail_page"]["expired_signatures"]))


class StepstoneScraper:
    def __init__(self, embedding_model=None, keywords_embeddings=None):
        self.embedding_model = embedding_model
        self.keywords_embeddings = keywords_embeddings
        self.query_urls = None
        self.query_matched_emb_accepted_jobs = []
        self.query_matched_emb_rejected_jobs = []
        self.description_scraped_jobs = [] # filled by run_description_scraper (stage 2)


    def run_scraper(self):
        if scraper_common_config["use_stepstone_scraper"]:
            self.query_urls = self.build_query_urls()
            logger.info(f"[Stepstone Scraper] Stepstone scraper built {len(self.query_urls)} query combinations")
            self.query_matched_emb_accepted_jobs, self.query_matched_emb_rejected_jobs = self.extract_job_urls(self.query_urls)
            logger.info(f"[Stepstone Scraper] Stepstone found total {len(self.query_matched_emb_accepted_jobs)} query matching accepted job urls and {len(self.query_matched_emb_rejected_jobs)} query matching rejected urls.")
        else:
            logger.warning(f"[Stepstone Scraper] Stepstone scraper is disabled in common config!")


    def run_description_scraper(self, run_timestamp: str):
        if scraper_common_config["use_stepstone_scraper"]:
            limit = stage2_config["max_detail_pages_per_platform"]
            pending_jobs = jobs_pending_description("stepstone", limit)
            logger.info(f"[Stepstone Scraper] {len(pending_jobs)} job detail pages pending (at most {limit} per run)")
            if pending_jobs:
                self.description_scraped_jobs = self.extract_job_descriptions(pending_jobs, run_timestamp)
            status_counts = dict(Counter(job["description_status"] for job in self.description_scraped_jobs))
            logger.info(f"[Stepstone Scraper] Detail pages visited: {status_counts}")
        else:
            logger.warning(f"[Stepstone Scraper] Stepstone scraper is disabled in common config!")


    @staticmethod
    def build_query_urls() -> list[str]:
        urls = []
        location_radius_pairs = stepstone_scraper_config["location_radius_pairs"]
        keywords_list = scraper_common_config["search_keywords"]
        job_age = stepstone_scraper_config["job_age"]
        base_url = stepstone_scraper_config["BASE_URL"]
        for k,v in location_radius_pairs.items():
            for kw in keywords_list:
                kw = kw.strip().lower().replace(" ", "-")
                k = k.strip().lower().replace(" ", "-")
                url = base_url.format(
                    keywords=kw,
                    location=k,
                    radius=v,
                    job_age=job_age,
                )
                urls.append(url)
        random.shuffle(urls)
        return urls


    def extract_job_urls(self, query_url_list:list[str]) -> tuple[list[dict], list[dict]]:
        accepted_job_urls = set()
        rejected_job_urls = set()
        accepted_jobs = []
        rejected_jobs = []
        threshold = scraper_common_config["embedding_match_config"]["threshold"]
        match_keywords = scraper_common_config["match_keywords"]
        search = stepstone_scraper_config["search_page"]

        profile_path = Path(scraper_common_config["browser_profile_path"])
        profile_path.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            logger.info(f"[Stepstone Scraper] Starting browser session (profile: {profile_path})")
            context = p.chromium.launch_persistent_context(
                str(profile_path),
                headless=stepstone_scraper_config["use_headless_mode"], # Headless scraping is not allowed on stepstone
                channel="chrome",
                locale="de-DE",
                timezone_id="Europe/Berlin",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            try:
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda exc: logger.error(f"[Stepstone Scraper] [Page Error] {exc}"))
                page.on("requestfailed", lambda req: logger.warning(f"[Stepstone Scraper] [Request Failed] {req.method} {req.url}"))
                max_failures = scraper_common_config["circuit_breaker"]["max_consecutive_failures"]
                consecutive_failures = 0
                for index, url in enumerate(query_url_list):
                    try:
                        page.goto(url, wait_until="domcontentloaded")
                        delay_after_page_load(scraper_common_config)
                        page.wait_for_selector(search["results_container"], timeout=15000)
                        # TODO: add accept cookies logic
                        random_scroll(page, scraper_common_config)
                        valid_hits = page.locator(search["hit_counter"])
                        number_of_valid_hits_displayed = int(valid_hits.get_attribute(search["hit_counter_attribute"])) # only collect urls of valid jobs (not recommendations) from page 1
                        if number_of_valid_hits_displayed == 0:
                            logger.info(f"[Stepstone Scraper] No matching job posting results found for query {url}")
                        else:
                            links = page.locator(search["links"])
                            for i in range(number_of_valid_hits_displayed):
                                href = links.nth(i).get_attribute("href")
                                title = links.nth(i).locator("div").nth(2).inner_text()
                                if href and title:
                                    href = "https://www.stepstone.de/"+ href
                                    job_title_emb = compute_embedding(self.embedding_model, title)
                                    best_index, max_sim = find_best_matching_keyword(self.keywords_embeddings, job_title_emb)
                                    max_sim = round(max_sim, 4)
                                    best_matching_keyword = match_keywords[best_index]
                                    if max_sim >= threshold:
                                        if href not in accepted_job_urls:
                                            accepted_job_urls.add(href)
                                            accepted_jobs.append(get_emb_match_job_dict(title, href, max_sim, "stepstone"))
                                    elif href not in rejected_job_urls:
                                        rejected_job_urls.add(href)
                                        rejected_jobs.append(get_emb_match_job_dict(title, href, max_sim, "stepstone", rejection_reason="below_threshold"))
                                        logger.warning(f"[Stepstone Scraper] Rejecting '{title}' (below_threshold) | score={max_sim} | closest keyword='{best_matching_keyword}' | URL={href}")
                        consecutive_failures = 0
                    except Exception as exc:
                        consecutive_failures += 1
                        error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                        block_reason = detect_block_page(page)
                        logger.warning(f"[Stepstone Scraper] Query failed ({consecutive_failures}/{max_failures} consecutive): {error} | URL: {url}")
                        if block_reason or consecutive_failures >= max_failures:
                            remaining = len(query_url_list) - index - 1
                            why = f"block page detected: {block_reason}" if block_reason else f"{consecutive_failures} queries failed in a row with no block page detected, last error: {error}"
                            logger.error(f"[Stepstone Scraper] Circuit breaker tripped -- {why}. Aborting this scraper with {remaining} of {len(query_url_list)} queries unvisited so a blocking site is not hammered further; {len(accepted_jobs)} accepted / {len(rejected_jobs)} rejected jobs collected so far are kept. Current page URL: {page.url}")
                            break
                    delay_between_queries(scraper_common_config)
                else:
                    logger.info(f"[Stepstone Scraper] Browser session completed successfully, all {len(query_url_list)} queries visited.")
            finally:
                self.query_matched_emb_accepted_jobs = accepted_jobs
                self.query_matched_emb_rejected_jobs = rejected_jobs
                context.close()
        return accepted_jobs, rejected_jobs


    def extract_job_descriptions(self, jobs: list[dict], run_timestamp: str) -> list[dict]:
        scraped_jobs = []
        max_attempts = stage2_config["max_description_attempts"]
        detail = stepstone_scraper_config["detail_page"]
        cookie_button = stepstone_scraper_config["cookie_button"]

        profile_path = Path(scraper_common_config["browser_profile_path"])
        profile_path.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            logger.info(f"[Stepstone Scraper] Starting browser session for {len(jobs)} job detail pages (profile: {profile_path})")
            context = p.chromium.launch_persistent_context(
                str(profile_path),
                headless=stepstone_scraper_config["use_headless_mode"], # Headless scraping is not allowed on stepstone
                channel="chrome",
                locale="de-DE",
                timezone_id="Europe/Berlin",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            try:
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda exc: logger.error(f"[Stepstone Scraper] [Page Error] {exc}"))
                page.on("requestfailed", lambda req: logger.warning(f"[Stepstone Scraper] [Request Failed] {req.method} {req.url}"))
                max_failures = scraper_common_config["circuit_breaker"]["max_consecutive_failures"]
                consecutive_failures = 0
                for index, job in enumerate(jobs):
                    url = job["url"]
                    scraped_jobs.append(job)
                    try:
                        response = page.goto(url, wait_until="domcontentloaded")
                        delay_after_page_load(scraper_common_config)
                        if cookie_button:
                            accept_cookies = page.locator(cookie_button)
                            if accept_cookies.is_visible():
                                delay_between_interactions(scraper_common_config)
                                accept_cookies.click() # accept cookies
                        expired_reason = detect_expired_page(page, response, STEPSTONE_EXPIRED_PATTERN)
                        if expired_reason:
                            mark_description_expired(job["url_key"], run_timestamp)
                            job["description_status"] = "expired"
                            logger.info(f"[Stepstone Scraper] Job posting expired ({expired_reason}) | URL: {url}")
                        else:
                            page.wait_for_selector(f"{detail['wait_for']}, script[type='application/ld+json']", state="attached", timeout=15000)
                            random_scroll(page, scraper_common_config)
                            fields = parse_job_posting_json_ld(page.content()) or {}
                            fields["description_source"] = "json_ld" if fields.get("description") else "css"
                            if not fields.get("description"):
                                fields["description"] = first_inner_text(page, detail["description"], min_chars=50)
                            if not fields.get("company"):
                                fields["company"] = first_inner_text(page, detail["company"])
                            if not fields.get("location"):
                                fields["location"] = first_inner_text(page, detail["location"])
                            if not fields["description"]:
                                raise ValueError("no description found (no JSON-LD JobPosting and the CSS fallback matched nothing)")
                            save_description(job["url_key"], fields, run_timestamp)
                            job.update(fields, description_status="ok")
                            logger.info(f"[Stepstone Scraper] Scraped description via {fields['description_source']} ({len(fields['description'])} chars) for '{job['title']}' at '{fields.get('company')}' | URL: {url}")
                        consecutive_failures = 0
                    except Exception as exc:
                        consecutive_failures += 1
                        error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                        job["description_status"] = record_description_failure(job["url_key"], max_attempts)
                        block_reason = detect_block_page(page)
                        logger.warning(f"[Stepstone Scraper] Detail page failed ({consecutive_failures}/{max_failures} consecutive, now '{job['description_status']}'): {error} | URL: {url}")
                        if block_reason or consecutive_failures >= max_failures:
                            remaining = len(jobs) - index - 1
                            why = f"block page detected: {block_reason}" if block_reason else f"{consecutive_failures} detail pages failed in a row with no block page detected, last error: {error}"
                            saved = sum(1 for j in scraped_jobs if j["description_status"] == "ok")
                            logger.error(f"[Stepstone Scraper] Circuit breaker tripped -- {why}. Aborting description scraping with {remaining} of {len(jobs)} detail pages unvisited (they stay pending for the next run) so a blocking site is not hammered further; {saved} descriptions saved so far are kept. Current page URL: {page.url}")
                            break
                    delay_between_detail_pages(stage2_config)
                else:
                    logger.info(f"[Stepstone Scraper] Browser session completed successfully, all {len(jobs)} detail pages visited.")
            finally:
                self.description_scraped_jobs = scraped_jobs
                context.close()
        return scraped_jobs


if __name__=="__main__":
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    stepstone_scraper = StepstoneScraper(embedding_model, keyword_embeddings)
    stepstone_scraper.run_scraper()
    upsert_stage1_jobs(stepstone_scraper.query_matched_emb_accepted_jobs + stepstone_scraper.query_matched_emb_rejected_jobs, run_timestamp)
    stepstone_scraper.run_description_scraper(run_timestamp)
