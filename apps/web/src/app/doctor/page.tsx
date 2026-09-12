"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import DoctorPortal from "@/components/DoctorPortal";

function DoctorContent() {
  const sp = useSearchParams();
  const sessionId = sp.get("session") ?? undefined;
  return <DoctorPortal sessionId={sessionId} />;
}

export default function DoctorPage() {
  return (
    <Suspense fallback={<main className="p-6">Loading…</main>}>
      <DoctorContent />
    </Suspense>
  );
}