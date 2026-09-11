# MediKiosk India Roadmap — Features Beyond the Problem Statement

**Purpose:** The SIH problem statement defines the core (history intake + document
digitization + summary). This roadmap plans features that attack real Indian
healthcare problems the statement does NOT cover, and — critically — makes the
platform deployable across India's linguistic and cultural diversity rather
than only the Hindi belt.

**Selection criteria (every feature had to pass all four):**
1. Solves a documented India-specific problem (not a generic "AI feature")
2. Builds on the existing architecture (ontology-YAML / services / registry) without rework
3. Demonstrable in the 9-minute SIH demo or a strong slides/README story
4. Contributes to regional flexibility or national-scale relevance

---

## 0. The Regional Flexibility Framework — the spine everything hangs on

India is not one deployment target. The same platform must work in a Chennai
OPD (Tamil, private-hospital lab formats, state scheme), a Patna PHC (Bhojpuri
in practice, Hindi forms), and an Assam tea-garden hospital (Assamese +
tribal-language patients). Hard-coding Hindi/English + one drug list makes the
product a demo, not a platform. Three config layers fix this:

### 0.1 Locale packs (12 languages, Bhashini-optional)
- Every ontology question already carries `voice_hi/voice_en` + touch options.
  Extend to per-locale overlays: `data/locales/<lang>/overrides.yaml` —
  contributors add one language WITHOUT touching code. Loader merges
  `base (en) → locale overlay` with missing-key fallback to English.
- ASR/TTS route by language: faster-whisper auto-detect (hi/en) stays default;
  add Bhashini ASR/TTS adapter (Government of India's National Language
  Translation Mission — public-good APIs for 22 scheduled languages) behind
  the same service contract. Bhashini down → English/Hindi fallback, session
  never dies.
- Sizes: loader change S; Bhashini adapter M (async client + fallback chain).
- This is the direct answer to "implementable in all regions of India".

### 0.2 Symptom idiom dictionaries (folk → clinical)
Patients do not speak textbook symptoms. They say:
- "garami badh gayi" (heat increased — Pitta framing) → fever/inflammation
- "safed pani aa raha hai" → white discharge (gyn)
- "khoon ka daura" / "dard ka daura" → paroxysmal episode
- "nazar lag gayi" → unexplained illness attribution (superstitious framing, still needs clinical intake)
- "pet mein keede" → worms/abdominal pain; "sharir jal raha hai" → burning sensation
- Regional variants: "tadi" (fever, AP/Telangana), "sarduk" (cold, TN)…

A naive LLM slot-filler trained on Western clinical English will miss ALL of
these. A per-region `idioms.yaml` maps folk phrases → canonical clinical slot
values, injected into (a) the LLM extraction prompt, (b) the `_fuzzy_snap`
option-matching in the dialogue engine. This is the deepest cultural
flexibility feature — and nobody demos it.
- Size M. Touchpoints: ontology package, dialogue engine, data dir.

### 0.3 State packs (config per deployment region)
One `data/states/<code>.yaml` file: local scheme names (PM-JAY / Aarogyasri /
BIS / state CF), preferred languages, regional drug brand forms, lab-panel
variants, local hospital HIS endpoint. The compose deployment picks a state
pack via env var. No code branches per region — config only.
- Size S. This is what makes "deploy in any state" real.

---

## 1. Returning-Patient Fast-Track ("Continuity Express")

**Problem:** The PS treats every patient as new. Reality: chronic follow-ups
(diabetes, hypertension, TB-DOTS, dialysis) are a large share of Indian OPD
load — estimates put follow-ups at roughly half or more of government OPD
footfall. These patients need a 60-second "anything changed?" flow, not a full
re-interview. This is ALSO the single biggest throughput lever the PS misses.

**How it works:**
- Patient identifies (ABHA or token/phone) → registry lookup finds prior
  completed sessions → screen: "पिछली बार जैसा ही है?" (same as last time?)
  - Yes → confirm 3 changes only (meds stopped? new symptoms? red-flag screen),
    copy prior summary forward with today's date, flag deltas
  - No → full intake as normal
- Delta view on the doctor screen: "vs last visit (12 Aug): BP med same, new
  complaint — knee pain". Doctors love diffs; nobody shows diffs.

**Touchpoints:** sessions_registry (already exists), new `/fasttrack` API
route, intake UI branch, summarizer delta section. Size **M**. Demo value:
very high (10-second segment: "returning patient flow").

## 2. Women's Health Privacy Mode

