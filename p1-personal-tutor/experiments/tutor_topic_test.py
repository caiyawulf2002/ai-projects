"""
Task 2 — P1 Tutor: 5-Topic Teaching Quality Audit
Runs P1's system prompt against 5 finance topics, then grades each response
with a second GPT-4o call acting as an evaluator.

Run: python p1-personal-tutor/experiments/tutor_topic_test.py
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.prompts import TUTOR_SYSTEM_PROMPT

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4o"

LEARNER_PROFILE = """\
Background: industrial engineer, worked at Walmart on process efficiency,
built GenAI tools at a supply chain company. Comfortable with systems
thinking and process flows. New to financial statement analysis.
Learning style: sees end-to-end first, then digs into details.
Theory-application score: 2/5 (prefers application first).
Session cadence: 90-min sessions, 3x per week.\
"""

SYSTEM = TUTOR_SYSTEM_PROMPT.replace("{learner_profile}", LEARNER_PROFILE)

TOPICS = [
    "Explain gross margin.",
    "Explain return on equity (ROE).",
    "Explain DuPont decomposition.",
    "Explain time value of money.",
    "What is a DCF?",
]

EVALUATOR_SYSTEM = """\
You are a teaching quality evaluator. A student asked a finance tutor a question
and you are reviewing the tutor's response.

Score the response 1–5 on "feels like a teacher (not a chatbot)" using this rubric:
  5 — Socratic, starts with a problem, forces retrieval, anchored to the learner
  4 — Structured and pedagogical but missing one key element above
  3 — Informative but reads like a textbook; no retrieval challenge
  2 — Correct but generic; could have come from any assistant
  1 — Dry, dense, or confusing; a student would disengage

Then identify the EXACT sentence where the response stops feeling like a teacher
and starts feeling like a chatbot or textbook. Quote it verbatim.

Respond in this exact JSON format (no markdown fences):
{
  "score": <1-5>,
  "score_rationale": "<one sentence>",
  "drift_sentence": "<exact quoted sentence, or 'none' if it never drifts>",
  "drift_reason": "<one sentence explaining why that sentence breaks the teaching arc>",
  "fix": "<one concrete change to make this feel more like a teacher>"
}\
"""


def call_tutor(topic: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": topic},
        ],
        temperature=0.3,
        max_tokens=700,
    )
    return resp.choices[0].message.content


def evaluate_response(topic: str, tutor_output: str) -> dict:
    prompt = f"Student asked: {topic}\n\nTutor responded:\n{tutor_output}"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": EVALUATOR_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=400,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw, "parse_error": True}


def divider(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    results = []

    for topic in TOPICS:
        divider(topic.upper())

        print("\n[TUTOR RESPONSE]")
        tutor_output = call_tutor(topic)
        print(tutor_output)

        print("\n[EVALUATION]")
        eval_result = evaluate_response(topic, tutor_output)
        print(json.dumps(eval_result, indent=2))

        results.append({
            "topic": topic,
            "tutor_output": tutor_output,
            "evaluation": eval_result,
        })

    # ── Write audit log ────────────────────────────────────────────────────────
    log_path = Path(__file__).parent.parent / "tutor_topic_audit.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("# P1 Tutor — 5-Topic Teaching Quality Audit\n\n")
        f.write(f"**Model:** {MODEL} | **Learner profile:** IE + supply chain background\n\n---\n\n")

        scores = []
        for r in results:
            ev = r["evaluation"]
            score = ev.get("score", "?")
            scores.append(score if isinstance(score, int) else 0)

            f.write(f"## Topic: {r['topic']}\n\n")
            f.write(f"**Score: {score}/5** — {ev.get('score_rationale', '')}\n\n")
            f.write(f"### Tutor response\n\n{r['tutor_output']}\n\n")

            drift = ev.get("drift_sentence", "")
            if drift and drift.lower() != "none":
                f.write(f"### Where it drifts\n\n> \"{drift}\"\n\n")
                f.write(f"**Why:** {ev.get('drift_reason', '')}\n\n")
            else:
                f.write("### Drift: none detected\n\n")

            f.write(f"### Fix\n\n{ev.get('fix', '')}\n\n---\n\n")

        avg = sum(scores) / len(scores) if scores else 0
        f.write(f"## Summary\n\n**Average score: {avg:.1f}/5**\n\n")
        f.write("| Topic | Score |\n|---|---|\n")
        for r in results:
            f.write(f"| {r['topic']} | {r['evaluation'].get('score', '?')}/5 |\n")

    print(f"\n\nAudit log written to: {log_path}")


if __name__ == "__main__":
    main()
