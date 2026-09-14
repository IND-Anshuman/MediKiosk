# MediKiosk "God-Level" Frontend UI — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> Design authority: `impeccable` skill (C:\Users\HP\Desktop\impeccable\.agents\skills\impeccable).
> Process skill: `claude-design` (surface-first, slop diagnostic, aesthetic review pass).
> Execution skill: `frontend-feature-dev` (read conventions, verify ladder, TDD).
> TDD skill governs every task.

**Goal:** Replace the current placeholder-grade patient + doctor UI with a
minimalistic, glassmorphic, depth-aware ("3D-feel") design system that keeps
every existing `data-testid` and behavior — a calm clinical instrument, not a
SaaS landing page.

**Architecture:** Token-first CSS layer on the existing Next.js 16 App Router
app (Tailwind v4 `@theme inline` + CSS custom properties). One design-system
file (`apps/web/src/styles/tokens.css` + `glass.css` + `scene.css`), then
restyled components in place — no route changes, no state-machine changes, no
new deps (no framer-motion needed; CSS keyframes + WebAudio suffice). Ambient
3D is ONE depth scene (layered translucent planes + tilt parallax), GPU-cheap,
`prefers-reduced-motion`-gated.

**Tech stack:** Next.js 16 · React 19 · Tailwind v4 · CSS custom properties
(OKLCH) · zero new runtime dependencies.

---

## 0. Context / Current State (verified by reading the repo)

- `apps/web/src/app/globals.css` — bare starter: `--background/--foreground`
  only, Arial body font, auto dark-mode via media query. **No real tokens.**
- Components (686 lines total): `LanguagePicker(42)`, `ConsentFlow(89)`,
  `IntakeView(340)`, `DocumentsView(82)`, `DoctorPortal(133)` — functional,
  testids per `docs/UI-CONTRACT.md`, but starter `border-slate-300` styling.
- Patient flow is a single page with client-side stages:
  `lang → consent → complaint → intake → docs` (`apps/web/src/app/page.tsx`).
- Doctor portal at `/doctor?session=...`.
- i18n exists (`packages/i18n/locales/hi.json`, `en.json`) and is already used.
- Full backend is LIVE in Docker (12 containers healthy; api :8000, web :3000).
- **Users of this UI:** elderly, low-literacy, first-time patients at a govt
  hospital kiosk, in a bright, noisy OPD hall. This dominates every aesthetic
  decision. Doctors read the summary on a clinic desktop.

**Register decision (impeccable gate):** the kiosk is a **product surface**
(design serves the task: an anxious 60-year-old must complete a medical
interview unaided). The doctor portal is likewise product. There is NO brand
surface here — no hero, no marketing copy. The "3D + glass" brief is satisfied
through **depth-as-structure**: layered elevation, one ambient depth scene,
glass reserved for purposeful layering — not decorative blur everywhere.

---

## 1. Design Direction — "The Calm Instrument"

One sentence: **a backlit glass instrument panel in a bright OPD hall —
high-contrast, few colors, obvious depth, zero decoration.**

### 1.1 Color strategy — Restrained (impeccable product default)

OKLCH palette. Light theme is the ONLY theme for the patient kiosk (bright OPD
hall, sunlight on screen; dark mode fails legibility there). Doctor portal
gets the same tokens (light default).

