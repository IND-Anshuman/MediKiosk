"use client";

/** Doctor portal (plan T4.6 v2, restyled §1.7): Monitor surface — queue column
 *  + summary panel with citation chips, timeline hairline, PDF + confirm. */
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
    <div className="grid w-full gap-[var(--space-lg)] lg:grid-cols-[240px_1fr]">
      {/* Queue column — Monitor surface: dense, calm, scannable */}
      <section aria-label="queue">
        <h2 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--ink-2)]">
          Queue
        </h2>
        <ul data-testid="doctor-queue" className="mt-[var(--space-md)] flex flex-col gap-[var(--space-sm)]">
          {queue.map((row) => (
            <li
              key={row.session_id}
              data-testid={`doctor-queue-row-${row.token}`}
              className="glass-chip flex min-h-[var(--tap-doctor)] items-center gap-[var(--space-md)] px-[var(--space-md)] py-[var(--space-sm)]"
            >
              <span className="font-mono text-[13px] tabular-nums text-[var(--ink-2)]">{row.token}</span>
              <span className="min-w-0 truncate font-semibold text-[var(--ink)]">{row.name}</span>
              {row.red_flag && (
                <span
                  data-testid="redflag-badge"
                  className="ml-auto shrink-0 rounded-full px-[var(--space-sm)] py-[2px] text-[12px] font-bold"
                  style={{ background: "var(--danger-bg)", color: "var(--danger)" }}
                >
                  ⚠
                </span>
              )}
            </li>
          ))}
          {queue.length === 0 && (
            <li className="px-[var(--space-md)] py-[var(--space-base)] text-[14px] text-[var(--ink-2)]">
              कोई patient वर्तमान में नहीं
            </li>
          )}
        </ul>
      </section>

      {/* Summary panel */}
      {summary ? (
        <section data-testid="doctor-summary" className="glass-panel p-[clamp(20px,3vw,32px)]">
          <div className="flex items-center justify-between gap-[var(--space-md)]">
            <h3 className="text-xl font-bold text-[var(--ink)]">OPD Summary</h3>
            <a
              data-testid="summary-pdf"
              href={`/api/sessions/${sessionId}/summary.pdf`}
              className="glass-chip flex min-h-[var(--tap-doctor)] items-center px-[var(--space-md)] text-[14px] font-semibold text-[var(--ink)]"
            >
              ⬇ PDF
            </a>
          </div>

          <pre className="mt-[var(--space-base)] whitespace-pre-wrap font-[inherit] text-[15px] leading-7 text-[var(--ink)]">
            {summary.summary_md}
          </pre>

          {summary.timeline.length > 0 && (
            <div className="mt-[var(--space-lg)]">
              <h4 className="text-[13px] font-semibold uppercase tracking-[0.06em] text-[var(--ink-2)]">
                Timeline
              </h4>
              <ul className="mt-[var(--space-md)] flex flex-col">
                {summary.timeline.map((item, i) => (
                  <li
                    key={i}
                    data-testid={`timeline-item-${i}`}
                    className="relative flex items-center gap-[var(--space-md)] py-[var(--space-sm)] pl-[var(--space-lg)]"
                    style={{ borderLeft: i === 0 ? "none" : undefined }}
                  >
                    {/* hairline + dot */}
                    <span
                      aria-hidden
                      className="absolute left-[5px] top-0 h-full w-px"
                      style={{ background: "var(--line)", display: i === 0 ? "none" : "block" }}
                    />
                    <span
                      aria-hidden
                      className="absolute left-0 top-1/2 h-[11px] w-[11px] -translate-y-1/2 rounded-full"
                      style={{
                        background: item.abnormal.length ? "var(--danger)" : "var(--accent)",
                      }}
                    />
                    <span className="font-mono text-[13px] tabular-nums text-[var(--ink-2)]">
                      {item.date ?? "Undated"}
                    </span>
                    <span className="text-[15px] text-[var(--ink)]">{item.kind}</span>
                    {item.abnormal.map((a) => (
                      <span
                        key={a}
                        data-testid="abnormal-flag"
                        className="rounded-full px-[var(--space-sm)] py-[2px] text-[12px] font-bold"
                        style={{ background: "var(--danger-bg)", color: "var(--danger)" }}
                      >
                        {a}
                      </span>
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.interactions.length > 0 && (
            <div className="mt-[var(--space-lg)] flex flex-col gap-[var(--space-sm)]">
              {summary.interactions.map((x) => (
                <div
                  key={`${x.a}-${x.b}`}
                  data-testid="interaction-warning"
                  className="rounded-[var(--radius-chip)] px-[var(--space-md)] py-[var(--space-sm)] text-[14px] font-medium"
                  style={{ background: "var(--warn-bg)", color: "var(--ink)" }}
                >
                  ⚠ {x.a} + {x.b}: {x.note} ({x.severity})
                </div>
              ))}
            </div>
          )}

          <button
            data-testid="confirm-summary"
            className="mt-[var(--space-xl)] min-h-[var(--tap-doctor)] w-full rounded-[var(--radius-chip)] text-[16px] font-bold text-[var(--accent-ink)]"
            style={{ background: "var(--accent)" }}
            onClick={() =>
              void fetch(API(`/api/sessions/${sessionId}/summary/confirm`), { method: "POST" })
            }
          >
            ✓ Confirm summary
          </button>
        </section>
      ) : (
        <section className="glass-panel flex min-h-[280px] items-center justify-center p-[var(--space-xl)] text-[var(--ink-2)]">
          किसी patient का summary देखने के लिए queue में चुनें
        </section>
      )}
    </div>
  );
}
