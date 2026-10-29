import { motion, useMotionValueEvent, useScroll } from "motion/react";
import { useState } from "react";
import { useInstall } from "../lib/pwa";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useI18n } from "../lib/i18n";
import { useSession } from "../lib/session";
import { StarRule, Wordmark } from "./brand";

export function Header() {
  const { t, lang, setLang } = useI18n();
  const { guest, signOut, theme, setTheme, setAuthOpen } = useSession();
  const { pathname } = useLocation();
  const overHero = pathname === "/";
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(!overHero);
  useMotionValueEvent(scrollY, "change", (y) => setSolid(!overHero || y > 40));

  const nextTheme = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-full px-3 py-1.5 text-sm transition ${isActive ? "bg-ink text-paper" : "text-ink-2 hover:text-ink"}`;

  return (
    <motion.header
      className={`sticky top-0 z-50 pt-[env(safe-area-inset-top)] transition-colors duration-500 ${solid ? "border-b border-line bg-paper/85 backdrop-blur-md" : "on-photo bg-gradient-to-b from-black/40 to-transparent"}`}
    >
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-paper">
        Skip to content
      </a>
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link to="/" aria-label="YupReserved home" className="min-w-0"><Wordmark /></Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          <NavLink to="/stays" className={link}>{t("stays")}</NavLink>
          <NavLink to="/trips" className={link}>{t("trips")}</NavLink>
          <NavLink to="/lab" className={link}>{t("lab")}</NavLink>
        </nav>
        <div className="flex shrink-0 items-center gap-0.5 sm:gap-1.5">
          <button onClick={() => setLang(lang === "en" ? "hi" : "en")}
            className="rounded-full px-2.5 py-1.5 text-sm text-ink-2 hover:bg-paper-2" aria-label="Switch language">
            {lang === "en" ? <span className="hindi">हिं</span> : "EN"}
          </button>
          <InstallButton />
          <button onClick={() => setTheme(nextTheme)} className="rounded-full px-2.5 py-1.5 text-sm text-ink-2 hover:bg-paper-2"
            aria-label={`Theme: ${theme}. Switch to ${nextTheme}`} title={`Theme: ${theme}`}>
            {theme === "dark" ? "☾" : theme === "light" ? "☀" : "◐"}
          </button>
          {guest ? (
            <div className="hidden items-center gap-2 md:flex">
              <Link to="/trips" className="grid h-9 w-9 place-items-center rounded-full bg-peacock text-sm font-semibold text-paper" title={`${guest.first_name} ${guest.last_name}`}>
                {guest.first_name[0]}{guest.last_name[0]}
              </Link>
              <button onClick={signOut} className="hidden text-sm text-ink-3 hover:text-ink sm:block">{t("signOut")}</button>
            </div>
          ) : (
            <button onClick={() => setAuthOpen(true)} className="hidden rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-sindoor md:block">
              {t("signIn")}
            </button>
          )}
        </div>
      </div>
    </motion.header>
  );
}

export function Footer() {
  return (
    <footer className="mt-24 border-t border-line bg-paper-2/60 pb-20 md:pb-0">
      <div className="jaali">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Wordmark />
            <p className="mt-4 max-w-sm text-ink-2">
              Made in India, for people who travel it. Real listings from 543 cities, prices you can read night by night,
              and UPI that just works.
            </p>
            <p className="hindi mt-3 text-lg text-ink-3">हाँ, आपकी जगह पक्की।</p>
          </div>
          <FooterCol title="Travel" links={[["Signature stays", "/stays?signature_only=true"], ["Heritage & palaces", "/stays?mood=heritage"], ["By the sea", "/stays?mood=beach"], ["Hill stays", "/stays?mood=hills"]]} />
          <FooterCol title="Your trips" links={[["My trips", "/trips"], ["Cancellation policy", "/trips#policy"]]} />
          <FooterCol title="Under the hood" links={[["Database lab", "/lab"], ["15 tables", "/lab?tab=tables"], ["Why can't I…?", "/lab?tab=why"], ["Query plans", "/lab?tab=plans"]]} />
        </div>
        <div className="mx-auto max-w-7xl px-4 pb-10 sm:px-6">
          <StarRule />
          <p className="mt-6 text-center text-xs text-ink-3">
            YupReserved is a DBMS course project. Hotel listings: Goibibo public dataset (2016). Signature stays, guests and bookings are simulated.
          </p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <p className="eyebrow">{title}</p>
      <ul className="mt-4 space-y-2">
        {links.map(([label, to]) => (
          <li key={to}><Link to={to} className="text-ink-2 hover:text-sindoor">{label}</Link></li>
        ))}
      </ul>
    </div>
  );
}


function InstallButton() {
  const { canPrompt, installed, ios, install } = useInstall();
  const [tip, setTip] = useState(false);
  if (installed || (!canPrompt && !ios)) return null;
  return (
    <div className="relative">
      <button onClick={() => (canPrompt ? install() : setTip((x) => !x))}
        className="rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink-2 hover:border-ink">
        ⤓ <span className="hidden sm:inline">Install app</span><span className="sm:hidden">App</span>
      </button>
      {tip && (
        <p className="absolute right-0 top-10 w-56 rounded-2xl border border-line bg-card p-3 text-xs text-ink shadow-xl">
          On iPhone: tap <b>Share</b> <span aria-hidden>⎋</span> then <b>Add to Home Screen</b>.
        </p>
      )}
    </div>
  );
}

/** Phone-only tab bar, like a native app. Respects the iPhone home-indicator area. */
export function BottomNav() {
  const { guest, setAuthOpen } = useSession();
  const { t } = useI18n();
  const tab = ({ isActive }: { isActive: boolean }) =>
    `flex flex-1 flex-col items-center gap-0.5 py-2 text-[0.68rem] font-medium transition ${isActive ? "text-sindoor" : "text-ink-3"}`;
  const Icon = ({ d }: { d: string }) => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>
  );
  return (
    <nav aria-label="App" className="fixed inset-x-0 bottom-0 z-50 flex border-t border-line bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden">
      <NavLink to="/" end className={tab}><Icon d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />Home</NavLink>
      <NavLink to="/stays" className={tab}><Icon d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM21 21l-4.3-4.3" />{t("stays")}</NavLink>
      <NavLink to="/trips" className={tab}><Icon d="M4 7h16v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM9 7V5a3 3 0 0 1 6 0v2" />{t("trips")}</NavLink>
      <NavLink to="/lab" className={tab}><Icon d="M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />Lab</NavLink>
      {guest ? (
        <NavLink to="/trips" className={() => tab({ isActive: false })}>
          <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-peacock text-[0.6rem] text-paper">{guest.first_name[0]}{guest.last_name[0]}</span>Me
        </NavLink>
      ) : (
        <button onClick={() => setAuthOpen(true)} className={tab({ isActive: false })}>
          <Icon d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0" />{t("signIn")}
        </button>
      )}
    </nav>
  );
}
