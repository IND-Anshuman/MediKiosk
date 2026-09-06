import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ConsentFlow from "@/components/ConsentFlow";

describe("ConsentFlow", () => {
  it("renders consent copy, grants on agree", async () => {
    const granted: string[] = [];
    render(<ConsentFlow sessionId="sess-mock-1" onGranted={(scopes) => granted.push(...scopes)} />);
    fireEvent.click(screen.getByTestId("consent-agree"));
    await waitFor(() => expect(granted).toContain("his_share"));
  });

  it("shows revoke button (disabled until granted)", () => {
    render(<ConsentFlow sessionId="sess-mock-1" onGranted={() => {}} />);
    const btn = screen.getByTestId("revoke-btn");
    expect(btn).toBeInTheDocument();
    expect(btn).toBeDisabled();
  });
});