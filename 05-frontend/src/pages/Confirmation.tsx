/** Success: a ticket stub you'd want to screenshot. */
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Link, useParams } from "react-router-dom";
import { Poster } from "../art/Poster";
import { Mark } from "../components/brand";
import { ErrorNote, Skeleton } from "../components/feedback";
import { Page } from "../components/motion";
import { api } from "../lib/api";
import { longDate, rupees } from "../lib/format";

export default function Confirmation() {
  const { ref = "" } = useParams();
  const b = useQuery({ queryKey: ["booking", ref], queryFn: () => api.booking(ref) });
  return (
    <Page className="mx-auto max-w-3xl px-4 pb-16 pt-10 sm:px-6">
      {b.error ? <ErrorNote error={b.error} /> : !b.data ? <Skeleton className="h-[32rem]" /> : (
        <>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="eyebrow text-center">Booking confirmed</motion.p>
          <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="display mt-2 text-center text-5xl sm:text-6xl">Yup. It's reserved.</motion.h1>
          <p className="hindi mt-2 text-center text-xl text-ink-3">हाँ, आपकी जगह पक्की।</p>

          <motion.div initial={{ opacity: 0, y: 40, rotate: -2 }} animate={{ opacity: 1, y: 0, rotate: 0 }}
            transition={{ delay: 0.25, type: "spring", damping: 18, stiffness: 120 }}
            className="ticket-edge mt-10 overflow-hidden rounded-[2rem] border border-line bg-card shadow-[0_40px_80px_-50px_rgb(var(--shadow)/0.7)]">
            <div className="grid sm:grid-cols-[1fr_200px]">
              <div className="p-7">
                <div className="flex items-center gap-2"><Mark size={22} /><span className="eyebrow">Boarding pass for a good night</span></div>
                <p className="display mt-4 text-3xl">{b.data.hotel_name}</p>
                <p className="text-ink-2">{b.data.city_name}</p>
                <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
                  <div><dt className="text-ink-3">Check-in</dt><dd className="font-semibold">{longDate(b.data.check_in)}</dd></div>
                  <div><dt className="text-ink-3">Check-out</dt><dd className="font-semibold">{longDate(b.data.check_out)}</dd></div>
                  <div><dt className="text-ink-3">Guests</dt><dd className="font-semibold">{b.data.adults} adults{b.data.children ? `, ${b.data.children} children` : ""}</dd></div>
                  <div><dt className="text-ink-3">Rooms</dt><dd className="font-semibold">{b.data.rooms_detail.map((r) => `${r.room_number}`).join(", ")} · {b.data.rooms_detail[0]?.type_name}</dd></div>
                </dl>
              </div>
              <div className="flex flex-col items-center justify-center gap-2 border-t border-dashed border-line bg-paper-2/60 p-6 sm:border-l sm:border-t-0">
                <p className="eyebrow">Reference</p>
                <p className="font-mono text-2xl font-semibold tracking-widest">{b.data.booking_ref}</p>
                <p className="mt-3 text-3xl font-semibold tabular">{rupees(b.data.total)}</p>
                <p className="text-xs text-ink-3">{b.data.payments.at(-1)?.method === "PAY_AT_HOTEL" ? "pay at the hotel" : `paid by ${b.data.payments.at(-1)?.method}`}</p>
              </div>
            </div>
            <Poster city={b.data.city_name} seed={b.data.hotel_id * 97} className="h-28" />
          </motion.div>

          <div className="mt-8 rounded-2xl border border-line p-5 text-sm">
            <p className="font-semibold">What just happened in the database</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-ink-2">
              <li><code className="font-mono">fn_book_stay</code> locked every room of this type (<code className="font-mono">SELECT … FOR UPDATE</code>) so nobody else could take it.</li>
              <li>It picked free rooms, inserted one row in <code className="font-mono">bookings</code> and {b.data.rooms_detail.length} in <code className="font-mono">booking_rooms</code>; triggers checked overlap and capacity.</li>
              <li>A <code className="font-mono">payments</code> row recorded the charge — and all of it committed together, or not at all.</li>
            </ol>
          </div>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/trips" className="rounded-full bg-ink px-6 py-3 text-paper">See my trips</Link>
            <Link to={`/stay/${b.data.hotel_id}`} className="rounded-full border border-line px-6 py-3">Back to the hotel</Link>
          </div>
        </>
      )}
    </Page>
  );
}
