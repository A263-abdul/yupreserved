/** English / हिन्दी for the interface chrome. Hotel content stays in English. */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { storage } from "./storage";

const dict = {
  en: {
    stays: "Stays", trips: "My trips", lab: "Under the hood", signIn: "Sign in", signOut: "Sign out",
    heroLine1: "India,", heroLine2: "one good night", heroLine3: "at a time.",
    heroSub: "Heritage palaces, beach shacks, houseboats and hill cottages. Real places, honest prices.",
    where: "Where to?", wherePh: "City, landmark or hotel — try “Gateway of India”",
    checkIn: "Check-in", checkOut: "Check-out", guests: "Guests", search: "Find stays",
    moods: "Or travel by mood", signature: "Signature stays", signatureSub: "Eighteen places we would send our own families to.",
    cities: "Where India is travelling", festive: "Festival calendar", festiveSub: "Prices rise when India travels. We show you exactly how much.",
    from: "from", perNight: "/ night", reserve: "Reserve", viewStay: "View stay",
    results: "stays", sort: "Sort", filters: "Filters", compare: "Compare",
    rooms: "Rooms", neighbourhood: "The neighbourhood", amenities: "What's here", reviews: "Guests say",
    checkout: "Checkout", pay: "Pay", confirm: "Confirm booking",
    empty: "Nothing matches that — yet.", emptySub: "Try fewer filters, or a nearby city.",
  },
  hi: {
    stays: "ठहराव", trips: "मेरी यात्राएँ", lab: "अंदर की बात", signIn: "साइन इन", signOut: "साइन आउट",
    heroLine1: "भारत,", heroLine2: "एक सुकून भरी रात", heroLine3: "एक बार में।",
    heroSub: "महल, समुद्र किनारे झोंपड़ियाँ, हाउसबोट और पहाड़ी कॉटेज। असली जगहें, सच्चे दाम।",
    where: "कहाँ जाना है?", wherePh: "शहर, स्थल या होटल — जैसे “गेटवे ऑफ़ इंडिया”",
    checkIn: "चेक-इन", checkOut: "चेक-आउट", guests: "मेहमान", search: "ठहराव खोजें",
    moods: "या मूड के हिसाब से", signature: "सिग्नेचर ठहराव", signatureSub: "अठारह जगहें जहाँ हम अपने परिवार को भेजेंगे।",
    cities: "भारत कहाँ घूम रहा है", festive: "त्योहारों का कैलेंडर", festiveSub: "त्योहारों में दाम बढ़ते हैं — हम बताते हैं कितना।",
    from: "से", perNight: "/ रात", reserve: "बुक करें", viewStay: "देखें",
    results: "ठहराव", sort: "क्रम", filters: "फ़िल्टर", compare: "तुलना",
    rooms: "कमरे", neighbourhood: "आस-पड़ोस", amenities: "सुविधाएँ", reviews: "मेहमानों की राय",
    checkout: "चेकआउट", pay: "भुगतान", confirm: "बुकिंग पक्की करें",
    empty: "अभी कुछ नहीं मिला।", emptySub: "कम फ़िल्टर या पास का शहर आज़माएँ।",
  },
} as const;

export type Lang = keyof typeof dict;
type Key = keyof (typeof dict)["en"];

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: Key) => string }>({
  lang: "en", setLang: () => {}, t: (k) => dict.en[k],
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (storage.get("yup-lang") as Lang) || "en");
  const value = useMemo(() => ({
    lang,
    setLang: (l: Lang) => {
      setLangState(l);
      storage.set("yup-lang", l);
      document.documentElement.lang = l === "hi" ? "hi" : "en";
    },
    t: (k: Key) => dict[lang][k],
  }), [lang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
