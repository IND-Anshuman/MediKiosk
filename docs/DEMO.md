# MediKiosk — SIH Demo Script (8 minutes)

Tight, rehearsed walkthrough of the working MVP. Each segment has a hard
time-box — practice to hit it. Do NOT improvise beyond the script; the
judges' 8 minutes are the whole story.

---

## Slide 0 — The one-liner (open, 20s)

> "In Indian govt hospitals, a doctor sees each patient for 2–5 minutes.
> MediKiosk records the patient's full medical history — by voice and
> touch, in their language — and digitizes old paper records BEFORE the
> doctor sees them. The doctor reads a complete, sourced history in
> seconds. Critical symptoms never wait in the queue."

Point at the live app already open on the language picker.

---

## Step 1 — Welcome + language (30s)

1. `docker compose up -d` (already running before the demo; do NOT rebuild live)
2. Click **Hindi** (huge button). Audio greeting plays.
3. Script: *"No reading required — everything is spoken. This works for a
   first-time patient with zero training."*

## Step 2 — Audio consent (30s)

1. Consent screen reads aloud in Hindi; patient taps **"Haan boliye"** (agree).
2. Show the **Revoke** button is always visible, even after grant.
3. Script: *"Consent is DPDP-compliant, granular, and revocable — and the
   ABDM consent artifact is mapped to this grant."*

## Step 3 — New patient → chest pain (1m30s)

1. Tap **"New Visit"** then **"Chest Pain"**.
2. The kiosk asks (voice + on-screen): onset → location → character →
   radiation → associated → severity.
3. Answer **one by voice** (say "do din pehle se" — 2 days ago). Show the
   **confirmation echo**: *"Did you say 2 days ago?"* (correct / try again).
4. Answer the rest **by touch** — no mic needed. Show dual-mode.

## Step 4 — Red-flag triage (30s)

1. For radiation answer "left arm" and associated "sweating".
2. Full-screen alert: **"🚨 You need immediate attention — call a nurse?"**
3. Script: *"This fired BEFORE the interview finished. The red-flag is a
   deterministic rule (radiation to left arm + sweating = MI suspicion) —
   never waits for a diagnosis."*

## Step 5 — Document upload (1m)

1. Take a phone-photo of a sample **printed prescription** (fixture).
2. In ~10s: OCR → NER extracts the drug + dose + frequency.
3. Upload a **lab report** — show abnormal value flagged **H** + reference
   range note.
4. Script: *"Handwritten OCR is honestly out of scope for this build — we
   demo printed. That's a stated v1.1 goal."*

## Step 6 — Doctor screen (1m)

1. Doctor portal shows the complete structured summary in cards:
   Chief Complaint → HPI → Past → Meds → Allergies → Family → ROS →
   Prior investigations.
2. Every sentence carries a **source chip** (🎤 voice / 👆 touch / 📄 doc).
3. Click a chip → reveals the raw source.
4. Doctor **edits** a field, **confirms** — summary is a draft, never an
   autonomous diagnosis ("AI-generated draft — physician must verify").

## Step 7 — FHIR + government integration (1m)

1. Show `/data/fhir-outbox/<session>.json` — the FHIR R4 bundle.
2. Show `curl /integrations/abdm/status` → `{enabled: true}` (sandbox creds
   configured) OR guide-mode honestly.
3. Show `/integrations/pmjay/eligibility` → eligibility outcome (or guide
   mode).
4. Script: *"The bundle links to the patient's ABHA; where ABDM sandbox
   creds are present, this pushes to the HIE. Where a government system has
   no open API — eSanjeevani, ANMOL — we export in their standard format
   (IDSP S-form) rather than fake a connection."*

## Step 8 — AYUSH Dashavidha (45s)

1. Toggle AYUSH mode on the intake page.
2. Dashavidha Pariksha asks the 10 parameters (Prakriti, Vikriti, Sara,
   Samhanana, Pramana, Satmya, Sattva, Ahara Shakti, Vyayama Shakti, Vaya).
3. Script: *"The same engine drives allopathic and Ayurvedic history — a
   YAML ontology, no code fork."*

## Step 9 — Architecture recap (30s)

1. One diagram slide: patient **web app** → **api gateway** →
   (asr / tts / dialogue / ocr / ner / docintel / summarizer / fhir) →
   Postgres + Redis + MinIO.
2. Script: *"Fully open source. Deploys with one `docker compose up`. Each AI
   service is independent and swappable — faster-whisper for ASR,
   Bhashini as the multilingual backend, rule-based NER for zero-model
   document extraction."*

That's **~8 minutes**. Leave 30–60s for the first judge question.

---

## Judge Q&A — prepared honest answers

**1. "Is this just dictation?"**
> No. It's a structured clinical interview — SOCRATES/OPQRST frameworks,
> red-flag rules, source-attributed summary. The LLM fills slots under a
> strict schema; it does not free-associate a diagnosis.

**2. "Name one place this could actually deploy?"**
> A govt hospital OPD with ABDM sandbox creds + a state pack (nearest local
> scheme/HIS/languages). Four planned integrations are live-API-ready
> (ABDM M1, Bhashini, PM-JAY read, IDSP export); two are assist-only
> export bridges with the adapter seam ready for when NHA opens APIs.

**3. "What did you NOT build and why?"**
> Handwritten OCR (honest limitation, printed-only). No live ABHA
> production (needs hospital partner). No claims/payments/Aadhaar
> (permanent policy). No autonomous diagnosis (fit-for-purpose, physician
> keeps final sign-off).

**4. "How is this better than a checkbox form?"**
> Voice + touch dual mode for low-literacy users; adaptive branching on
> the chief complaint; red-flag triage; document digitization; and a
> source-cited, physician-ready summary — a form does none of that.