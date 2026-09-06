"use client";

import { useEffect, useState } from "react";
import { onLangChange, setLang, t, type Lang } from "@/lib/i18n";

export default function LanguagePicker() {
  const [lang, setLocal] = useState<Lang>("hi");
  useEffect(() => onLangChange(setLocal), []);

  const pick = (l: Lang) => {
    setLang(l);
    // play pre-baked audio greeting for the chosen language (AD-2)
    void fetch(`/tts/ui:welcome:${l}.mp3`).catch(() => {});
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-50">
      <h1 className="text-4xl font-bold text-slate-900" data-testid="welcome-title">
        {t("welcome")}
      </h1>
      <div className="flex gap-6">
        <button
          data-testid="lang-hi"
          onClick={() => pick("hi")}
          className={`rounded-2xl border-4 px-16 py-10 text-3xl font-semibold transition ${
            lang === "hi" ? "border-blue-600 bg-blue-50" : "border-slate-300 bg-white"
          }`}
        >
          हिन्दी
        </button>
        <button
          data-testid="lang-en"
          onClick={() => pick("en")}
          className={`rounded-2xl border-4 px-16 py-10 text-3xl font-semibold transition ${
            lang === "en" ? "border-blue-600 bg-blue-50" : "border-slate-300 bg-white"
          }`}
        >
          English
        </button>
      </div>
    </main>
  );
}