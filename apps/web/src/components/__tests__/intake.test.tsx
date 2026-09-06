import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import IntakePageInner from "@/components/IntakeView";
import { resetDialogueMock } from "@/mocks/handlers";

/** Walk N answers. multi_choice: tap option-0 then option-confirm; else tap option-0. */
async function walk(n: number) {
  for (let i = 0; i < n; i++) {
    await screen.findByTestId("question-card", {}, { timeout: 3000 });
    const confirmBtn = await screen.queryByTestId("option-confirm");
    if (confirmBtn && !(confirmBtn as HTMLButtonElement).disabled) {
      fireEvent.click(confirmBtn);
    } else {
      fireEvent.click(await screen.findByTestId("option-0"));
      // multi_choice: after tap, click confirm
      const c = await screen.queryByTestId("option-confirm");
      if (c && !(c as HTMLButtonElement).disabled) fireEvent.click(c);
    }
    await waitFor(
      () => {
        // advance is complete when question text or a terminal card changes;
        // simplest: wait a tick for state update
        return new Promise((r) => setTimeout(r, 120));
      },
      { timeout: 1000 }
    );
  }
}

describe("IntakeView", () => {
  it("renders question + touch options; tapping advances (MSW)", async () => {
    resetDialogueMock();
    render(<IntakePageInner sessionId="sess-mock-1" lang="hi" />);
    expect(await screen.findByTestId("question-card")).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId("option-0"));
    await waitFor(() => expect(screen.getByTestId("question-progress")).toBeInTheDocument());
  });

  it("shows red-flag banner on the 5th answer (MSW associated=Sweating)", async () => {
    resetDialogueMock();
    render(<IntakePageInner sessionId="sess-mock-1" lang="hi" />);
    // 4 single answers: onset, location, character, radiation
    for (let i = 0; i < 4; i++) {
      await screen.findByTestId("question-card", {}, { timeout: 3000 });
      fireEvent.click(await screen.findByTestId("option-0"));
      await new Promise((r) => setTimeout(r, 300));
    }
    // 5th: associated (multi_choice) -> tap Sweating then confirm
    await screen.findByTestId("question-card", {}, { timeout: 3000 });
    fireEvent.click(await screen.findByTestId("option-0"));
    fireEvent.click(await screen.findByTestId("option-confirm"));
    await waitFor(() => expect(screen.getByTestId("redflag-banner")).toBeInTheDocument(), {
      timeout: 3000,
    });
  });

  it("confirmation echo renders yes/no when server asks (low confidence)", async () => {
    resetDialogueMock();
    render(
      <IntakePageInner
        sessionId="sess-mock-1"
        lang="hi"
        replay={{ enabled: true, confidence: 0.4 }}
      />
    );
    // replay auto-answers with asr_confidence 0.4; the 4th (radiation) triggers confirm
    await waitFor(() => expect(screen.getByTestId("confirm-yes")).toBeInTheDocument(), {
      timeout: 8000,
    });
  });
});