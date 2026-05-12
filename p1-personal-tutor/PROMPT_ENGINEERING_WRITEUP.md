# Prompt Engineering for a Finance Learning Tutor
**P1 — Personal Learning Tutor | May 2026**

---

## Overview

This write-up documents a structured prompt engineering experiment run on P1,
a LangChain LCEL conversational tutor that teaches finance through Socratic
dialogue. The goal was to identify the best prompting strategy for a teaching
use case, audit the existing system prompt against real topics, and fix what
broke.

Two experiments were run back-to-back:

1. **Pattern comparison** — four prompting strategies tested on the same topic
2. **Teaching quality audit** — the P1 system prompt graded across five finance
   topics, bugs found, fixes applied, and re-tested

---

## Experiment 1 — Pattern Comparison

### Setup

All four variants were tested on the same user message: *"Explain gross margin."*
Model: GPT-4o at temperature 0.3. The four patterns:

| # | Pattern | System prompt description |
|---|---|---|
| 1 | Zero-shot | `"You are a helpful assistant."` |
| 2 | Few-shot (3 examples) | Three worked examples of finance explanations in the user turn |
| 3 | CoT + role prompting | Finance professor identity + 5 numbered output steps |
| 4 | P1 system prompt | Full P1 identity, pedagogy rules, and learner profile |

Full outputs are in [prompt_patterns_log.md](prompt_patterns_log.md).

---

### Results

**Zero-shot** produced a technically correct encyclopedia entry — formula,
bullet points, worked example — with no connection to the learner and no
question at the end. It defaulted to the most common format in its training
data: the Wikipedia article.

**Few-shot** produced the *shortest* response of all four. The three examples I
gave were crisp 2-3 sentence definitions, so the model learned "short = correct"
and compressed accordingly. This is the core trap of few-shot prompting: **you
are teaching output form just as much as content.** If your examples are brief,
the output will be brief. Few-shot is the right tool when you need format
consistency (JSON output, SQL, structured tables), not when you need depth.

