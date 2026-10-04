import random
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus

from loguru import logger
from playwright.sync_api import sync_playwright

from config.indeed_scraper_config import indeed_scraper_config
from config.scraper_common_config import scraper_common_config
from config.stage2_config import stage2_config
from utils.util import (
    compute_embedding,
    get_emb_match_job_dict,
    find_best_matching_keyword,
    load_embedding_model_and_keyword_embeddings,
    detect_block_page,
    has_required_title_word,
)
from utils.throttle import delay_after_page_load, delay_between_interactions, delay_between_queries, delay_between_detail_pages, random_scroll
from utils.db import jobs_pending_description, save_description, mark_description_expired, record_description_failure, upsert_stage1_jobs
from utils.detail_page import parse_job_posting_json_ld, first_inner_text, detect_expired_page

INDEED_EXPIRED_PATTERN = re.compile("|".join(re.escape(s.lower()) for s in indeed_scraper_config["detail_page"]["expired_signatures"]))


class IndeedScraper:
    def __init__(self, embedding_model=None, keywords_embeddings=None):
        self.embedding_model = embedding_model
        self.keywords_embeddings = keywords_embeddings
        self.query_urls = None
        self.query_matched_emb_accepted_jobs = []
        self.query_matched_emb_rejected_jobs = []
        self.query_yield = [] # accepted urls per query
        self.description_scraped_jobs = [] # filled by run_description_scraper (stage 2)


    def run_scraper(self):
        if scraper_common_config["use_indeed_scraper"]:
            self.query_urls = self.build_query_urls()
            logger.info(f"[Indeed Scraper] Indeed scraper built {len(self.query_urls)} query combinations")
            self.query_matched_emb_accepted_jobs, self.query_matched_emb_rejected_jobs = self.extract_job_urls(self.query_urls)
            logger.info(f"[Indeed Scraper] Indeed found total {len(self.query_matched_emb_accepted_jobs)} query matching accepted job urls and {len(self.query_matched_emb_rejected_jobs)} query matching rejected urls.")
        else:
            logger.info(f"[Indeed Scraper] Indeed scraper is disabled in common config!")

    def run_description_scraper(self):
        if scraper_common_config["use_indeed_scraper"]:
            limit = stage2_config["max_detail_pages_per_platform"]
            pending_jobs = jobs_pending_description("indeed", limit)
            logger.info(f"[Indeed Scraper] {len(pending_jobs)} job detail pages pending (at most {limit} per run)")
            if pending_jobs:
                self.description_scraped_jobs = self.extract_job_descriptions(pending_jobs)
            status_counts = dict(Counter(job["description_status"] for job in self.description_scraped_jobs))
            logger.info(f"[Indeed Scraper] Detail pages visited: {status_counts}")
        else:
            logger.info(f"[Indeed Scraper] Indeed scraper is disabled in common config!")


    @staticmethod
    def build_query_urls() -> list[tuple[str, str, str]]:
        urls = []
        location_radius_pairs = indeed_scraper_config["location_radius_pairs"]
        keywords_list = scraper_common_config["search_keywords"]
        job_age = indeed_scraper_config["job_age"]
        base_url = indeed_scraper_config["BASE_URL"]
        for location, v in location_radius_pairs.items():
            for keyword in keywords_list:
                kw = keyword.strip()
                k = location.strip()
                url = base_url.format(
                    keywords=quote_plus(kw),
                    location=quote_plus(k),
                    radius=v,
                    job_age=job_age,
                )
                urls.append((url, keyword, location))
        random.shuffle(urls)
        return urls


    def extract_job_urls(self, query_url_list:list[tuple[str, str, str]]) -> tuple[list[dict], list[dict]]:
        accepted_job_urls = set()
        rejected_job_urls = set()
        accepted_jobs = []
        rejected_jobs = []
        threshold = scraper_common_config["embedding_match_config"]["threshold"]
        match_keywords = scraper_common_config["match_keywords"]
        search = indeed_scraper_config["search_page"]
        cookie_button = indeed_scraper_config["cookie_button"]

        profile_path = Path(scraper_common_config["browser_profile_path"])
        profile_path.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            logger.info(f"[Indeed Scraper] Starting browser session (profile: {profile_path})")
            context = p.chromium.launch_persistent_context(
                str(profile_path),
                headless=indeed_scraper_config["use_headless_mode"], # Headless scraping is not allowed on indeed
                channel="chrome",
                locale="de-DE",
                timezone_id="Europe/Berlin",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            try:
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda exc: logger.debug(f"[Indeed Scraper] [Page Error] {exc}"))
                page.on("requestfailed", lambda req: logger.debug(f"[Indeed Scraper] [Request Failed] {req.method} {req.url} ({req.failure})"))
                max_failures = scraper_common_config["circuit_breaker"]["max_consecutive_failures"]
                consecutive_failures = 0
                for index, (url, keyword, location) in enumerate(query_url_list):
                    query_accepted = []
                    try:
                        page.goto(url, wait_until="domcontentloaded")
                        delay_after_page_load(scraper_common_config)
                        reject_cookies = page.locator(cookie_button)
                        if reject_cookies.is_visible():
                            delay_between_interactions(scraper_common_config)
                            reject_cookies.click() # reject cookies
                        page.wait_for_selector(search["results_container"], timeout=15000)
                        random_scroll(page, scraper_common_config)
                        empty_result = page.locator(search["no_results"]).is_visible()
                        if empty_result:
                            logger.info(f"[Indeed Scraper] No matching job posting results found for query {url}")
                        else:
                            cards = page.locator(search["cards"])
                            card_count = cards.count()
                            if card_count == 0:
                                logger.info(f"[Indeed Scraper] Results-list selector matched 0 cards for query {url} (page layout may differ, e.g. a single-result redirect to a job detail page)")
                            for i in range(card_count):
                                card = cards.nth(i)
                                job_id = card.get_attribute("data-jk")
                                if job_id:
                                    full_url = f"https://de.indeed.com/viewjob?jk={job_id}"
                                    title = self.extract_title(card)
                                    if title:
                                        job_title_emb = compute_embedding(self.embedding_model, title)
                                        best_index, max_sim = find_best_matching_keyword(self.keywords_embeddings, job_title_emb)
                                        max_sim = round(max_sim, 4)
                                        best_matching_keyword = match_keywords[best_index]
                                        if max_sim >= threshold and has_required_title_word(title):
                                            query_accepted.append(full_url)
                                            if full_url not in accepted_job_urls:
                                                accepted_job_urls.add(full_url)
                                                accepted_jobs.append(get_emb_match_job_dict(title, full_url, max_sim, best_matching_keyword, "indeed"))
                                        elif full_url not in rejected_job_urls:
                                            rejected_job_urls.add(full_url)
                                            rejected_jobs.append(get_emb_match_job_dict(title, full_url, max_sim, best_matching_keyword, "indeed"))
                                            logger.debug(f"[Indeed Scraper] Rejecting '{title}' ({'below threshold' if max_sim < threshold else 'no required title word'}) | score={max_sim} | closest keyword='{best_matching_keyword}' | URL={full_url}")
                                    elif full_url not in accepted_job_urls and full_url not in rejected_job_urls:
                                        logger.warning(f"[Indeed Scraper] Could not extract a title for {full_url} -- saved to the rejected CSV without a score.")
                                        rejected_job_urls.add(full_url)
                                        rejected_jobs.append(get_emb_match_job_dict(None, full_url, None, None, "indeed"))
                        self.query_yield.append({"keyword": keyword, "location": location, "accepted_urls": query_accepted})
                        logger.debug(f"[Indeed Scraper] '{keyword}' in {location}: {len(query_accepted)} accepted")
                        consecutive_failures = 0
                    except Exception as exc:
                        consecutive_failures += 1
                        error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                        block_reason = detect_block_page(page)
                        logger.warning(f"[Indeed Scraper] Query failed ({consecutive_failures}/{max_failures} consecutive): {error} | URL: {url}")
                        if block_reason or consecutive_failures >= max_failures:
                            remaining = len(query_url_list) - index - 1
                            why = f"block page detected: {block_reason}" if block_reason else f"{consecutive_failures} queries failed in a row with no block page detected, last error: {error}"
                            logger.error(f"[Indeed Scraper] Circuit breaker tripped -- {why}. Aborting this scraper with {remaining} of {len(query_url_list)} queries unvisited so a blocking site is not hammered further; {len(accepted_jobs)} accepted / {len(rejected_jobs)} rejected jobs collected so far are kept. Current page URL: {page.url}")
                            break
                    delay_between_queries(scraper_common_config)
                else:
                    logger.info(f"[Indeed Scraper] Browser session completed successfully, all {len(query_url_list)} queries visited.")
            finally:
                self.query_matched_emb_accepted_jobs = accepted_jobs
                self.query_matched_emb_rejected_jobs = rejected_jobs
                context.close()
        return accepted_jobs, rejected_jobs


    def extract_job_descriptions(self, jobs: list[dict]) -> list[dict]:
        scraped_jobs = []
        max_attempts = stage2_config["max_description_attempts"]
        detail = indeed_scraper_config["detail_page"]
        cookie_button = indeed_scraper_config["cookie_button"]

        profile_path = Path(scraper_common_config["browser_profile_path"])
        profile_path.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            logger.info(f"[Indeed Scraper] Starting browser session for {len(jobs)} job detail pages (profile: {profile_path})")
            context = p.chromium.launch_persistent_context(
                str(profile_path),
                headless=indeed_scraper_config["use_headless_mode"], # Headless scraping is not allowed on indeed
                channel="chrome",
                locale="de-DE",
                timezone_id="Europe/Berlin",
                args=["--disable-blink-features=AutomationControlled"],
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            try:
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda exc: logger.debug(f"[Indeed Scraper] [Page Error] {exc}"))
                page.on("requestfailed", lambda req: logger.debug(f"[Indeed Scraper] [Request Failed] {req.method} {req.url} ({req.failure})"))
                max_failures = scraper_common_config["circuit_breaker"]["max_consecutive_failures"]
                consecutive_failures = 0
                for index, job in enumerate(jobs):
                    url = job["url"]
                    scraped_jobs.append(job)
                    try:
                        response = page.goto(url, wait_until="domcontentloaded")
                        delay_after_page_load(scraper_common_config)
                        if cookie_button:
                            reject_cookies = page.locator(cookie_button)
                            if reject_cookies.is_visible():
                                delay_between_interactions(scraper_common_config)
                                reject_cookies.click() # reject cookies
                        expired_reason = detect_expired_page(page, response, INDEED_EXPIRED_PATTERN)
                        if expired_reason:
                            mark_description_expired(job["id"])
                            job["description_status"] = "expired"
                            logger.info(f"[Indeed Scraper] Job posting expired ({expired_reason}) | URL: {url}")
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
                            job.update(save_description(job["id"], fields))
                            duplicate = f" -- duplicate of job #{job['original_id']} ({job['match']}); URL kept on it, row not stored" if job.get("original_id") else ""
                            logger.info(f"[Indeed Scraper] Scraped description via {job['description_source']} ({len(job['description'])} chars) for '{job['title']}' at '{job['company']}'{duplicate} | URL: {url}")
                        consecutive_failures = 0
                    except Exception as exc:
                        consecutive_failures += 1
                        error = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
                        job["description_status"] = record_description_failure(job["id"], max_attempts)
                        block_reason = detect_block_page(page)
                        logger.warning(f"[Indeed Scraper] Detail page failed ({consecutive_failures}/{max_failures} consecutive, now '{job['description_status']}'): {error} | URL: {url}")
                        if block_reason or consecutive_failures >= max_failures:
                            remaining = len(jobs) - index - 1
                            why = f"block page detected: {block_reason}" if block_reason else f"{consecutive_failures} detail pages failed in a row with no block page detected, last error: {error}"
                            saved = sum(1 for j in scraped_jobs if j["description_status"] == "ok")
                            logger.error(f"[Indeed Scraper] Circuit breaker tripped -- {why}. Aborting description scraping with {remaining} of {len(jobs)} detail pages unvisited (they stay pending for the next run) so a blocking site is not hammered further; {saved} descriptions saved so far are kept. Current page URL: {page.url}")
                            break
                    delay_between_detail_pages(stage2_config)
                else:
                    logger.info(f"[Indeed Scraper] Browser session completed successfully, all {len(jobs)} detail pages visited.")
            finally:
                self.description_scraped_jobs = scraped_jobs
                context.close()
        return scraped_jobs


    @staticmethod
    def extract_title(card) -> str | None:
        try:
            title_span = card.locator(indeed_scraper_config["search_page"]["title"])
            if title_span.count(): # count() first, a miss would wait 15 s
                title = title_span.first.get_attribute("title") or title_span.first.inner_text()
            else:
                title = card.inner_text()
            return title.strip() or None
        except Exception:
            return None


if __name__=="__main__":
    logger.remove()
    logger.add(sys.stderr, level=scraper_common_config["log_level"])
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    indeed_scraper = IndeedScraper(embedding_model, keyword_embeddings)
    indeed_scraper.run_scraper()
    upsert_stage1_jobs(indeed_scraper.query_matched_emb_accepted_jobs)
    indeed_scraper.run_description_scraper()


# Example of href scraped from HTML:
# "/rc/clk?jk=7d79172975914a6c&bb=r6STzscjGymbQadnjPTxYUuqozf0DHAMtElUW1i-8QubawdLKL7PNk7qHQixZLOmLO8txAQbl6aGauzPwr5RmJ9qfLu45DUHWGh48l7WOW8mIynrK5nb77Q3GAeVHwaS&xkcb=SoCm67M3hFOv3FzNV50LbzkdCdPP&fccid=6a9687b53c8c4525&cmp=eiei-4-einzelhandel-gmbh&ti=IT+Manager&vjs=3"
