/**
 * Sign in with phone + OTP.
 * The server generates the code, stores only its hash, expires it after
 * 5 minutes and allows 5 tries; this dialog shows those limits honestly.
 * On Android Chrome the code is read from the SMS automatically (WebOTP).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, authToken, type Guest } from "../lib/api";
import { useSession } from "../lib/session";
import { Mark } from "./brand";
import { ErrorNote } from "./feedback";

function useCountdown(seconds: number, key: unknown) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    setLeft(seconds);
    const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [seconds, key]);
  return left;
}

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export function AuthDialog() {
  const { authOpen, setAuthOpen, signIn } = useSession();
  const [step, setStep] = useState<"phone" | "otp" | "profile">("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [profile, setProfile] = useState({ first_name: "", last_name: "", email: "", date_of_birth: "1995-06-15", id_type: "PAN", id_number: "" });
  const dialog = useRef<HTMLDialogElement>(null);
  const demo = useQuery({ queryKey: ["demo-guests"], queryFn: api.demoGuests, enabled: authOpen });

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (authOpen && !d.open) d.showModal();
    if (!authOpen && d.open) d.close();
  }, [authOpen]);

  const reset = () => { setStep("phone"); setOtp(""); setToken(null); send.reset(); verify.reset(); create.reset(); };
  const done = (g: Guest, t: string) => { signIn(g, t); setAuthOpen(false); reset(); };

  const send = useMutation({ mutationFn: () => api.sendOtp(phone), onSuccess: () => { setOtp(""); setStep("otp"); } });
  const verify = useMutation({
    mutationFn: (code: string) => api.verifyOtp(phone, code),
    onSuccess: (r) => (r.guest ? done(r.guest, r.token) : (setToken(r.token), setStep("profile"))),
    onError: () => setOtp(""),
  });
  const create = useMutation({
    mutationFn: () => {
      authToken.set(token);          // the account call is authorised by the verified-OTP token
      return api.createGuest(profile);
    },
    onSuccess: (r) => done(r.guest, r.token),
  });

  const expiresIn = useCountdown(send.data?.expires_in ?? 300, send.data);
  const resendIn = useCountdown(send.data?.resend_in ?? 30, send.data);

  // WebOTP: Android Chrome offers to fill the code from the SMS
  useEffect(() => {
    if (step !== "otp" || !("OTPCredential" in window)) return;
    const ac = new AbortController();
    (navigator.credentials as any).get({ otp: { transport: ["sms"] }, signal: ac.signal })
      .then((c: any) => { if (c?.code) { setOtp(c.code); verify.mutate(c.code); } })
      .catch(() => {});
    return () => ac.abort();
  }, [step]);  // eslint-disable-line react-hooks/exhaustive-deps

  const typeOtp = (v: string) => {
    const code = v.replace(/\D/g, "").slice(0, 6);
    setOtp(code);
    if (code.length === 6 && !verify.isPending) verify.mutate(code);
  };

  const input = "w-full rounded-xl border border-line bg-paper px-4 py-3 text-ink focus:border-ink focus:outline-none";
  return (
    <dialog ref={dialog} onClose={() => { setAuthOpen(false); reset(); }}
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-[1.75rem] border border-line bg-card p-0 text-ink shadow-2xl backdrop:bg-ink/40 backdrop:backdrop-blur-sm">
      <div className="p-6 sm:p-8">
        <div className="flex items-center justify-between">
          <Mark size={34} />
          <button onClick={() => setAuthOpen(false)} className="rounded-full px-3 py-1 text-ink-3 hover:bg-paper-2" aria-label="Close">✕</button>
        </div>

        {step === "phone" && (
          <form onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
            <h2 className="display mt-4 text-3xl">Welcome. Yup, just your number.</h2>
            <p className="mt-1 text-ink-2">We'll text you a 6-digit code. No passwords.</p>
            <label className="mt-6 block text-sm font-medium" htmlFor="phone">Mobile number</label>
            <div className="mt-2 flex items-center gap-2 rounded-xl border border-line bg-paper px-4 focus-within:border-ink">
              <span className="text-ink-3">+91</span>
              <input id="phone" inputMode="numeric" autoComplete="tel-national" maxLength={10} value={phone} autoFocus
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))} placeholder="98765 43210"
                className="w-full bg-transparent py-3 tracking-wider focus:outline-none" />
            </div>
            {phone.length === 10 && !/^[6-9]/.test(phone) && <p className="mt-2 text-sm text-sindoor">Indian mobile numbers start with 6, 7, 8 or 9.</p>}
            <button disabled={!/^[6-9][0-9]{9}$/.test(phone) || send.isPending}
              className="mt-4 w-full rounded-xl bg-sindoor py-3 font-semibold text-sindoor-ink disabled:opacity-40">
              {send.isPending ? "Sending…" : "Send code"}
            </button>
            {send.error && <div className="mt-3"><ErrorNote error={send.error} compact /></div>}
            {demo.data?.length ? (
              <div className="mt-6 border-t border-line pt-4">
                <p className="text-xs text-ink-3">Demo: use a real guest from the dataset</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {demo.data.map((g) => (
                    <button type="button" key={g.guest_id} onClick={() => setPhone(g.phone)}
                      className="rounded-full border border-line px-3 py-1 text-xs hover:border-ink">
                      {g.first_name} {g.last_name[0]}. · {g.bookings} trips
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </form>
        )}

        {step === "otp" && (
          <form onSubmit={(e) => { e.preventDefault(); verify.mutate(otp); }}>
            <h2 className="display mt-4 text-3xl">Enter the code</h2>
            <p className="mt-1 text-ink-2">
              Sent to +91 {phone.slice(0, 5)} {phone.slice(5)} ·{" "}
              <button type="button" onClick={reset} className="text-sindoor underline-offset-2 hover:underline">change</button>
            </p>
            <input autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp}
              onChange={(e) => typeOtp(e.target.value)} disabled={verify.isPending || expiresIn === 0}
              className={`${input} mt-6 text-center text-3xl tracking-[0.6em] tabular`} aria-label="6-digit code" />
            <div className="mt-2 flex justify-between text-xs text-ink-3" aria-live="polite">
              <span>{expiresIn > 0 ? `Code expires in ${mmss(expiresIn)}` : "This code has expired"}</span>
              {resendIn > 0 ? <span>Resend in {resendIn}s</span> : (
                <button type="button" onClick={() => send.mutate()} disabled={send.isPending} className="font-semibold text-sindoor">Resend code</button>
              )}
            </div>
            {send.data?.demo_otp && (
              <div className="mt-4 rounded-xl border border-dashed border-haldi bg-haldi/10 p-3 text-sm">
                <p><b>Demo mode</b> — no SMS provider is connected, so the code is shown here.</p>
                <button type="button" onClick={() => typeOtp(send.data!.demo_otp!)} className="mt-1 font-mono text-lg font-semibold tracking-widest text-ink">
                  {send.data.demo_otp} <span className="font-sans text-xs font-normal text-ink-3">tap to fill</span>
                </button>
              </div>
            )}
            <button disabled={otp.length !== 6 || verify.isPending}
              className="mt-4 w-full rounded-xl bg-sindoor py-3 font-semibold text-sindoor-ink disabled:opacity-40">
              {verify.isPending ? "Checking…" : "Verify"}
            </button>
            {verify.error && <div className="mt-3"><ErrorNote error={verify.error} compact /></div>}
            {send.error && <div className="mt-3"><ErrorNote error={send.error} compact /></div>}
          </form>
        )}

        {step === "profile" && (
          <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-3">
            <h2 className="display mt-4 text-3xl">Number verified ✓</h2>
            <p className="text-ink-2">New here — two quick lines. Hotels in India need an ID at check-in, so we ask once.</p>
            <div className="grid grid-cols-2 gap-3">
              <input required placeholder="First name" autoComplete="given-name" className={input} value={profile.first_name} onChange={(e) => setProfile({ ...profile, first_name: e.target.value })} />
              <input required placeholder="Last name" autoComplete="family-name" className={input} value={profile.last_name} onChange={(e) => setProfile({ ...profile, last_name: e.target.value })} />
            </div>
            <input required type="email" placeholder="Email" autoComplete="email" className={input} value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
            <label className="block text-sm text-ink-2">Date of birth
              <input required type="date" className={`${input} mt-1`} value={profile.date_of_birth} onChange={(e) => setProfile({ ...profile, date_of_birth: e.target.value })} />
            </label>
            <div className="grid grid-cols-[1fr_1.4fr] gap-3">
              <select className={input} value={profile.id_type} onChange={(e) => setProfile({ ...profile, id_type: e.target.value })}>
                <option value="PAN">PAN</option><option value="PASSPORT">Passport</option>
                <option value="DRIVING_LICENCE">Driving licence</option><option value="VOTER_ID">Voter ID</option>
              </select>
              <input required placeholder="ID number" className={input} value={profile.id_number} onChange={(e) => setProfile({ ...profile, id_number: e.target.value.toUpperCase() })} />
            </div>
            <button disabled={create.isPending} className="w-full rounded-xl bg-sindoor py-3 font-semibold text-sindoor-ink disabled:opacity-40">
              {create.isPending ? "Creating…" : "Create account"}
            </button>
            {create.error && <ErrorNote error={create.error} compact />}
          </form>
        )}
      </div>
    </dialog>
  );
}
