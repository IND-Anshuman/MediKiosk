"use client";

import { use } from "react";
import IntakePageInner from "@/components/IntakeView";

export default function IntakePage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  return <IntakePageInner sessionId={sessionId} lang="hi" />;
}