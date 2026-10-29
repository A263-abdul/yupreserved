# 01 · Dataset

```
raw/          the source file, untouched
reference/    small hand-made reference tables used by the pipeline
pipeline/     vocab.py (cleaning rules) · build_dataset.py (the pipeline)
processed/    one clean CSV per database table + _manifest.json + _amenity_mapping.csv
```

## Source

**Indian Hotels on Goibibo** — 4,000 Indian hotel listings crawled from goibibo.com in 2016,
published by PromptCloud on Kaggle (`PromptCloudHQ/hotels-on-goibibo`) and mirrored on Hugging Face
(`jason1966/PromptCloudHQ_hotels-on-goibibo`). 36 columns: name, address, locality, city, state,
latitude/longitude, star rating, property type, room type, room count, hotel and room facilities,
points of interest, review scores and more.

## What is real and what is generated

| data | origin |
|------|--------|
| 3,565 hotels: names, addresses, cities, states, coordinates, stars, property types, facilities, nearby points of interest, room counts, check-in/out times | **real** (the dataset) |
| 95 famous landmarks with coordinates (Gateway of India, Charminar…) | real places, coordinates curated in `reference/landmarks_curated.csv` |
| 16 festival / holiday seasons 2025–27 | real festival dates, multipliers chosen by us |
| 18 *Signature* hotels | **original**, written for YupReserved (`reference/signature_stays.json`) |
| room-type tiers, room prices, guests, bookings, reviews | **simulated** (seed 2026) — no public dataset contains them |
| nightly rates, GST and payments | computed inside PostgreSQL by `fn_quote_stay` |

## Cleaning rules (counts in `processed/_manifest.json`)

| rule | effect |
|------|--------|
| C1 | drop duplicate (name, city) listings |
| C2 | drop coordinates outside India's bounding box |
| C3 | drop listings of big hotel chains (YupReserved is an independent platform) — 431 rows |
| C4 | keep only known states and property types |
| — | state spellings → 2-letter codes; Hyderabad → Telangana, Leh → Ladakh, Chandigarh → UT, Orissa → Odisha |
| — | Cochin / Ernakulam → Kochi; ALL-CAPS names title-cased; HTML entities decoded |
| — | 356 raw facility labels → 52 amenities (see `processed/_amenity_mapping.csv`) |
| — | check-in / check-out times parsed from the policy text |

## Pricing model

`base_price = star_base × property_type_factor × city_factor × review_factor × noise`, rounded to
₹x,x99 and tiered per room type. Resulting quartiles: ₹1,699 / ₹2,699 / ₹5,299 per night.

## Rebuild

```bash
python3 01-dataset/pipeline/build_dataset.py     # ~45 s, deterministic
```
