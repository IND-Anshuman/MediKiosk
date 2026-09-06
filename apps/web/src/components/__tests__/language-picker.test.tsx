import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import LanguagePicker from "@/components/LanguagePicker";
import { getLang } from "@/lib/i18n";

describe("LanguagePicker", () => {
  it("shows Hindi and English, sets language on click", () => {
    render(<LanguagePicker />);
    fireEvent.click(screen.getByTestId("lang-hi"));
    expect(getLang()).toBe("hi");
    fireEvent.click(screen.getByTestId("lang-en"));
    expect(getLang()).toBe("en");
  });
});