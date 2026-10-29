/** Signed-in guest, theme and the compare tray — app-wide state. */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authToken, type Guest, type HotelCard } from "./api";
import { storage } from "./storage";

type Theme = "light" | "dark" | "system";

type Session = {
  guest: Guest | null;
  signIn: (g: Guest, token: string) => void;
  signOut: () => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
  compare: HotelCard[];
  toggleCompare: (h: HotelCard) => void;
  clearCompare: () => void;
  authOpen: boolean;
  setAuthOpen: (open: boolean) => void;
};

const Ctx = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  // a guest saved before tokens existed (or with an expired token) must sign in again
  const [guest, setGuest] = useState<Guest | null>(() => (authToken.get() ? storage.json<Guest | null>("yup-guest", null) : null));
  const [theme, setThemeState] = useState<Theme>(() => (storage.get("yup-theme") as Theme) || "system");
  const [compare, setCompare] = useState<HotelCard[]>([]);
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    const out = () => { setGuest(null); storage.set("yup-guest", null); };
    window.addEventListener("yup:signed-out", out);
    return () => window.removeEventListener("yup:signed-out", out);
  }, []);

  useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);

  const value = useMemo<Session>(() => ({
    guest,
    signIn: (g, token) => { setGuest(g); authToken.set(token); storage.set("yup-guest", JSON.stringify(g)); },
    signOut: () => { setGuest(null); authToken.set(null); storage.set("yup-guest", null); },
    theme,
    setTheme: (t) => { setThemeState(t); storage.set("yup-theme", t === "system" ? null : t); },
    compare,
    toggleCompare: (h) => setCompare((c) =>
      c.some((x) => x.hotel_id === h.hotel_id) ? c.filter((x) => x.hotel_id !== h.hotel_id) : [...c, h].slice(-3)),
    clearCompare: () => setCompare([]),
    authOpen,
    setAuthOpen,
  }), [guest, theme, compare, authOpen]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
