"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import DoctorPortal from "@/components/DoctorPortal";

export const dynamic = "force-dynamic";

export default function DoctorPage() {
  const sp = useSearchParams();
  const sessionId = sp.get("session") ?? undefined;
  return (
    <Suspense fallback={<main className="p-6">Loading…</main>}>
      <DoctorPortal sessionId={sessionId} />
    </Suspense>
  );
}