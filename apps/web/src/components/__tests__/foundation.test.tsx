/** Phase A foundation tests (plan §2 Phase A): tokens, glass tiers, strata
 *  scene, kiosk shell. jsdom cannot compute backdrop-filter/animation from
 *  imported CSS, so stylesheet rules are asserted textually; behavior via DOM. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DepthScene from "@/components/DepthScene";
import KioskShell from "@/components/KioskShell";

const read = (p: string) =>
  readFileSync(resolve(__dirname, "../../../src/styles", p), "utf-8");

describe("glass tiers (plan §1.3) — stylesheet contract", () => {
  const css = read("glass.css");

  it("defines exactly two tiers with distinct blur values", () => {
    expect(css).toMatch(/\.glass-panel[^}]*blur\(14px\)/s);
    expect(css).toMatch(/\.glass-chip[^}]*blur\(8px\)/s);
  });

  it("panels carry elevation shadow + inset toplight (not flat glass)", () => {
    expect(css).toMatch(/--glass-shadow/);
    expect(css).toMatch(/--glass-toplight/);
  });

  it("has a solid fallback for GPUs without backdrop-filter", () => {
    expect(css).toMatch(/@supports not[^{]*backdrop-filter/s);
  });

  it("selected chip swaps to accent fill", () => {
    expect(css).toMatch(/\.glass-chip\.is-selected[^}]*var\(--accent\)/s);
  });
});

describe("tokens (plan §1.1/1.6) — token contract", () => {
  const css = read("tokens.css");

  it("pins the palette to OKLCH with teal accent (no AI-indigo)", () => {
    expect(css).toContain("--accent: oklch(0.55 0.11 210)");
    expect(css).not.toMatch(/--accent:.*(?:#6366f1|8b5cf6)/i);
  });

  it("defines 4pt spacing scale and radii ceiling 16px", () => {
    expect(css).toContain("--space-xs: 4px");
    expect(css).toContain("--space-4xl: 96px");
    expect(css).toContain("--radius-panel: 16px");
  });

  it("defines patient touch target 72px", () => {
    expect(css).toContain("--tap-patient: 72px");
  });
});

describe("strata depth scene (plan §1.4)", () => {
  const css = read("scene.css");

  it("renders exactly three planes, aria-hidden", () => {
    render(<DepthScene />);
    const scene = screen.getByTestId("depth-scene");
    expect(scene.getAttribute("aria-hidden")).toBe("true");
    expect(scene.querySelectorAll("i")).toHaveLength(3);
  });

  it("three planes drift on transform-only keyframes", () => {
    const loops = css.match(/@keyframes strata-drift-[abc]/g) ?? [];
    expect(loops).toHaveLength(3);
    expect(css).toMatch(/animation: strata-drift-a 90s/);
    expect(css).not.toMatch(/animation[^;]*(left|top|width|margin):/); // transform-only
  });

  it("reduced motion kills the scene", () => {
    const block = css.split("@media (prefers-reduced-motion: reduce)")[1] ?? "";
    expect(block).toContain("animation: none");
  });
});

describe("kiosk shell (plan §1.6)", () => {
  it("renders header, progress for intake stage, and children", () => {
    render(
      <KioskShell stage="intake">
        <div>child-content</div>
      </KioskShell>,
    );
    expect(screen.getByTestId("kiosk-shell")).toBeTruthy();
    expect(screen.getByText("MediKiosk")).toBeTruthy();
    expect(screen.getByText("child-content")).toBeTruthy();
    expect(screen.getByText("2/3")).toBeTruthy();
  });

  it("doctor variant is wide and hides progress", () => {
    render(
      <KioskShell stage="intake" variant="doctor">
        <div>doc</div>
      </KioskShell>,
    );
    expect(screen.queryByText("2/3")).toBeNull();
  });
});