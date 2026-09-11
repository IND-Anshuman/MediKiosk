"use client";

import { useState } from "react";
import ConsentFlow from "@/components/ConsentFlow";
import { ComplaintPicker } from "@/components/IntakeView";
import IntakePageInner from "@/components/IntakeView";
import DocumentsView from "@/components/DocumentsView";
import { setLang, type Lang } from "@/lib/i18n";

/** Patient journey (plan 3.4): lang -> consent -> complaint -> intake -> documents */
export default function Home() {
  const [stage, setStage] = useState<"lang" | "consent" | "complaint" | "intake" | "docs">("lang");
  const [sessionId] = useState(() => `sess-${Math.random().toString(36).slice(2, 10)}`);
  const [complaint, setComplaint] = useState("chest_pain");

  if (stage === "lang") {
    return <LangStage onPicked={(l: Lang) => { setLang(l); setStage("consent"); }} />;
  }
  if (stage === "consent") {
    return <ConsentFlow sessionId={sessionId} onGranted={() => setStage("complaint")} />;
  }
  if (stage === "complaint") {
    return (
      <ComplaintPicker
        onSelect={(cc) => {
          setComplaint(cc);
          setStage("intake");
        }}
      />
    );
  }
  if (stage === "intake") {
    return (
      <div>
        <IntakePageInner sessionId={sessionId} lang="hi" complaint={complaint} />
        <div className="pb-6 text-center">
          <button
            data-testid="to-documents"
            onClick={() => setStage("docs")}
            className="rounded-xl border border-slate-300 px-6 py-3 text-slate-700"
          >
            → 📄
          </button>
        </div>
      </div>
    );
  }
  return <DocumentsView sessionId={sessionId} />;
}

function LangStage({ onPicked }: { onPicked: (l: Lang) => void }) {
  // minimal inline picker (same testids as LanguagePicker component contract)
  const pick = (l: Lang) => {
    setLang(l);
    onPicked(l);
  };
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-50">
      <h1 className="text-4xl font-bold text-slate-900">स्वागत है / Welcome</h1>
      <div className="flex gap-6">
        <button
          data-testid="lang-hi"
          onClick={() => pick("hi")}
          className="rounded-2xl border-4 border-slate-300 bg-white px-16 py-10 text-3xl font-semibold"
        >
          हिन्दी
        </button>
        <button
          data-testid="lang-en"
          onClick={() => pick("en")}
          className="rounded-2xl border-4 border-slate-300 bg-white px-16 py-10 text-3xl font-semibold"
        >
          English
        </button>
      </div>
    </main>
  );
}