```css
:root {
  /* Neutrals — cool clinical, chroma toward teal hue not warm */
  --bg:          oklch(0.97 0.008 210);   /* near-white, cool */
  --bg-deep:     oklch(0.93 0.012 210);   /* recessed panels */
  --surface:     oklch(0.99 0.004 210);   /* cards */
  --ink:         oklch(0.22 0.02 230);    /* body text, ~13:1 on --bg */
  --ink-2:       oklch(0.45 0.02 230);    /* secondary text, ≥4.5:1 */
  --line:        oklch(0.88 0.015 220);   /* hairlines */

  /* Accent — deep clinical teal (NOT indigo/violet AI default) */
  --accent:      oklch(0.55 0.11 210);
  --accent-ink:  oklch(0.98 0.01 210);    /* text on accent */

  /* Status — functional only */
  --danger:      oklch(0.55 0.19 25);
  --danger-bg:   oklch(0.96 0.03 25);
  --warn:        oklch(0.72 0.14 75);
  --ok:          oklch(0.60 0.12 155);

  /* Glass (see 1.3) */
  --glass-bg:    oklch(0.99 0.005 210 / 0.72);
  --glass-bg-2:  oklch(0.99 0.005 210 / 0.55);
  --glass-line:  oklch(1 0 0 / 0.65);
}
```

### 1.2 Typography

- **One family, chosen not defaulted:** `Noto Sans` (Google Fonts, already
  ships full **Devanagari + Latin** in one family — critical for hi/en parity;
  Arial currently renders Hindi poorly). Weights 400/600/700 only.
- Body 17–18px (kiosk viewing distance), line-height 1.65. Question text is
  the largest text on screen after the header: 24–28px/700.
- Display letter-spacing ≥ −0.02em (never tighter). `text-wrap: balance` on
  questions/headings.
- Numbers (token id, vitals) use `font-variant-numeric: tabular-nums`.

### 1.3 Glassmorphism — two tiers ONLY, elevation-backed

impeccable rule: glass must sit on a real depth system or it's slop.

| Tier | Where | Recipe |
|---|---|---|
| **T1 panel** | intake card, consent card, doctor summary | `background: var(--glass-bg); backdrop-filter: blur(14px) saturate(1.35); border: 1px solid var(--glass-line); box-shadow: 0 1px 2px oklch(0.22 0.02 230/0.06), 0 24px 48px -24px oklch(0.22 0.02 230/0.25);` + 1px inset top highlight `inset 0 1px 0 oklch(1 0 0/0.5)` |
| **T2 chip** | option buttons, status chips, source chips (🎤👆📄) | `background: var(--glass-bg-2); backdrop-filter: blur(8px) saturate(1.2); border: 1px solid var(--glass-line); box-shadow: 0 1px 2px …/0.05;` |

Rules: no glass on text, no glass-on-glass nesting, glass always over the
ambient scene (1.4) so the blur has something real to diffuse. Cards top out
at `border-radius: 16px` (chips 12px, pill only for tags).

### 1.4 The one depth scene — "Strata" (ambient 3D, GPU-cheap)

The patient screens share a fixed full-viewport background: **three soft
translucent color planes** drifting at different rates (CSS `@keyframes`,
transform-only, 60–90s loops) + a static conic light-source gradient. This is
the 3D: real parallax depth behind glass, not fake floating cards. Components
tilt subtly ONCE on stage transitions (see 1.5). All motion gated:

```css
@media (prefers-reduced-motion: reduce) {
  .strata i { animation: none; }
  * { transition-duration: 0.01ms !important; }
}
```

Strata recipe (in `scene.css`): `.strata` fixed inset-0, z-0, `overflow:hidden`;
three `<i>` planes: 120–140% size, radial-gradients of `--accent`/`--warn`/
`--ok` at ≤6% alpha, `will-change: transform`, translate3d loops. Tilt parallax:
scene wrapper gets `transform: perspective(1200px) rotateX(±1.2deg) rotateY(±2deg)`
driven by pointer (rAF-throttled, ±2° max — claude-design motion band for
ambient; anything more reads as seasick on a kiosk).

### 1.5 Motion inventory (complete — nothing else animates)

