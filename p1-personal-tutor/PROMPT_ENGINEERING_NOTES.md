# P1 Prompt Engineering Notes
*Session: 2026-05-12 | Task 1 + 2 of 16-week plan*

---

## What we did

Ran a 4-pattern prompt comparison on a single topic (gross margin), then audited
P1's system prompt across 5 finance topics. Found two bugs. Fixed them. Re-ran
to confirm the fix.

---

## The 4 patterns compared (Task 1)

| Pattern | Score | When to use |
|---|---|---|
| Zero-shot | Baseline | Quick answer, no format requirements |
| Few-shot | Format match | When you need consistent output shape (JSON, SQL, short defs) |
| CoT + role prompting | Best structure | When reasoning quality and teaching arc matter |
| P1 system prompt | Most personalized | For P1 — combines role + pedagogy + learner profile |

**Key finding:** Role prompting sets the model's *identity*. Chain-of-thought
forces the *reasoning path*. You need both. P1 had strong identity but weak
structural forcing — the CoT prompt's numbered steps were a harder constraint
than P1's prose pedagogy principles.

**Why few-shot got shorter, not better:** The examples I provided were 2-3
sentence definitions. The model learned "this format = correct" and replicated
brevity, not depth. Few-shot shapes output *form* as much as content — design
your examples accordingly.

---

## Bugs found in P1 (Task 2, before fix)

### Bug 1 — Prompt leakage in `<explain_mode>`
**What broke:** Topics 3 (DuPont) and 4 (TVM) echoed the internal step labels
directly into the response output:
```
1. IDENTIFY the concept...
2. CHECK learner history...
3. Run a one-module mini-lesson...
```
The numbered protocol was written as instructions but the model treated it as
an output template.

**Root cause:** Numbered steps in a system prompt are a strong structural
signal. The model pattern-matched to "numbered list → produce numbered list."
It didn't distinguish "internal reasoning steps" from "output format."

**Fix applied (`config/prompts.py` — both prompt variants):**
Added explicit instruction: *"Follow this reasoning sequence internally — do NOT
output these steps as headers or numbered labels. The steps are your private
reasoning, not your output."*

### Bug 2 — Passive offer substituting for retrieval challenge
**What broke:** Several topics closed with:
> *"Want to see how this changes if we adjust X?"*

That's a menu option, not a retrieval challenge. A learner who doesn't know
they need it will decline. The `<pedagogy>` block says "RETRIEVAL OVER
RECOGNITION" but the model read "OFFER a what-if" as equally valid.

**Root cause:** The `<explain_mode>` step 6 said "OFFER a what-if" with no
constraint that the learner had to produce an answer. It gave the model an
easy exit from the harder job of writing a real retrieval question.

**Fix applied:**
Replaced step 6 with an explicit mandate:
*"Close with an open-ended retrieval question the learner must answer from
memory. This is mandatory — never substitute a passive offer for a real
retrieval challenge."*

---

## Before vs. after (DuPont — the worst case)

**Before (prompt leakage):**
```
1. IDENTIFY the concept: DuPont decomposition breaks down ROE into...
2. CHECK learner history: Since you're new to financial statement analysis...
3. Run a one-module mini-lesson:
   - Build Task: Let's take a hypothetical company...
   - Retrieval Challenge: Explain in your own words how each component...
```

**After (clean):**
> The DuPont decomposition is a method used to break down the components of
> Return on Equity (ROE)... [explanation, IE anchor, worked example]...
> **Now, can you explain how improving asset turnover might impact a company's ROE?**

---

## What the automated evaluator got wrong

The GPT-4o evaluator scored everything 5/5 before AND after the fix. It was
checking for structural presence (ends with a question? IE analogy present?)
not teaching quality. Lesson: automated eval with a weak rubric will pass
broken prompts. A rubric that tests *what kind* of question (retrieval vs.
passive offer) would have caught Bug 2 before we did.

Improvement to make: add a rubric criterion that specifically checks whether
the closing question *requires the learner to produce an answer* (retrieval)
vs. *can be answered yes/no* (passive offer).

---

## Remaining weaknesses (not fixed yet)

1. **No problem-first opening.** Every response still opens with a definition.
   The `<pedagogy>` block says "PROBLEM FIRST: every concept starts with the
   concrete problem it solves" but no response led with a business problem.
   The fix: add a hard constraint to `<teach_mode>` — "your first sentence
   must name the business decision this concept helps make, not the definition."

2. **DCF underscaffolded.** The DCF response is the shortest despite being the
   most complex concept. The model allocated depth by topic length, not by
   concept difficulty. No fix applied yet.

3. **"CHECK learner history" is vestigial.** In a stateless API call there IS
   no session history. That step will always trigger the "no prior session"
   branch. It's only meaningful when P1 is connected to the SQLite profile
   store and the session history is passed in context.

---

## Files changed this session

| File | Change |
|---|---|
| `config/prompts.py` | Fixed `<explain_mode>` in both `TUTOR_SYSTEM_PROMPT` and `TUTOR_SYSTEM_PROMPT_RETURNING` |
| `experiments/prompt_comparison.py` | New — 4-pattern comparison script |
| `experiments/tutor_topic_test.py` | New — 5-topic audit with GPT-4o evaluator |
| `prompt_patterns_log.md` | New — full outputs from all 4 prompt patterns |
| `tutor_topic_audit.md` | New — before/after audit across 5 topics |
| `PROMPT_ENGINEERING_NOTES.md` | This file |