**Problem:** Indian public-health data (NFHS pattern) consistently shows women
under-report gynecological and mental-health symptoms — especially with
husband/mother-in-law in the room or a male doctor. The kiosk is the FIRST
point in the system where a woman is alone with a screen.

**How it works:**
- Language-pick screen adds a small "🔒" → Privacy Mode:
  - Female TTS voice preference (edge-tts `hi-IN-SwaraNeural` already female;
    add male option for choice)
  - "Attendant step away" interstitial with headphone prompt
  - Sensitive-question routing (gyn/mental-health ROS questions) offered as
    **type or discreet-tap only** — never voice-echoed aloud in a shared hall
  - Session summary shows gyn section only inside doctor's verified view
- Zero new infrastructure; it is a UI routing + consent-scope feature.

**Touchpoints:** i18n keys, IntakeView modes, Patient preference field,
summarizer scope filter. Size **S**. Demo value: high emotional impact;
judges remember it.

## 3. Assisted-Mode Provenance (data honesty)

**Problem:** Elderly patients arrive with a son/daughter or ASHA volunteer who
answers FOR them. Clinically, second-hand answers are lower-confidence data —
but every intake system silently records them as patient-voice.

**How it works:** Attractively simple: toggle on the consent screen —
"क्या आप किसी की मदद से जवाब दे रहे हैं?" Session gets `assisted=true` +
answers carry `responder: patient|attendant` provenance. Doctor summary shows
a subtle "(via attendant)" chip. Slot `confidence` reflects it.
- Touchpoints: ConsentFlow UI, SessionState field, citation chips. Size **S**.
- This is the "doctors trust the summary" play — provenance beats polish.

## 4. Syndromic Surveillance (outbreak early-warning)

**Problem:** Dengue, malaria, cholera, COVID-type outbreaks are visible in OPD
chief-complaint streams days-to-weeks before lab confirmation reaches the
public health chain (IDSP/IHIP flows are lab-confirmed and lag). A hospital
running MediKiosk sits on a real-time symptom firehose and uses none of it.

**How it works:**
- Nightly (or live) aggregation job: chief complaint + secondary complaints +
  extracted diagnoses, binned by day × pincode/district (from registration),
  fully anonymized — no names, no ABHA, aggregate-only counts
- Fever+cough/fever+rash clusters trigger threshold alerts to an admin
  dashboard (`/admin/surveillance`): "Fever + retro-orbital cluster, 3.4×
  baseline, ward 7 pincode cluster" — dengue signature, week earlier than labs
- Export format aligned to IDSP's syndromic reporting categories so it drops
  into existing government pipes.

**Touchpoints:** registry query + aggregation service, admin page, threshold
config in state pack. Size **M**. Demo value: massive — "one kiosk network =
city-scale early warning". Genuine public-health novelty.

## 5. Jan Aushadhi Cost Advisor (affordable medicine swap)

**Problem:** Out-of-pocket spending is the dominant Indian health-cost pattern
and medicine cost is a top driver of treatment abandonment (estimates: tens of
millions pushed below the poverty line annually by health costs). Patients
silently stop expensive branded drugs — the doctor never knows.

**How it works:**
- `drugs.json` (already exists, 40 drugs) gains fields:
  `{generic, brand_ref_price, jan_aushadhi_price}` (PMBJP price list is
  public data)
- When a scanned old prescription contains a branded drug with a Jan Aushadhi
  generic equivalent, the doctor summary shows: "₹ cost flag: Atorvastatin —
  Jan Aushadhi equivalent ~₹7.5/month vs brand ~₹95/month" as a suggestion
  chip — the DOCTOR decides; we inform.
- Pharmacists we spoke to in the plan's spirit: this is the feature hospital
  administrators mention unprompted.

**Touchpoints:** drugs.json schema, docintel extraction, summarizer chip.
Size **S–M**. Demo value: high — the "₹" slide lands hard with Indian judges.

## 6. Patient-Readable Prescription Summary (compliance layer)

**Problem:** The PS ends at the doctor's screen. But the PATIENT leaves with a
prescription they often cannot read (English Rx abbreviations, illegible
script) — medication non-adherence in chronic disease in India is estimated at
~50%. The whole intake platform's value dies at the pharmacy if the patient
doesn't take the meds.

**How it works:** After the doctor confirms the summary, MediKiosk generates a
patient-side card in the PATIENT's language: medicine names in Devanagari
(+regional script), "khana khane ke BAAD, subah-raat" plain-language timing,
one line per medicine, plus an **audio version** (edge-tts, our existing TTS
service) playable on any phone via QR + SMS link (feature-phone compatible —
IVR call option for non-smartphone users).
- Touchpoints: summarizer patient-view template, TTS service (already has
  runtime synth), QR + link generation (new small service route), i18n.
