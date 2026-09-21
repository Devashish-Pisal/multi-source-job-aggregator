from loguru import logger
from playwright.sync_api import sync_playwright

from config.xing_scraper_config import xing_scraper_config
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


class XingScraper:
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
        if scraper_common_config["use_xing_scraper"]:
            self.query_urls = self.build_query_urls()
            logger.info(f"[Xing Scraper] Xing scraper built {len(self.query_urls)} query combinations")
            self.query_matched_emb_accepted_jobs, self.query_matched_emb_rejected_jobs = self.extract_job_urls(self.query_urls)
            logger.info(f"[Xing Scraper] Xing found total {len(self.query_matched_emb_accepted_jobs)} query matching accepted job urls and {len(self.query_matched_emb_rejected_jobs)} query matching rejected urls.")
        else:
            logger.warning(f"[Xing Scraper] Xing scraper is disabled in common config!")

    @staticmethod
    def build_query_urls() -> list[str]:
        urls = []
        location_radius_pairs = xing_scraper_config["location_radius_pairs"]
        keywords_list = scraper_common_config["search_keywords"]
        job_age = xing_scraper_config["job_age"]
        base_url = xing_scraper_config["BASE_URL"]
        for k,v in location_radius_pairs.items():
            for kw in keywords_list:
                kw = kw.strip().lower().replace(" ", "%20")
                k = k.strip().replace(" ", "%20")
                url = base_url.format(
                    keywords=kw,
                    location=k,
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
                "Xing Scraper",
                user_data_dir=scraper_common_config["browser_profile_path"],
                headless=xing_scraper_config["use_headless_mode"], # Headless scraping is not allowed on xing
            ) as session:
                page = session.new_page()
                for url in query_url_list:
                    with query_error_boundary("Xing Scraper", url):
                        page.goto(url)
                        delay_after_page_load(scraper_common_config)
                        accept_cookies = page.locator("button[data-action-type='accept'][id='accept']")
                        if accept_cookies.is_visible():
                            delay_between_interactions(scraper_common_config)
                            accept_cookies.click() # accept cookies
                        page.wait_for_selector("div[class*='container__Container']", timeout=15000) # fail fast (e.g. on a block page) instead of the 30s default
                        random_scroll(page, scraper_common_config)
                        cards = page.locator("div[class*='container__Container'] > div > ol[class*='results-styles'] > li > article[data-xds='Card']")
                        card_count = cards.count()
                        if card_count == 0:
                            logger.info(f"[Xing Scraper] No matching job posting results found for query {url}")
                        else:
                            for i in range(card_count):
                                card_anchor = cards.nth(i).locator("a")
                                href = card_anchor.get_attribute("href")
                                if href:
                                    full_url = "https://www.xing.com" + href
                                    title = self.extract_title(card_anchor)
                                    if title:
                                        job_title_emb = compute_embedding(self.embedding_model, title)
                                        best_index, max_sim = find_best_matching_keyword(self.keywords_embeddings, job_title_emb)
                                        max_sim = round(max_sim, 4)
                                        best_matching_keyword = search_keywords[best_index]
                                        level_compatible = is_employment_level_compatible(best_matching_keyword, title)
                                        if max_sim >= threshold and level_compatible:
                                            if full_url not in accepted_job_urls:
                                                accepted_job_urls.add(full_url)
                                                accepted_jobs.append(get_emb_match_job_dict(title, full_url, max_sim, "xing"))
                                        elif full_url not in rejected_job_urls:
                                            rejected_job_urls.add(full_url)
                                            reason = "employment_level_mismatch" if not level_compatible else "below_threshold"
                                            rejected_jobs.append(get_emb_match_job_dict(title, full_url, max_sim, "xing", rejection_reason=reason))
                                            logger.warning(f"[Xing Scraper] Rejecting '{title}' ({reason}) | score={max_sim} | matched keyword='{best_matching_keyword}' | URL={full_url}")
                                    elif full_url not in accepted_job_urls and full_url not in rejected_job_urls:
                                        # Fail-soft: couldn't extract a title (selector drift on Xing's side) --
                                        # keep the URL so coverage doesn't regress, but it can't be scored/ranked.
                                        logger.warning(f"[Xing Scraper] Could not extract a title for {full_url} -- keeping URL without a relevance score.")
                                        rejected_job_urls.add(full_url)
                                        rejected_jobs.append(get_emb_match_job_dict(None, full_url, None, "xing", rejection_reason="title_extraction_failed"))
                    delay_between_queries(scraper_common_config)
        return accepted_jobs, rejected_jobs


    @staticmethod
    def extract_title(card_anchor) -> str | None:
        """
        The card's anchor is a transparent click-overlay with no visible text
        (confirmed by inspecting the live DOM) -- its title lives in the
        `aria-label` attribute instead (e.g. "Werkstudent im Bereich Cloud &
        Modern Infrastructure..."), which as an accessibility/semantic
        attribute is also more stable than Xing's auto-generated CSS classes.
        inner_text() is kept as a fallback in case aria-label is ever absent,
        so a layout change degrades gracefully instead of losing the title.
        """
        try:
            label = card_anchor.get_attribute("aria-label")
            if label and label.strip():
                return label.strip()
            text = card_anchor.inner_text().strip()
            return text if text else None
        except Exception:
            return None


if __name__=="__main__":
    embedding_model, keyword_embeddings = load_embedding_model_and_keyword_embeddings()
    xing_scraper = XingScraper(embedding_model, keyword_embeddings)
    xing_scraper.run_scraper()
