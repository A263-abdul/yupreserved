"""
Fetch free-licence photos of cities and landmarks from Wikipedia / Wikimedia Commons.

    python3 01-dataset/pipeline/fetch_photos.py

For every city that has hotels and every curated landmark, ask the Wikipedia
API for the article's lead image (two sizes: 960 px for cards, 1920 px for
heroes), skip maps / flags / logos, then read the author and licence of each
file from Commons. Result: reference/photos.csv (kind, name, state_code,
photo_url, photo_url_hd, photo_credit, source_page). The pipeline merges it
into cities.csv and landmarks.csv. Images are hot-linked from Wikimedia with
credit, which their reuse policy allows; nothing is downloaded.

The file is a cache: re-run only to refresh photos (a few dozen API calls).
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASET = HERE.parent
OUT = DATASET / "reference" / "photos.csv"
API = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = "YupReserved/1.0 (DBMS student project; educational, non-commercial)"

NOT_A_PHOTO = re.compile(r"map|locator|flag|seal|emblem|logo|coat[_ ]of|\.svg|\.gif|diagram|chart|banner|symbol|icon", re.I)

# Wikipedia titles that differ from the dataset's city names
TITLE_FIX = {
    "Bangalore": "Bengaluru", "Alleppey": "Alappuzha", "Coorg": "Kodagu district", "Corbett": "Jim Corbett National Park",
    "Pondicherry": "Puducherry", "Goa": "Goa", "Ooty": "Ooty", "Gurgaon": "Gurgaon", "Delhi": "New Delhi",
    "Mysore": "Mysore Palace", "Kochi": "Fort Kochi", "Mahabaleshwar": "Mahabaleshwar", "Munnar": "Munnar",
}
LANDMARK_FIX = {
    ("City Palace", "Jaipur"): "City Palace, Jaipur", ("City Palace", "Udaipur"): "City Palace, Udaipur",
    ("Jantar Mantar", "Jaipur"): "Jantar Mantar, Jaipur", ("Jantar Mantar", "Delhi"): "Jantar Mantar, New Delhi",
    ("Mall Road", "Shimla"): "The Ridge, Shimla", ("Mall Road", "Manali"): "Manali, Himachal Pradesh",
    ("The Ridge", "Shimla"): "The Ridge, Shimla", ("Chinese Fishing Nets", "Kochi"): "Chinese fishing nets",
    ("Promenade Beach", "Pondicherry"): "Promenade Beach", ("MG Road", "Bangalore"): "Mahatma Gandhi Road, Bangalore",
    ("MG Marg", "Gangtok"): "Gangtok", ("Park Street", "Kolkata"): "Park Street, Kolkata",
    ("Government Botanical Garden", "Ooty"): "Government Botanical Garden, Udhagamandalam",
    ("Mall Road", "Shimla"): "The Ridge, Shimla", ("Cyber Hub", "Gurgaon"): "DLF CyberHub",
    ("Puri Beach", "Puri"): "Puri", ("Tiger Hill", "Darjeeling"): "Tiger Hill, Darjeeling",
    ("Vembanad Lake", "Alleppey"): "Vembanad Lake", ("Alappuzha Beach", "Alleppey"): "Alappuzha",
}


def get(url: str, params: dict) -> dict:
    q = url + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    req = urllib.request.Request(q, headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:                          # usually HTTP 429: back off politely
            print(f"  retry {attempt + 1} after {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"request failed: {q[:120]}")


def lead_images(titles: list[str], size: int) -> dict[str, dict]:
    """title → {thumb, file, page} for up to 50 titles per call, following redirects."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        d = get(API, {"action": "query", "titles": "|".join(chunk), "redirects": 1, "prop": "pageimages|pageprops",
                      "piprop": "thumbnail|name", "pithumbsize": size, "pilicense": "free", "ppprop": "disambiguation"})
        back = {t: t for t in chunk}
        for k in ("normalized", "redirects"):
            for m in d.get("query", {}).get(k, []):
                for orig, cur in list(back.items()):
                    if cur == m["from"]:
                        back[orig] = m["to"]
        pages = {p["title"]: p for p in d.get("query", {}).get("pages", [])}
        for orig, final in back.items():
            pg = pages.get(final)
            if not pg or "missing" in pg or "disambiguation" in pg.get("pageprops", {}):
                continue
            if "thumbnail" in pg and not NOT_A_PHOTO.search(pg.get("pageimage", "")):
                out[orig] = {"thumb": pg["thumbnail"]["source"].split("?")[0], "file": pg["pageimage"], "page": final}
        time.sleep(1.5)
    return out


def credits(files: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        d = get(COMMONS, {"action": "query", "titles": "|".join(f"File:{f}" for f in chunk),
                          "prop": "imageinfo", "iiprop": "extmetadata"})
        for pg in d.get("query", {}).get("pages", []):
            meta = (pg.get("imageinfo") or [{}])[0].get("extmetadata", {})
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip() or "Unknown author"
            lic = meta.get("LicenseShortName", {}).get("value", "free licence")
            out[pg["title"].removeprefix("File:").replace(" ", "_")] = f"{artist[:80]} · {lic} · Wikimedia Commons"
        time.sleep(1.5)
    return out


def main():
    processed = DATASET / "processed"
    cities = list(csv.DictReader(open(processed / "cities.csv", encoding="utf-8")))
    states = {r["state_code"]: r["state_name"] for r in csv.DictReader(open(DATASET / "reference" / "states.csv"))}
    curated = list(csv.DictReader(open(DATASET / "reference" / "landmarks_curated.csv", encoding="utf-8")))

    wanted: list[tuple[str, str, str, list[str]]] = []      # (kind, name, state, candidate titles)
    for c in cities:
        n, st = c["city_name"], states[c["state_code"]]
        wanted.append(("city", n, c["state_code"], [TITLE_FIX.get(n, n), f"{n}, {st}", f"{n} district"]))
    for l in curated:
        n, city = l["landmark_name"], l["city"]
        wanted.append(("landmark", n, l["state_code"], [LANDMARK_FIX.get((n, city), n), f"{n}, {city}", f"{n} ({city})"]))

    found: dict[int, dict] = {}
    for round_ in range(3):                                  # try the candidate titles in order
        todo = [i for i in range(len(wanted)) if i not in found and round_ < len(wanted[i][3])]
        titles = sorted({wanted[i][3][round_] for i in todo})
        print(f"round {round_ + 1}: {len(titles)} titles")
        small, big = lead_images(titles, 960), lead_images(titles, 1920)
        for i in todo:
            t = wanted[i][3][round_]
            if t in small:
                found[i] = {**small[t], "hd": big.get(t, small[t])["thumb"]}

    creds = credits(sorted({f["file"] for f in found.values()}))
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "name", "state_code", "photo_url", "photo_url_hd", "photo_credit", "source_page"])
        for i, f in sorted(found.items()):
            kind, name, sc, _ = wanted[i]
            w.writerow([kind, name, sc, f["thumb"], f["hd"], creds.get(f["file"], "Wikimedia Commons"),
                        "https://en.wikipedia.org/wiki/" + urllib.parse.quote(f["page"].replace(" ", "_"))])
    n_city = sum(1 for i in found if wanted[i][0] == "city")
    print(f"✓ {OUT.name}: {n_city}/{len(cities)} cities, {len(found) - n_city}/{len(curated)} landmarks")


if __name__ == "__main__":
    main()
