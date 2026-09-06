# UI Contract (plan T4.0)

Every patient/doctor screen element gets a `data-testid`. Pages are built to
this contract; E2E + unit tests assert it. Any testid change updates this file
in the same commit (checked by `infra/scripts/check_ui_contract.py`).

## Patient flow
| Screen | testid | Element |
|---|---|---|
| Language | `lang-hi` / `lang-en` | big language buttons |
| Consent | `consent-agree` | agree + grant button |
| Consent | `revoke-btn` | revoke & delete data |
| Identity | `token-input` / `abha-input` / `name-input` | text fields |
| Identity | `start-visit` | continue button |
| Complaint picker | `cc-chest_pain` / `cc-fever` / `cc-abdominal_pain` / `cc-cough` / `cc-headache` / `cc-ayurvedic_assessment` | big icon buttons |
| Intake | `option-{i}` | touch option button i |
| Intake | `option-confirm` | multi_choice confirm bar |
| Intake | `mic-btn` | hold-to-speak mic |
| Intake | `replay-indicator` | visible when replay mode answering |
| Intake | `confirm-yes` / `confirm-no` | confirmation echo buttons |
| Intake | `redflag-banner` | full-screen alert |
| Intake | `nurse-call` | alert staff button |
| Intake | `interview-done` | end-of-interview card |
| Documents | `doc-upload` | file input |
| Documents | `doc-item` | uploaded doc row |
| Documents | `doc-status` | processing chip |
| Summary | `summary-ready` | "your summary is ready" |
| Summary | `go-to-room` | proceed CTA |

## Doctor portal
| testid | Element |
|---|---|
| `doctor-queue` | queue list |
| `doctor-queue-row-{token}` | one patient row |
| `doctor-summary` | summary card |
| `timeline-item-{i}` | timeline entry i |
| `abnormal-flag` | abnormal lab badge |
| `interaction-warning` | drug interaction badge |
| `summary-pdf` | download link |
| `confirm-summary` | accept/confirm button |

## Mocks (MSW)
Unit/E2E tests never hit real services: `src/mocks/handlers.ts` serves
canned dialogue + session fixtures, including one low-confidence confirm
step and the chest-pain red-flag journey.