"""
YupReserved dataset pipeline
============================

    raw/goibibo_com-travel_sample.csv  +  reference/*   ──►   processed/<table>.csv

Stage 1  CLEAN     real hotel listings  -> states, cities, hotels, amenities,
                                            hotel_amenities, landmarks, hotel_landmarks
Stage 2  ENRICH    room inventory       -> room_types, rooms, seasons
Stage 3  SIMULATE  platform activity    -> guests, bookings, booking_rooms, reviews

(payments and nightly rates are computed inside PostgreSQL from the pricing
 function, so the money rules live in exactly one place - see 02-database.)

Run:  python3 01-dataset/pipeline/build_dataset.py
Deterministic: the same seed always produces the same files.
"""
from __future__ import annotations

import csv
import html
import json
import math
import random
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

import vocab

SEED = 2026
TODAY = date(2026, 10, 29)                    # "now" for the simulated platform
WINDOW_START, WINDOW_END = date(2025, 1, 1), date(2027, 3, 25)
TARGET_BOOKINGS = 72_000
TARGET_GUESTS = 26_000

HERE = Path(__file__).resolve().parent
DATASET = HERE.parent
RAW = DATASET / "raw" / "goibibo_com-travel_sample.csv"
REF = DATASET / "reference"
OUT = DATASET / "processed"

rng = random.Random(SEED)
report: dict[str, object] = {}                # written to processed/_manifest.json


# ════════════════════════════════════════════════════════════════════════════
#  helpers
# ════════════════════════════════════════════════════════════════════════════
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tidy(text) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(text or ""))).strip(" ,|")


def title_if_shouting(text: str) -> str:
    return text.title() if text.isupper() else text


def parse_time(text: str, which: str) -> str:
    m = re.search(rf"{which} time is (\d{{1,2}}):(\d{{2}}) ?(AM|PM)", str(text), re.I)
    if not m:
        return "12:00" if which == "check-in" else "11:00"
    h, mnt, ampm = int(m[1]), int(m[2]), m[3].upper()
    h = h % 12 + (12 if ampm == "PM" else 0)
    return time(h, mnt).strftime("%H:%M")


def write_csv(name: str, rows: list[dict], columns: list[str]) -> None:
    OUT.mkdir(exist_ok=True)
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    report.setdefault("row_counts", {})[name] = len(rows)
    print(f"  ✓ {name:<16} {len(rows):>7,} rows")


# ════════════════════════════════════════════════════════════════════════════
#  STAGE 1 — CLEAN the real listings
# ════════════════════════════════════════════════════════════════════════════
def load_listings() -> pd.DataFrame:
    df = pd.read_csv(RAW)
    rules = {"C0 raw rows": len(df)}

    df["city"] = df["city"].map(tidy).map(title_if_shouting).replace(vocab.CITY_RENAMES)
    df["state_code"] = df["state"].map(lambda s: vocab.STATE_ALIASES.get(tidy(s).lower()))
    df["state_code"] = [vocab.CITY_STATE_OVERRIDES.get(c, s) for c, s in zip(df.city, df.state_code)]
    df["property_name"] = df["property_name"].map(tidy)

    before = len(df)
    df = df.drop_duplicates(subset=["property_name", "city"])
    rules["C1 duplicate (name, city) removed"] = before - len(df)

    before = len(df)
    df = df[df.latitude.between(6, 37.5) & df.longitude.between(68, 97.5)]
    rules["C2 coordinates outside India removed"] = before - len(df)

    before = len(df)
    chain = df["hotel_brand"].notna() | df["property_name"].str.contains(vocab.CHAIN_PATTERN)
    df = df[~chain]
    rules["C3 chain-brand listings removed"] = before - len(df)

    before = len(df)
    df = df[df.state_code.notna() & df.property_type.isin(vocab.PROPERTY_TYPES)]
    rules["C4 unknown state / property type removed"] = before - len(df)

    rules["C5 clean listings kept"] = len(df)
    report["cleaning_rules"] = rules
    return df.reset_index(drop=True)


SENSITIVE_PHOTO = re.compile(r"cremation|funeral|riot|protest|flood|accident|slum|corpse", re.I)


