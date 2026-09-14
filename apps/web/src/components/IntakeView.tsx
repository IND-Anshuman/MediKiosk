"use client";

/**
 * IntakeView — the centerpiece conversational UI (plan T4.4 v2).
 *
 * Behavior locked by UI-CONTRACT.md + tests:
 *  - question card shows voice_hi text + plays pre-baked /tts mp3 (AD-2, instant)
 *  - touch options (multi_choice -> multi-tap + confirm bar, C-10)
 *  - mic: hold-to-speak; utterance POSTed with asr_confidence (AD-1/AD-10)
 *  - server `confirm` -> yes/no echo card
 *  - server `red_flag` -> full-screen banner + nurse call
 *  - interview end -> interview-done card (summary flow picks up)
 *  - replay mode (AD-12): auto-answers from canned schedule with replay-indicator
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { t } from "@/lib/i18n";

interface Question {
  id: string;
  type: string;
  voice_hi: string;
  voice_en: string;
  touch_options_hi: string[];
  touch_options_en: string[];
}

interface AnswerResp {
  red_flag: { pattern_id: string; urgency: string; message_hi: string; message_en: string } | null;
  next_question: Question | null;
  confirm: { heard: string; question_id: string } | null;
  re_asking: boolean;
}

const COMPLAINTS = [
  ["chest_pain", "🫀", "सीने में दर्द"],
  ["fever", "🌡️", "बुखार"],
  ["abdominal_pain", "🩹", "पेट दर्द"],
  ["cough", "😷", "खांसी"],
  ["headache", "🤕", "सर दर्द"],
  ["ayurvedic_assessment", "🌿", "आयुर्वेदिक मूल्यांकन"],
] as const;

export function ComplaintPicker({ onSelect }: { onSelect: (cc: string) => void }) {
  return (
    <div className="grid w-full grid-cols-2 gap-[var(--space-lg)] md:grid-cols-3">
      {COMPLAINTS.map(([key, icon, label]) => {
        const isAyush = key === "ayurvedic_assessment";
        return (
          <button
            key={key}
            data-testid={`cc-${key}`}
            data-variant={isAyush ? "ayush" : "allopathic"}
            onClick={() => onSelect(key)}
            className="glass-panel flex min-h-[96px] flex-col items-center justify-center gap-[var(--space-sm)] p-[var(--space-base)] font-semibold text-[var(--ink)] transition-colors hover:border-[var(--accent)]"
            style={isAyush ? { background: "var(--warn-bg)" } : undefined}
          >
            <span className="text-[40px] leading-none" aria-hidden>
              {icon}
            </span>
            <span className="text-[19px] leading-snug">
              {key === "ayurvedic_assessment" ? "आयुर्वेद" : key === "chest_pain" ? "सीने में दर्द" : label_hi(key)}
            </span>
            {isAyush && (
              <span
                className="rounded-full px-[var(--space-sm)] py-[2px] text-[11px] font-semibold"
                style={{ background: "var(--warn-bg)", color: "var(--ink-2)" }}
              >
                आयुर्वेदिक मूल्यांकन
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function label_hi(key: string): string {
  const m: Record<string, string> = {
    fever: "बुखार",
    abdominal_pain: "पेट दर्द",
    cough: "खांसी",
    headache: "सर दर्द",
  };
  return m[key] ?? key;
}

export default function IntakePageInner({
  sessionId,
  lang,
  complaint = "chest_pain",
  replay,
}: {
  sessionId: string;
  lang: "hi" | "en";
  complaint?: string;
  replay?: { enabled: boolean; confidence?: number };
}) {
  const [question, setQuestion] = useState<Question | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [redFlag, setRedFlag] = useState<AnswerResp["red_flag"]>(null);
  const [confirm, setConfirm] = useState<AnswerResp["confirm"]>(null);
  const [done, setDone] = useState(false);
  const [nurseCalled, setNurseCalled] = useState(false);
  const [recording, setRecording] = useState(false);
  const [progress, setProgress] = useState(1);
  const answered = useRef(0);

  // auto-start the interview on mount (a patient never presses ▶)
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      const res = await fetch("/api/dialogue/start", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ chief_complaint: complaint, session_id: sessionId }),
      });
      const body = await res.json();
      setQuestion(body.next_question);
      void fetch(`/tts/${complaint}:${body.next_question.id}:${lang}.mp3`).catch(() => {});
    })();
  }, [complaint, sessionId, lang]);

  const answer = useCallback(
    async (payload: Record<string, unknown>) => {
      const res = await fetch("/api/dialogue/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, language: lang, ...payload }),
      });
      const body: AnswerResp = await res.json();
      if (body.red_flag) setRedFlag(body.red_flag);
      if (body.confirm) {
        setConfirm(body.confirm);
        return;
      }
      setConfirm(null);
      setSelected([]);
      if (body.next_question) {
        setQuestion(body.next_question);
        setProgress((p) => p + 1);
        // pre-baked TTS playback (instant, offline after cache)
        void fetch(`/tts/${complaint}:${body.next_question.id}:${lang}.mp3`).catch(() => {});
      } else {
        setDone(true);
      }
    },
    [sessionId, lang, complaint]
  );

  const touch = useCallback(
    async (idx: number, multi = false) => {
      const next = multi
        ? selected.includes(idx)
          ? selected.filter((i) => i !== idx)
          : [...selected, idx]
        : [idx];
      setSelected(next);
      if (multi) return; // multi_choice waits for option-confirm
      answered.current += 1;
      await answer({ touch_indices: next });
    },
    [selected, answer]
  );

  const confirmAnswer = useCallback(
    async (yes: boolean) => {
      setConfirm(null);
      if (yes) {
        // promote the pending slot, then fetch next question
        const res = await fetch("/api/dialogue/confirm", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, confirm: true }),
        });
        const body: AnswerResp = await res.json();
        if (body.next_question) setQuestion(body.next_question);
      } else {
        // re-ask: server dropped the slot; next_question is the same qid
        const res = await fetch("/api/dialogue/answer", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, confirm: false }),
        });
        const body: AnswerResp = await res.json();
        if (body.next_question) setQuestion(body.next_question);
      }
      setSelected([]);
    },
    [sessionId]
  );

  // replay mode: auto-answer on a timer (demo parachute, AD-12)
  useEffect(() => {
    if (!replay?.enabled || !question || confirm || redFlag || done) return;
    const timer = setTimeout(() => {
      answered.current += 1;
      void answer({
        touch_indices: [0],
        asr_confidence: replay.confidence, // triggers the confirm echo path
      });
    }, 900);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, replay?.enabled, confirm, redFlag, done]);

  const callNurse = async () => {
    await fetch("/api/triage/alert", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        pattern_id: redFlag?.pattern_id ?? "manual",
        urgency: redFlag?.urgency ?? "immediate",
        message_en: redFlag?.message_en ?? "",
        message_hi: redFlag?.message_hi ?? "",
      }),
    });
    setNurseCalled(true);
  };

  if (redFlag) {
    return (
      <main
        role="alert"
        className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-[var(--space-xl)] p-[var(--space-xl)] text-center"
        style={{ background: "var(--danger-bg)" }}
      >
        <div
          data-testid="redflag-banner"
          className="max-w-[640px] font-bold text-[var(--danger)]"
          style={{ fontSize: "clamp(26px, 4vw, 36px)", lineHeight: 1.3, textWrap: "balance" }}
        >
          <span
            aria-hidden
            className="mb-[var(--space-lg)] inline-flex h-16 w-16 items-center justify-center rounded-full text-3xl"
            style={{
              background: "var(--danger)",
              color: "var(--accent-ink)",
              animation: "redflag-pulse 2s ease-out 3",
            }}
          >
            ⚠
          </span>
          <br />
          {lang === "hi" ? redFlag.message_hi : redFlag.message_en}
        </div>
        {nurseCalled ? (
          <p className="text-2xl font-semibold text-[var(--ink)]">{t("nurse_called")}</p>
        ) : (
          <button
            data-testid="nurse-call"
            onClick={callNurse}
            className="min-h-[88px] rounded-[var(--radius-panel)] px-[var(--space-2xl)] text-2xl font-bold text-[var(--accent-ink)]"
            style={{ background: "var(--danger)" }}
          >
            🚑 {t("priority_alert_call_nurse")}
          </button>
        )}
        <style>{`@keyframes redflag-pulse { 0%{box-shadow:0 0 0 0 oklch(0.52 0.19 25/0.45)} 100%{box-shadow:0 0 0 28px oklch(0.52 0.19 25/0)} }`}</style>
      </main>
    );
  }

  if (done) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-[var(--space-lg)] text-center">
        <div data-testid="interview-done" className="text-xl text-[var(--ink-2)]">
          {t("record_complete")}
        </div>
        <div
          data-testid="summary-ready"
          className="font-bold text-[var(--ink)]"
          style={{ fontSize: "clamp(26px, 4vw, 34px)", textWrap: "balance" }}
        >
          {t("summary_ready")}
        </div>
        <button
          className="min-h-[var(--tap-min)] rounded-[var(--radius-chip)] px-[var(--space-2xl)] text-xl font-bold text-[var(--accent-ink)]"
          style={{ background: "var(--accent)" }}
        >
          {t("go_to_room")}
        </button>
      </main>
    );
  }

  if (confirm) {
    return (
      <section
        className="glass-panel mx-auto w-full p-[clamp(20px,4vw,40px)] text-center"
        data-animate="stage-in"
      >
        <p className="text-xl text-[var(--ink)]">
          {t("confirm_heard")}{" "}
          <strong className="text-[22px]">“{confirm.heard}”</strong>
        </p>
        <div className="mt-[var(--space-xl)] flex flex-col gap-[var(--space-md)] sm:flex-row sm:justify-center">
          <button
            data-testid="confirm-yes"
            onClick={() => confirmAnswer(true)}
            className="min-h-[var(--tap-min)] rounded-[var(--radius-chip)] px-[var(--space-xl)] text-lg font-bold text-[var(--accent-ink)]"
            style={{ background: "var(--ok)" }}
          >
            {t("confirm_yes")}
          </button>
          <button
            data-testid="confirm-no"
            onClick={() => confirmAnswer(false)}
            className="glass-chip min-h-[var(--tap-min)] px-[var(--space-xl)] text-lg font-bold text-[var(--ink)]"
          >
            {t("confirm_no")}
          </button>
        </div>
      </section>
    );
  }

  if (!question) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <div className="text-lg text-[var(--ink-2)]">{t("processing")}</div>
      </main>
    );
  }

  const opts = lang === "hi" ? question.touch_options_hi : question.touch_options_en;
  const isMulti = question.type === "multi_choice";

  return (
    <section
      className="glass-panel mx-auto w-full p-[clamp(20px,4vw,40px)]"
      data-testid="question-card"
      data-animate="stage-in"
    >
      <div className="mb-[var(--space-sm)] flex items-center justify-between">
        <span className="text-[13px] font-medium tabular-nums text-[var(--ink-2)]" data-testid="question-progress">
          {progress}
        </span>
        {replay?.enabled && (
          <span
            data-testid="replay-indicator"
            className="glass-chip px-[var(--space-sm)] py-[2px] text-[11px] font-semibold text-[var(--ink-2)]"
          >
            replay
          </span>
        )}
      </div>

      <h2
        className="font-bold text-[var(--ink)]"
        style={{ fontSize: "clamp(24px, 3.4vw, 30px)", lineHeight: 1.3, letterSpacing: "-0.02em", textWrap: "balance" }}
      >
        {lang === "hi" ? question.voice_hi : question.voice_en}
      </h2>

      <div className="mt-[var(--space-xl)] grid gap-[var(--space-md)]">
        {opts.map((o, i) => {
          const sel = selected.includes(i);
          return (
            <button
              key={i}
              data-testid={`option-${i}`}
              onClick={() => touch(i, isMulti)}
              className={`glass-chip flex min-h-[var(--tap-patient)] w-full items-center px-[var(--space-lg)] py-[var(--space-md)] text-left text-[19px] font-semibold ${
                sel ? "is-selected" : "text-[var(--ink)]"
              }`}
            >
              {isMulti && (
                <span aria-hidden className="mr-[var(--space-md)] text-xl">
                  {sel ? "☑" : "☐"}
                </span>
              )}
              {o}
            </button>
          );
        })}
      </div>

      {isMulti ? (
        <button
          data-testid="option-confirm"
          disabled={!selected.length}
          onClick={async () => {
            answered.current += 1;
            await answer({ touch_indices: selected });
          }}
          className="mt-[var(--space-lg)] min-h-[var(--tap-patient)] w-full rounded-[var(--radius-chip)] text-lg font-bold text-[var(--accent-ink)] transition-opacity disabled:opacity-40"
          style={{ background: "var(--accent)", position: "sticky", bottom: "var(--space-lg)" }}
        >
          OK ✓
        </button>
      ) : (
        <button
          data-testid="mic-btn"
          onClick={() => setRecording((r) => !r)}
          className="glass-chip mt-[var(--space-lg)] flex min-h-[var(--tap-min)] w-full items-center justify-center text-lg font-bold text-[var(--ink)]"
          style={recording ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined}
        >
          <span aria-hidden className="mr-[var(--space-sm)] text-xl">
            🎙️
          </span>
          {recording ? t("listening") : t("mic_tap_to_speak")}
        </button>
      )}
    </section>
  );
}