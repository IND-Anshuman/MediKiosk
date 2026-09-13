# MediKiosk — AI Clinical History Intake Platform

MediKiosk is a patient-facing software platform that records a patient's full
medical history **before** the consultation — by natural voice and guided
touch, in the patient's language — and digitizes their existing paper medical
records (prescriptions, lab reports, discharge summaries). It produces a
physician-ready, source-cited clinical summary linked to the patient's ABHA
record via ABDM, with red-flag emergency triage.

**One-line pitch:** *Doctors win time. Patients tell their story once.
Critical symptoms never wait in the queue.*

> Built for the **Smart India Hackathon**. Targets Indian public-hospital OPDs
> (2–5 minute consultations) and AYUSH settings (Dashavidha Pariksha).

---

## Feature at a glance

| Capability | Status |
|---|---|
| Voice + touch conversational history (5 chief complaints + AYUSH mode) | ✅ |
| Hindi + English, icon-first, low-literacy friendly, audio prompts | ✅ |
| Document capture → OCR → clinical entity extraction + medical timeline | ✅ |
| Physician dashboard with source-cited summary + PDF export | ✅ |
| Red-flag → immediate-priority triage alert | ✅ |
| Consent (DPDP-aware, revocable, purge) + FHIR R4 bundle → HIS/ABDM | ✅ |
| ABDM sandbox adapter (ABHA create/verify) | ✅ |
| Bhashini/ULCA 22-language ASR/TTS backend | ✅ |
| PM-JAY eligibility (credentialed read or guide-mode) | ✅ |
| IDSP syndromic export, eSanjeevani hand-off packet | ✅ |
| Docker Compose deployment (`make up`) | ✅ |

---

## Architecture

Three tiers, fully containerized:

```
patient web app (Next.js PWA)
        │  HTTPS + WebSocket
   api gateway (FastAPI)  ── sessions / consent / triage
        │
   ┌────┴──────────────┬───────────────────────┐
 asr   tts  dialogue  ocr  ner  docintel  summarizer  fhir
 faster-whisper / edge-tts / Bhashini         │
                                              └── PostgreSQL · Redis · MinIO
```

Each AI capability is an **independent FastAPI microservice** that can be
scaled or swapped without touching the others. Everything is open source
except the optional LLM API key.

**Services (ports):**

| Service | Port | Role |
|---|---|---|
| `web` | 3000 | Next.js patient app + doctor portal |
| `api` | 8000 | gateway: sessions, consent, triage |
| `asr` | 8001 | speech → text (faster-whisper / Bhashini) |
| `tts` | 8002 | text → speech (pre-baked + edge-tts / Bhashini) |
| `dialogue` | 8003 | conversational history engine |
| `ocr` | 8004 | printed text extraction (PaddleOCR) |
| `ner` | 8005 | clinical entity extraction (rule-based) |
| `docintel` | 8006 | document pipeline: timeline, interactions, ref-ranges |
| `summarizer` | 8007 | structured summary + PDF |
| `fhir` | 8008 | FHIR R4 bundle + ABDM/PM-JAY/IDSP adapters |

---

## Quick start

### Prerequisites
- **Python 3.11+**, **Node 20+**, **Docker Desktop**, `uv`, `pnpm`
- A microphone + camera for the full demo (file upload works too)

### 1. Configure environment

```bash
cp .env.example .env
# edit .env — see "Configuration" below
```

### 2. Start the whole stack (Docker)

```bash
make up        # docker compose up -d --build
make logs      # tail logs
make down
```

Or bare metal (each service via `uv run uvicorn <pkg>.main:app ...`).

### 3. Verify

```bash
make test-unit test-contract   # backend tests
cd apps/web && pnpm test       # frontend tests
cd infra/compose && docker compose config --quiet && echo valid
# each service responds on its /healthz
```

### 4. Demo

Follow the 8-minute script in **`docs/DEMO.md`** (including prepared judge Q&A).

---

## Configuration

Copy `.env.example` → `.env`. Everything has a safe default or a graceful
fallback — the only variable that gates a **live** LLM is listed first.

### LLM (the one you'll actually set)

One OpenAI-compatible config works for **any** provider:

