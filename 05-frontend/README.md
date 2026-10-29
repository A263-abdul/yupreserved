# 05 · Frontend — the YupReserved website

```bash
npm install
npm run dev          # http://localhost:5173  (proxies /api to the backend on :8000)
npm run build        # static files in dist/ — deployable to any static host (Vercel, Netlify, Cloudflare Pages)
```

## Creative direction

**Vintage Indian railway posters, printed on handmade paper.** Every place gets a poster drawn
in code (`src/art/Poster.tsx`): flat layered silhouettes of the Gateway of India over the harbour,
Charminar's minarets, a palace on Lake Pichola, backwaters and palms, tea hills, ghats with
evening lamps. Each hotel has its own seed and time of day, and the posters weigh a few kB,
so pages load instantly on a slow phone connection and work offline.

- **Mark** — a ticket stub with a jaali rosette punched through it: the moment a trip becomes real.
  Wordmark: a soft, slightly wonky italic *Yup* beside a quiet *reserved*.
- **Palette** — paper `#F6EFE4`, indigo ink `#1E2233`, sindoor `#C4472B`, haldi `#E3A72F`,
  peacock `#1F6F6B`. Dark mode is a monsoon night in indigo, designed separately.
- **Type** — Fraunces (display, with personality), Hanken Grotesk (interface),
  Tiro Devanagari Hindi (हिंदी), JetBrains Mono (SQL).
- **Motion** — slow headline type-setting, layered parallax on hero posters, calm scroll reveals,
  spring micro-interactions; everything settles when the OS asks for reduced motion.
- **References** — Aman (restraint and whitespace), Six Senses (story before amenities),
  The Hoxton (warm, confident voice).

## Pages

Home · Search results (filters in the URL, compare up to 3) · Hotel (story, neighbourhood with
walking times, rooms priced for your dates, night-by-night breakdown, reviews) · Checkout (phone +
OTP, UPI first, honest price) · Confirmation · My trips (cancel with refund preview, review) ·
Under the hood (the DBMS lab) · 404.

Every page shows its SQL through the floating **SQL · Under the hood** button.

## Code map

```
src/art/Poster.tsx        procedural poster scenes
src/components/           brand, layout, search, cards, overlays (sign-in, SQL drawer, compare), feedback states, motion
src/lib/                  api client (typed), formatting (₹, dates), i18n (EN / हिं), session, storage
src/pages/                one file per page
src/styles/global.css     design tokens (light + dark), textures
```
