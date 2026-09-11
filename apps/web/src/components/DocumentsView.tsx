"use client";

/** Documents capture UI (plan T4.5): camera/file upload, per-doc status chips. */
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
    <main className="mx-auto max-w-xl p-6">
      <h2 className="text-2xl font-bold text-slate-900">{t("documents_scan")}</h2>
      <label
        htmlFor="doc-input"
        className="mt-4 flex min-h-[8rem] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white text-slate-600"
      >
        <span className="text-4xl" aria-hidden>
          📄
        </span>
        <span className="text-lg">{t("documents_scan")}</span>
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
      <ul className="mt-4 space-y-2">
        {docs.map((d) => (
          <li
            key={d.doc_id}
            data-testid="doc-item"
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3"
          >
            <span className="text-slate-800">{d.name}</span>
            <span
              data-testid="doc-status"
              className={`rounded-full px-3 py-1 text-sm ${
                d.status === "done" ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"
              }`}
            >
              {d.status === "done" ? "✓" : "⏳"} {d.status}
            </span>
          </li>
        ))}
      </ul>
    </main>
  );
}