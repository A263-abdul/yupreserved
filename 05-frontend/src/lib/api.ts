/**
 * Typed client for the YupReserved API (03-backend).
 * Every response carries a `trace` — the SQL the backend ran — which is pushed
 * into the trace store so the "Under the hood" drawer can show it.
 */
import { storage } from "./storage";
import { pushTrace } from "./traceStore";

/** signed session token from /auth/verify, sent as "Authorization: Bearer …" */
export const authToken = {
  get: () => storage.get("yup-token"),
  set: (t: string | null) => storage.set("yup-token", t),
};

export type TraceStep = { sql: string; params: unknown; rows: number; ms: number };

export class ApiError extends Error {
  status: number;
  body: DbError;
  constructor(status: number, body: DbError) {
    super(body.error || body.detail || "Request failed");
    this.status = status;
    this.body = body;
  }
}

/** Shape of a database rule violation, explained by the backend (errors.py). */
export type DbError = {
  error: string;
  detail?: string | null;
  hint?: string | null;
  sqlstate?: string | null;
  constraint?: string | null;
  table?: string | null;
  rule?: string;
  raised_in?: string | null;
};

async function request<T>(path: string, init?: RequestInit, label?: string): Promise<T> {
  let res: Response;
  const token = authToken.get();
  try {
    res = await fetch(path, {
      ...init,
      headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
    });
  } catch {
    throw new ApiError(0, { error: "Can't reach the YupReserved server. Is the backend running on port 8000?" });
  }
  const body = await res.json().catch(() => ({}));
  if (res.status === 401 && token) {
    authToken.set(null);
    window.dispatchEvent(new Event("yup:signed-out"));
  }
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg;
    throw new ApiError(res.status, { error: body.error ?? detail ?? res.statusText, ...body, detail });
  }
  if (body.trace?.length) pushTrace(label ?? path, body.trace);
  return body.data as T;
}

const qs = (params: Record<string, unknown>) => {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => u.append(k, String(x)));
    else u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
};

// ── types ──────────────────────────────────────────────────────────────────
export type HotelCard = {
  hotel_id: number;
  hotel_name: string;
  property_type: string;
  star_rating: number;
  is_signature?: boolean;
  tagline?: string | null;
  locality?: string | null;
  city_name: string;
  state_name?: string;
  avg_rating: number | null;
  review_count: number;
  from_price: number;
  distance_km?: number | null;
  highlights?: string[] | null;
  free_rooms?: number;
  stay_total?: number | null;
  photo_url?: string | null;
  photo_credit?: string | null;
  photo_caption?: string | null;
};

export type GalleryPhoto = { caption: string; photo_url: string; photo_url_hd: string | null; photo_credit: string; distance_km: number | null };

export type Destination = { kind: "city" | "landmark" | "hotel"; id: number; label: string; sublabel: string; hotels: number | null };

export type RoomType = {
  room_type_id: number; type_name: string; bed_type: string; max_adults: number; max_children: number;
  area_sqft: number; base_price: number; rooms: number;
};

export type HotelDetail = HotelCard & {
  description: string; address: string; latitude: number; longitude: number; check_in_time: string;
  check_out_time: string; city_id: number; state_code: string; region: string; source: string;
  amenities: { amenity_id: number; amenity_name: string; category: string }[];
  landmarks: { landmark_id: number; landmark_name: string; category: string; distance_km: number | null }[];
  room_types: RoomType[];
  rating_breakdown: { rating: number; reviews: number }[];
  reviews: { rating: number; title: string; body: string | null; posted: string; first_name: string; last_initial: string; from_city: string | null; nights: number }[];
  nearby: HotelCard[];
  media: { media_id: number; title: string }[];
  photo: { photo_url: string | null; photo_url_hd: string | null; photo_credit: string | null; photo_caption: string | null } | null;
  gallery: GalleryPhoto[];
};

export type Availability = {
  room_type_id: number; type_name: string; base_price: number; max_adults: number; max_children: number;
  total_rooms: number; free_rooms: number; stay_total: number | null;
};

export type QuoteNight = {
  night: string; day_name: string; season_name: string | null; base_price: number; season_multiplier: number;
  weekend_multiplier: number; nightly_rate: number; gst_rate: number; gst_amount: number; rooms: number; night_total: number;
};
export type Quote = { nights: QuoteNight[]; rooms: number; subtotal: number; tax: number; total: number };

export type Guest = {
  guest_id: number; first_name: string; last_name: string; phone: string; email: string;
  date_of_birth: string; id_type: string; home_city_id: number | null; home_city: string | null;
};

export type BookingSummary = {
  booking_id: number; booking_ref: string; status: string; guest_id: number; guest_name: string;
  hotel_id: number; hotel_name: string; city_name: string; check_in: string; check_out: string; nights: number;
  adults: number; children: number; rooms: number; subtotal: number; tax: number; total: number; paid: number;
  refunded: number; booked_at: string; property_type?: string; locality?: string; reviewed?: boolean;
};

