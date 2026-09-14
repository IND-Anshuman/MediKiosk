"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";

/** Consent (plan §1.7): single glass panel, big paired actions, revoke always
 *  visible. Copy strips internal jargon (patient says "खाता", not "ABHA"). */
const SCOPES = ["his_share", "storage"];

export default function ConsentFlow({
  sessionId,
  onGranted,
}: {
  sessionId: string;
  onGranted: (scopes: string[]) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [granted, setGranted] = useState(false);

  const agree = async () => {
    setBusy(true);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/consent`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scopes: SCOPES }),
      });
      if (res.ok) {
        setGranted(true);
        onGranted(SCOPES);
      }
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    try {
      await fetch(`/api/sessions/${sessionId}/consent/revoke`, { method: "POST" });
      setGranted(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="glass-panel mx-auto w-full p-[clamp(20px,4vw,40px)]"
      data-animate="stage-in"
    >
      <p
        className="font-semibold text-[var(--ink)]"
        style={{ fontSize: "clamp(20px, 2.6vw, 24px)", lineHeight: 1.45, textWrap: "balance" }}
      >
        {t("consent_intro")}
      </p>

      <ul className="mt-[var(--space-lg)] flex flex-col gap-[var(--space-md)]">
        {[
          ["🩺", t("consent_his")],
          ["🔐", t("consent_abha")],
          ["📄", t("consent_storage")],
        ].map(([icon, text]) => (
          <li
            key={text}
            className="glass-chip flex items-start gap-[var(--space-md)] px-[var(--space-base)] py-[var(--space-md)] text-[var(--ink)]"
          >
            <span aria-hidden className="text-xl leading-6">
              {icon}
            </span>
            <span className="text-[16px] leading-7">{text}</span>
          </li>
        ))}
      </ul>

      <div className="mt-[var(--space-xl)] flex flex-col gap-[var(--space-md)]">
        {!granted && (
          <button
            data-testid="consent-agree"
            disabled={busy}
            onClick={agree}
            className="min-h-[var(--tap-min)] w-full rounded-[var(--radius-chip)] py-[var(--space-md)] text-xl font-bold text-[var(--accent-ink)] transition-opacity disabled:opacity-50"
            style={{ background: "var(--accent)" }}
          >
            ✓ {t("confirm_yes")}
          </button>
        )}
        {granted && (
          <p
            className="rounded-[var(--radius-chip)] p-[var(--space-md)] font-semibold"
            style={{ background: "var(--accent-soft)", color: "var(--ok)" }}
          >
            ✓ {t("record_complete")}
          </p>
        )}
        <button
          data-testid="revoke-btn"
          disabled={busy || !granted}
          onClick={revoke}
          title={granted ? t("revoke_consent") : undefined}
          className="min-h-[var(--tap-patient)] w-full rounded-[var(--radius-chip)] border py-[var(--space-md)] text-lg font-semibold transition-colors disabled:opacity-40"
          style={{ borderColor: "var(--line)", color: "var(--danger)" }}
        >
          {t("revoke_consent")}
        </button>
      </div>
    </section>
  );
}
