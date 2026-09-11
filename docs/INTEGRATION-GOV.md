# MediKiosk Government-Integration Assessment & Plan

**Question this doc answers:** Can MediKiosk integrate with present Govt of
India websites/software to pull information or assist their operation — and if
not, what integration features must be built?

**Verdict up front (honest):**
- **Natural fit:** ABDM (ABHA IDs, HIE, consent), Bhashini (ASR/TTS), PM-JAY
  (read-only eligibility), IDSP/IHIP (syndromic export), eSanjeevani
  (hand-off only), NHA NCD framework.
- **Not open today (with evidence):** eSanjeevani has NO public third-party
  API; ANMOL/RCH has no public API; PM-JAY transaction APIs are
  partner-empanelled (NHA credential-gated); IHIP ingestion is offline/lab
  flow. For all of these the plan ships adapter seams + mock/simulated
  integrations, clearly labeled — never fake a live integration claim.

---

## 1. Integration-by-integration assessment

### 1.1 ABDM / ABHA — the backbone ✅ READY (sandbox + production path)

The National Health Authority's Digital Health Mission is explicitly built
for this: a public sandbox (sandbox.abdm.gov.in) any software can join, with
milestoned compliance (M1: ABHA creation/verification; M2: linking records
to Health Information Provider; M3: Health Information User consented
fetch; M4: unified). Our repo already has: `fhir/` bundle builder, ABHA
validator (14-digit + address form), `AbhaAdapter` protocol with
`AbhaMock`, sandbox application logged (T0.5).

**Gap to close (all in existing services, no rework):**
- **ABDM M1 (candidate now):** OTP-verified ABHA creation at the kiosk for
  walk-ins (mobile-number-based ABHA, exactly the demographic the
  walk-in flow captures). Env `ABDM_BASE_URL` + client id/secret; adapter
  interface already exists — implement `AbdmSandboxAdapter` beside the mock.
- **HIP (M2):** after doctor confirms summary, our FHIR bundle becomes a
  `DocumentReference`/`Composition` care-context bundle linked to the
  patient's ABHA — "push to HIE" stops being a logged outbox and becomes
  the real `/links/context` + confirm flow.
- **HIU (M3):** pull PRIOR records — our document-scan step is the fallback
  when the patient has no linked history. Reverse of the same coin:
  `ConsentArtifact` (already in the schema) maps directly onto ABDM consent
  artifacts; revoke/purge endpoints map onto ABDM consent-artifact revoke.
- **Credentials reality:** sandbox is free/self-serve (days); production M1
  needs partner onboarding — flag honestly at judging, ship the sandbox
  adapter + mock fallback.

**Build:** `services/fhir/adapters/abdm_sandbox.py` (M1: generate/verify
ABHA), extend `/push` to attempt HIE link when creds exist; consent router
gains consent-artifact ID mapping. Size **M**. Demo: real sandbox call
(2 registered test numbers) or mock behind env flag — same code path.

### 1.2 Bhashini / ULCA — regional languages ✅ READY (registration needed)

Bhashini (National Language Translation Mission) exposes free-to-register
org APIs: ASR, NMT (translation), TTS pipelines (ULCA) across 22 scheduled
languages. This is the regional-flexibility spine (ROADMAP §0.1) made real
by a government service.

**Build:** `services/asr` + `services/tts` each gain a `bhashini` backend
behind the existing contract (ASR: language auto-detect → ULCA pipeline
service-id → transcript; TTS: text → pipeline → audio). `LANG_BACKEND=local|bhashini|edge`
env chain with graceful fallback to faster-whisper/edge-tts when quota or
network fails. NMT adapter also translates the doctor's CONFIRMED summary
into the patient's language for the readable-Rx card (ROADMAP feature 6).
Size **S–M per adapter**. The service contracts already isolate this —
adapter pattern already proven (ASR `_transcribe`, TTS `_synthesize`).

### 1.3 PM-JAY / Ayushman Bharat — eligibility READ ✅ / claims ❌ (by design)

NHA's scheme systems: beneficiary eligibility APIs exist for empanelled
hospitals (credential-gated); transaction/claims flow through empanelled
HIS only. MediKiosk must NOT do claims (ROADMAP rejects it).

**Build (read-only, huge value, low risk):** at Identify step, patient (or
attendant) taps "Ayushman card?" → we check `pmjay_eligible` via:
(a) empanelled-hospital credential if the deployment has one (state pack
field), else (b) the public beneficiary-lookup experience (ABHA-linked
family details) rendered as a guided assist: step-by-step on-screen guide
to check on the PMJAY portal/Amrit app — the kiosk walks the attendant
through it in their language. Registry row gains `scheme: pmjay|state|none`
for queue prioritization + admin dashboards. **No claims, no payments, no
fake eligibility API** — if no credential exists we say "guide mode" on
screen. Size **S (guide) + M (credentialed adapter)**.

### 1.4 IDSP / IHIP — syndromic surveillance export ✅ FORMAT-READY

Integrated Health Information Platform (IHIP) is the national outbreak
pipeline; its weekly syndromic forms (fever/cough/rash clusters by
district) are exactly what our ROADMAP feature 4 aggregates. There is no
public self-serve ingestion API — so we EXPORT in their shape.