export type SearchParams = {
  city_id?: number; landmark_id?: number; q?: string; mood?: string; check_in?: string; check_out?: string;
  adults?: number; min_price?: number; max_price?: number; stars?: number[]; types?: string[];
  amenities?: number[]; signature_only?: boolean; sort?: string; page?: number; page_size?: number;
};

// ── endpoints ──────────────────────────────────────────────────────────────
export const api = {
  stats: () => request<Record<string, number>>("/api/stats"),
  moods: () => request<{ key: string; label: string }[]>("/api/moods"),
  destinations: (q: string) => request<Destination[]>(`/api/destinations${qs({ q })}`, undefined, "Search box"),
  featured: () =>
    request<{ stays: HotelCard[];
      cities: { city_id: number; city_name: string; state_name: string; hotels: number; from_price: number; photo_url: string | null; photo_credit: string | null }[];
      seasons: { season_name: string; start_date: string; end_date: string; multiplier: number }[];
      hero: import("../components/Photo").HeroSlide[] }>("/api/featured", undefined, "Home page"),
  search: (p: SearchParams) =>
    request<{ total: number; page: number; page_size: number; results: HotelCard[] }>(`/api/search${qs(p)}`, undefined, "Search results"),
  amenities: () => request<{ amenity_id: number; amenity_name: string; category: string; hotels: number }[]>("/api/amenities"),
  hotel: (id: number) => request<HotelDetail>(`/api/hotels/${id}`, undefined, "Hotel page"),
  availability: (id: number, check_in: string, check_out: string, rooms = 1) =>
    request<Availability[]>(`/api/hotels/${id}/availability${qs({ check_in, check_out, rooms })}`, undefined, "Room availability"),
  quote: (room_type_id: number, check_in: string, check_out: string, rooms = 1) =>
    request<Quote>(`/api/quote${qs({ room_type_id, check_in, check_out, rooms })}`, undefined, "Price breakdown"),
  sendOtp: (phone: string) =>
    request<{ sent: boolean; expires_in: number; resend_in: number; provider: string; demo_otp?: string }>(
      "/api/auth/otp", { method: "POST", body: JSON.stringify({ phone }) }, "Send OTP"),
  verifyOtp: (phone: string, otp: string) =>
    request<{ guest: Guest | null; is_new: boolean; token: string }>("/api/auth/verify", { method: "POST", body: JSON.stringify({ phone, otp }) }, "Verify OTP"),
  demoGuests: () => request<{ guest_id: number; first_name: string; last_name: string; phone: string; bookings: number }[]>("/api/guests/demo"),
  createGuest: (g: Record<string, unknown>) =>
    request<{ guest: Guest; token: string }>("/api/guests", { method: "POST", body: JSON.stringify(g) }, "Create account"),
  book: (b: Record<string, unknown>) =>
    request<{ booking_id: number; booking_ref: string; total_amount: number; status: string }>("/api/bookings", { method: "POST", body: JSON.stringify(b) }, "Booking (fn_book_stay)"),
  trips: (guestId: number) => request<BookingSummary[]>(`/api/guests/${guestId}/bookings`, undefined, "My trips"),
  booking: (ref: string) => request<BookingSummary & { rooms_detail: any[]; payments: any[] }>(`/api/bookings/${ref}`, undefined, "Booking details"),
  cancel: (ref: string) => request<{ booking_ref: string; refund_amount: number }>(`/api/bookings/${ref}/cancel`, { method: "POST" }, "Cancel (sp_cancel_booking)"),
  review: (ref: string, r: { rating: number; title: string; body?: string }) =>
    request<{ review_id: number }>(`/api/bookings/${ref}/review`, { method: "POST", body: JSON.stringify(r) }, "Write review"),

  lab: {
    overview: () => request<any[]>("/api/lab/overview"),
    table: (name: string, page = 1, page_size = 25) =>
      request<{ table: string; columns: string[]; rows: unknown[][]; page: number; page_size: number; approx_total: number; sql: string }>(
        `/api/lab/tables/${name}${qs({ page, page_size })}`),
    schema: (name: string) => request<any>(`/api/lab/tables/${name}/schema`),
    list: (kind: "queries" | "plans" | "why") => request<LabEntry[]>(`/api/lab/${kind}`),
    run: (kind: "queries" | "plans" | "why", name: string) => request<any>(`/api/lab/${kind}/${name}/run`, { method: "POST" }),
    explainQuery: (name: string) => request<any>(`/api/lab/queries/${name}/explain`, { method: "POST" }),
    concurrency: () => request<{ name: string; doc: string }[]>("/api/lab/concurrency"),
    runConcurrency: (name: string) => request<any>(`/api/lab/concurrency/${name}/run`, { method: "POST" }),
  },
};

export type LabEntry = { name: string; title: string; topic: string; algebra: string; explain: string; setup: string; sql: string; file: string };
