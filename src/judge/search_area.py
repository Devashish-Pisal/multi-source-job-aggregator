import csv
import re
from math import asin, cos, radians, sin, sqrt

from config.path_config import PLACES_FILE_PATH
from config.stage3_config import stage3_config
from deduplication.normalize import normalize_location, FOLD

REMOTE_PATTERN = re.compile(r"\b(?:remote|home office|homeoffice|home-office|mobile office|mobiles arbeiten|deutschlandweit|bundesweit)\b")
ALIASES = {"munich": "muenchen", "cologne": "koeln", "nuremberg": "nuernberg", "hanover": "hannover", "brunswick": "braunschweig"}
ABROAD = { # the place list covers Germany only
    "wien": (48.21, 16.37), "vienna": (48.21, 16.37), "zuerich": (47.37, 8.54), "zurich": (47.37, 8.54), "basel": (47.56, 7.59),
    "luxembourg": (49.61, 6.13), "luxemburg": (49.61, 6.13), "strasbourg": (48.57, 7.75), "strassburg": (48.57, 7.75),
    "paris": (48.86, 2.35), "amsterdam": (52.37, 4.90), "london": (51.51, -0.13), "prag": (50.08, 14.44), "prague": (50.08, 14.44),
}

PLACE_INDEX = None # loaded on first use


def load_place_index() -> dict:
    index = {}
    with open(PLACES_FILE_PATH, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            tokens = normalize_location(row["name"]).translate(FOLD).split()
            point = (float(row["latitude"]), float(row["longitude"]))
            for end in range(1, len(tokens) + 1): # "frankfurt" finds "frankfurt am main"
                name = " ".join(tokens[:end])
                if name not in index:
                    index[name] = []
                index[name].append(point)
    return index


def place_index() -> dict:
    global PLACE_INDEX
    if PLACE_INDEX is None:
        PLACE_INDEX = load_place_index()
    return PLACE_INDEX


def distance_km(first, second) -> float:
    # haversine formula, earth radius 6371 km
    lat1 = radians(first[0])
    lon1 = radians(first[1])
    lat2 = radians(second[0])
    lon2 = radians(second[1])
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def place_distance(place: str, centre):
    place = place.translate(FOLD) # "nussloch" finds "Nußloch"
    place = ALIASES.get(place, place)
    if place in ABROAD:
        return distance_km(centre, ABROAD[place])
    index = place_index()
    for tokens in [place.split(), place.replace("-", " ").split()]: # "frankfurt-flughafen" -> "frankfurt"
        for end in range(len(tokens), 0, -1):
            points = index.get(" ".join(tokens[:end]))
            if not points:
                continue
            nearest = None
            for point in points: # same name twice: the nearer one
                km = distance_km(centre, point)
                if nearest is None or km < nearest:
                    nearest = km
            return nearest
    return None


def outside_search_area(location):
    area = stage3_config["search_area"]
    location = normalize_location(location)
    if not area or not location or REMOTE_PATTERN.search(location):
        return None
    centre = (area["latitude"], area["longitude"])
    nearest_place = None
    nearest_km = None
    for place in location.split(" | "):
        km = place_distance(place, centre)
        if km is None:
            return None # unknown place, the judge decides
        if nearest_km is None or km < nearest_km:
            nearest_place = place
            nearest_km = km
    if nearest_km <= area["radius_km"]:
        return None
    return f"{nearest_place} is {nearest_km:.0f} km away"
