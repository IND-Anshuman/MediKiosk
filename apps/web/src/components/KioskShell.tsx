"use client";

/** Kiosk shell (plan §1.6): header + strata progress bar + 720px column.
 *  Doctor variant: wider, no progress bar. */
import type { ReactNode } from "react";

export type KioskStage = "lang" | "consent" | "complaint" | "intake" | "docs";

const STEP_OF: Record<KioskStage, number> = {
  lang: 0,
  consent: 1,
  complaint: 1,
  intake: 2,
  docs: 3,
};

const STEPS_HI = ["सहमति", "साक्षात्कार", "दस्तावेज़"];
const STEPS_EN = ["Consent", "Interview", "Documents"];

export default function KioskShell({
  stage,
  variant = "patient",
  children,
}: {
  stage: KioskStage;
  variant?: "patient" | "doctor";
  children: ReactNode;
}) {
  const step = STEP_OF[stage];
  const steps = step > 0 ? (stage === "docs" ? STEPS_HI : STEPS_HI) : STEPS_HI;
  const stepLabels = steps; // Hindi-first kiosk; labels localized post-A5
  const wide = variant === "doctor";

  return (
    <div className="relative z-10 flex min-h-screen flex-col" data-testid="kiosk-shell">
      <header className="flex items-center justify-between px-[clamp(20px,5vw,56px)] pt-[var(--space-lg)]">
        <span className="flex items-center gap-[var(--space-sm)] text-[15px] font-semibold tracking-[-0.01em] text-[var(--ink)]">
          <span
            aria-hidden
            className="inline-block h-[10px] w-[10px] rounded-full"
            style={{ background: "var(--accent)" }}
          />
          MediKiosk
        </span>
        {wide ? (
          <span className="text-[13px] font-medium text-[var(--ink-2)]">डॉक्टर पोर्टल</span>
        ) : (
          <span className="text-[13px] font-medium text-[var(--ink-2)]">
            {step > 0 ? `${step}/3` : ""}
          </span>
        )}
      </header>

      {!wide && step > 0 && (
        <nav
          aria-label="progress"
          className="mx-auto flex w-full max-w-[720px] items-center gap-[var(--space-sm)] px-[clamp(20px,5vw,56px)] pt-[var(--space-md)]"
        >
          {stepLabels.map((label, i) => {
            const idx = i + 1;
            const state =
              idx < step ? "done" : idx === step ? "current" : "todo";
            return (
              <div key={label} className="flex flex-1 flex-col gap-[var(--space-xs)]">
                <div
                  aria-hidden
                  className="h-[3px] rounded-full"
                  style={{
                    background:
                      state === "done"
                        ? "var(--accent)"
                        : state === "current"
                          ? "var(--accent)"
                          : "var(--line)",
                    opacity: state === "current" ? 1 : state === "done" ? 0.55 : 1,
                  }}
                />
                <span
                  className="text-[11px] font-medium"
                  style={{ color: state === "todo" ? "var(--ink-2)" : "var(--ink)" }}
                >
                  {label}
                  {state === "done" ? " ✓" : ""}
                </span>
              </div>
            );
          })}
        </nav>
      )}

      <main
        className={`mx-auto flex w-full flex-1 flex-col ${
          wide ? "max-w-[1040px]" : "max-w-3xl"
        } px-[clamp(20px,5vw,56px)] py-[var(--space-xl)]`}
      >
        {children}
      </main>
    </div>
  );
}