| Element | Motion | Timing |
|---|---|---|
| Stage transitions (lang→consent→…) | incoming card: `translateY(12px)→0` + opacity, **outgoing: none** (unmount) | 320ms ease-out-quart |
| Question advance (intake) | question text swap: old fades 8px up, new rises in | 240ms |
| Option select | T2 chip `scale(0.985)` press, then selected chip fills `--accent` | 120ms / 200ms fill |
| Confirm echo | sheet slides up from bottom edge | 280ms |
| **Red-flag alert** | banner drops from top, red bg, **slow 2s pulse** on the icon ring (the ONE attention animation) | drop 240ms, pulse 2s ×3 |
| Documents upload | progress = chip border sweep (conic-gradient), no spinner | per-upload |
| Strata scene | planes drift; pointer tilt ±2° | 60–90s loops |
| Doctor summary reveal | rows cascade-in, 40ms stagger (list reveal, not page reflex) | 240ms/row |

No entrances on scroll (kiosk has no scroll narrative). No looping pulses
except red-flag. `prefers-reduced-motion` kills strata + cascades; transitions
become crossfades.

### 1.6 Layout system

- 4pt spacing tokens (`--space-xs:4px … --space-4xl:96px`). Section padding
  one value: `clamp(24px, 4vw, 48px)`.
- Kiosk shell: content max-width **720px** centered (single-column patient
  flow; reading + huge targets), with `.shell` horizontal gutters
  `clamp(20px, 5vw, 56px)`.
- **Touch targets ≥ 72px height** for patient options (elderly + tremor),
  64px minimum everywhere else patient-facing. Doctor portal uses 40px+
  (desktop mouse).
- Progress: a thin 3-step "strata bar" under the header (Consent → Interview →
  Documents), current step filled `--accent`, completed steps get a ✓.

### 1.7 Component treatments (per existing component)

