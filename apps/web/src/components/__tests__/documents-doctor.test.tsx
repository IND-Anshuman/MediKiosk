import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DoctorPortal from "@/components/DoctorPortal";
import DocumentsPageInner from "@/components/DocumentsView";

describe("DocumentsView", () => {
  it("uploads a file, shows doc row + status chip (MSW)", async () => {
    render(<DocumentsPageInner sessionId="sess-mock-1" />);
    const input = screen.getByTestId("doc-upload");
    fireEvent.change(input, {
      target: { files: [new File(["x"], "lab.png", { type: "image/png" })] },
    });
    await waitFor(() => expect(screen.getByTestId("doc-item")).toBeInTheDocument());
    expect(screen.getByTestId("doc-status")).toBeInTheDocument();
  });
});

describe("DoctorPortal", () => {
  it("renders queue row with red-flag badge (MSW)", async () => {
    render(<DoctorPortal />);
    const row = await screen.findByTestId("doctor-queue-row-T-0042");
    expect(row).toBeInTheDocument();
    expect(screen.getByTestId("redflag-badge")).toBeInTheDocument();
  });

  it("renders summary with timeline + abnormal + interaction + pdf (MSW)", async () => {
    render(<DoctorPortal sessionId="sess-mock-1" />);
    await screen.findByTestId("doctor-summary");
    expect(screen.getByTestId("timeline-item-0")).toBeInTheDocument();
    expect(screen.getByTestId("abnormal-flag")).toBeInTheDocument();
    expect(screen.getByTestId("interaction-warning")).toBeInTheDocument();
    expect(screen.getByTestId("summary-pdf")).toBeInTheDocument();
  });
});