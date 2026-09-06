/**
 * MSW handlers (plan T4.0): canned backend for unit + E2E tests.
 * Includes the full chest-pain journey with one low-confidence confirm step
 * and the MI red flag — mirrors tests/contract/test_dialogue.py walks.
 */
import { http, HttpResponse } from "msw";

export interface DialogueQuestion {
  id: string;
  type: string;
  voice_hi: string;
  voice_en: string;
  touch_options_hi: string[];
  touch_options_en: string[];
}

const chestPainQuestions: DialogueQuestion[] = [
  {
    id: "onset",
    type: "duration",
    voice_hi: "Aapko kab se ye dard hai?",
    voice_en: "When did the pain start?",
    touch_options_hi: ["1 ghante se kam", "Aaj", "Kal se", "2-3 din se", "1 hafte se zyada"],
    touch_options_en: ["Less than 1 hour", "Today", "Yesterday", "2-3 days", "More than a week"],
  },
  {
    id: "location",
    type: "single_choice",
    voice_hi: "Dard kahan hai?",
    voice_en: "Where is the pain?",
    touch_options_hi: ["Seene ke beech mein", "Baayein taraf", "Daayein taraf", "Poore seene mein"],
    touch_options_en: ["Center of chest", "Left side", "Right side", "All over chest"],
  },
  {
    id: "character",
    type: "single_choice",
    voice_hi: "Dard kaisa hai?",
    voice_en: "How would you describe the pain?",
    touch_options_hi: ["Dabbaav jaisa (pressure)", "Chhuru jaisa (tez)", "Jalta hua", "Dheere dard"],
    touch_options_en: ["Crushing/pressure", "Sharp/stabbing", "Burning", "Dull ache"],
  },
  {
    id: "radiation",
    type: "single_choice",
    voice_hi: "Kya dard kisi aur jagah phelta hai?",
    voice_en: "Does the pain spread anywhere?",
    touch_options_hi: ["Baayein haath mein", "Jabde mein", "Peeth mein", "Ek hi jagah rehta hai", "Pata nahi"],
    touch_options_en: ["Left arm", "Jaw", "Back", "Stays in one place", "Not sure"],
  },
  {
    id: "associated",
    type: "multi_choice",
    voice_hi: "Kya aur bhi takleef hai?",
    voice_en: "Any other symptoms along with it?",
    touch_options_hi: ["Pasina aa raha hai", "Saans lene mein takleef", "Ulti jaisa", "Chakkar", "Kuch nahi"],
    touch_options_en: ["Sweating", "Shortness of breath", "Nausea", "Dizziness", "None"],
  },
  {
    id: "severity",
    type: "scale",
    voice_hi: "0 se 10 mein dard kitna hai?",
    voice_en: "Rate the pain from 0 to 10.",
    touch_options_hi: ["0-3", "4-6", "7-10"],
    touch_options_en: ["0-3", "4-6", "7-10"],
  },
  {
    id: "other_problems",
    type: "multi_choice",
    voice_hi: "Koi aur bimari ya takleef bhi hai?",
    voice_en: "Any other problems or illnesses?",
    touch_options_hi: ["Bukhar", "Khaansi", "Sar dard", "Pet dard", "Sugar/BP", "Kuch nahi"],
    touch_options_en: ["Fever", "Cough", "Headache", "Abdominal pain", "Diabetes/BP", "None"],
  },
];

let questionIdx = 0;

const RED_FLAG = {
  pattern_id: "mi_suspect",
  urgency: "immediate",
  message_hi: "Aapke lakshan gambhir ho sakte hain. Turant nurse ko bulayein?",
  message_en: "Your symptoms may be serious. Call a nurse now?",
};

export const handlers = [
  http.post("/api/sessions", () =>
    HttpResponse.json({ session_id: "sess-mock-1", language: "hi" }, { status: 201 })
  ),
  http.get("/api/sessions/:sid", () =>
    HttpResponse.json({
      session: { session_id: "sess-mock-1", language: "hi", red_flags: [], documents: [] },
    })
  ),
  http.post("/api/sessions/:sid/consent", () => HttpResponse.json({ consent: {} }, { status: 201 })),
  http.post("/api/dialogue/start", () =>
    HttpResponse.json({ session_id: "sess-mock-1", next_question: chestPainQuestions[0] })
  ),
  http.post("/api/dialogue/answer", async ({ request }) => {
    const body = (await request.json()) as { touch_indices?: number[]; asr_confidence?: number };
    const answered = questionIdx;
    // 4th answer (radiation) with low confidence triggers confirm echo (AD-10)
    if (questionIdx === 3 && body.asr_confidence !== undefined && body.asr_confidence < 0.75) {
      return HttpResponse.json({
        red_flag: null,
        next_question: null,
        confirm: { heard: "baayein haath", question_id: "radiation" },
        re_asking: false,
      });
    }
    questionIdx += 1;
    const isRedFlagStep = questionIdx === 5; // after 'associated' answered (5th answer)
    return HttpResponse.json({
      red_flag: isRedFlagStep ? RED_FLAG : null,
      next_question: isRedFlagStep ? null : (chestPainQuestions[questionIdx] ?? null),
      confirm: null,
      re_asking: false,
    });
  }),
  http.post("/api/dialogue/confirm", () =>
    HttpResponse.json({ red_flag: null, next_question: chestPainQuestions[4], confirm: null, re_asking: false })
  ),
  http.post("/api/triage/alert", () => HttpResponse.json({ recorded: true }, { status: 201 })),
  http.post("/api/documents/upload", () =>
    HttpResponse.json({ doc_id: "doc-1", status: "processing" }, { status: 201 })
  ),
  http.get("/api/documents/:id/status", () =>
    HttpResponse.json({ doc_id: "doc-1", status: "done", kind: "lab" })
  ),
  http.get("/api/doctor/queue", () =>
    HttpResponse.json({
      queue: [
        {
          session_id: "sess-mock-1",
          token: "T-0042",
          name: "Sita Devi",
          complaint: "chest_pain",
          red_flag: true,
          status: "summary_ready",
        },
      ],
    })
  ),
  http.get("/api/sessions/:sid/summary", () =>
    HttpResponse.json({
      summary_md:
        "# OPD Summary\n## Chief Complaint\n- chest pain [👆 tap]\n## Red Flags\n⚠️ Possible cardiac emergency",
      timeline: [
        { date: "2026-08-01", kind: "lab", abnormal: ["Hb 6.5 g/dL (low)"] },
      ],
      interactions: [{ a: "aspirin", b: "warfarin", severity: "major", note: "bleeding risk" }],
    })
  ),
  http.post("/api/sessions/:sid/summary/confirm", () =>
    HttpResponse.json({ confirmed: true })
  ),
  http.get("/tts/:key", () =>
    new HttpResponse(new ArrayBuffer(64), { headers: { "content-type": "audio/mpeg" } })
  ),
];

export function resetDialogueMock() {
  questionIdx = 0;
}