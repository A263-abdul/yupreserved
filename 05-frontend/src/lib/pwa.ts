/** "Install app": Android/desktop Chrome give us a prompt event; iPhone needs Share → Add to Home Screen. */
import { useEffect, useState } from "react";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

let deferred: InstallEvent | null = null;
const listeners = new Set<() => void>();
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferred = e as InstallEvent;
  listeners.forEach((l) => l());
});
window.addEventListener("appinstalled", () => {
  deferred = null;
  listeners.forEach((l) => l());
});

export const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches || (navigator as any).standalone === true;
export const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent);

export function useInstall() {
  const [, force] = useState(0);
  useEffect(() => {
    const l = () => force((n) => n + 1);
    listeners.add(l);
    return () => void listeners.delete(l);
  }, []);
  return {
    canPrompt: !!deferred,
    installed: isStandalone(),
    ios: isIOS(),
    install: async () => {
      if (!deferred) return false;
      await deferred.prompt();
      const { outcome } = await deferred.userChoice;
      deferred = null;
      force((n) => n + 1);
      return outcome === "accepted";
    },
  };
}
