from urllib.parse import quote_plus, parse_qs, urlparse

from loguru import logger
from playwright.sync_api import sync_playwright

from config.indeed_scraper_config import indeed_scraper_config
from config.scraper_common_config import scraper_common_config
from src.utils.util import (
    compute_embedding,
    get_emb_match_job_dict,
    find_best_matching_keyword,
    is_employment_level_compatible,
    load_embedding_model_and_keyword_embeddings,
)
from src.utils.browser_session import BrowserSession, query_error_boundary
from src.utils.throttle import delay_after_page_load, delay_between_interactions, delay_between_queries, random_scroll


class IndeedScraper:
    def __init__(self, embedding_model, keywords_embeddings):
        self.embedding_model = embedding_model
        self.keywords_embeddings = keywords_embeddings
        self.query_urls = None
        self.query_matched_emb_accepted_jobs = []
        self.query_matched_emb_rejected_jobs = []
        self.all_query_matched_jobs = None # scrape job descriptions and construct list of JOB objects
        self.matching_jobs = None # Resume matching jobs in embedding space --> save these jobs into db immediately
        self.db_saved_jobs = None # Successfully saved jobs to the DB


    def run_scraper(self):
        if scraper_common_config["use_indeed_scraper"]:
            self.query_urls = self.build_query_urls()
            logger.info(f"[Indeed Scraper] Indeed scraper built {len(self.query_urls)} query combinations")
            self.query_matched_emb_accepted_jobs, self.query_matched_emb_rejected_jobs = self.extract_job_urls(self.query_urls)
            logger.info(f"[Indeed Scraper] Indeed found total {len(self.query_matched_emb_accepted_jobs)} query matching accepted job urls and {len(self.query_matched_emb_rejected_jobs)} query matching rejected urls.")
        else:
            logger.warning(f"[Indeed Scraper] Indeed scraper is disabled in common config!")

    @staticmethod
    def build_query_urls() -> list[str]:
        urls = []
        location_radius_pairs = indeed_scraper_config["location_radius_pairs"]
        keywords_list = scraper_common_config["search_keywords"]
        job_age = indeed_scraper_config["job_age"]
        base_url = indeed_scraper_config["BASE_URL"]
        for k,v in location_radius_pairs.items():
            for kw in keywords_list:
                kw = kw.strip()
                k = k.strip()
                url = base_url.format(
                    keywords=quote_plus(kw),
                    location=quote_plus(k),
                    radius=v,
                    job_age=job_age,
                )
                urls.append(url)
        return urls


    def extract_job_urls(self, query_url_list:list[str]) -> tuple[list[dict], list[dict]]:
        accepted_job_urls = set()
        rejected_job_urls = set()
        accepted_jobs = []
        rejected_jobs = []
        threshold = scraper_common_config["embedding_match_config"]["threshold"]
        search_keywords = scraper_common_config["search_keywords"]

        with sync_playwright() as p:
            with BrowserSession(
                p,
                "Indeed Scraper",
                user_data_dir=scraper_common_config["browser_profile_path"],
                headless=indeed_scraper_config["use_headless_mode"], # Headless scraping is not allowed on indeed
            ) as session:
                page = session.new_page()
                for url in query_url_list:
                    with query_error_boundary("Indeed Scraper", url):
                        page.goto(url, wait_until="domcontentloaded")
                        delay_after_page_load(scraper_common_config)
                        reject_cookies = page.locator("button[id='onetrust-reject-all-handler']")
                        if reject_cookies.is_visible():
                            delay_between_interactions(scraper_common_config)
                            reject_cookies.click() # reject cookies
                        page.wait_for_selector("div[class*='jobsearch-LeftPane']", timeout=15000) # fail fast (e.g. on a block page) instead of the 30s default
                        random_scroll(page, scraper_common_config)
                        empty_result = page.locator("div[class*='jobsearch-NoResult-messageContainer']").is_visible()
                        if empty_result:
                            logger.info(f"[Indeed Scraper] No matching job posting results found for query {url}")
                        else:
                            cards = page.locator("#mosaic-jobResults #mosaic-provider-jobcards ul > li[class*='css']  a[id*='job']") # > div[class*='vjs-highlight']
                            card_count = cards.count()
                            if card_count == 0:
                                logger.info(f"[Indeed Scraper] Results-list selector matched 0 cards for query {url} (page layout may differ, e.g. a single-result redirect to a job detail page)")
                            for i in range(card_count):
                                card = cards.nth(i)
                                href = card.get_attribute("href")
                                if href and href.startswith("/rc/clk?"): # only allow valid hrefs
                                    full_url = self.normalize_indeed_url("https://de.indeed.com/viewjob?"+ href[8:len(href)]) # construct full_url by removing "/rc/clk?"
                                    title = self.extract_title(href, card)
                                    if title:
                                        job_title_emb = compute_embedding(self.embedding_model, title)
                                        best_index, max_sim = find_best_matching_keyword(self.keywords_embeddings, job_title_emb)
                                        max_sim = round(max_sim, 4)
                                        best_matching_keyword = search_keywords[best_index]
                                        level_compatible = is_employment_level_compatible(best_matching_keyword, title)
                                        if max_sim >= threshold and level_compatible:
                                            if full_url not in accepted_job_urls:
                                                accepted_job_urls.add(full_url)
                                                accepted_jobs.append(get_emb_match_job_dict(title, full_url, max_sim, "indeed"))
                                        elif full_url not in rejected_job_urls:
                                            rejected_job_urls.add(full_url)
                                            reason = "employment_level_mismatch" if not level_compatible else "below_threshold"
                                            rejected_jobs.append(get_emb_match_job_dict(title, full_url, max_sim, "indeed", rejection_reason=reason))
                                            logger.warning(f"[Indeed Scraper] Rejecting '{title}' ({reason}) | score={max_sim} | matched keyword='{best_matching_keyword}' | URL={full_url}")
                                    elif full_url not in accepted_job_urls and full_url not in rejected_job_urls:
                                        # Fail-soft: couldn't extract a title (selector drift on Indeed's side) --
                                        # keep the URL so coverage doesn't regress, but it can't be scored/ranked.
                                        logger.warning(f"[Indeed Scraper] Could not extract a title for {full_url} -- keeping URL without a relevance score.")
                                        rejected_job_urls.add(full_url)
                                        rejected_jobs.append(get_emb_match_job_dict(None, full_url, None, "indeed", rejection_reason="title_extraction_failed"))
                    delay_between_queries(scraper_common_config)
        return accepted_jobs, rejected_jobs


    @staticmethod
    def extract_title(href: str, card) -> str | None:
        """
        Indeed's own click-tracking href already carries the job title as a
        `ti=` query param (see the example in normalize_indeed_url below) --
        reading it there is more robust than a DOM selector, which Indeed
        restyles often. Falls back to a DOM lookup only if that param is ever
        missing, so a layout change degrades gracefully instead of losing the
        title entirely.
        """
        query = parse_qs(urlparse(href).query)
        title = query.get("ti", [None])[0]
        if title:
            return title
        try:
            fallback = card.locator("h2[class*='jobTitle']").inner_text()
            return fallback if fallback else None
        except Exception:
            return None


    @staticmethod
    def normalize_indeed_url(url: str) -> str:
        query = parse_qs(urlparse(url).query)
        job_id = query.get("jk", [None])[0]
        if not job_id:
            return url
        return f"https://de.indeed.com/viewjob?jk={job_id}"


if __name__=="__main__":
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    indeed_scraper = IndeedScraper(embedding_model, keyword_embeddings)
    indeed_scraper.run_scraper()


# Example of href scraped from HTML:
# "/rc/clk?jk=7d79172975914a6c&bb=r6STzscjGymbQadnjPTxYUuqozf0DHAMtElUW1i-8QubawdLKL7PNk7qHQixZLOmLO8txAQbl6aGauzPwr5RmJ9qfLu45DUHWGh48l7WOW8mIynrK5nb77Q3GAeVHwaS&xkcb=SoCm67M3hFOv3FzNV50LbzkdCdPP&fccid=6a9687b53c8c4525&cmp=eiei-4-einzelhandel-gmbh&ti=IT+Manager&vjs=3"