**CoT + role prompting** was the structural winner. Assigning the "finance
professor" identity shifted the model toward higher-quality explanations, and
the five numbered output steps forced sequential, structured reasoning — problem
first, plain English definition, worked example, common mistake, diagnostic
question. The model followed all five steps in order and produced the only
response that ended with a *real* retrieval question (computational: "if gross
margin is 50% and revenue is $200k, what is COGS?") rather than a summary.

**P1 system prompt** was the most personalized — it picked up the IE analogy
("think of gross margin like process efficiency") and anchored to the learner's
Walmart background. But it closed with: *"Want to see how this changes if we
adjust COGS or revenue?"* — a passive offer, not a retrieval challenge. The
`<pedagogy>` block says "RETRIEVAL OVER RECOGNITION" but the model treated it
as a guideline, not a constraint.

---

### Key Insight

> **Role prompting sets the model's identity. Chain-of-thought forces the
> reasoning path. You need both.**

P1's system prompt was strong on identity — the tutor persona, the pedagogy
principles, the learner profile — but weak on structural forcing. The CoT
prompt's five numbered steps were a harder constraint than prose guidelines
because the model treats a numbered list as an output template. The mechanism:
the model's prior distribution from training strongly associates "numbered list
in instructions → produce numbered list in output." Named steps are enforced;
abstract principles are aspirational.

---

## Experiment 2 — 5-Topic Teaching Audit

### Setup

P1's system prompt was tested against five finance topics in order of
complexity:

1. Gross margin
2. Return on equity (ROE)
3. DuPont decomposition
4. Time value of money
5. What is a DCF

A second GPT-4o call acted as an automated evaluator, scoring each response
1–5 on "feels like a teacher, not a chatbot" and identifying the exact sentence
where the response drifted. Full results are in
[tutor_topic_audit.md](tutor_topic_audit.md).

---

### Bugs Found

#### Bug 1 — Prompt leakage

Topics 3 (DuPont) and 4 (TVM) echoed the system prompt's internal step labels
directly into the response:

```
1. IDENTIFY the concept: DuPont decomposition breaks down ROE into...
2. CHECK learner history: Since you're new to financial statement analysis...
3. Run a one-module mini-lesson:
   - Build Task: Let's take a hypothetical company...
   - Retrieval Challenge: Explain in your own words...
```

The `<explain_mode>` block had six numbered steps written as instructions. The
model read "numbered list in system prompt → numbered list in output" and
echoed the step labels verbatim. The response read like a robot reading from a
manual.

**Root cause:** The model doesn't distinguish between "steps I should follow
internally" and "steps I should write out for the user." Both look the same in
the prompt. The fix is to be explicit: tell the model the steps are private
reasoning, not output structure.

**Fix:**
```
Follow this reasoning sequence internally — do NOT output these steps as
headers or numbered labels. Your response must read as natural conversation,
not a numbered protocol. The steps are your private reasoning, not your output.
```

#### Bug 2 — Passive offer substituting for retrieval

Multiple topics closed with:

> *"Want to see how this changes if we adjust X?"*

That is not a retrieval challenge. A learner who doesn't know they need it will
decline. The original step 6 read "OFFER a what-if" — which the model
interpreted as a closing pleasantry equally valid to a real question. This
violated the core pedagogy principle ("RETRIEVAL OVER RECOGNITION") without the
model knowing it had done so, because the instruction didn't define what
disqualified an offer.

**Fix:**
```
Close with an open-ended retrieval question the learner must answer from
memory. This is mandatory — never substitute a passive offer ("Want to see
how this changes?") for a real retrieval challenge. A retrieval question
requires the learner to produce an answer, not accept or decline an offer.
```

---

### Before vs. After

**DuPont — before (prompt leakage, score 2/5 on real rubric):**

```
1. IDENTIFY the concept: DuPont decomposition breaks down ROE into three
   parts: Profit Margin, Asset Turnover, and Financial Leverage...
2. CHECK learner history: Since you're new to financial statement analysis,
   I will assume this concept hasn't appeared in a prior session.
3. Run a one-module mini-lesson:
   - Build Task: Let's take a hypothetical company with the following
     financial data...
   - Retrieval Challenge: Explain in your own words how each component
     of the DuPont formula affects the overall ROE.
```

**DuPont — after (clean, score 4/5):**

> The DuPont decomposition is a method used to break down the components of
> Return on Equity (ROE) to understand the underlying drivers of a company's
> financial performance. Given your background in systems thinking, you can
> think of this like analyzing a process flow in engineering — tracing financial
> performance through different "nodes" of a company's operations...
>
> **Now, can you explain how improving asset turnover might impact a company's
> ROE?**

The output is now conversational. The steps disappeared. The retrieval question
is real — it requires the learner to reason about the relationship between two
components, not just accept an offer.

---

### What the Automated Evaluator Got Wrong

The GPT-4o evaluator scored all five topics 5/5 before and after the fix. It
was checking for surface features: *does a question appear at the end? Is there
an IE analogy?* It couldn't distinguish a retrieval question from a passive
offer, because neither my evaluator rubric nor the model drew that line.

This is a broader lesson about LLM-based evaluation: **a weak rubric will pass
broken prompts.** The rubric needs to test the same quality you care about, not
a proxy for it. "Ends with a question" is not the same as "forces retrieval."

A better rubric criterion: *"Can the closing question be answered yes/no? If
yes, it is not a retrieval challenge."*

---

## Remaining Weaknesses

Three issues were identified but not fixed in this session:

**1. No problem-first opening.**
Every response still opens with a definition. The `<pedagogy>` block says
"PROBLEM FIRST: every concept starts with the concrete problem it solves" but
no topic led with a business problem. The principle is stated but not forced.
Fix: add a hard constraint to `<teach_mode>` — *"Your first sentence must name
the business decision this concept helps make, not the definition."*

**2. DCF is underscaffolded.**
The DCF response was the shortest despite being the most complex topic. The
model allocated depth by topic name length, not by conceptual complexity.
Fix: add a difficulty signal to the learner profile or teach_mode so the model
knows when to slow down.

**3. CHECK learner history is vestigial in stateless calls.**
The `<explain_mode>` step "check learner history" always triggers the "no prior
session" branch in a direct API call because there is no session history in
context. This step is only meaningful when P1 is connected to the SQLite
profile store and prior session summaries are passed in the system prompt. It
currently adds noise without adding value.

---

## What Changed

| File | Change |
|---|---|
| `config/prompts.py` | Fixed `<explain_mode>` in both `TUTOR_SYSTEM_PROMPT` and `TUTOR_SYSTEM_PROMPT_RETURNING` — added no-label instruction and mandatory retrieval question |
| `experiments/prompt_comparison.py` | 4-pattern comparison script with auto-generated log |
| `experiments/tutor_topic_test.py` | 5-topic audit with GPT-4o evaluator and before/after diff |
| `prompt_patterns_log.md` | Full outputs from all 4 prompt patterns |
| `tutor_topic_audit.md` | Before/after audit results across 5 topics |

---

## Key Takeaways

1. **Numbered steps in a system prompt are output templates, not just
   instructions.** If you don't want them echoed, say so explicitly.

2. **"RETRIEVAL OVER RECOGNITION" as prose is weaker than a single sentence
   that defines what disqualifies.** Constraints need a definition of
   violation, not just a goal.

3. **Few-shot shapes form as much as content.** Design your examples for the
   depth you want, not just the format.

4. **Role + CoT outperforms role alone.** Identity sets the prior; numbered
   steps enforce the reasoning path. Prose principles require both to be
   present.

5. **LLM evaluators need rubrics that test the thing you care about, not
   proxies.** "Ends with a question" is not the same as "forces retrieval."
