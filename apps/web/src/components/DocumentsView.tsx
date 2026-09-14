"use client";

/** Documents capture (plan §1.7): dashed drop-zone + T2 status-chip rows. */
import { useCallback, useState } from "react";
import { t } from "@/lib/i18n";

interface DocRow {
  doc_id: string;
  name: string;
  status: string;
}

export default function DocumentsView({ sessionId }: { sessionId: string }) {
  const [docs, setDocs] = useState<DocRow[]>([]);

  const upload = useCallback(
    async (files: FileList | null) => {
      if (!files) return;
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`/api/documents/upload?session_id=${sessionId}`, {
          method: "POST",
          body: form,
        });
        const body = await res.json();
        const row: DocRow = { doc_id: body.doc_id, name: file.name, status: body.status ?? "processing" };
        setDocs((d) => [...d, row]);
        // poll status until done
        const timer = setInterval(async () => {
          const s = await fetch(`/api/documents/${row.doc_id}/status`).then((r) => r.json());
          setDocs((d) => d.map((x) => (x.doc_id === row.doc_id ? { ...x, status: s.status } : x)));
          if (s.status === "done") clearInterval(timer);
        }, 1500);
      }
    },
    [sessionId]
  );

  return (
    <div className="flex w-full flex-col gap-[var(--space-lg)]">
      <h2
        className="font-bold text-[var(--ink)]"
        style={{ fontSize: "clamp(24px, 3.4vw, 30px)", letterSpacing: "-0.02em" }}
      >
        {t("documents_scan")}
      </h2>

      <label
        htmlFor="doc-input"
        className="glass-panel flex min-h-[160px] cursor-pointer flex-col items-center justify-center gap-[var(--space-sm)] text-[var(--ink-2)] transition-colors hover:border-[var(--accent)]"
        style={{ borderStyle: "dashed" }}
      >
        <span className="text-[44px] leading-none" aria-hidden>
          📄
        </span>
        <span className="text-lg font-semibold text-[var(--ink)]">{t("documents_scan")}</span>
        <span className="text-[13px]">दस्तावेज़ की फोटो लें या अपलोड करें</span>
        <input
          id="doc-input"
          data-testid="doc-upload"
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="hidden"
          onChange={(e) => void upload(e.target.files)}
        />
      </label>

      <ul className="flex flex-col gap-[var(--space-md)]">
        {docs.map((d) => (
          <li
            key={d.doc_id}
            data-testid="doc-item"
            className="glass-chip flex items-center justify-between px-[var(--space-base)] py-[var(--space-md)]"
          >
            <span className="min-w-0 truncate font-medium text-[var(--ink)]">{d.name}</span>
            <span
              data-testid="doc-status"
              className="ml-[var(--space-md)] shrink-0 rounded-full px-[var(--space-md)] py-[var(--space-xs)] text-[13px] font-semibold"
              style={
                d.status === "done"
                  ? { background: "var(--accent-soft)", color: "var(--ok)" }
                  : { background: "var(--warn-bg)", color: "var(--ink-2)" }
              }
            >
              {d.status === "done" ? "✓" : "⏳"} {d.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