| Component | Treatment |
|---|---|
| `LanguagePicker` | Two 50/50 split full-height T1 panels, `हिन्दी` / `English` at 32px/700, subline in the other language at 15px. Entire panel is the button (72px+). Hover: border brightens to accent, no scale. |
| `ConsentFlow` | Single T1 card, one scope-question per screen with two big chips (Yes / No). Revoke link quiet at footer, always visible. Audio replay icon top-right (🔇/🔊 toggle already exists as TTS behavior — style it). |
| `ComplaintPicker` | 2×3 grid of T1 cards, each with a **large icon area (64px)** + label 20px/600. Selected: accent border 2px. AYUSH card visually distinct (warmer tint from `--warn` at 6% alpha) with a small "आयुर्वेद" tag. |
| `IntakeView` | T1 card centered; question 26px/700 with `text-wrap: balance`; voice prompt auto-plays; options as full-width T2 chips stacked (48–72px), multi-select fills accent; `option-confirm` sticky bottom bar (full-width, 72px, accent). Mic button: 88px circular, accent, bottom-right of card, `:active` ring pulse. Confirm-echo: bottom sheet with the heard text + हाँ/नहीं chips. Red-flag: full-bleed `--danger-bg` banner replaces card content, 32px/700 text, nurse-call chip 88px tall. |
| `DocumentsView` | Drop-zone = dashed 2px `--line` panel with camera icon; uploaded docs as T2 rows with per-doc status chip (`queued/reading/done` → neutral/accent/ok). |
| `DoctorPortal` | **Monitor surface.** Dense, calm: queue left column (240px), summary right (T1). Summary rows: section label 12px caps `--ink-2` (NOT an eyebrow-above-everything — it's a data table), value 16px, source chips (🎤/👆/📄) right-aligned T2. Abnormal labs get `--danger` text + `--danger-bg` chip; interactions same in `--warn`. PDF button + Confirm button accent, 48px. Timeline: vertical hairline + dots, `tabular-nums`. |

### 1.8 Copy discipline (claude-design content rule)

All patient-facing strings come from `packages/i18n` — audit them against
impeccable's jargon rule: **no "ABDM", "FHIR", "HIS", "OCR", "session" in
patient copy.** Current `hi.json` is mostly clean (says "रिकॉर्ड", "दस्तावेज़");
replace any "ABHA खाते" usage where "अपना खाता" works for patients (keep ABHA
only on the identity entry screen where the number is actually entered).
Doctor-facing UI may keep clinical vocabulary.

### 1.9 Slop self-audit targets (must score ≤2/10 before done)

Claude-design's ten tells, pre-committed mitigations: no tech gradients (1.1),
teal accent not indigo (1.1), no feature-tile grids (1.7 uses functional
grids), no accent rails, glass is tiered + elevation-backed (1.3), no
monument stats, no icon-toppers (complaint icons are functional selectors),
composition is stage-based single-focus (not center-stack), Noto Sans chosen
for Devanagari (not default Inter), surface register = product throughout.

---

## 2. Implementation Plan (TDD, bite-sized tasks)

> Every task: RED test → GREEN component/CSS → full suite → commit.
> Frontend tests use vitest + RTL; assertions on testids/classes/DOM state
> (frontend-feature-dev rule), not pixels. Visual verification via headless
> Edge screenshots (claude-design recipe) after each phase + `vision_analyze`.

### Phase A — Foundation (Tasks A1–A5)

**A1. Tokens file.** Create `apps/web/src/styles/tokens.css` with §1.1 palette
+ §1.2 type scale + §1.6 spacing tokens. Import into `globals.css` before
`@theme inline`. Update `globals.css`: body font Noto Sans (via
`next/font/google` in `layout.tsx` — `Noto_Sans`, weights 400/600/700,
`devanagari` subset), remove Arial fallback rule. Delete the auto-dark media
query (kiosk is light-only). Verify: `pnpm exec tsc --noEmit` clean; `pnpm
build` passes; screenshot `localhost:3000` still renders.

**A2. Glass utilities.** Create `apps/web/src/styles/glass.css` exporting
`.glass-panel` (T1) and `.glass-chip` (T2) exactly per §1.3. Import after
tokens. Test (RED): `apps/web/__tests__/glass.test.tsx` — render a probe div
with each class, assert computed `backdrop-filter` contains `blur(14px)` (T1)
/ `blur(8px)` (T2) via `getComputedStyle`. Commit.

**A3. Strata scene.** Create `apps/web/src/styles/scene.css` + component
`apps/web/src/components/DepthScene.tsx` (server component, pure CSS, three
`<i>` planes per §1.4). Mount in `layout.tsx` behind everything (`fixed
inset-0 -z-10`, `aria-hidden`). RED test: renders 3 planes, `aria-hidden=true`,
`prefers-reduced-motion` emulation (RTL `reduceMotion: 'reduce'`) leaves
planes without `animation`. Pointer tilt hook `useTiltParallax.ts` (rAF,
±2°, disabled under reduced motion; test asserts transform stays identity
under reduceMotion).

**A4. Kiosk shell.** `apps/web/src/components/KioskShell.tsx` — the shared
patient-frame: top header (wordmark "MediKiosk" text-only 15px/600 +
language switch chip), StrataBar progress (§1.6), `.shell` gutters, 720px
max-width, children slot. RED test: renders children, shows stage index
mapping (1/2/3 for consent/intake/docs), header text present. Wire into
`app/page.tsx` + `/doctor` (doctor variant: wider 1040px, no strata-bar).
Commit.

**A5. Fonts + i18n copy audit.** Add `Noto_Sans` via `next/font/google` in
`app/layout.tsx` (`subsets: ['latin','devanagari']`, variable
`--font-noto`). Grep `packages/i18n/locales/*.json` for patient-copy jargon
per §1.8; fix offenders (add `abha_entry` keeps ABHA; strip it from consent
copy). Verify hi/en parity test still passes (`tests/unit/test_i18n.py` is
backend but frontend parity too — extend `test_i18n` if needed). Commit.

### Phase B — Patient screens (Tasks B1–B5)

**B1. LanguagePicker.** Restyle per §1.7 (split panels, 32px labels, entire
panel clickable ≥72px). Keep testids `lang-hi/lang-en` and existing
`onSelect` contract. RED test first: assert `getComputedStyle` font-size ≥
28px, panel height ≥ 72px, border-color transitions on hover class.
Commit.

**B2. ConsentFlow.** One scope per screen with paired chips; keep
`consent-agree`, `revoke-btn` testids; add progress step 1/3 in KioskShell.
RED test: agree button ≥ 64px, revoke present + enabled-state logic
unchanged (existing 3 tests must stay green — extend, don't rewrite).
Commit.

**B3. ComplaintPicker.** 2×3 T1 grid per §1.7, AYUSH distinct tint, keep all
`cc-*` testids. RED: 6 cards render, each ≥ 96px tall, icon area present,
AYUSH card has distinct data attribute (`data-variant="ayush"`). Commit.

**B4. IntakeView (the centerpiece).** Restyle per §1.7 within the EXISTING
340-line component — re-order JSX classes, extract two subcomponents in-file
(`OptionChip`, `ConfirmEchoSheet`) without touching the dialogue state
machine or MSW wiring. All existing 6 tests must stay green untouched
(testids unchanged); add RED tests for: option chip height ≥ 72px, selected
state class `is-selected` + accent fill, confirm bar sticky bottom, redflag
banner full-bleed + `role="alert"`, stage transition animation class present
(`data-animate="stage-in"`). Visual check: full headless screenshot of an
intake run. Commit.

**B5. DocumentsView.** Drop-zone + T2 rows per §1.7, keep `doc-upload`,
`doc-item`, `doc-status` testids. RED: upload flow test (existing) stays
green; add status-chip class assertions. Commit.

### Phase C — Doctor portal (Task C1)

**C1. DoctorPortal.** Monitor-surface layout per §1.7 (queue 240px + summary
T1, section-label rows, source chips, timeline hairline+dots, danger/warn
chips). Keep ALL doctor testids (`doctor-queue`, `doctor-queue-row-{token}`,
`doctor-summary`, `timeline-item-{i}`, `abnormal-flag`, `interaction-warning`,
`summary-pdf`, `confirm-summary`). Existing tests green; RED adds: queue row
height ≥ 40px, abnormal chip has `--danger` text color class, layout is
2-col at ≥1024px (assert `getBoundingClientRect` of queue vs summary x
positions). Commit.

### Phase D — Polish + verification (Tasks D1–D4)

**D1. Slop audit + aesthetic pass.** Run claude-design's 10-tell diagnostic
against built pages (score in commit message); fix anything >2. Spacing sweep:
`grep -E "(gap|padding|margin):\s*[0-9]"` → all values on tokens. Line-height
audit: body ≥1.65, questions ≥1.3.

**D2. Visual verification ladder.** Headless Edge screenshots (per
ui-visual-refinement): patient flow at 1280×800 (kiosk) + 390×844 (tablet
fallback), doctor at 1440×900. `vision_analyze` each: check chips don't
overlap, question text legible at arm's length, left edges aligned, glass
blur visible over strata, red-flag readable. Fix findings, re-shoot.

**D3. Contrast + a11y pass.** Verify all ink/bg pairs ≥4.5:1 (script:
`oklch` → hex via culori-free approximation or manual check of the five
pairs in §1.1). Focus states: every interactive element gets `:focus-visible`
ring (2px `--accent`, offset 2px). Touch target audit ≥72px patient / ≥40px
doctor. `role="alert"` on redflag. Tab order = visual order.

**D4. Build + regression gate.** `pnpm exec tsc --noEmit` clean → `pnpm
test` (all existing + new tests) → `pnpm build` (production, standalone
output for Docker) → `docker compose up -d --build web` → screenshot live
`localhost:3000` + `curl /doctor`. Update `docs/UI-CONTRACT.md` if any
testid changed (none should). Final commit + push.

---

## 3. Files likely to change

```
apps/web/src/styles/tokens.css          [new]
apps/web/src/styles/glass.css           [new]
apps/web/src/styles/scene.css           [new]
apps/web/src/components/DepthScene.tsx  [new]
apps/web/src/components/KioskShell.tsx  [new]
apps/web/src/components/useTiltParallax.ts [new]
apps/web/src/app/layout.tsx             [modify — font + scene mount]
apps/web/src/app/globals.css            [modify — tokens import, Noto]
apps/web/src/app/page.tsx               [modify — KioskShell wrapper]
apps/web/src/components/LanguagePicker.tsx  [restyle]
apps/web/src/components/ConsentFlow.tsx     [restyle]
apps/web/src/components/IntakeView.tsx      [restyle + 2 subcomponents]
apps/web/src/components/DocumentsView.tsx   [restyle]
apps/web/src/components/DoctorPortal.tsx    [restyle]
apps/web/src/components/__tests__/*     [extend — RED tests per task]
packages/i18n/locales/*.json            [copy audit fixes only]
docs/UI-CONTRACT.md                     [only if a testid changes — none planned]
README.md                               [screenshot section, optional]
```

**No changes:** dialogue/state logic, MSW handlers, API routes, backend
services, next.config, package.json (zero new deps).

---

## 4. Tests / validation

| Layer | Tool | Gate |
|---|---|---|
| Component behavior | vitest + RTL (existing 9 + ~12 new) | all green |
| UI contract | `data-testid` (checked by `infra/scripts/check_ui_contract.py`) | unchanged |
| Types | `pnpm exec tsc --noEmit` | clean |
| Production build | `pnpm build` | succeeds |
| Visual | headless Edge + `vision_analyze` (1280×800, 390×844, 1440×900) | no overlap/clipping, glass + strata visible |
| Contrast | 5 pairs in §1.1 | ≥4.5:1 body, ≥3:1 large |
| Reduced motion | RTL `reduceMotion: 'reduce'` | no animation |
| Live | `docker compose up -d --build web` + curl 3000 | 200 + screenshot |

---

## 5. Risks / tradeoffs / open questions

| Risk | Mitigation |
|---|---|
| backdrop-filter perf on cheap kiosk hardware | Strata planes are transform-only; blur radii ≤14px; test on the actual demo device in D2; fallback `@supports not (backdrop-filter)` = solid `--surface` |
| Elderly users misread glass affordances | Depth carries meaning only (T1=container, T2=action); text never sits on glass without a surface behind it; contrast held ≥4.5:1 |
| Restyling IntakeView breaks its 6 existing tests | Tests assert testids/behavior, not classes — contract untouched; new assertions additive |
| Devanagari rendering | Noto Sans (single family both scripts) — replaces Arial which renders Hindi poorly |
| "3D" ambition vs product register | Depth = strata scene + tiered elevation + one transition tilt; no floating-card parallax, no WebGL (frontend-feature-dev product-surface gate) |
| Light-only theme | Deliberate: bright OPD hall. Doctor portal shares tokens; if doctors work in dark rooms later, dark tokens are one media-query addition |

**Open questions (defaults chosen, flag to change):**
1. Accent hue teal `oklch(0.55 0.11 210)` vs a deeper medical blue — teal chosen to avoid the AI-indigo tell; switchable by editing one token.
2. Voice input affordance: hold-to-speak (current) — keep, style as 88px circular press-and-hold.
3. Kiosk is desktop-first 1280×800; phone fallback (390px) is single-column stacking, not a designed mobile experience (matches hardware reality).

---

## 6. Execution handoff

Suggested: subagent-driven-development, one subagent per phase (A foundation,
B patient screens, C doctor portal, D polish) with the two-stage review.
Phase A first alone — tokens+glass+scene unblock everything; B tasks can
parallelize after A lands.

**Plan complete.** Save path noted below; execution not started.
