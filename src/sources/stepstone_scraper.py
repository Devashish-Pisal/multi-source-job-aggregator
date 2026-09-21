import random
from pathlib import Path

from loguru import logger
from playwright.sync_api import sync_playwright

from config.stepstone_scraper_config import stepstone_scraper_config
from config.scraper_common_config import scraper_common_config
from utils.util import (
    compute_embedding,
    get_emb_match_job_dict,
    find_best_matching_keyword,
    load_embedding_model_and_keyword_embeddings,
    detect_block_page,
)
from utils.throttle import delay_after_page_load, delay_between_queries, random_scroll


class StepstoneScraper:
    def __init__(self, embedding_model, keywords_embeddings):
        self.embedding_model = embedding_model
        self.keywords_embeddings = keywords_embeddings
        self.query_urls = None
        self.query_matched_emb_accepted_jobs = []
        self.query_matched_emb_rejected_jobs = []
        self.all_query_matched_job_urls = None
        self.all_query_matched_jobs = None # scrape job descriptions and construct list of JOB objects
        self.matching_jobs = None # Resume matching jobs in embedding space --> save these jobs into db immediately
        self.db_saved_jobs = None # Successfully saved jobs to the DB


    def run_scraper(self):
        if scraper_common_config["use_stepstone_scraper"]:
            self.query_urls = self.build_query_urls()
            logger.info(f"[Stepstone Scraper] Stepstone scraper built {len(self.query_urls)} query combinations")
            self.query_matched_emb_accepted_jobs, self.query_matched_emb_rejected_jobs = self.extract_job_urls(self.query_urls)
            logger.info(f"[Stepstone Scraper] Stepstone found total {len(self.query_matched_emb_accepted_jobs)} query matching accepted job urls and {len(self.query_matched_emb_rejected_jobs)} query matching rejected urls.")
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
                        page.wait_for_selector("div[class*='res-'][data-genesis-element='BASE']", timeout=15000)
                        # TODO: add accept cookies logic
                        random_scroll(page, scraper_common_config)
                        valid_hits = page.locator("[data-resultlist-offers-numbers]")
                        number_of_valid_hits_displayed = int(valid_hits.get_attribute("data-resultlist-offers-main-displayed")) # only collect urls of valid jobs (not recommendations) from page 1
                        if number_of_valid_hits_displayed == 0:
                            logger.info(f"[Stepstone Scraper] No matching job posting results found for query {url}")
                        else:
                            links = page.locator("a[href*='/stellenangebote']")
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


if __name__=="__main__":
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    stepstone_scraper = StepstoneScraper(embedding_model, keyword_embeddings)
    stepstone_scraper.run_scraper()
