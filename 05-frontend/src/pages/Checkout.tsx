/**
 * Checkout — trustworthy, clear and fast.
 * One page, three short sections, the full price always visible.
 * "Confirm" calls fn_book_stay: rooms are locked, chosen, booked and paid
 * for inside ONE database transaction.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Photo } from "../components/Photo";
import { ErrorNote, Skeleton } from "../components/feedback";
import { Page } from "../components/motion";
import { api } from "../lib/api";
import { longDate, nightsBetween, rupees, TODAY } from "../lib/format";
import { useSession } from "../lib/session";
import { PriceTable } from "./Hotel";

type Method = "UPI" | "CARD" | "NETBANKING" | "PAY_AT_HOTEL";
const UPI_APPS = [["okaxis", "Google Pay"], ["ybl", "PhonePe"], ["paytm", "Paytm"], ["oksbi", "BHIM / SBI"]];

export default function Checkout() {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const { guest, setAuthOpen } = useSession();
  const hotelId = Number(sp.get("hotel"));
  const roomTypeId = Number(sp.get("room_type"));
  const checkIn = sp.get("check_in") ?? "";
  const checkOut = sp.get("check_out") ?? "";
  const rooms = Number(sp.get("rooms") ?? 1);
  const [adults, setAdults] = useState(Number(sp.get("adults") ?? 2));
  const [children, setChildren] = useState(0);
  const [method, setMethod] = useState<Method>("UPI");
  const [vpa, setVpa] = useState("");
  const [request, setRequest] = useState("");

  const hotel = useQuery({ queryKey: ["hotel", hotelId], queryFn: () => api.hotel(hotelId), enabled: !!hotelId });
  const quote = useQuery({ queryKey: ["quote", roomTypeId, checkIn, checkOut, rooms], queryFn: () => api.quote(roomTypeId, checkIn, checkOut, rooms), enabled: !!roomTypeId });
  const book = useMutation({
    mutationFn: () => api.book({
      room_type_id: roomTypeId, check_in: checkIn, check_out: checkOut, rooms, adults, children,
      method, upi_vpa: method === "UPI" ? vpa.trim().toLowerCase() : null, special_request: request || null,
    }),
    onSuccess: (r) => nav(`/booked/${r.booking_ref}`),
  });

  const room = hotel.data?.room_types.find((r) => r.room_type_id === roomTypeId);
  const nights = checkIn && checkOut ? nightsBetween(checkIn, checkOut) : 0;
  const vpaOk = /^[a-z0-9._-]{2,}@[a-z]{2,}$/i.test(vpa.trim());
  const canPay = !!guest && (method !== "UPI" || vpaOk) && !book.isPending;
  const daysToGo = checkIn ? nightsBetween(TODAY, checkIn) : 0;

  if (!roomTypeId) return <Page className="mx-auto max-w-xl p-10"><p>Pick a room first. <Link to="/stays" className="text-sindoor">Browse stays →</Link></p></Page>;

  const section = "rounded-[1.75rem] border border-line bg-card p-6";
  return (
    <Page className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6">
      <p className="eyebrow">Checkout · secure</p>
      <h1 className="display mt-2 text-4xl sm:text-5xl">Almost yours.</h1>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_420px]">
        <div className="space-y-6">
          {/* 1 · who */}
          <section className={section} aria-labelledby="who">
            <h2 id="who" className="display text-2xl"><span className="text-ink-3">1 ·</span> Who's travelling</h2>
            {guest ? (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">{guest.first_name} {guest.last_name}</p>
                  <p className="text-sm text-ink-3">+91 {guest.phone} · {guest.email}</p>
                </div>
                <span className="rounded-full bg-peacock/15 px-3 py-1 text-sm text-peacock">Signed in with OTP ✓</span>
              </div>
            ) : (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-paper-2/60 p-4">
                <p className="text-ink-2">Sign in with your mobile number to book. It takes ten seconds.</p>
                <button onClick={() => setAuthOpen(true)} className="rounded-full bg-ink px-5 py-2.5 text-paper">Sign in with OTP</button>
              </div>
            )}
            <div className="mt-5 grid grid-cols-2 gap-3 sm:max-w-sm">
              <Counter label="Adults" value={adults} min={1} max={(room?.max_adults ?? 2) * rooms + 2} onChange={setAdults} />
              <Counter label="Children" value={children} min={0} max={6} onChange={setChildren} />
            </div>
            {room && adults > room.max_adults * rooms && (
              <p className="mt-3 text-sm text-sindoor">Heads-up: {rooms} × {room.type_name} sleeps {room.max_adults * rooms} adults. The database will refuse this booking — that's the capacity trigger at work.</p>
            )}
            <label className="mt-5 block text-sm text-ink-2">Anything the hotel should know? <span className="text-ink-3">(optional)</span>
              <input value={request} onChange={(e) => setRequest(e.target.value)} maxLength={200} placeholder="Late arrival, ground floor for parents…"
                className="mt-1 w-full rounded-xl border border-line bg-paper px-4 py-3 text-ink" />
            </label>
          </section>

          {/* 2 · pay */}
          <section className={section} aria-labelledby="pay">
            <h2 id="pay" className="display text-2xl"><span className="text-ink-3">2 ·</span> Pay</h2>
            <div role="radiogroup" className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {([["UPI", "UPI"], ["CARD", "Card"], ["NETBANKING", "Net banking"], ["PAY_AT_HOTEL", "Pay at hotel"]] as [Method, string][]).map(([m, l]) => (
                <button key={m} role="radio" aria-checked={method === m} onClick={() => setMethod(m)}
                  className={`rounded-2xl border px-3 py-3 text-sm font-medium ${method === m ? "border-ink bg-ink text-paper" : "border-line hover:border-ink/40"}`}>
                  {l}{m === "UPI" && <span className="block text-[0.65rem] font-normal opacity-70">recommended</span>}
                </button>
              ))}
            </div>
            {method === "UPI" && (
              <div className="mt-5">
                <label className="text-sm text-ink-2" htmlFor="vpa">UPI ID</label>
                <input id="vpa" value={vpa} onChange={(e) => setVpa(e.target.value)} placeholder="yourname@okaxis" autoComplete="off"
                  className={`mt-1 w-full rounded-xl border bg-paper px-4 py-3 text-ink ${vpa && !vpaOk ? "border-sindoor" : "border-line"}`} />
                <div className="mt-2 flex flex-wrap gap-2">
                  {UPI_APPS.map(([h, l]) => (
                    <button key={h} type="button" onClick={() => setVpa(`${(guest?.first_name ?? "guest").toLowerCase()}@${h}`)}
                      className="rounded-full border border-line px-3 py-1 text-xs hover:border-ink">{l}</button>
                  ))}
                </div>
                <p className="mt-2 text-xs text-ink-3">Demo payment — nothing is charged. A collect request would appear in your UPI app.</p>
              </div>
            )}
            {method === "CARD" && <p className="mt-4 text-sm text-ink-2">Card entry is mocked in this demo; the payment is recorded as a successful card charge.</p>}
            {method === "NETBANKING" && <p className="mt-4 text-sm text-ink-2">You'd be redirected to your bank. In the demo the charge succeeds instantly.</p>}
            {method === "PAY_AT_HOTEL" && <p className="mt-4 text-sm text-ink-2">Your room is held; the payment is recorded as PENDING until you pay at check-in.</p>}
          </section>

          {/* 3 · policy */}
          <section className={section} aria-labelledby="policy">
            <h2 id="policy" className="display text-2xl"><span className="text-ink-3">3 ·</span> If plans change</h2>
            <ul className="mt-3 space-y-1 text-ink-2">
              <li>— Cancel 7+ days before check-in: <b className="text-ink">full refund</b></li>
              <li>— 2 to 6 days before: <b className="text-ink">50% refund</b></li>
              <li>— Less than 2 days: no refund</li>
            </ul>
            {checkIn && <p className="mt-2 text-sm text-peacock">You're {daysToGo} days out — free cancellation until {longDate(new Date(new Date(checkIn).getTime() - 7 * 864e5).toISOString().slice(0, 10))}.</p>}
          </section>

          {book.error && <ErrorNote error={book.error} />}
        </div>

        {/* summary */}
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="ticket-edge overflow-hidden rounded-[1.75rem] border border-line bg-card">
            <Photo src={hotel.data?.photo?.photo_url} alt="" city={hotel.data?.city_name} propertyType={hotel.data?.property_type} seed={hotelId * 97} className="h-40" />
            <div className="p-6">
              {hotel.data ? (
                <>
                  <p className="eyebrow">{hotel.data.city_name}</p>
                  <p className="display mt-1 text-2xl">{hotel.data.hotel_name}</p>
                  <p className="mt-1 text-sm text-ink-2">{rooms} × {room?.type_name}</p>
                  <p className="text-sm text-ink-2">{longDate(checkIn)} → {longDate(checkOut)} · {nights} night{nights > 1 ? "s" : ""}</p>
                </>
              ) : <Skeleton className="h-20" />}
              <div className="mt-5">{quote.data ? <PriceTable q={quote.data} /> : quote.error ? <ErrorNote error={quote.error} compact /> : <Skeleton className="h-40" />}</div>
              <button disabled={!canPay || !quote.data} onClick={() => book.mutate()}
                className="mt-6 w-full rounded-2xl bg-sindoor py-4 text-lg font-semibold text-sindoor-ink transition disabled:opacity-40">
                {book.isPending ? "Locking your room…" : !guest ? "Sign in to book" : `Confirm & pay ${quote.data ? rupees(quote.data.total) : ""}`}
              </button>
              <p className="mt-3 text-center text-xs text-ink-3">The price above is final. No convenience fee.</p>
            </div>
          </div>
        </aside>
      </div>
    </Page>
  );
}

function Counter({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (n: number) => void }) {
  return (
    <div className="rounded-2xl border border-line px-4 py-2">
      <p className="text-xs text-ink-3">{label}</p>
      <div className="flex items-center justify-between">
        <button aria-label={`Fewer ${label}`} onClick={() => onChange(Math.max(min, value - 1))} className="px-2 text-xl text-ink-2">−</button>
        <span className="text-lg font-semibold tabular" aria-live="polite">{value}</span>
        <button aria-label={`More ${label}`} onClick={() => onChange(Math.min(max, value + 1))} className="px-2 text-xl text-ink-2">+</button>
      </div>
    </div>
  );
}
