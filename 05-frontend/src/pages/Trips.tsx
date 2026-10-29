/** My trips: upcoming and past stays, cancellations and reviews. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Poster } from "../art/Poster";
import { Empty, ErrorNote, Skeleton } from "../components/feedback";
import { Page } from "../components/motion";
import { api, type BookingSummary } from "../lib/api";
import { longDate, nightsBetween, rupees, TODAY } from "../lib/format";
import { useSession } from "../lib/session";

const STATUS_STYLE: Record<string, string> = {
  CONFIRMED: "bg-peacock/15 text-peacock", PENDING: "bg-haldi/20 text-ink", CHECKED_IN: "bg-haldi/25 text-ink",
  COMPLETED: "bg-ink/10 text-ink-2", CANCELLED: "bg-sindoor/15 text-sindoor", NO_SHOW: "bg-sindoor/10 text-sindoor",
};

export default function Trips() {
  const { guest, setAuthOpen } = useSession();
  const trips = useQuery({ queryKey: ["trips", guest?.guest_id], queryFn: () => api.trips(guest!.guest_id), enabled: !!guest });
  // lives here, not in the card: a cancelled trip moves to the other list and its card is re-created
  const [notice, setNotice] = useState<string | null>(null);

  if (!guest) {
    return (
      <Page className="mx-auto max-w-3xl px-4 sm:px-6">
        <Empty page title="Your trips live here" sub="Sign in with your mobile number to see bookings, cancel or leave a review."
          action={<button onClick={() => setAuthOpen(true)} className="rounded-full bg-sindoor px-6 py-3 font-semibold text-sindoor-ink">Sign in with OTP</button>} />
      </Page>
    );
  }
  const upcoming = trips.data?.filter((t) => t.check_out > TODAY && !["CANCELLED", "NO_SHOW"].includes(t.status)) ?? [];
  const past = trips.data?.filter((t) => !upcoming.includes(t)) ?? [];

  return (
    <Page className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6">
      <p className="eyebrow">Namaste, {guest.first_name}</p>
      <h1 className="display mt-2 text-5xl">My trips</h1>
      {notice && (
        <div role="status" className="mt-6 flex items-center justify-between gap-4 rounded-2xl border border-peacock/40 bg-peacock/[0.08] px-5 py-4">
          <p className="text-peacock">{notice}</p>
          <button onClick={() => setNotice(null)} className="text-sm text-ink-3 hover:text-ink" aria-label="Dismiss">✕</button>
        </div>
      )}
      {trips.error ? <div className="mt-8"><ErrorNote error={trips.error} onRetry={() => trips.refetch()} /></div> :
        !trips.data ? <div className="mt-8 space-y-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-36" />)}</div> :
        trips.data.length === 0 ? <Empty title="No trips yet" sub="Your first stay is a search away." action={<Link to="/stays" className="rounded-full bg-ink px-5 py-2.5 text-paper">Find a stay</Link>} /> : (
          <>
            <h2 className="display mt-10 text-2xl">Coming up <span className="text-ink-3">· {upcoming.length}</span></h2>
            <div className="mt-4 space-y-4">{upcoming.length ? upcoming.map((t) => <TripCard key={t.booking_id} t={t} onNotice={setNotice} />) : <p className="text-ink-3">Nothing planned. <Link to="/stays" className="text-sindoor">Plan something →</Link></p>}</div>
            <h2 className="display mt-14 text-2xl">Past & cancelled <span className="text-ink-3">· {past.length}</span></h2>
            <div className="mt-4 space-y-4">{past.map((t) => <TripCard key={t.booking_id} t={t} onNotice={setNotice} />)}</div>
          </>
        )}
      <section id="policy" className="mt-16 rounded-3xl bg-paper-2/60 p-6 text-sm text-ink-2">
        <p className="font-semibold text-ink">Cancellation policy</p>
        <p className="mt-1">7 or more days before check-in: full refund · 2–6 days: 50% · less than 2 days: no refund. Refunds go back to the original payment method.
          (Enforced by the stored procedure <code className="font-mono">sp_cancel_booking</code>.)</p>
      </section>
    </Page>
  );
}

function TripCard({ t, onNotice }: { t: BookingSummary; onNotice: (msg: string) => void }) {
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const days = nightsBetween(TODAY, t.check_in);
  const pct = days >= 7 ? 100 : days >= 2 ? 50 : 0;
  const net = Number(t.paid) - Number(t.refunded);
  const cancel = useMutation({
    mutationFn: () => api.cancel(t.booking_ref),
    onSuccess: (r) => {
      onNotice(`${t.hotel_name} (${r.booking_ref}) is cancelled. ${Number(r.refund_amount) > 0 ? `Refund of ${rupees(r.refund_amount, true)} is on its way to your original payment method.` : "No refund applies this close to check-in."}`);
      qc.invalidateQueries({ queryKey: ["trips"] });
    },
  });
  const canCancel = ["CONFIRMED", "PENDING"].includes(t.status) && t.check_in > TODAY;
  const canReview = t.status === "COMPLETED" && !t.reviewed;

  return (
    <article className="grid gap-4 rounded-3xl border border-line bg-card p-4 sm:grid-cols-[140px_1fr_auto]">
      <Poster city={t.city_name} propertyType={t.property_type} seed={t.hotel_id * 97} className="aspect-[4/3] rounded-2xl" />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[t.status] ?? ""}`}>{t.status.replace("_", " ")}</span>
          <span className="font-mono text-xs text-ink-3">{t.booking_ref}</span>
        </div>
        <Link to={`/stay/${t.hotel_id}`} className="display mt-1 block truncate text-2xl hover:text-sindoor">{t.hotel_name}</Link>
        <p className="text-sm text-ink-2">{t.city_name} · {longDate(t.check_in)} → {longDate(t.check_out)} · {t.nights}n · {t.rooms} room{t.rooms > 1 ? "s" : ""}</p>
        {cancel.error && <div className="mt-3"><ErrorNote error={cancel.error} compact /></div>}
        {reviewing && <ReviewForm bookingRef={t.booking_ref} onDone={() => { setReviewing(false); onNotice("Thanks — your review is live on the hotel page."); qc.invalidateQueries({ queryKey: ["trips"] }); }} />}
      </div>
      <div className="flex flex-col items-end justify-between gap-3 text-right">
        <div>
          <p className="text-lg font-semibold tabular">{rupees(t.total)}</p>
          {Number(t.refunded) > 0 && <p className="text-xs text-peacock">refunded {rupees(t.refunded)}</p>}
        </div>
        {canCancel && !confirming && <button onClick={() => setConfirming(true)} className="rounded-full border border-line px-4 py-2 text-sm hover:border-sindoor hover:text-sindoor">Cancel</button>}
        {canCancel && confirming && (
          <div className="rounded-2xl bg-paper-2 p-3 text-left text-xs">
            <p>Refund: <b>{pct}%</b> = {rupees((net * pct) / 100)} ({days} days before check-in)</p>
            <div className="mt-2 flex gap-2">
              <button onClick={() => cancel.mutate()} disabled={cancel.isPending} className="rounded-full bg-sindoor px-3 py-1.5 font-semibold text-sindoor-ink">{cancel.isPending ? "Cancelling…" : "Yes, cancel"}</button>
              <button onClick={() => setConfirming(false)} className="rounded-full border border-line px-3 py-1.5">Keep it</button>
            </div>
          </div>
        )}
        {canReview && !reviewing && <button onClick={() => setReviewing(true)} className="rounded-full bg-ink px-4 py-2 text-sm text-paper">Write a review</button>}
        {t.reviewed && <span className="text-xs text-ink-3">Reviewed ✓</span>}
      </div>
    </article>
  );
}

function ReviewForm({ bookingRef, onDone }: { bookingRef: string; onDone: () => void }) {
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const m = useMutation({ mutationFn: () => api.review(bookingRef, { rating, title, body }), onSuccess: onDone });
  return (
    <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="mt-3 space-y-2 rounded-2xl bg-paper-2/60 p-3">
      <div className="flex gap-1" role="radiogroup" aria-label="Rating">
        {[1, 2, 3, 4, 5].map((s) => (
          <button type="button" key={s} role="radio" aria-checked={rating === s} onClick={() => setRating(s)}
            className={`text-2xl ${s <= rating ? "text-haldi" : "text-line"}`}>★</button>
        ))}
      </div>
      <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="In one line…" className="w-full rounded-xl border border-line bg-paper px-3 py-2" />
      <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="What would you tell a friend?" rows={2} className="w-full rounded-xl border border-line bg-paper px-3 py-2" />
      <button disabled={m.isPending} className="rounded-full bg-sindoor px-4 py-2 text-sm font-semibold text-sindoor-ink">Post review</button>
      {m.error && <ErrorNote error={m.error} compact />}
    </form>
  );
}
