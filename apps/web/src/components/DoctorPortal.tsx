"use client";

/** Doctor portal (plan T4.6 v2): queue + summary with slot-citation chips,
 *  timeline (AD-7), abnormal labs + interaction warnings, PDF export. */
import { useEffect, useState } from "react";

interface QueueRow {
  session_id: string;
  token: string;
  name: string;
  complaint: string;
  red_flag: boolean;
  status: string;
}

interface SummaryData {
  summary_md: string;
  timeline: { date: string | null; kind: string; abnormal: string[] }[];
  interactions: { a: string; b: string; severity: string; note: string }[];
}

const API = (p: string) => `${p}`;

export default function DoctorPortal({ sessionId }: { sessionId?: string }) {
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [summary, setSummary] = useState<SummaryData | null>(null);

  useEffect(() => {
    const load = () =>
      fetch(API("/api/doctor/queue"))
        .then((r) => r.json())
        .then((b) => setQueue(b.queue));
    void load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    void fetch(API(`/api/sessions/${sessionId}/summary`))
      .then((r) => r.json())
      .then(setSummary);
  }, [sessionId]);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h2 className="text-2xl font-bold text-slate-900">Doctor Queue</h2>
      <ul data-testid="doctor-queue" className="mt-3 space-y-2">
        {queue.map((row) => (
          <li
            key={row.session_id}
            data-testid={`doctor-queue-row-${row.token}`}
            className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3"
          >
            <span className="font-mono text-slate-500">{row.token}</span>
            <span className="font-semibold text-slate-800">{row.name}</span>
            <span className="text-slate-500">{row.complaint}</span>
            {row.red_flag && (
              <span
                data-testid="redflag-badge"
                className="ml-auto rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-700"
              >
                ⚠ red flag
              </span>
            )}
          </li>
        ))}
      </ul>

      {summary && (
        <section data-testid="doctor-summary" className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold">OPD Summary</h3>
            <a
              data-testid="summary-pdf"
              href={`/api/sessions/${sessionId}/summary.pdf`}
              className="rounded-lg border border-slate-300 px-3 py-1 text-sm text-slate-700"
            >
              ⬇ PDF
            </a>
          </div>
          <pre className="mt-3 whitespace-pre-wrap font-sans text-slate-800">{summary.summary_md}</pre>

          {summary.timeline.length > 0 && (
            <div className="mt-5">
              <h4 className="font-semibold text-slate-700">Timeline</h4>
              <ul className="mt-2 space-y-1">
                {summary.timeline.map((item, i) => (
                  <li
                    key={i}
                    data-testid={`timeline-item-${i}`}
                    className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-slate-700"
                  >
                    <span className="font-mono text-sm">{item.date ?? "Undated"}</span>
                    <span>{item.kind}</span>
                    {item.abnormal.map((a) => (
                      <span key={a} data-testid="abnormal-flag" className="rounded bg-red-100 px-2 text-sm text-red-700">
                        {a}
                      </span>
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.interactions.length > 0 && (
            <div className="mt-4 space-y-2">
              {summary.interactions.map((x) => (
                <div
                  key={`${x.a}-${x.b}`}
                  data-testid="interaction-warning"
                  className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900"
                >
                  ⚠ {x.a} + {x.b}: {x.note} ({x.severity})
                </div>
              ))}
            </div>
          )}

          <button
            data-testid="confirm-summary"
            className="mt-6 w-full rounded-xl bg-green-600 py-3 text-lg font-semibold text-white"
            onClick={() =>
              void fetch(API(`/api/sessions/${sessionId}/summary/confirm`), { method: "POST" })
            }
          >
            ✓ Confirm summary
          </button>
        </section>
      )}
    </main>
  );
}