```ini
OPENAI_API_KEY=***              # credential
OPENAI_BASE_URL=                # endpoint; omit for api.openai.com
OPENAI_MODEL=gpt-4o-mini        # model id
LLM_BACKEND=stub                # "openai" = live model, "stub" = offline
```

| Provider | `OPENAI_BASE_URL` |
|---|---|
| OpenAI | *(leave empty)* |
| Featherless | `https://api.featherless.ai/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Together | `https://api.together.xyz/v1` |
| local vLLM / Ollama | `http://localhost:8000/v1` |

Set `LLM_BACKEND=openai` **and** `OPENAI_API_KEY` to use a live model. With
`LLM_BACKEND=stub` (default) the project runs fully offline on a deterministic
extractor — great for a rehearsed demo with no network/credential risk.

### Languages (optional)

`LANG_BACKEND=local` (default) = faster-whisper on CPU (English + Hindi) and
pre-baked edge-tts audio — no key needed. `LANG_BACKEND=bhashini` unlocks 22
Indian languages via ULCA/Bhashini (key + pipeline ids from
https://ulca.bhashini.gov.in).

### National-health integrations (all optional, graceful fallbacks)

| Group | Variables | When to set |
|---|---|---|
| **ABDM/ABHA** | `ABDM_BASE_URL`, `ABDM_CLIENT_ID`, `ABDM_CLIENT_SECRET` | ABDM sandbox approval (already pending) |
| **PM-JAY** | `PMJAY_HOSPITAL_ID`, `PMJAY_API_KEY` | empanelled hospital only; else guide-mode |
| **HIS** | `HIS_FHIR_URL` | real hospital integration; else bundles written to `data/fhir-outbox/` |

See **`docs/INTEGRATION-GOV.md`** for the full assessment of each government
system (which have real APIs, which are export-bridges, and what's impossible).

---

## Project layout

```
apps/web/          Next.js 16 patient + doctor app
services/          9 FastAPI microservices (asr, tts, dialogue, ... )
packages/          shared Pydantic models, clinical ontology (YAML), i18n
infra/             docker compose, Dockerfiles, scripts
tests/             unit + integration + contract (pytest)
data/reference/    drug dictionaries, lab ref-ranges
docs/              DEMO.md, INTEGRATION-GOV.md, ROADMAP-INDIA.md
```

The clinical history is **ontology-driven**: each chief complaint lives in a
YAML file (`packages/ontology/data/*.yaml`) with questions, touch options and
red-flag rules — adding a complaint is a data change, not a code change.

---

## Tests

| Layer | Command | Count (current) |
|---|---|---|
| Backend (unit + integration + contract) | `uv run pytest tests/` | **144 passed, 2 skipped** |
| Frontend (vitest) | `cd apps/web && pnpm test` | 9 |
| E2E (Playwright) | `cd apps/web && pnpm test:e2e` | 1 happy-path |

Every AI service is TDD-verified with a stub-able model interface, so CI runs
without a GPU; real-model tests are opt-in (`RUN_LIVE_LLM=1`, `RUN_GPU_TESTS=1`).

---

## Security & privacy

- **No patient PII ever sent to a remote LLM** (AD-3): the LLM sees only the
  utterance text + slot schema, never names, ABHA numbers, or session IDs.
- Consent is **DPDP-aware, granular, and revocable**, with a purge path that
  deletes PHI on request.
- **No Aadhaar, no claims, no payments** — permanent design policy.
- `.env` is gitignored; credentials never enter the repository.

---

## Documentation index

- `docs/DEMO.md` — 8-minute SIH demo script + judge Q&A
- `docs/INTEGRATION-GOV.md` — ABDM, Bhashini, PM-JAY, IDSP, eSanjeevani assessment
- `docs/ROADMAP-INDIA.md` — planned features beyond the problem statement
- `docs/UI-CONTRACT.md` — frontend test-id/data contract
- `docs/abdm-sandbox-status.md` — ABDM sandbox application log

---

## Known limits (honest)

- Handwritten OCR is **not** included (printed only) — stated v1.1 goal.
- Live ABHA/HIS/PM-JAY integration requires external approval/credentials;
  the project ships sandbox/mock/outbox fallbacks and labels them honestly.
- Full `docker compose up` needs Docker Desktop running with the daemon up
  (GPU reservations optional — ASR defaults to CPU).