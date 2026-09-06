"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";

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
    <main className="mx-auto max-w-xl p-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-lg text-slate-800">{t("consent_intro")}</p>
        <ul className="mt-4 space-y-3 text-slate-700">
          <li className="flex gap-3">
            <span aria-hidden>🩺</span>
            <span>{t("consent_his")}</span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden>🔐</span>
            <span>{t("consent_abha")}</span>
          </li>
          <li className="flex gap-3">
            <span aria-hidden>📄</span>
            <span>{t("consent_storage")}</span>
          </li>
        </ul>
        <div className="mt-6 space-y-3">
          {!granted && (
            <button
              data-testid="consent-agree"
              disabled={busy}
              onClick={agree}
              className="w-full rounded-xl bg-blue-600 py-4 text-xl font-semibold text-white disabled:opacity-50"
            >
              ✓ {t("confirm_yes")}
            </button>
          )}
          {granted && (
            <p className="rounded-lg bg-green-50 p-3 text-green-800">✓ {t("record_complete")}</p>
          )}
          <button
            data-testid="revoke-btn"
            disabled={busy || !granted}
            onClick={revoke}
            title={granted ? t("revoke_consent") : undefined}
            className="w-full rounded-xl border border-red-300 py-3 text-red-700 disabled:opacity-40"
          >
            {t("revoke_consent")}
          </button>
        </div>
      </section>
    </main>
  );
}