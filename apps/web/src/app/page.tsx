"use client";

import { useState } from "react";
import ConsentFlow from "@/components/ConsentFlow";
import KioskShell, { type KioskStage } from "@/components/KioskShell";
import { ComplaintPicker } from "@/components/IntakeView";
import IntakePageInner from "@/components/IntakeView";
import DocumentsView from "@/components/DocumentsView";
import LanguagePicker from "@/components/LanguagePicker";
import { setLang, type Lang } from "@/lib/i18n";

/** Patient journey (plan 3.4): lang -> consent -> complaint -> intake -> docs.
 *  All stages share the KioskShell frame; each stage animates in. */
export default function Home() {
  const [stage, setStage] = useState<KioskStage>("lang");
  const [sessionId] = useState(() => `sess-${Math.random().toString(36).slice(2, 10)}`);
  const [complaint, setComplaint] = useState("chest_pain");

  return (
    <KioskShell stage={stage}>
      <div key={stage} data-animate="stage-in" className="flex flex-1 flex-col">
        {stage === "lang" && (
          <LanguagePicker
            onPicked={(l: Lang) => {
              setLang(l);
              setStage("consent");
            }}
          />
        )}
        {stage === "consent" && (
          <ConsentFlow sessionId={sessionId} onGranted={() => setStage("complaint")} />
        )}
        {stage === "complaint" && (
          <div className="flex flex-1 flex-col justify-center">
            <ComplaintPicker
              onSelect={(cc) => {
                setComplaint(cc);
                setStage("intake");
              }}
            />
          </div>
        )}
        {stage === "intake" && (
          <div className="flex flex-1 flex-col">
            <IntakePageInner sessionId={sessionId} lang="hi" complaint={complaint} />
            <div className="pb-[var(--space-lg)] text-center">
              <button
                data-testid="to-documents"
                onClick={() => setStage("docs")}
                className="glass-chip min-h-[var(--tap-min)] px-[var(--space-xl)] font-semibold text-[var(--ink)]"
              >
                दस्तावेज़ स्कैन करें →
              </button>
            </div>
          </div>
        )}
        {stage === "docs" && <DocumentsView sessionId={sessionId} />}
      </div>
        </KioskShell>
  );
}