def load_photos() -> dict[tuple[str, str, str], dict]:
    """reference/photos.csv (made by fetch_photos.py) → {(kind, name, state_code): photo columns}"""
    path = REF / "photos.csv"
    if not path.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if SENSITIVE_PHOTO.search(r["photo_url"]):
            continue                                   # not the right first impression for a booking site
        out[(r["kind"], r["name"], r["state_code"])] = {
            "photo_url": r["photo_url"], "photo_url_hd": r["photo_url_hd"], "photo_credit": r["photo_credit"][:250]}
    return out


PHOTOS: dict = {}
CITY_LANDMARK_FALLBACK = {"Varanasi": ("Dashashwamedh Ghat", "Assi Ghat")}
PHOTO_COLS = ["photo_url", "photo_url_hd", "photo_credit"]


def build_geography(df: pd.DataFrame, signature: list[dict]):
    states = pd.read_csv(REF / "states.csv")
    region_of = dict(zip(states.state_code, states.region))

    pairs = defaultdict(list)
    for r in df.itertuples():
        pairs[(r.city, r.state_code)].append((r.latitude, r.longitude))
    for s in signature:
        pairs[(s["city"], s["state_code"])].append((s["latitude"], s["longitude"]))

    cities, city_id = [], {}
    for i, (name, sc) in enumerate(sorted(pairs, key=lambda k: (k[1], k[0])), start=1):
        pts = pairs[(name, sc)]
        # median is robust to the odd mis-geocoded listing
        lat = sorted(p[0] for p in pts)[len(pts) // 2]
        lon = sorted(p[1] for p in pts)[len(pts) // 2]
        tier = 1 if name in vocab.METRO_CITIES else 2 if name in vocab.TIER2_CITIES else 3
        city_id[(name, sc)] = i
        photo = PHOTOS.get(("city", name, sc)) or next(
            (v for (k, n, s), v in PHOTOS.items() if k == "landmark" and s == sc and n in CITY_LANDMARK_FALLBACK.get(name, ())), {})
        cities.append(dict(city_id=i, city_name=name, state_code=sc,
                           latitude=round(lat, 5), longitude=round(lon, 5),
                           is_metro=str(tier == 1).lower(), tier=tier, **photo))
    write_csv("states", states.to_dict("records"),
              ["state_code", "state_name", "region", "is_union_territory"])
    write_csv("cities", cities, ["city_id", "city_name", "state_code", "latitude",
                                 "longitude", "is_metro", "tier"] + PHOTO_COLS)
    return cities, city_id, region_of


HILL = {"Shimla", "Manali", "Ooty", "Munnar", "Coorg", "Mussoorie", "Nainital",
        "Darjeeling", "Gangtok", "Srinagar", "Kodaikanal", "Mahabaleshwar",
        "Dharamshala", "Mcleodganj", "Kasauli", "Lonavala", "Chikmagalur",
        "Wayanad", "Leh", "Pahalgam", "Gulmarg", "Shillong", "Dalhousie",
        "Kasol", "Auli", "Ranikhet", "Almora", "Yercaud", "Matheran"}
BEACH = {"Goa", "Puri", "Pondicherry", "Alleppey", "Kovalam", "Varkala",
         "Gokarna", "Havelock", "Port Blair", "Diu", "Digha", "Mandarmani",
         "Daman", "Alibaug", "Murudeshwar", "Mahabalipuram"}
HERITAGE_TYPES = {"Palace", "Heritage Hotel", "Haveli"}


def describe(name, ptype, star, locality, city, amenities) -> str:
    stars = f"{star}-star " if star else ""
    setting = ""
    if city in HILL:
        setting = " A quiet hill stay with mountain air and cool evenings."
    elif city in BEACH:
        setting = " A coastal stay close to the beach and the sea."
    if ptype in HERITAGE_TYPES:
        setting += " Heritage architecture with old-world character."
    loved = ", ".join(sorted(amenities)[:4]).lower()
    where = f"{locality}, {city}" if locality and locality != city else city
    return tidy(f"{name} is a {stars}{ptype.lower()} in {where}.{setting}"
                f"{' Guests value the ' + loved + '.' if loved else ''}")


def build_hotels(df, signature, city_id):
    hotels, amen_of = [], {}
    for i, s in enumerate(signature, start=1):           # signature stays get ids 1..18
        hotels.append(dict(
            hotel_id=i, source_ref=s["code"], source="YUPRESERVED",
            hotel_name=s["name"], property_type=s["property_type"],
            star_rating=s["star_rating"], city_id=city_id[(s["city"], s["state_code"])],
            locality=s["locality"], address=s["address"],
            latitude=s["latitude"], longitude=s["longitude"],
            tagline=s["tagline"], description=s["description"],
            check_in_time="14:00", check_out_time="11:00", is_signature="true",
            _quality=4.6, _city=s["city"]))
        amen_of[i] = set(s["amenities"])

    for j, r in enumerate(df.itertuples(), start=len(signature) + 1):
        amen = (vocab.canonical_amenities(r.hotel_facilities)
                | vocab.canonical_amenities(r.room_facilities)
                | vocab.canonical_amenities(r.additional_info))
        locality = title_if_shouting(tidy(r.locality if isinstance(r.locality, str) else r.area))
        star = int(r.hotel_star_rating)
        hotels.append(dict(
            hotel_id=j, source_ref=r.property_id, source="GOIBIBO",
            hotel_name=r.property_name, property_type=r.property_type,
            star_rating=star, city_id=city_id[(r.city, r.state_code)],
            locality=locality or None, address=tidy(r.address),
            latitude=round(r.latitude, 6), longitude=round(r.longitude, 6),
            tagline=None,
            description=describe(r.property_name, r.property_type, star, locality, r.city, amen),
            check_in_time=parse_time(r.hotel_description, "check-in"),
            check_out_time=parse_time(r.hotel_description, "check-out"),
            is_signature="false",
            _quality=r.site_review_rating if r.site_review_rating == r.site_review_rating else 3.8,
            _city=r.city, _rooms=int(r.room_count), _room_type=tidy(r.room_type),
            _poi=str(r.point_of_interest) if isinstance(r.point_of_interest, str) else ""))
        amen_of[j] = amen

    write_csv("hotels", hotels, [
        "hotel_id", "source_ref", "source", "hotel_name", "property_type",
        "star_rating", "city_id", "locality", "address", "latitude", "longitude",
        "tagline", "description", "check_in_time", "check_out_time", "is_signature"])
    return hotels, amen_of


def build_amenities(amen_of):
    catalogue = vocab.amenity_catalogue()
    amenity_id = {name: i for i, (name, _c) in enumerate(catalogue, start=1)}
    rows = [dict(amenity_id=amenity_id[n], amenity_name=n, category=c) for n, c in catalogue]
    links = []
    for hid, names in amen_of.items():
        for n in sorted(names):
            if n not in amenity_id:
                raise ValueError(f"amenity {n!r} on hotel {hid} is not in the catalogue")
            links.append(dict(hotel_id=hid, amenity_id=amenity_id[n]))
    write_csv("amenities", rows, ["amenity_id", "amenity_name", "category"])
    write_csv("hotel_amenities", links, ["hotel_id", "amenity_id"])

    # transparency file: how every raw label was mapped (1NF clean-up evidence)
    raw = pd.read_csv(RAW, usecols=["hotel_facilities", "room_facilities"])
    labels = sorted({l.strip() for col in raw for s in raw[col].dropna() for l in s.split("|") if l.strip()})
    with open(OUT / "_amenity_mapping.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["raw_label", "canonical_amenity"])
        for l in labels:
            w.writerow([l, next(iter(vocab.canonical_amenities(l)), "(dropped)")])


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def build_landmarks(hotels, cities, city_id):
    cur = pd.read_csv(REF / "landmarks_curated.csv")
    landmarks, key_to_id = [], {}

    def add(cid, name, cat, lat, lon, photo=None):
        key = (cid, norm(name))
        if key in key_to_id:
            return key_to_id[key]
        lid = len(landmarks) + 1
        key_to_id[key] = lid
        landmarks.append(dict(landmark_id=lid, city_id=cid, landmark_name=name,
                              category=cat, latitude=lat, longitude=lon, **(photo or {})))
        return lid

    for r in cur.itertuples():
        if (r.city, r.state_code) in city_id:
            add(city_id[(r.city, r.state_code)], r.landmark_name, r.category, r.latitude, r.longitude,
                PHOTOS.get(("landmark", r.landmark_name, r.state_code)))

    # dataset points of interest: keep names that at least 2 hotels in the city list
    counts = defaultdict(int)
    for h in hotels:
        for p in {tidy(x) for x in h.get("_poi", "").split("|")}:
            if 4 <= len(p) <= 40 and not vocab.GENERIC_POI.match(p):
                counts[(h["city_id"], p)] += 1
    for (cid, p), n in sorted(counts.items()):
        if n >= 2:
            add(cid, p, vocab.poi_category(p), None, None)

    by_city = defaultdict(list)
    for l in landmarks:
        by_city[l["city_id"]].append(l)

    links = {}
    for h in hotels:
        listed = {norm(tidy(x)) for x in h.get("_poi", "").split("|")}
        for l in by_city[h["city_id"]]:
            dist = None
            if l["latitude"] is not None and l["latitude"] == l["latitude"]:
                dist = haversine_km(h["latitude"], h["longitude"], l["latitude"], l["longitude"])
                if dist > 25:                       # too far to be "nearby"
                    continue
            elif norm(l["landmark_name"]) not in listed:
                continue                            # dataset POI: only if the listing names it
            links[(h["hotel_id"], l["landmark_id"])] = dict(
                hotel_id=h["hotel_id"], landmark_id=l["landmark_id"],
                distance_km=None if dist is None else round(dist, 2))

    for l in landmarks:                              # NaN -> empty (NULL in SQL)
        if l["latitude"] != l["latitude"]:
            l["latitude"] = l["longitude"] = None
    write_csv("landmarks", landmarks, ["landmark_id", "city_id", "landmark_name",
                                       "category", "latitude", "longitude"] + PHOTO_COLS)
    write_csv("hotel_landmarks", list(links.values()), ["hotel_id", "landmark_id", "distance_km"])


# ════════════════════════════════════════════════════════════════════════════
#  STAGE 2 — ENRICH: room types, physical rooms, seasons
# ════════════════════════════════════════════════════════════════════════════
STAR_BASE = {0: 1500, 1: 1700, 2: 2400, 3: 3900, 4: 6900, 5: 12500}
TYPE_FACTOR = {"Resort": 1.35, "Palace": 3.0, "Villa": 2.0, "Luxury Yacht": 4.0,
               "Houseboat": 1.6, "Tent": 1.1, "Homestay": 0.85, "Guest House": 0.7,
               "Hostel": 0.45, "Lodge": 0.7, "BnB": 0.9, "Service Apartment": 1.1,
               "Bungalow": 1.4, "Farm Stay": 1.1, "Beach Hut": 0.9, "Motel": 0.8,
               "Cottage": 1.0, "Hotel": 1.0, "Heritage Hotel": 1.6, "Haveli": 1.3,
               "Boutique Hotel": 1.2}
CITY_FACTOR = {"Mumbai": 1.45, "Goa": 1.30, "Udaipur": 1.30, "Delhi": 1.25,
               "Gurgaon": 1.15, "Bangalore": 1.2, "Jaisalmer": 1.1}
LADDER = ["Standard Room", "Deluxe Room", "Super Deluxe Room", "Premium Room",
          "Junior Suite", "Suite", "Presidential Suite"]
TIER_PRICE = [1.0, 1.35, 1.75, 2.4, 3.4, 5.0, 8.0]


def city_factor(city: str) -> float:
    if city in CITY_FACTOR:
        return CITY_FACTOR[city]
    if city in vocab.METRO_CITIES:
        return 1.2
    if city in HILL or city in BEACH:
        return 1.15
    return 1.05 if city in vocab.TIER2_CITIES else 0.85


def rupee_price(x: float) -> int:
    return max(499, int(round(x / 100.0)) * 100 - 1)       # ₹3,499 style


def clean_room_name(raw: str) -> str:
    n = re.sub(r"\(.*?\)", "", raw)
    n = re.sub(r"\b(non[- ]?a\.?c\.?|a\.?/?c\.?)\b", lambda m: "Non-AC" if "non" in m[0].lower() else "AC", n, flags=re.I)
    n = tidy(n).title().replace("Ac ", "AC ").replace("Non-Ac", "Non-AC")
    if not re.search(r"room|suite|villa|tent|cottage|hut|dorm|boat|studio|apartment|bungalow|chalet|house", n, re.I):
        n += " Room"
    return n[:60]


def room_plan(h) -> list[dict]:
    """Room types offered by one hotel (name, capacity, price, count)."""
    star, ptype = h["star_rating"], h["property_type"]
    base_price = STAR_BASE[star] * TYPE_FACTOR.get(ptype, 1.0) * city_factor(h["_city"])
    base_price *= 1 + (min(max(h["_quality"], 1), 5) - 3.8) * 0.08
    base_price *= rng.lognormvariate(0, 0.22)

    n_types = {0: 2, 1: 2, 2: 3, 3: 3, 4: 4, 5: 5}[star]
    if ptype in {"Homestay", "Guest House", "BnB", "Lodge", "Cottage", "Tent", "Beach Hut", "Houseboat"}:
        n_types = min(n_types, 2)

    first = clean_room_name(h.get("_room_type") or "Standard Room")
    names = [first] + [n for n in LADDER[1:] if n.lower() != first.lower()]
    if ptype == "Hostel":
        names = ["Dorm Bed (6-share)", "Private Room"]
    plan = []
    for t in range(n_types):
        name = names[t] if t < len(names) else f"{LADDER[min(t, 6)]} {t}"
        is_suite = "suite" in name.lower()
        family = t == n_types - 1 and n_types >= 3 and not is_suite
        dorm = name.startswith("Dorm")
        plan.append(dict(
            type_name=name,
            bed_type="BUNK" if dorm else "TWIN" if family else ("KING" if t >= 2 or star >= 4 else rng.choice(["DOUBLE", "QUEEN"])),
            max_adults=1 if dorm else 4 if family else 3 if is_suite else 2,
            max_children=0 if dorm else 2 if family else 1,
            area_sqft=int((60 if dorm else 140 + 30 * star) * (1 + 0.35 * t)),
            base_price=rupee_price(base_price * (0.3 if dorm else TIER_PRICE[t]))))
    return plan


def build_inventory(hotels, signature):
    sig = {s["code"]: s for s in signature}
    room_types, rooms = [], []
    for h in hotels:
        if h["source"] == "YUPRESERVED":
            plan = [dict(type_name=r["name"], bed_type=r["bed"], max_adults=r["adults"],
                         max_children=r["children"], area_sqft=r["sqft"],
                         base_price=r["price"], _count=r["count"])
                    for r in sig[h["source_ref"]]["rooms"]]
        else:
            plan = room_plan(h)
            total = h["_rooms"] if h["_rooms"] > 0 else rng.randint(6, 12)
            total = max(len(plan) + 1, min(total, 60))
            weights = [0.5, 0.25, 0.14, 0.07, 0.04][:len(plan)]
            counts = [max(1, int(total * w / sum(weights))) for w in weights]
            for p, c in zip(plan, counts):
                p["_count"] = c

        prefix = {"Tent": "T", "Houseboat": "HB", "Beach Hut": "H", "Cottage": "C",
                  "Villa": "V", "Bungalow": "B"}.get(h["property_type"])
        seq = 0
        for p in plan:
            rtid = len(room_types) + 1
            room_types.append(dict(room_type_id=rtid, hotel_id=h["hotel_id"], **p))
            p["room_type_id"] = rtid
            for _ in range(p["_count"]):
                if prefix:
                    number, floor = f"{prefix}-{seq + 1:02d}", None
                else:
                    floor = 1 + seq // 12
                    number = str(floor * 100 + seq % 12 + 1)
                rooms.append(dict(hotel_id=h["hotel_id"], room_number=number,
                                  room_type_id=rtid, floor_no=floor))
                seq += 1
        h["_plan"] = plan

    write_csv("room_types", room_types, ["room_type_id", "hotel_id", "type_name", "bed_type",
                                         "max_adults", "max_children", "area_sqft", "base_price"])
    write_csv("rooms", rooms, ["hotel_id", "room_number", "room_type_id", "floor_no"])

    seasons = pd.read_csv(REF / "seasons.csv")
    seasons.insert(0, "season_id", range(1, len(seasons) + 1))
    write_csv("seasons", seasons.to_dict("records"),
              ["season_id", "season_name", "start_date", "end_date", "multiplier", "notes"])
    return room_types, rooms, seasons


# ════════════════════════════════════════════════════════════════════════════
#  STAGE 3 — SIMULATE platform activity (guests, bookings, reviews)
# ════════════════════════════════════════════════════════════════════════════
def build_guests(cities, region_of):
    home_weights = [(c["city_id"], 30 if c["tier"] == 1 else 6 if c["tier"] == 2 else 1, region_of[c["state_code"]])
                    for c in cities]
    ids, w, regions = zip(*home_weights)
    phones, emails, docs, guests = set(), set(), set(), []
    for gid in range(1, TARGET_GUESTS + 1):
        k = rng.choices(range(len(ids)), weights=w)[0]
        first = rng.choice(vocab.FIRST_NAMES)
        last = rng.choice(vocab.LAST_NAMES_BY_REGION[regions[k]] if rng.random() < 0.8
                          else vocab.LAST_NAMES_BY_REGION[rng.choice(list(vocab.LAST_NAMES_BY_REGION))])
        while (phone := f"{rng.choice('6789')}{rng.randint(0, 999_999_999):09d}") in phones:
            pass
        phones.add(phone)
        base = re.sub(r"[^a-z]", "", f"{first}.{last}".lower().replace(".", "_"))
        email = f"{base}{rng.randint(1, 999)}@example.in"
        while email in emails:
            email = f"{base}{rng.randint(1000, 99999)}@example.in"
        emails.add(email)
        id_type = rng.choices(["PAN", "PASSPORT", "DRIVING_LICENCE", "VOTER_ID"], [50, 20, 20, 10])[0]
        while True:
            L = lambda n: "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(n))
            D = lambda n: "".join(rng.choice("0123456789") for _ in range(n))
            id_no = {"PAN": L(5) + D(4) + L(1), "PASSPORT": L(1) + D(7),
                     "DRIVING_LICENCE": L(2) + D(13), "VOTER_ID": L(3) + D(7)}[id_type]
            if (id_type, id_no) not in docs:
                docs.add((id_type, id_no))
                break
        created = datetime(2024, 6, 1) + timedelta(minutes=rng.randint(0, 60 * 24 * 860))
        guests.append(dict(
            guest_id=gid, first_name=first, last_name=last, phone=phone, email=email,
            date_of_birth=date(1955, 1, 1) + timedelta(days=rng.randint(0, 365 * 50)),
            id_type=id_type, id_number=id_no, home_city_id=ids[k],
            referred_by=rng.randint(1, gid - 1) if gid > 50 and rng.random() < 0.12 else None,
            created_at=created.isoformat(sep=" ", timespec="seconds")))
    write_csv("guests", guests, ["guest_id", "first_name", "last_name", "phone", "email",
                                 "date_of_birth", "id_type", "id_number", "home_city_id",
                                 "referred_by", "created_at"])
    return guests


def season_multiplier(seasons):
    m = {}
    for s in seasons.itertuples():
        d = date.fromisoformat(s.start_date)
        while d <= date.fromisoformat(s.end_date):
            m[d] = s.multiplier
            d += timedelta(days=1)
    return m


def build_bookings(hotels, guests, seasons):
    smult = season_multiplier(seasons)
    days = [WINDOW_START + timedelta(days=i) for i in range((WINDOW_END - WINDOW_START).days)]
    day_w = []
    for d in days:
        w = smult.get(d, 1.0) ** 3 * (1.35 if d.weekday() in (4, 5) else 1.0)
        if d > TODAY:                                   # fewer bookings far in the future
            w *= max(0.05, 1 - (d - TODAY).days / 150)
        day_w.append(w)

    def hotel_weight(h):
        w = {1: 6, 2: 3, 3: 1}[h["_tier"]] * (1 + h["star_rating"] / 3)
        return w * (6 if h["is_signature"] == "true" else 1)
    hw = [hotel_weight(h) for h in hotels]
    # guests: a few loyal travellers book often (Zipf-like)
    gw = [1 / (i + 10) ** 0.6 for i in range(len(guests))]
    guest_since = [datetime.fromisoformat(g["created_at"]) for g in guests]

    busy = defaultdict(list)                            # (hotel, room) -> [(ci, co)]
    rooms_of_type = defaultdict(list)
    for h in hotels:
        for p in h["_plan"]:
            rooms_of_type[p["room_type_id"]] = h["_rooms_by_type"][p["room_type_id"]]

    refs, bookings, booking_rooms = set(), [], []
    REQUESTS = ["Late check-in after 10 pm", "Ground-floor room for elderly parent",
                "Extra bed for child", "Celebrating anniversary", "Early check-in if possible",
                "Vegetarian meals only", "Airport pickup needed", "Quiet room away from lift"]
    attempts = 0
    hotel_idx = rng.choices(range(len(hotels)), weights=hw, k=TARGET_BOOKINGS * 2)
    ci_pick = rng.choices(days, weights=day_w, k=TARGET_BOOKINGS * 2)
    while len(bookings) < TARGET_BOOKINGS and attempts < TARGET_BOOKINGS * 2:
        h, ci = hotels[hotel_idx[attempts]], ci_pick[attempts]
        attempts += 1
        nights = rng.choices([1, 2, 3, 4, 5, 6, 7, 10], [24, 30, 20, 10, 6, 4, 4, 2])[0]
        co = ci + timedelta(days=nights)
        plan = h["_plan"]
        p = rng.choices(plan, weights=[0.55, 0.25, 0.12, 0.05, 0.03][:len(plan)])[0]
        n_rooms = rng.choices([1, 2, 3], [86, 10, 4])[0]

        # status from the timeline
        if co <= TODAY:
            status = rng.choices(["COMPLETED", "CANCELLED", "NO_SHOW"], [86, 10, 4])[0]
        elif ci <= TODAY:
            status = "CHECKED_IN"
        else:
            status = rng.choices(["CONFIRMED", "CANCELLED", "PENDING"], [88, 8, 4])[0]

        free = [rn for rn in rooms_of_type[p["room_type_id"]]
                if all(co <= a or ci >= b for a, b in busy[(h["hotel_id"], rn)])]
        if len(free) < n_rooms:
            continue
        chosen = rng.sample(free, n_rooms)
        if status != "CANCELLED":                        # cancelled stays free the room
            for rn in chosen:
                busy[(h["hotel_id"], rn)].append((ci, co))

        lead = int(rng.expovariate(1 / 21))
        booked = datetime.combine(ci - timedelta(days=min(lead, 180)), time()) + timedelta(minutes=rng.randint(0, 1439))
        booked = min(booked, datetime.combine(TODAY, time(9, 0)) - timedelta(minutes=rng.randint(0, 9000)))
        booked = min(booked, datetime.combine(ci, time()) - timedelta(minutes=rng.randint(1, 600)))
        gi = rng.choices(range(len(guests)), weights=gw)[0]
        guest = guests[gi]
        if guest_since[gi] > booked:                     # a guest must exist before booking
            booked_for = guest_since[gi] + timedelta(minutes=rng.randint(1, 600))
            if booked_for.date() >= ci:
                continue
            booked = booked_for

        cancelled_at = None
        if status == "CANCELLED":
            limit = min(datetime.combine(ci, time()), datetime.combine(TODAY, time(9, 0)))
            span = max(1, int((limit - booked).total_seconds() // 60) - 1)
            cancelled_at = booked + timedelta(minutes=rng.randint(1, span))

        while (ref := "YR" + "".join(rng.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))) in refs:
            pass
        refs.add(ref)
        bid = len(bookings) + 1
        adults = sum(rng.randint(1, p["max_adults"]) for _ in chosen)
        children = sum(rng.choices(range(p["max_children"] + 1))[0] for _ in chosen) if rng.random() < 0.3 else 0
        bookings.append(dict(
            booking_id=bid, booking_ref=ref, guest_id=guest["guest_id"], hotel_id=h["hotel_id"],
            check_in=ci, check_out=co, adults=adults, children=children, status=status,
            special_request=rng.choice(REQUESTS) if rng.random() < 0.06 else None,
            booked_at=booked.isoformat(sep=" ", timespec="seconds"),
            cancelled_at=cancelled_at.isoformat(sep=" ", timespec="seconds") if cancelled_at else None,
            _quality=h["_quality"]))
        for rn in chosen:
            booking_rooms.append(dict(booking_id=bid, hotel_id=h["hotel_id"], room_number=rn))

    bookings.sort(key=lambda b: (b["booked_at"], b["booking_id"]))  # ids follow booking time
    remap = {b["booking_id"]: i for i, b in enumerate(bookings, start=1)}
    for b in bookings:
        b["booking_id"] = remap[b["booking_id"]]
    for br in booking_rooms:
        br["booking_id"] = remap[br["booking_id"]]
    booking_rooms.sort(key=lambda r: (r["booking_id"], r["room_number"]))

    write_csv("bookings", bookings, ["booking_id", "booking_ref", "guest_id", "hotel_id",
                                     "check_in", "check_out", "adults", "children", "status",
                                     "special_request", "booked_at", "cancelled_at"])
    write_csv("booking_rooms", booking_rooms, ["booking_id", "hotel_id", "room_number"])
    return bookings


def build_reviews(bookings):
    reviews = []
    for b in bookings:
        if b["status"] != "COMPLETED" or rng.random() > 0.38:
            continue
        mean = min(max(float(b["_quality"]), 1.5), 4.9)
        rating = int(min(5, max(1, round(rng.gauss(mean, 0.8)))))
        posted = datetime.combine(b["check_out"], time(10)) + timedelta(hours=rng.randint(1, 240))
        if posted.date() > TODAY:
            posted = datetime.combine(TODAY, time(8))
        reviews.append(dict(
            review_id=len(reviews) + 1, booking_id=b["booking_id"], rating=rating,
            title=rng.choice(vocab.REVIEW_TITLES[rating]), body=rng.choice(vocab.REVIEW_BODIES[rating]),
            created_at=posted.isoformat(sep=" ", timespec="seconds")))
    write_csv("reviews", reviews, ["review_id", "booking_id", "rating", "title", "body", "created_at"])


# ════════════════════════════════════════════════════════════════════════════
def main():
    print("YupReserved dataset pipeline")
    signature = json.loads((REF / "signature_stays.json").read_text())["stays"]
    PHOTOS.update(load_photos())

    print("Stage 1 · clean real listings")
    df = load_listings()
    cities, city_id, region_of = build_geography(df, signature)
    hotels, amen_of = build_hotels(df, signature, city_id)
    build_amenities(amen_of)
    build_landmarks(hotels, cities, city_id)

    print("Stage 2 · room inventory & seasons")
    room_types, rooms, seasons = build_inventory(hotels, signature)
    tier = {c["city_id"]: c["tier"] for c in cities}
    by_type = defaultdict(list)
    for r in rooms:
        by_type[r["room_type_id"]].append(r["room_number"])
    for h in hotels:
        h["_tier"] = tier[h["city_id"]]
        h["_rooms_by_type"] = {p["room_type_id"]: by_type[p["room_type_id"]] for p in h["_plan"]}

    print("Stage 3 · simulate platform activity")
    guests = build_guests(cities, region_of)
    bookings = build_bookings(hotels, guests, seasons)
    build_reviews(bookings)

    prices = sorted(rt["base_price"] for rt in room_types)
    report["base_price_quartiles_inr"] = {q: prices[int(len(prices) * f)] for q, f in
                                          [("p25", .25), ("median", .5), ("p75", .75)]}
    report["seed"], report["simulated_today"] = SEED, TODAY.isoformat()
    report["total_rows"] = sum(report["row_counts"].values())
    (OUT / "_manifest.json").write_text(json.dumps(report, indent=2))
    print(f"\nDone - {report['total_rows']:,} rows written to {OUT.relative_to(DATASET.parent)}/")
    print("Cleaning:", json.dumps(report["cleaning_rules"], indent=2))


if __name__ == "__main__":
    main()
