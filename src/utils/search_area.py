import csv
import re
from functools import cache
from math import asin, cos, radians, sin, sqrt

from config.path_config import PLACES_FILE_PATH
from config.stage2_config import stage2_config
from deduplication.normalize import normalize_location, FOLD

REMOTE_PATTERN = re.compile(r"\b(?:remote|home office|homeoffice|home-office|mobile office|mobiles arbeiten|deutschlandweit|bundesweit)\b")
ALIASES = {"munich": "muenchen", "cologne": "koeln", "nuremberg": "nuernberg", "hanover": "hannover", "brunswick": "braunschweig"}
ABROAD = { # the place list covers Germany only
    "wien": (48.21, 16.37), "vienna": (48.21, 16.37), "zuerich": (47.37, 8.54), "zurich": (47.37, 8.54), "basel": (47.56, 7.59),
    "luxembourg": (49.61, 6.13), "luxemburg": (49.61, 6.13), "strasbourg": (48.57, 7.75), "strassburg": (48.57, 7.75),
    "paris": (48.86, 2.35), "amsterdam": (52.37, 4.90), "london": (51.51, -0.13), "prag": (50.08, 14.44), "prague": (50.08, 14.44),
}


@cache
def place_index() -> dict[str, list[tuple[float, float]]]:
    index = {}
    with open(PLACES_FILE_PATH, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            tokens = normalize_location(row["name"]).translate(FOLD).split()
            point = (float(row["latitude"]), float(row["longitude"]))
            for end in range(1, len(tokens) + 1): # every leading part, so "frankfurt" finds "frankfurt am main"
                index.setdefault(" ".join(tokens[:end]), []).append(point)
    return index


def distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*first, *second))
    return 2 * 6371 * asin(sqrt(sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2))


def place_distance(place: str, centre: tuple[float, float]) -> float | None:
    place = place.translate(FOLD) # "nussloch" finds "Nußloch"
    place = ALIASES.get(place, place)
    if place in ABROAD:
        return distance_km(centre, ABROAD[place])
    for tokens in (place.split(), place.replace("-", " ").split()): # "frankfurt-flughafen" -> "frankfurt"
        for end in range(len(tokens), 0, -1):
            points = place_index().get(" ".join(tokens[:end]))
            if points:
                return min(distance_km(centre, point) for point in points) # same name twice: the nearer one
    return None


def outside_search_area(location: str | None) -> str | None:
    area = stage2_config["search_area"]
    location = normalize_location(location)
    if not area or not location or REMOTE_PATTERN.search(location):
        return None
    centre = (area["latitude"], area["longitude"])
    distances = {}
    for place in location.split(" | "):
        km = place_distance(place, centre)
        if km is None:
            return None # unknown place, the judge decides
        distances[place] = km
    nearest = min(distances, key=distances.get)
    if distances[nearest] <= area["radius_km"]:
        return None
    return f"{nearest} is {distances[nearest]:.0f} km away"