**Build:** surveillance aggregator gains an "IDSP syndromic report"
renderer: our day×pincode bins → the S-form weekly fields (fever, ARI,
rash, acute diarrheal) as CSV/PDF a district officer can paste into IHIP.
Later: MOU with a state for direct push. Size **S** (renderer on existing
aggregation). This turns "fancy dashboard" into "feeds a 120-year-old
national surveillance program" — the difference between a demo and public
infrastructure.

### 1.5 eSanjeevani — telemedicine hand-off ⚠️ NO PUBLIC API (bridge honestly)

National telemedicine service, fully MoHFW-integrated, but no third-party
API; patients use its own portal/app. MediKiosk should not (and cannot)
embed it.

**Build (assist, don't compete):** the kiosk's role is the physical OPD's
digital front door — add an "eSanjeevani queue assist": when the doctor's
queue is long / patient is a follow-up suited to teleconsult, generate the
patient's structured summary as a **printable/PDF hand-off packet** with QR
(linking to our patient-side card) that the tele-consult doctor on the other
end can read — we hand off to the doctor, not to the platform. If/when NHA
opens an API, the same FHIR bundle posts there (our /push shape is ready).
Size **S**. Slide framing: "respects the government's telemedicine stack;
makes it better-fed."

### 1.6 ANMOL / RCH portal — maternal-child health ❌ NO PUBLIC API (assist + export)

ANMOL (ANM Online) is the ASHA/ANM ground-truth app for ANC visits and
immunization; no public third-party API. But the MCP-card capture
(ROADMAP feature 7) produces structured immunization data that is
 laborious for ANMs to re-enter.

**Build:** MCP-card OCR produces an immunization-gap check + a
"RCH-friendly" export (the WHO-immunization schedule mapped to India's
UIP dates) printed as a slip the ANM can staple into her ANMOL entry
workflow; later state-MOU direct sync. This assists the operation of a
govt system at the exact point it hurts (data entry burden). Size **S**.

### 1.7 NCD portal / NPCDCS screening framework ⚠️ ALIGNMENT (no push, standard shapes)

The national NCD screening program (CBNAST/CPHC framework) uses standard
reporting templates for PHC/NCD screening; state NCD cells submit through
their own HMIS. Our chronic follow-up (fast-track) + abnormal-lab flags
produce the same fields.

**Build:** registry/report generator emitting the NCD screening summary
format (per state pack template) as PDF/CSV for the NCD cell. Size **S**.

### 1.8 HIS/eHospital — the actual day-1 reality ✅ (already designed)

Most government hospitals run eHospital or a state HMIS with FHIR-ish or
HL7-ish interfaces (or none). Our adapter seam already exists
(`HIS_FHIR_URL` + outbox fallback). State pack declares the local HIS
endpoint + auth; where the hospital has no API, the doctor-portal summary +
PDF IS the integration (print + attach to file). Size **0 extra** — this
is deployment configuration, exactly as planned.

---

## 2. Integration feature list added to the roadmap

| ID | Feature | Integrates with | Status | Size |
|---|---|--- assessment |---|---|
| G1 | ABDM M1 sandbox adapter: kiosk-side ABHA creation + verify | ABDM sandbox → prod | **build now** | M |
| G2 | HIP push: confirmed summary → HIE care context (M2 flow) | ABDM | build now (sandbox) | M |
| G3 | Consent-artifact mapping: our grant/revoke ↔ ABDM consent manager | ABDM | build now | S |
| G4 | Bhashini ASR/TTS/NMT backends behind existing contracts | ULCA/Bhashini | **build now** | S–M |
| G5 | PM-JAY eligibility chip (credentialed read) + guide-mode fallback | NHA scheme systems | build now (guide) | S+M |
| G6 | IDSP-format syndromic export renderer | IHIP/IDSP | build now | S |
| G7 | eSanjeevani hand-off packet (summary PDF + QR for teleconsult) | eSanjeevani (assist) | build now | S |
| G8 | MCP-card immunization export in RCH/ANMOL-friendly shape | ANMOL (assist) | post-SIH | S |
| G9 | NCD screening summary export (state NCD cell template) | NPCDCS framework | post-SIH | S |

All G-features sit behind the **state pack** (ROADMAP §0.3): which adapters
are enabled, credential env names, local formats. One deployment = one
state pack = config, not code.

## 3. What this changes in the demo story

- "Integrates with ABDM sandbox" (real call if creds arrive; mock labeled)
- "Speaks 12+ languages via Bhashini, falls back to Hindi/English + touch"
- "Feeds IDSP's syndromic pipeline in their format"
- "Hands teleconsult doctors a structured packet instead of a portal login"
- Honest slide: "closed systems (eSanjeevani, ANMOL) get export-bridges
  today, API bridges when NHA opens them — our adapter seams are ready."

## 4. Honest constraints (for judges)

1. ABDM sandbox approval takes days (applied T0.5) — sandbox demo if
   granted, labeled mock otherwise. Production M1 needs hospital partner.
2. Bhashini is registration-gated (org account) and quota-managed —
   fallback chain is part of the design, not an apology.
3. PM-JAY eligibility API requires empanelment credentials — we ship
   guide-mode as the default experience, credentialed read when the
   hospital provides it.
4. No claims, no payments, no Aadhaar — permanent policy (AD-6).