- Size **M**. Demo value: extremely high — closing the loop from intake to
  adherence; "the story ends at the patient, not the doctor."

## 7. Family Registry (Indian family healthcare behavior)

**Problem:** Indian healthcare is family-mediated: one adult child manages
records for two elderly parents and children, attends every OPD visit, carries
every document. Our current model is one-session-per-human; the attendant
re-enters the same phone number three times.

**How it works:** Attendant phone (already an Identifier) becomes a
`family_group` anchor. Registry UI: "Add family member" — each keeps own
ABHA/session/consent (consent is per-person, DPDP-clean), but the attendant
gets one queue view, document uploads routed to the right member, and a
"family dashboard" (last visits for all members). Kids get MCP-card
immunization photo capture (Mother-Child Protection card — a real, physical
artifact every Indian parent carries) with immunization-gap flags.
- Touchpoints: Identifier system + registry schema + a relations table +
  doctor/admin UI. Size **M–L**. Demo value: medium-high; strong "we
  understand how India actually goes to hospital" story.

## 8. Offline-Resilient Intake (power-cut proof)

**Problem:** Government hospitals have power cuts and patchy broadband;
mid-interview data loss means starting a 6-minute interview over — the worst
possible failure for an elderly patient's patience.

**How it works:**
- Intake state (slots captured so far) mirrored to browser localStorage on
  every answer (cheap: SessionState JSON is small); service-worker queue for
  completed-but-unsynced answers
- On reconnect (or on another kiosk at the token desk): resume exactly where
  the interview stopped — the RedisSessionStore sliding-TTL design (AD-9)
  already makes server-side resume trivial; this adds the client half
- Battery-backed kiosk = intake survives generator switchover

**Touchpoints:** IntakeView persistence, sync queue module, sessions router
(resume-upsert). Size **M**. Demo value: medium — but operationally this is
table-stakes for real PHC deployment; judges with field experience will probe
it.

---

## Prioritized build order (impact × effort)

| # | Feature | Size | Demo punch | Build now? |
|---|---|---|---|---|
| 1 | Locale packs + state packs (0.1, 0.3) | S–M | Architecture slide | **Yes — unlocks everything** |
| 2 | Symptom idioms (0.2) | M | Unique, cultural | **Yes** |
| 3 | Assisted-mode provenance (3) | S | Trust story | **Yes — one evening** |
| 4 | Women's privacy mode (2) | S | Emotional | **Yes** |
| 5 | Returning fast-track (1) | M | Throughput hero | **Yes** |
| 6 | Jan Aushadhi advisor (5) | S–M | The ₹ slide | **Yes** |
| 7 | Patient Rx summary (6) | M | Loop-closer | Next (post-SIH polish) |
| 8 | Syndromic surveillance (4) | M | Scale hero | Next (needs volume to be interesting) |
| 9 | Family registry (7) | M–L | Depth story | v1.1 |
| 10 | Offline sync (8) | M | Field-proof | v1.1 (after PWA hardening) |

**SIH demo strategy:** the 9-minute demo can absorb at most ~2 new segments.
Tent-poles: **fast-track (returning patient)** + **Jan Aushadhi ₹ flag**, with
**privacy mode** as the 10-second emotional beat. Idioms + locale packs live
in the architecture slide ("deploy in any state by dropping a YAML"), not the
live demo.

## Deliberately NOT planned (judgment call)

- **Insurance/claim processing** — TPAs are a regulatory swamp; the kiosk informs
  eligibility at most, never claims.
- **Vitals hardware (BP cuff, SpO2)** — breaks the software-only constraint and
  the PS explicitly de-scoped hardware.
- **Telemedicine consult inside the kiosk** — eSanjeevani already exists at
  national scale; integrate later, don't compete.
- **Autonomous diagnosis suggestions** — physicians reject it, liability
  nightmare, DPDP-risky; the plan's AD-4 (doctor confirms) stays absolute.
- **Aadhaar-based anything** — locked out by design (AD-6); no UPI, no eKYC.

## Honest constraints to state at judging

- Bhashini coverage and quality vary by language; our fallback chain (locale →
  Hindi → English + touch-always-available) is the contract, not perfect ASR.
- Jan Aushadhi prices drift; state-pack update is an ops task, not a code task.
- Surveillance needs aggregated volumes across days to matter — demo shows the
  mechanism on synthetic volume, say so.
- Privacy mode mitigates under-reporting; it cannot fix a family structure that
  answers for the patient — that's what assisted-mode provenance is for.
