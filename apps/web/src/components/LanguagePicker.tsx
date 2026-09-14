"use client";

import { useEffect, useState } from "react";
import { onLangChange, setLang, t, type Lang } from "@/lib/i18n";

/** Language picker (plan §1.7): two split glass panels, entire panel is the
 *  button. 72px+ target; label 32px/700 + subline in the other language.
 *  `onPicked` (optional) additionally advances the patient journey stage. */
export default function LanguagePicker({
  onPicked,
}: {
  onPicked?: (l: Lang) => void;
}) {
  const [lang, setLocal] = useState<Lang>("hi");
  useEffect(() => onLangChange(setLocal), []);

  const pick = (l: Lang) => {
    setLang(l);
    // play pre-baked audio greeting for the chosen language (AD-2)
    void fetch(`/tts/ui:welcome:${l}.mp3`).catch(() => {});
    onPicked?.(l);
  };

  return (
    <div className="flex w-full flex-1 flex-col justify-center gap-[var(--space-xl)]">
      <h1
        className="text-center font-bold text-[var(--ink)]"
        data-testid="welcome-title"
        style={{ fontSize: "clamp(28px, 5vw, 40px)", letterSpacing: "-0.02em", textWrap: "balance" }}
      >
        {t("welcome")}
      </h1>

      <div className="grid gap-[var(--space-lg)] sm:grid-cols-2">
        <button
          data-testid="lang-hi"
          onClick={() => pick("hi")}
          className="glass-panel flex min-h-[var(--tap-patient)] flex-col items-center justify-center gap-[var(--space-xs)] px-[var(--space-xl)] py-[var(--space-2xl)] text-[var(--ink)] transition-colors hover:border-[var(--accent)]"
        >
          <span style={{ fontSize: "32px", fontWeight: 700, lineHeight: 1.15 }}>हिन्दी</span>
          <span className="text-[15px] text-[var(--ink-2)]">Choose Hindi</span>
        </button>

        <button
          data-testid="lang-en"
          onClick={() => pick("en")}
          className="glass-panel flex min-h-[var(--tap-patient)] flex-col items-center justify-center gap-[var(--space-xs)] px-[var(--space-xl)] py-[var(--space-2xl)] text-[var(--ink)] transition-colors hover:border-[var(--accent)]"
        >
          <span style={{ fontSize: "32px", fontWeight: 700, lineHeight: 1.15 }}>English</span>
          <span className="text-[15px] text-[var(--ink-2)]">अंग्रेज़ी में</span>
        </button>
      </div>
    </div>
  );
}
