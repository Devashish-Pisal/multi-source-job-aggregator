import random
import time

from src.utils.logger import logger


def random_delay(min_seconds: float, max_seconds: float, reason: str = "") -> None:
    delay = random.uniform(min_seconds, max_seconds)
    if reason:
        logger.debug(f"Throttling {delay:.2f}s ({reason})")
    time.sleep(delay)


def delay_between_queries(config: dict) -> None:
    cfg = config["throttle_config"]["between_queries"]
    random_delay(cfg["min_seconds"], cfg["max_seconds"], "between queries")


def delay_between_interactions(config: dict) -> None:
    cfg = config["throttle_config"]["between_interactions"]
    random_delay(cfg["min_seconds"], cfg["max_seconds"], "between interactions")


def delay_after_page_load(config: dict) -> None:
    cfg = config["throttle_config"]["post_page_load"]
    random_delay(cfg["min_seconds"], cfg["max_seconds"], "after page load")


def delay_between_sources(config: dict) -> None:
    cfg = config["throttle_config"]["between_sources"]
    random_delay(cfg["min_seconds"], cfg["max_seconds"], "between sources")


def random_scroll(page, config: dict) -> None:
    """
    Scrolls down by a random number of random-sized steps, pausing briefly
    between each -- mimics a human skimming a results page instead of the
    instant, uniform viewport a bare script produces.
    """
    cfg = config["throttle_config"]["scroll"]
    steps = random.randint(cfg["min_steps"], cfg["max_steps"])
    for _ in range(steps):
        pixels = random.randint(cfg["step_min_pixels"], cfg["step_max_pixels"])
        page.mouse.wheel(0, pixels)
        random_delay(cfg["step_min_seconds"], cfg["step_max_seconds"])
