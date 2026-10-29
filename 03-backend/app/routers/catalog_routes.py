"""Browse: platform stats, destination autocomplete, search, hotel pages."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..db import Trace, fetch, fetch_one, transaction

router = APIRouter(prefix="/api", tags=["browse"])

# mood presets → an extra WHERE predicate on hotels h (all hand-written, no user SQL)
MOODS = {
    "heritage": ("Heritage & palaces",
                 "(h.property_type IN ('Palace','Heritage Hotel','Haveli') OR h.search_doc @@ to_tsquery('english', 'heritage | palace | haveli | fort'))"),
    "hills": ("Quiet hill stays",
              "h.search_doc @@ to_tsquery('english', 'hill | mountain')"),
    "beach": ("By the sea",
              "(h.property_type = 'Beach Hut' OR EXISTS (SELECT 1 FROM hotel_landmarks hl JOIN landmarks l USING (landmark_id) "
              "WHERE hl.hotel_id = h.hotel_id AND l.category = 'BEACH' AND hl.distance_km <= 3))"),
    "water": ("Houseboats & lakes",
              "(h.property_type IN ('Houseboat','Luxury Yacht') OR EXISTS (SELECT 1 FROM hotel_landmarks hl JOIN landmarks l USING (landmark_id) "
              "WHERE hl.hotel_id = h.hotel_id AND l.category = 'LAKE' AND hl.distance_km <= 1.5))"),
    "spiritual": ("Ghats & temples",
                  "EXISTS (SELECT 1 FROM hotel_landmarks hl JOIN landmarks l USING (landmark_id) "
                  "WHERE hl.hotel_id = h.hotel_id AND l.category = 'TEMPLE' AND hl.distance_km <= 1.5)"),
    "workation": ("Work from anywhere",
                  "(SELECT count(*) FROM hotel_amenities ha JOIN amenities a USING (amenity_id) WHERE ha.hotel_id = h.hotel_id "
                  "AND a.amenity_name IN ('Free Wi-Fi','Business Centre','Cafe')) >= 2"),
    "family": ("Big family trips",
               "EXISTS (SELECT 1 FROM room_types rt WHERE rt.hotel_id = h.hotel_id AND rt.max_adults >= 4)"),
    "budget": ("Under ₹2,000",
               "(SELECT min(base_price) FROM room_types rt WHERE rt.hotel_id = h.hotel_id) < 2000"),
}

# home-page hero slideshow, in this order
HERO = ["Gateway of India", "Taj Mahal", "Hawa Mahal", "Lake Pichola", "Dashashwamedh Ghat", "Dal Lake",
        "Golden Temple", "Calangute Beach", "Jaisalmer Fort", "Victoria Memorial", "Mysore Palace", "Charminar"]

SORTS = {
    "recommended": "h.is_signature DESC, (coalesce(h.avg_rating, 3.5) * ln(2 + h.review_count)) DESC, h.hotel_id",
    "price_asc": "from_price ASC, h.hotel_id",
    "price_desc": "from_price DESC, h.hotel_id",
    "rating": "h.avg_rating DESC NULLS LAST, h.review_count DESC",
    "distance": "distance_km ASC NULLS LAST, h.hotel_id",
}


@router.get("/stats")
def stats():
    trace = Trace()
    with transaction(read_only=True) as conn:
        row = fetch_one(conn, """
            SELECT (SELECT count(*) FROM hotels)  AS hotels,
                   (SELECT count(*) FROM cities WHERE EXISTS (SELECT 1 FROM hotels h WHERE h.city_id = cities.city_id)) AS cities,
                   (SELECT count(*) FROM rooms)   AS rooms,
                   (SELECT count(*) FROM states s WHERE EXISTS (SELECT 1 FROM cities c JOIN hotels h USING (city_id) WHERE c.state_code = s.state_code)) AS states,
                   (SELECT count(*) FROM bookings) AS bookings,
                   (SELECT count(*) FROM reviews)  AS reviews""", trace=trace)
    return {"data": row, "trace": trace.steps}


@router.get("/moods")
def moods():
    return {"data": [{"key": k, "label": v[0]} for k, v in MOODS.items()]}


@router.get("/destinations")
def destinations(q: str = Query("", max_length=60), limit: int = Query(8, le=20)):
    """Autocomplete over cities, landmarks and hotel names (UNION of three sources)."""
    trace = Trace()
    term = q.strip()
    with transaction(read_only=True) as conn:
        if not term:
            rows = fetch(conn, """
                SELECT 'city' AS kind, c.city_id AS id, c.city_name AS label, s.state_name AS sublabel,
                       count(h.hotel_id) AS hotels
                FROM cities c JOIN states s USING (state_code) JOIN hotels h USING (city_id)
                GROUP BY c.city_id, s.state_name
                ORDER BY count(h.hotel_id) DESC LIMIT %(limit)s""", {"limit": limit}, trace)
        else:
            rows = fetch(conn, """
                SELECT * FROM (
                    SELECT 'city' AS kind, c.city_id AS id, c.city_name AS label, s.state_name AS sublabel,
                           (SELECT count(*) FROM hotels h WHERE h.city_id = c.city_id) AS hotels,
                           similarity(c.city_name, %(q)s) + CASE WHEN c.city_name ILIKE %(prefix)s THEN 1 ELSE 0 END AS score
                    FROM cities c JOIN states s USING (state_code)
                    WHERE c.city_name ILIKE %(prefix)s OR c.city_name %% %(q)s
                  UNION ALL
                    SELECT 'landmark', l.landmark_id, l.landmark_name, c.city_name,
                           (SELECT count(*) FROM hotel_landmarks hl WHERE hl.landmark_id = l.landmark_id),
                           similarity(l.landmark_name, %(q)s) + CASE WHEN l.latitude IS NOT NULL THEN 0.6 ELSE 0 END
                             + CASE WHEN l.landmark_name ILIKE %(prefix)s THEN 0.5 ELSE 0 END
                    FROM landmarks l JOIN cities c USING (city_id)
                    WHERE l.landmark_name ILIKE %(contains)s OR l.landmark_name %% %(q)s
                  UNION ALL
                    SELECT 'hotel', h.hotel_id, h.hotel_name, c.city_name, NULL,
                           similarity(h.hotel_name, %(q)s) + CASE WHEN h.is_signature THEN 0.5 ELSE 0 END
                    FROM hotels h JOIN cities c USING (city_id)
                    WHERE h.hotel_name ILIKE %(contains)s OR h.hotel_name %% %(q)s
                ) AS u
                WHERE kind <> 'landmark' OR hotels > 0
                ORDER BY score DESC, hotels DESC NULLS LAST
                LIMIT %(limit)s""",
                {"q": term, "prefix": f"{term}%", "contains": f"%{term}%", "limit": limit}, trace)
    return {"data": rows, "trace": trace.steps}


@router.get("/featured")
def featured():
    trace = Trace()
    with transaction(read_only=True) as conn:
        stays = fetch(conn, """
            SELECT hotel_id, hotel_name, property_type, star_rating, tagline, locality, city_name,
                   state_name, avg_rating, review_count, from_price, photo_url, photo_credit, photo_caption
            FROM v_hotel_cards WHERE is_signature ORDER BY hotel_id""", trace=trace)
        hero = fetch(conn, """
            SELECT l.landmark_id, l.landmark_name, c.city_name, c.city_id, l.photo_url_hd, l.photo_credit
            FROM landmarks l JOIN cities c USING (city_id)
            WHERE l.photo_url_hd IS NOT NULL
              AND l.landmark_name = ANY(%s)
            ORDER BY array_position(%s, l.landmark_name::text)""",
            (HERO, HERO), trace)
        cities = fetch(conn, """
            SELECT c.city_id, c.city_name, s.state_name, count(DISTINCT h.hotel_id) AS hotels,
                   min(rt.base_price) AS from_price, c.photo_url, c.photo_credit
            FROM cities c JOIN states s USING (state_code)
            JOIN hotels h USING (city_id) JOIN room_types rt USING (hotel_id)
            WHERE c.city_name IN ('Mumbai','Udaipur','Goa','Hyderabad','Jaipur','Varanasi','Munnar','Srinagar','Delhi','Alleppey','Jaisalmer','Shimla')
            GROUP BY c.city_id, s.state_name
            ORDER BY count(DISTINCT h.hotel_id) DESC""", trace=trace)
        seasons = fetch(conn, """
            SELECT season_name, start_date, end_date, multiplier FROM seasons
            WHERE end_date >= DATE '2026-10-29' ORDER BY start_date LIMIT 4""", trace=trace)
    return {"data": {"stays": stays, "cities": cities, "seasons": seasons, "hero": hero}, "trace": trace.steps}


@router.get("/search")
def search(
    city_id: int | None = None,
    landmark_id: int | None = None,
    q: str | None = Query(None, max_length=80),
    mood: str | None = None,
    check_in: date | None = None,
    check_out: date | None = None,
    adults: int = Query(2, ge=1, le=24),
    min_price: int | None = None,
    max_price: int | None = None,
    stars: list[int] = Query(default=[]),
    types: list[str] = Query(default=[]),
    amenities: list[int] = Query(default=[]),
    signature_only: bool = False,
    sort: str = "recommended",
    page: int = Query(1, ge=1),
    page_size: int = Query(18, ge=1, le=48),
):
    if mood and mood not in MOODS:
        raise HTTPException(422, f"unknown mood {mood!r}")
    if sort not in SORTS:
        raise HTTPException(422, f"unknown sort {sort!r}")
    if (check_in is None) != (check_out is None):
        raise HTTPException(422, "give both check_in and check_out, or neither")

    where: list[str] = ["TRUE"]
    p: dict[str, Any] = {"adults": adults}
    if city_id:
        where.append("h.city_id = %(city_id)s"); p["city_id"] = city_id
    if landmark_id:
        where.append("EXISTS (SELECT 1 FROM hotel_landmarks x WHERE x.hotel_id = h.hotel_id AND x.landmark_id = %(landmark_id)s)")
        p["landmark_id"] = landmark_id
    if q:
        where.append("h.search_doc @@ websearch_to_tsquery('english', %(q)s)"); p["q"] = q
    if mood:
        where.append(MOODS[mood][1])
    if min_price is not None:
        where.append("price.from_price >= %(min_price)s"); p["min_price"] = min_price
    if max_price is not None:
        where.append("price.from_price <= %(max_price)s"); p["max_price"] = max_price
    if stars:
        where.append("h.star_rating = ANY(%(stars)s)"); p["stars"] = stars
    if types:
        where.append("h.property_type::text = ANY(%(types)s)"); p["types"] = types
    if amenities:
        # relational division again: hotels that have ALL the requested amenities
        where.append("(SELECT count(*) FROM hotel_amenities ha WHERE ha.hotel_id = h.hotel_id AND ha.amenity_id = ANY(%(amenities)s)) = %(n_amen)s")
        p["amenities"], p["n_amen"] = amenities, len(set(amenities))
    if signature_only:
        where.append("h.is_signature")
    where.append("EXISTS (SELECT 1 FROM room_types rt WHERE rt.hotel_id = h.hotel_id AND rt.max_adults * 3 >= %(adults)s)")

    landmark_join = ""
    if landmark_id:
        landmark_join = """LEFT JOIN LATERAL (SELECT hl.distance_km FROM hotel_landmarks hl
                           WHERE hl.hotel_id = h.hotel_id AND hl.landmark_id = %(landmark_id)s) dist ON true"""
    else:
        landmark_join = "LEFT JOIN LATERAL (SELECT NULL::numeric AS distance_km) dist ON true"

    base = f"""
        FROM hotels h
        JOIN cities c ON c.city_id = h.city_id
        JOIN states s ON s.state_code = c.state_code
        JOIN LATERAL (SELECT min(base_price) AS from_price FROM room_types rt WHERE rt.hotel_id = h.hotel_id) price ON true
        JOIN v_hotel_photo ph ON ph.hotel_id = h.hotel_id
        {landmark_join}
        WHERE {' AND '.join(f'({w})' for w in where)}"""

    trace = Trace()
    with transaction(read_only=True) as conn:
        total = fetch_one(conn, f"SELECT count(*) AS n {base}", p, trace)["n"]
        p.update(limit=page_size, offset=(page - 1) * page_size)
        rows = fetch(conn, f"""
            SELECT h.hotel_id, h.hotel_name, h.property_type, h.star_rating, h.is_signature, h.tagline,
                   h.locality, c.city_name, s.state_name, h.avg_rating, h.review_count,
                   price.from_price, dist.distance_km, ph.photo_url, ph.photo_caption,
                   (SELECT array_agg(a.amenity_name ORDER BY a.category, a.amenity_name)
                    FROM hotel_amenities ha JOIN amenities a USING (amenity_id)
                    WHERE ha.hotel_id = h.hotel_id AND a.category IN ('WELLNESS','DINING','EXPERIENCE')) AS highlights
            {base}
            ORDER BY {SORTS[sort]}
            LIMIT %(limit)s OFFSET %(offset)s""", p, trace)

        if check_in and rows:
            # price & availability for the chosen dates — only for this page of results
            stay = fetch(conn, """
                SELECT a.hotel_id, sum(a.free_rooms) AS free_rooms,
                       min(fn_stay_total(a.room_type_id, %(ci)s, %(co)s)) FILTER (WHERE a.free_rooms > 0) AS stay_total
                FROM (SELECT h.hotel_id, f.* FROM unnest(%(ids)s::int[]) AS h(hotel_id)
                      CROSS JOIN LATERAL fn_available_rooms(h.hotel_id, %(ci)s, %(co)s) f) a
                GROUP BY a.hotel_id""",
                {"ids": [r["hotel_id"] for r in rows], "ci": check_in, "co": check_out}, trace)
            by_id = {s["hotel_id"]: s for s in stay}
            for r in rows:
                r["free_rooms"] = by_id.get(r["hotel_id"], {}).get("free_rooms", 0)
                r["stay_total"] = by_id.get(r["hotel_id"], {}).get("stay_total")
    return {"data": {"total": total, "page": page, "page_size": page_size, "results": rows},
            "trace": trace.steps}


@router.get("/amenities")
def amenity_list():
    with transaction(read_only=True) as conn:
        rows = fetch(conn, """
            SELECT a.amenity_id, a.amenity_name, a.category, count(ha.hotel_id) AS hotels
            FROM amenities a LEFT JOIN hotel_amenities ha USING (amenity_id)
            GROUP BY a.amenity_id ORDER BY a.category, a.amenity_name""")
    return {"data": rows}


@router.get("/hotels/{hotel_id}")
def hotel_detail(hotel_id: int):
    trace = Trace()
    with transaction(read_only=True) as conn:
        hotel = fetch_one(conn, """
            SELECT h.hotel_id, h.hotel_name, h.property_type, h.star_rating, h.is_signature, h.tagline,
                   h.description, h.locality, h.address, h.latitude, h.longitude,
                   h.check_in_time, h.check_out_time, h.avg_rating, h.review_count, h.source,
                   c.city_id, c.city_name, s.state_code, s.state_name, s.region
            FROM hotels h JOIN cities c USING (city_id) JOIN states s USING (state_code)
            WHERE h.hotel_id = %s""", (hotel_id,), trace)
        if not hotel:
            raise HTTPException(404, "hotel not found")
        hotel["amenities"] = fetch(conn, """
            SELECT a.amenity_id, a.amenity_name, a.category
            FROM hotel_amenities ha JOIN amenities a USING (amenity_id)
            WHERE ha.hotel_id = %s ORDER BY a.category, a.amenity_name""", (hotel_id,), trace)
        hotel["landmarks"] = fetch(conn, """
            SELECT l.landmark_id, l.landmark_name, l.category, hl.distance_km
            FROM hotel_landmarks hl JOIN landmarks l USING (landmark_id)
            WHERE hl.hotel_id = %s
            ORDER BY hl.distance_km NULLS LAST, l.landmark_name LIMIT 10""", (hotel_id,), trace)
        hotel["room_types"] = fetch(conn, """
            SELECT rt.room_type_id, rt.type_name, rt.bed_type, rt.max_adults, rt.max_children,
                   rt.area_sqft, rt.base_price, count(r.room_id) AS rooms
            FROM room_types rt LEFT JOIN rooms r USING (room_type_id)
            WHERE rt.hotel_id = %s GROUP BY rt.room_type_id ORDER BY rt.base_price""", (hotel_id,), trace)
        hotel["rating_breakdown"] = fetch(conn, """
            SELECT r.rating, count(*) AS reviews
            FROM reviews r JOIN bookings b USING (booking_id)
            WHERE b.hotel_id = %s GROUP BY r.rating ORDER BY r.rating DESC""", (hotel_id,), trace)
        hotel["reviews"] = fetch(conn, """
            SELECT r.rating, r.title, r.body, r.created_at::date AS posted,
                   g.first_name, left(g.last_name, 1) AS last_initial, hc.city_name AS from_city, b.nights
            FROM reviews r JOIN bookings b USING (booking_id) JOIN guests g USING (guest_id)
            LEFT JOIN cities hc ON hc.city_id = g.home_city_id
            WHERE b.hotel_id = %s ORDER BY r.created_at DESC LIMIT 6""", (hotel_id,), trace)
        hotel["nearby"] = fetch(conn, """
            SELECT v.hotel_id, v.hotel_name, v.property_type, v.star_rating, v.avg_rating, v.from_price, v.locality, v.photo_url
            FROM v_hotel_cards v WHERE v.city_id = %s AND v.hotel_id <> %s
            ORDER BY v.is_signature DESC, v.review_count DESC LIMIT 4""", (hotel["city_id"], hotel_id), trace)
        hotel["media"] = fetch(conn, "SELECT media_id, title FROM lab.hotel_media WHERE hotel_id = %s",
                               (hotel_id,), trace)
        hotel["photo"] = fetch_one(conn, "SELECT photo_url, photo_url_hd, photo_credit, photo_caption FROM v_hotel_photo WHERE hotel_id = %s",
                                   (hotel_id,), trace)
        # the neighbourhood in pictures: photographed landmarks nearby, then the city
        hotel["gallery"] = fetch(conn, """
            SELECT * FROM (
                SELECT l.landmark_name AS caption, l.photo_url, l.photo_url_hd, l.photo_credit, hl.distance_km
                FROM hotel_landmarks hl JOIN landmarks l USING (landmark_id)
                WHERE hl.hotel_id = %(h)s AND l.photo_url IS NOT NULL
                UNION
                SELECT c.city_name, c.photo_url, c.photo_url_hd, c.photo_credit, NULL
                FROM hotels x JOIN cities c USING (city_id) WHERE x.hotel_id = %(h)s AND c.photo_url IS NOT NULL
            ) g ORDER BY distance_km NULLS LAST LIMIT 6""", {"h": hotel_id}, trace)
    return {"data": hotel, "trace": trace.steps}


@router.get("/hotels/{hotel_id}/availability")
def availability(hotel_id: int, check_in: date, check_out: date, rooms: int = Query(1, ge=1, le=6)):
    trace = Trace()
    with transaction(read_only=True) as conn:
        rows = fetch(conn, """
            SELECT a.*, CASE WHEN a.free_rooms >= %(rooms)s
                             THEN fn_stay_total(a.room_type_id, %(ci)s, %(co)s, %(rooms)s) END AS stay_total
            FROM fn_available_rooms(%(hid)s, %(ci)s, %(co)s) a""",
            {"hid": hotel_id, "ci": check_in, "co": check_out, "rooms": rooms}, trace)
    return {"data": rows, "trace": trace.steps}


@router.get("/quote")
def quote(room_type_id: int, check_in: date, check_out: date, rooms: int = Query(1, ge=1, le=6)):
    """Night-by-night price breakdown — the 'price for two nights' retrieval."""
    trace = Trace()
    with transaction(read_only=True) as conn:
        nights = fetch(conn, "SELECT * FROM fn_quote_stay(%s, %s, %s, %s)",
                       (room_type_id, check_in, check_out, rooms), trace)
        subtotal = sum(n["nightly_rate"] for n in nights) * rooms
        tax = sum(n["gst_amount"] for n in nights) * rooms
    return {"data": {"nights": nights, "rooms": rooms, "subtotal": round(subtotal, 2),
                     "tax": round(tax, 2), "total": round(subtotal + tax, 2)},
            "trace": trace.steps}
