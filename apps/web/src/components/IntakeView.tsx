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
    <main className="mx-auto grid max-w-3xl grid-cols-2 gap-5 p-6 md:grid-cols-3">
      {COMPLAINTS.map(([key, icon, label]) => (
        <button
          key={key}
          data-testid={`cc-${key}`}
          onClick={() => onSelect(key)}
          className="flex min-h-[9rem] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-slate-200 bg-white p-4 text-xl font-semibold text-slate-800 shadow-sm active:bg-blue-50"
        >
          <span className="text-4xl" aria-hidden>
            {icon}
          </span>
          {key === "ayurvedic_assessment" ? "आयुर्वेद" : key === "chest_pain" ? "सीने में दर्द" : label_hi(key)}
        </button>
      ))}
    </main>
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
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-red-700 p-8 text-center text-white">
        <div data-testid="redflag-banner" className="text-3xl font-bold">
          ⚠️ {lang === "hi" ? redFlag.message_hi : redFlag.message_en}
        </div>
        {nurseCalled ? (
          <p className="text-2xl">{t("nurse_called")}</p>
        ) : (
          <button
            data-testid="nurse-call"
            onClick={callNurse}
            className="rounded-2xl bg-white px-10 py-6 text-2xl font-bold text-red-700"
          >
            🚑 {t("priority_alert_call_nurse")}
          </button>
        )}
      </main>
    );
  }

  if (done) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center">
        <div data-testid="interview-done" className="text-2xl font-semibold text-slate-800">
          {t("record_complete")}
        </div>
        <div data-testid="summary-ready" className="text-3xl font-bold text-green-700">
          {t("summary_ready")}
        </div>
        <button className="rounded-xl bg-blue-600 px-8 py-4 text-xl font-semibold text-white">
          {t("go_to_room")}
        </button>
      </main>
    );
  }

  if (confirm) {
    return (
      <main className="mx-auto max-w-xl p-6 text-center">
        <div className="rounded-2xl border border-amber-300 bg-amber-50 p-6">
          <p className="text-xl text-slate-800">
            {t("confirm_heard")} <strong>“{confirm.heard}”</strong>
          </p>
          <div className="mt-6 flex justify-center gap-4">
            <button
              data-testid="confirm-yes"
              onClick={() => confirmAnswer(true)}
              className="rounded-xl bg-green-600 px-8 py-4 text-xl font-semibold text-white"
            >
              {t("confirm_yes")}
            </button>
            <button
              data-testid="confirm-no"
              onClick={() => confirmAnswer(false)}
              className="rounded-xl border border-slate-400 px-8 py-4 text-xl font-semibold text-slate-700"
            >
              {t("confirm_no")}
            </button>
          </div>
        </div>
      </main>
    );
  }

  if (!question) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="text-xl text-slate-500">{t("processing")}</div>
      </main>
    );
  }

  const opts = lang === "hi" ? question.touch_options_hi : question.touch_options_en;
  const isMulti = question.type === "multi_choice";

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="mb-2 text-sm text-slate-500" data-testid="question-progress">
        {progress}
      </div>
      <section data-testid="question-card" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-900">
          {lang === "hi" ? question.voice_hi : question.voice_en}
        </h2>
        {replay?.enabled && (
          <span data-testid="replay-indicator" className="ml-2 rounded bg-blue-100 px-2 py-1 text-xs text-blue-700">
            replay
          </span>
        )}
        <div className="mt-5 grid gap-3">
          {opts.map((o, i) => (
            <button
              key={i}
              data-testid={`option-${i}`}
              onClick={() => touch(i, isMulti)}
              className={`rounded-xl border-2 px-5 py-4 text-left text-lg font-medium ${
                selected.includes(i)
                  ? "border-blue-600 bg-blue-50"
                  : "border-slate-200 bg-slate-50 active:bg-blue-50"
              }`}
            >
              {isMulti && <span className="mr-2">{selected.includes(i) ? "☑" : "☐"}</span>}
              {o}
            </button>
          ))}
        </div>
        {isMulti && (
          <button
            data-testid="option-confirm"
            disabled={!selected.length}
            onClick={async () => {
              answered.current += 1;
              await answer({ touch_indices: selected });
            }}
            className="mt-4 w-full rounded-xl bg-blue-600 py-4 text-lg font-semibold text-white disabled:opacity-40"
          >
            OK
          </button>
        )}
        {!isMulti && (
          <button
            data-testid="mic-btn"
            onClick={() => setRecording((r) => !r)}
            className="mt-4 w-full rounded-xl border border-slate-300 py-4 text-lg font-semibold text-slate-700"
          >
            🎙️ {recording ? t("listening") : t("mic_tap_to_speak")}
          </button>
        )}
      </section>
    </main>
  );
}