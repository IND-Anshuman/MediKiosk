"use client";

import { use } from "react";
import DocumentsView from "@/components/DocumentsView";

export default function DocumentsPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  return <DocumentsView sessionId={sessionId} />;
}